"""Recovery and explicit upgrade tests use frozen schema-1 and synthetic bytes."""
from pathlib import Path
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import zipfile
import pytest
from utilityos import SCHEMA_VERSION
from utilityos.config import ROOT
from utilityos.db import Store
from utilityos.service import Ledger
from utilityos.operations import backup, restore, check, migrate, instance_lock
from utilityos.security import set_password, verify_password


def legacy_workspace(directory, raw):
    directory.mkdir()
    sources=directory/'sources';sources.mkdir()
    sha=hashlib.sha256(raw).hexdigest()
    (sources/(sha+'.csv')).write_bytes(raw)
    with sqlite3.connect(directory/'utilityos.sqlite3') as db:
        db.executescript((ROOT/'tests/fixtures/schema_v1.sql').read_text())
        db.executemany('INSERT INTO settings VALUES (?,?)',[('schema_version','1'),('mode','demo')])
        from utilityos.parsers import parse_csv
        bill=parse_csv(raw)[0]
        db.execute("INSERT INTO providers VALUES (1,'Example Electric')")
        db.execute("INSERT INTO accounts VALUES (1,1,'DEMO-E05 account')")
        db.execute("INSERT INTO buildings VALUES (1,'Demo Workshop',NULL)")
        db.execute("INSERT INTO meters VALUES (1,'DEMO-E05',1,'electricity','kWh')")
        db.execute("INSERT INTO account_meters VALUES (1,1,1,'2026-08-01','2026-09-01')")
        db.execute("INSERT INTO documents VALUES (1,?,'synthetic.csv','.csv',?,'2026-09-01')",(sha,len(raw)))
        db.execute("INSERT INTO staged VALUES (1,1,'bill','approved',?,?,'2026-09-01','2026-09-01')",(json.dumps(bill),json.dumps(bill)))
        db.execute("INSERT INTO bills VALUES (1,1,'SYN-NEW-WORKSHOP-202608','2026-09-03',57980,1,1,'2026-09-03')")
        db.execute("INSERT INTO bill_lines VALUES (1,1,1,'2026-08-01','2026-09-01','2860','kWh',57980,'consumption','actual')")
    return Store(directory,'demo',initialize=False,expected_schema=1)


def test_explicit_migration_preserves_bytes_ids_history_and_old_backup(tmp_path,raw_csv):
    old=legacy_workspace(tmp_path/'old',raw_csv)
    set_password(old,'synthetic-migration-passphrase')
    before=old.path.read_bytes()
    with pytest.raises(ValueError,match='SCHEMA_VERSION_UNSUPPORTED'):
        Store(old.directory,'demo')
    assert old.path.read_bytes()==before
    with instance_lock(old.directory):saved=migrate(old.directory,'demo')
    new=Store(old.directory,'demo')
    assert check(new)['schema_version']==SCHEMA_VERSION
    assert verify_password(new,'synthetic-migration-passphrase')
    ledger=Ledger(new)
    assert ledger.overview()['total_cents']==57980
    assert ledger.stage(1)['payload']['invoice_number']=='SYN-NEW-WORKSHOP-202608'
    assert ledger.stage(1)['bill']['history'][0]['action']=='approved'
    with zipfile.ZipFile(saved) as archive:
        assert json.loads(archive.read('MANIFEST.json'))['schema_version']==1
    item=ledger.create_correction(1,'Synthetic rebill')['staged_id']
    ledger.approve_bill(item,ledger.stage(item)['payload'],True)
    assert ledger.overview()['total_cents']==57980


def test_failed_migration_does_not_touch_original(tmp_path,raw_csv,monkeypatch):
    old=legacy_workspace(tmp_path/'old',raw_csv)
    before=old.path.read_bytes()
    real_replace=os.replace
    def fail_database(source,target):
        if Path(target)==old.path:raise OSError('SYNTHETIC_WRITE_FAILURE')
        return real_replace(source,target)
    monkeypatch.setattr(os,'replace',fail_database)
    with instance_lock(old.directory),pytest.raises(OSError):migrate(old.directory,'demo')
    assert old.path.read_bytes()==before
    assert list((old.directory/'backups').glob('*.zip'))
    assert check(Store(old.directory,'demo',initialize=False,expected_schema=1))['schema_version']==1


def test_migration_bad_source_or_wrong_mode_fails_without_mutation(tmp_path,raw_csv):
    old=legacy_workspace(tmp_path/'old',raw_csv)
    before=old.path.read_bytes()
    with pytest.raises(ValueError,match='MODE_DATA_MISMATCH'):migrate(old.directory,'staff')
    next(old.sources.iterdir()).write_bytes(b'SYNTHETIC_CORRUPTION')
    with pytest.raises(ValueError,match='SOURCE_INTEGRITY'):migrate(old.directory,'demo')
    assert old.path.read_bytes()==before


def test_restore_orphans_can_be_reimported_without_overwriting(ledger,raw_csv):
    saved=backup(ledger.store)
    ledger.import_file('first.csv',raw_csv)
    with instance_lock(ledger.store.directory):restore(ledger.store,saved,'demo')
    assert ledger.stages()==[]
    assert ledger.import_file('retry.csv',raw_csv)['count']==1
    assert next(ledger.store.sources.iterdir()).read_bytes()==raw_csv


