"""Real process interruption, audit boundaries, and deterministic local recovery."""
from pathlib import Path
from decimal import Decimal
import errno
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time
import zipfile
import pytest
from utilityos import SCHEMA_VERSION
from utilityos.config import ROOT
from utilityos.db import Store
from utilityos.service import Ledger
from utilityos.operations import backup, restore, check, migrate
from utilityos.migrations import upgrade_copy, STEPS
from utilityos import audit, storage
from test_operations import legacy_workspace


def kill_at(tmp_path, operation, checkpoint, directory, *args):
    marker=tmp_path/(operation+'-'+checkpoint+'.ready')
    child=subprocess.Popen([sys.executable,str(ROOT/'tests/crash_worker.py'),operation,checkpoint,str(directory),str(marker),*[str(a) for a in args]],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        deadline=time.monotonic()+15
        while not marker.exists() and time.monotonic()<deadline and child.poll() is None:
            time.sleep(.02)
        assert marker.exists(),child.communicate(timeout=1) if child.poll() is not None else 'checkpoint timeout'
        child.kill();child.communicate(timeout=10)
        assert child.returncode != 0
    finally:
        if child.poll() is None:child.kill();child.communicate(timeout=10)


@pytest.mark.parametrize('checkpoint',['partial_source','published_source'])
def test_killed_import_retries_without_partial_records(ledger,raw_csv,tmp_path,checkpoint):
    kill_at(tmp_path,'import',checkpoint,ledger.store.directory)
    assert ledger.stages()==[]
    result=ledger.import_file('retry.csv',raw_csv)
    assert result['count']==1
    assert ledger.overview()['stats']['approved_bills']==0
    assert check(ledger.store)['sources']=='ok'
    with pytest.raises(ValueError,match='DUPLICATE_SOURCE_DOCUMENT'):
        ledger.import_file('renamed.csv',raw_csv)
    assert len(ledger.stages())==1


@pytest.mark.parametrize('checkpoint',['approval_transaction','lost_response'])
def test_killed_approval_is_atomic_and_retry_cannot_double_post(ledger,raw_csv,tmp_path,checkpoint):
    item=ledger.import_file('synthetic.csv',raw_csv)['staged_ids'][0]
    kill_at(tmp_path,'approval',checkpoint,ledger.store.directory,item)
    if checkpoint=='approval_transaction':
        assert ledger.stage(item)['status']=='pending'
        assert ledger.overview()['stats']['approved_bills']==0
        ledger.approve_bill(item,ledger.stage(item)['payload'],True)
    else:
        assert ledger.stage(item)['status']=='approved'
    with pytest.raises(ValueError,match='PENDING_BILL_REQUIRED'):
        ledger.approve_bill(item,ledger.stage(item)['payload'],True)
    assert ledger.overview()['total_cents']==57980
    assert ledger.overview()['stats']['approved_bills']==1
    assert check(ledger.store)['audit']=='ok'


@pytest.mark.parametrize('checkpoint',['migration_transaction','database_switch'])
def test_killed_migration_preserves_old_database_and_retries(tmp_path,raw_csv,checkpoint):
    old=legacy_workspace(tmp_path/'legacy',raw_csv)
    before=old.path.read_bytes()
    kill_at(tmp_path,'migration',checkpoint,old.directory)
    assert old.path.read_bytes()==before
    assert list((old.directory/'backups').glob('*.zip'))
    migrate(old.directory,'demo')
    new=Store(old.directory,'demo',initialize=False)
    assert check(new)['schema_version']==SCHEMA_VERSION
    assert Ledger(new).overview()['total_cents']==57980


@pytest.mark.parametrize('checkpoint',['partial_source','published_source','database_switch'])
def test_killed_restore_preserves_current_sources_and_financial_state(ledger,raw_csv,tmp_path,checkpoint):
    item=ledger.import_file('synthetic.csv',raw_csv)['staged_ids'][0]
    ledger.approve_bill(item,ledger.stage(item)['payload'],True)
    first=backup(ledger.store)
    ledger.import_file('additional.csv',raw_csv.replace(b'SYN-NEW-WORKSHOP',b'SYN-ADDITIONAL'))
    later=backup(ledger.store)
    target=Store(tmp_path/'recover','demo')
    restore(target,first,'demo')
    kill_at(tmp_path,'restore',checkpoint,target.directory,later)
    assert Ledger(target).overview()['total_cents']==57980
    assert check(target)['sources']=='ok'
    assert len(Ledger(target).stages())==1
    restore(target,later,'demo')
    assert len(Ledger(target).stages())==2
    assert check(target)['audit']=='ok'


def test_killed_backup_is_not_published(ledger,raw_csv,tmp_path):
    ledger.import_file('synthetic.csv',raw_csv)
    kill_at(tmp_path,'backup','incomplete_backup',ledger.store.directory)
    assert not list((ledger.store.directory/'backups').glob('*.zip'))
    assert check(ledger.store)['audit']=='ok'
    saved=backup(ledger.store)
    target=Store(tmp_path/'recovered','demo');restore(target,saved,'demo')
    assert len(Ledger(target).stages())==1
    incomplete=tmp_path/'incomplete.zip';incomplete.write_bytes(saved.read_bytes()[:100])
    with pytest.raises(zipfile.BadZipFile):restore(target,incomplete,'demo')
    assert check(target)['database']=='ok'


def test_disk_full_during_source_publication_leaves_no_import(ledger,raw_csv,monkeypatch):
    def fail(*args,**kwargs):raise OSError(errno.ENOSPC,'SYNTHETIC_PRIVATE_PATH_9988')
    monkeypatch.setattr(storage.os,'fsync',fail)
    with pytest.raises(OSError):ledger.import_file('synthetic.csv',raw_csv)
    assert ledger.stages()==[]
    assert not list(ledger.store.sources.iterdir())


@pytest.mark.parametrize('damaged',['{invalid','[]','{"lines":[]}'])
def test_corrupt_draft_is_isolated_and_recovery_requires_review(ledger,raw_csv,damaged):
    item=ledger.import_file('synthetic.csv',raw_csv)['staged_ids'][0]
    original=ledger.stage(item)['payload']
    saved=ledger.save_draft(item,original,0)
    with ledger.store.connect() as db:db.execute('UPDATE staged SET review_payload=? WHERE id=?',(damaged,item))
    assert ledger.stages()[0]['data_error']=='DRAFT_DATA_DAMAGED_RECOVERY_REQUIRED'
    assert ledger.stage(item)['data_error']=='DRAFT_DATA_DAMAGED_RECOVERY_REQUIRED'
    with pytest.raises(ValueError,match='DRAFT_DATA_DAMAGED'):
        ledger.approve_bill(item,original,True)
    with pytest.raises(ValueError,match='CONFIRM_DRAFT_RECOVERY'):ledger.recover_draft(item,1)
    recovered=ledger.recover_draft(item,saved['revision'],True)
    assert recovered['payload']==original and recovered['revision']==2
    assert recovered['status']=='pending' and ledger.overview()['total_cents']==0
    ledger.approve_bill(item,recovered['payload'],True,revision=2)
    assert ledger.overview()['total_cents']==57980


def test_changed_valid_json_is_detected_against_saved_revision(ledger,raw_csv):
    item=ledger.import_file('synthetic.csv',raw_csv)['staged_ids'][0]
    payload=ledger.stage(item)['payload'];ledger.save_draft(item,payload,0)
    payload['current_total']='1.00'
    with ledger.store.connect() as db:db.execute('UPDATE staged SET review_payload=? WHERE id=?',(json.dumps(payload),item))
    assert ledger.stage(item)['data_error']
    assert Decimal(ledger.recover_draft(item,1,True)['payload']['current_total'])==Decimal('579.80')


def test_audit_append_rules_chain_and_private_values(ledger,raw_csv):
    item=ledger.import_file('SYNTHETIC_SECRET_FILENAME.csv',raw_csv)['staged_ids'][0]
    ledger.approve_bill(item,ledger.stage(item)['payload'],True)
    with audit.acting_as('reauthenticated_operator'):
        ledger.cancel_bill(1,'SYNTHETIC_PRIVATE_REASON_9988',True)
    with ledger.store.connect() as db:
        assert audit.verify(db)=='ok'
        rows=[dict(r) for r in db.execute('SELECT * FROM audit_events')]
        for sql in ['DELETE FROM audit_events','UPDATE audit_events SET code=code']:
            with pytest.raises(sqlite3.IntegrityError,match='AUDIT_APPEND_ONLY'):db.execute(sql)
    encoded=json.dumps(rows)
    for private in ['SYNTHETIC_SECRET_FILENAME','SYNTHETIC_PRIVATE_REASON','DEMO-E05','579.80','Example Electric']:
        assert private not in encoded
    assert rows[-1]['actor']=='reauthenticated_operator'
    assert rows[-1]['code']=='CANCEL_BILL'
    with ledger.store.connect() as db:
        db.execute('DROP TRIGGER audit_no_update')
        db.execute("UPDATE audit_events SET actor='local_maintainer' WHERE id=1")
    with pytest.raises(ValueError,match='AUDIT_INTEGRITY'):check(ledger.store)
    with pytest.raises(ValueError,match='AUDIT_INTEGRITY'):backup(ledger.store)
    with pytest.raises(ValueError,match='AUDIT_INTEGRITY'):Store(ledger.store.directory,'demo')


def test_audit_rejects_unbounded_events_and_records_restore_boundary(ledger,tmp_path):
    with ledger.store.connect() as db:
        with pytest.raises(ValueError,match='AUDIT_FIXED'):audit.event(db,'PRIVATE_MESSAGE_9988')
    saved=backup(ledger.store)
    target=Store(tmp_path/'restored','demo')
    restore(target,saved,'demo')
    with target.connect() as db:
        row=db.execute('SELECT * FROM audit_events ORDER BY id DESC LIMIT 1').fetchone()
        assert row['code']=='RESTORE_SNAPSHOT' and len(row['related_hash'])==64
        assert audit.verify(db)=='ok'
    assert len(list((target.directory/'backups').glob('*.zip')))==1


def previous_store(tmp_path,raw_csv,version):
    store=legacy_workspace(tmp_path/'old',raw_csv)
    if version==2:
        frozen=tmp_path/'frozen-v2.sqlite3'
        with sqlite3.connect(frozen) as target,store.connect() as source:
            target.executescript((ROOT/'tests/fixtures/schema_v2.sql').read_text())
            for table in ['settings','buildings','providers','accounts','meters','account_meters','documents','staged','bills','bill_lines','interval_channels','interval_readings','audit_events']:
                columns=[r[1] for r in source.execute(f'PRAGMA table_info({table})')]
                values=source.execute(f'SELECT * FROM {table}').fetchall()
                target.executemany(f"INSERT INTO {table}({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})", values)
            target.execute("UPDATE settings SET value='2' WHERE key='schema_version'")
            target.execute("INSERT INTO bill_history(bill_id,at,action) SELECT id,approved_at,'approved' FROM bills")
        target.close();os.replace(frozen,store.path)
        return Store(store.directory,'demo',initialize=False,expected_schema=2)
    if version>1:
        upgraded=tmp_path/'step.sqlite3'
        upgrade_copy(store,upgraded,target_version=version)
        os.replace(upgraded,store.path)
        store=Store(store.directory,'demo',initialize=False,expected_schema=version)
    return store


@pytest.mark.parametrize('version',[1,2])
def test_each_supported_previous_schema_upgrades_with_provenance(tmp_path,raw_csv,version):
    old=previous_store(tmp_path,raw_csv,version)
    saved=migrate(old.directory,'demo')
    new=Store(old.directory,'demo')
    assert Ledger(new).overview()['total_cents']==57980
    assert Ledger(new).stage(1)['importer_version']=='legacy-unrecorded'
    with zipfile.ZipFile(saved) as z:assert json.loads(z.read('MANIFEST.json'))['schema_version']==version
    assert check(new)['audit']=='ok'


@pytest.mark.parametrize('version',[1,2,3])
@pytest.mark.parametrize('fail',[False,True])
def test_future_upgrade_framework_from_every_supported_schema(tmp_path,raw_csv,version,fail):
    old=previous_store(tmp_path,raw_csv,version)
    original=old.path.read_bytes()
    def future(db):
        db.execute('CREATE TABLE synthetic_future_probe(id INTEGER PRIMARY KEY)')
        if fail:raise ValueError('SYNTHETIC_FUTURE_STEP_FAILED')
    steps={**STEPS,3:future};target=tmp_path/'future.sqlite3'
    if fail:
        with pytest.raises(ValueError,match='SYNTHETIC_FUTURE'):upgrade_copy(old,target,4,steps)
        with sqlite3.connect(target) as db:
            assert not db.execute("SELECT 1 FROM sqlite_master WHERE name='synthetic_future_probe'").fetchone()
    else:
        upgrade_copy(old,target,4,steps)
        with sqlite3.connect(target) as db:
            assert db.execute("SELECT value FROM settings WHERE key='schema_version'").fetchone()[0]=='4'
            assert db.execute('SELECT COUNT(*) FROM bills').fetchone()[0]==1
            assert audit.verify(db)=='ok'
    assert old.path.read_bytes()==original


def test_unregistered_migration_refuses_before_creating_copy(tmp_path,raw_csv):
    old=previous_store(tmp_path,raw_csv,2);target=tmp_path/'unsupported.sqlite3'
    with pytest.raises(ValueError,match='MIGRATION_PATH_UNSUPPORTED'):
        upgrade_copy(old,target,4)
    assert not target.exists()


def test_interval_review_cannot_approve_changed_cached_source(ledger,raw_csv,raw_xml):
    item=ledger.import_file('synthetic.csv',raw_csv)['staged_ids'][0]
    ledger.approve_bill(item,ledger.stage(item)['payload'],True)
    interval=ledger.import_file('synthetic.xml',raw_xml)['staged_ids'][0]
    with ledger.store.connect() as db:
        payload=json.loads(db.execute('SELECT payload FROM staged WHERE id=?',(interval,)).fetchone()[0])
        payload['readings'][0]['quantity']='999'
        db.execute('UPDATE staged SET payload=? WHERE id=?',(json.dumps(payload),interval))
    with pytest.raises(ValueError,match='DRAFT_DATA_DAMAGED'):
        ledger.approve_intervals(interval,'DEMO-E05')
    assert ledger.intervals()['total_readings']==0


def test_recovery_refuses_unreadable_history_without_overwriting_it(ledger,raw_csv):
    item=ledger.import_file('synthetic.csv',raw_csv)['staged_ids'][0]
    with ledger.store.connect() as db:db.execute("UPDATE staged SET payload='[]',review_payload='[]' WHERE id=?",(item,))
    with pytest.raises(ValueError,match='DRAFT_RECOVERY_REQUIRES_IT'):
        ledger.recover_draft(item,0,True)
    ledger.reject(item)
    assert ledger.stages()[0]['status']=='rejected'
    assert ledger.overview()['total_cents']==0


def test_restore_boundary_links_to_head_actually_retained_in_safety_backup(ledger,raw_csv,tmp_path):
    saved=backup(ledger.store)
    item=ledger.import_file('synthetic.csv',raw_csv)['staged_ids'][0]
    ledger.approve_bill(item,ledger.stage(item)['payload'],True)
    safety=restore(ledger.store,saved,'demo')
    with zipfile.ZipFile(safety) as archive:
        manifest=json.loads(archive.read('MANIFEST.json'))
        snapshot=tmp_path/'safety.sqlite3';snapshot.write_bytes(archive.read('utilityos.sqlite3'))
    with sqlite3.connect(snapshot) as db:
        assert audit.head(db)==manifest['audit_head']
        assert db.execute('SELECT COUNT(*) FROM bills').fetchone()[0]==1
        assert audit.verify(db)=='ok'
    with ledger.store.connect() as db:
        boundary=db.execute('SELECT * FROM audit_events ORDER BY id DESC LIMIT 1').fetchone()
        assert boundary['related_hash']==manifest['audit_head']
    assert ledger.overview()['stats']['approved_bills']==0


def test_old_pending_review_is_not_hidden_by_recent_closed_imports(ledger,raw_csv):
    original=ledger.import_file('synthetic-pending.csv',raw_csv)['staged_ids'][0]
    for index in range(501):
        item=ledger.import_file('synthetic-closed.csv',raw_csv+b'\n'*(index+1))['staged_ids'][0]
        ledger.reject(item)
    items=ledger.stages()
    assert len(items)==501
    assert [item['id'] for item in items if item['status']=='pending']==[original]
    assert ledger.overview()['stats']['pending']==1