def test_corrupt_orphan_does_not_get_overwritten(ledger,raw_csv):
    sha=hashlib.sha256(raw_csv).hexdigest()
    path=ledger.store.sources/(sha+'.csv')
    path.write_bytes(b'SYNTHETIC_CORRUPT_ORPHAN')
    with pytest.raises(ValueError,match='SOURCE_STORAGE_CONFLICT'):ledger.import_file('retry.csv',raw_csv)
    assert path.read_bytes()==b'SYNTHETIC_CORRUPT_ORPHAN'
    assert ledger.stages()==[]


def test_correction_backup_restore_recovers_all_versions_and_password(ledger,raw_csv,tmp_path):
    item=ledger.import_file('first.csv',raw_csv)['staged_ids'][0]
    original=ledger.approve_bill(item,ledger.stage(item)['payload'],True)['id']
    draft=ledger.create_correction(original,'Synthetic correction')['staged_id']
    ledger.approve_bill(draft,ledger.stage(draft)['payload'],True)
    set_password(ledger.store,'synthetic-restore-passphrase')
    saved=backup(ledger.store)
    other=Store(tmp_path/'recovered','demo')
    with instance_lock(other.directory):restore(other,saved,'demo')
    assert verify_password(other,'synthetic-restore-passphrase')
    assert Ledger(other).stage(item)['bill']['versions']==ledger.stage(item)['bill']['versions']
    assert Ledger(other).overview()['total_cents']==57980
    assert check(other)['sources']=='ok'


@pytest.mark.parametrize('damage',['hash','path','manifest','foreign_key','mode','schema'])
def test_damaged_backup_fails_before_replacing_database(ledger,raw_csv,tmp_path,damage):
    ledger.import_file('source.csv',raw_csv)
    saved=backup(ledger.store)
    with zipfile.ZipFile(saved) as z:files={n:z.read(n) for n in z.namelist()}
    manifest=json.loads(files['MANIFEST.json'])
    if damage=='hash':files['utilityos.sqlite3']+=b'bad'
    elif damage=='path':
        files['../escape']=b'bad';manifest['files']['../escape']=hashlib.sha256(b'bad').hexdigest()
    elif damage=='manifest':manifest=[]
    elif damage in {'mode','schema'}:manifest['mode' if damage=='mode' else 'schema_version']='wrong'
    else:
        dbpath=tmp_path/'mutated.sqlite3';dbpath.write_bytes(files['utilityos.sqlite3'])
        with sqlite3.connect(dbpath) as db:db.execute('UPDATE staged SET document_id=9999')
        files['utilityos.sqlite3']=dbpath.read_bytes();manifest['files']['utilityos.sqlite3']=hashlib.sha256(files['utilityos.sqlite3']).hexdigest()
    files['MANIFEST.json']=json.dumps(manifest).encode()
    bad=tmp_path/'bad.zip'
    with zipfile.ZipFile(bad,'w') as z:
        for name,data in files.items():z.writestr(name,data)
    before=ledger.store.path.read_bytes()
    with instance_lock(ledger.store.directory),pytest.raises(ValueError):restore(ledger.store,bad,'demo')
    assert ledger.store.path.read_bytes()==before


def test_backup_write_failure_does_not_leave_downloadable_archive(ledger,monkeypatch):
    def fail(*args,**kwargs):raise OSError('SYNTHETIC_FULL_DISK')
    monkeypatch.setattr(zipfile.ZipFile,'writestr',fail)
    with pytest.raises(OSError):backup(ledger.store)
    assert not list((ledger.store.directory/'backups').glob('*.zip'))


def test_cli_requires_stopped_workspace_and_explicit_migration(store,tmp_path):
    command=[sys.executable,str(ROOT/'run.py'),'check','--mode','demo','--data-dir',str(store.directory)]
    before=store.path.read_bytes()
    result=subprocess.run(command,capture_output=True,text=True)
    assert result.returncode==0
    assert store.path.read_bytes()==before
    with instance_lock(store.directory):result=subprocess.run(command,capture_output=True,text=True)
    assert result.returncode==1 and 'WORKSPACE_ALREADY_RUNNING' in result.stderr
    missing=tmp_path/'missing'
    command[-1]=str(missing)
    assert subprocess.run(command,capture_output=True).returncode==1
    assert not missing.exists()


def test_cli_failure_does_not_echo_private_exception(tmp_path):
    # A malformed archive may contain arbitrary snippets; CLI output stays fixed.
    bad=tmp_path/'synthetic-secret-9988.zip';bad.write_bytes(b'NOT-A-ZIP-SYNTHETIC-9988')
    command=[sys.executable,str(ROOT/'run.py'),'restore','--mode','demo','--data-dir',str(tmp_path/'recovery'),
             '--archive',str(bad),'--confirm-restore','--restore-to-new-workspace']
    result=subprocess.run(command,capture_output=True,text=True)
    assert result.returncode==1
    assert 'LOCAL_ACTION_FAILED_CHECK_STORAGE_AND_ARCHIVE' in result.stderr
    assert '9988' not in result.stderr and str(tmp_path) not in result.stderr


def test_cli_refuses_migration_without_confirmation(tmp_path,raw_csv):
    store=legacy_workspace(tmp_path/'legacy',raw_csv)
    before=store.path.read_bytes()
    result=subprocess.run([sys.executable,str(ROOT/'run.py'),'migrate','--mode','demo','--data-dir',str(store.directory)],capture_output=True,text=True)
    assert result.returncode==1 and 'MIGRATION_REQUIRES_CONFIRM_MIGRATE' in result.stderr
    assert store.path.read_bytes()==before
