"""The support report uses bounded categories, including damaged installations."""
import json
import os
import shutil
import socket
import subprocess
import sys
from types import SimpleNamespace
from pathlib import Path
import pytest
from utilityos import diagnostics
from utilityos.config import ROOT
from utilityos.operations import backup
from utilityos.security import set_password


def test_diagnostics_omit_records_configuration_and_exception_text(ledger,raw_csv,monkeypatch):
    ledger.import_file('SYNTHETIC_FILENAME_9988.csv',raw_csv)
    set_password(ledger.store,'SYNTHETIC_PASSPHRASE_9988')
    with ledger.store.connect() as db:
        db.execute("INSERT INTO settings VALUES ('future_secret','SYNTHETIC_FUTURE_SECRET_9988')")
        db.execute("INSERT INTO settings VALUES ('local_admin_path','SYNTHETIC_PRIVATE_PATH_9988')")
    backup(ledger.store)
    monkeypatch.setenv('UTILITYOS_FUTURE_TOKEN','SYNTHETIC_ENV_SECRET_9988')
    result=diagnostics.report(ledger.store.directory,'demo')
    assert set(result['checks'])=={'python_compatible','database','migration','disk_space','backup_location','permissions','loopback_port','release_integrity','audit','interrupted_source_files'}
    assert result['checks']['database']=='accessible'
    assert result['checks']['migration']=='current'
    assert result['checks']['audit']=='ok'
    assert result['checks']['backup_location']=='workspace_subdirectory'
    encoded=json.dumps(result)
    for private in ['9988','DEMO-E05','579.80','Example Electric',str(ledger.store.directory),'password_hash','future_secret']:
        assert private not in encoded
    assert '9988' not in ledger.export_csv().decode()


@pytest.mark.parametrize('free,status',[(0,'below_256_mib'),(500*1024**2,'below_1_gib'),(4*1024**3,'at_least_1_gib')])
def test_space_categories_have_no_exact_usage_or_path(ledger,monkeypatch,free,status):
    monkeypatch.setattr(shutil,'disk_usage',lambda path:SimpleNamespace(free=free))
    assert diagnostics.report(ledger.store.directory,'demo')['checks']['disk_space']==status


def test_cli_can_diagnose_incompatible_or_corrupt_database_without_modifying_it(ledger):
    command=[sys.executable,str(ROOT/'run.py'),'diagnostics','--mode','demo','--data-dir',str(ledger.store.directory)]
    with ledger.store.connect() as db:db.execute("UPDATE settings SET value='9988' WHERE key='schema_version'")
    before=ledger.store.path.read_bytes()
    run=subprocess.run(command,capture_output=True,text=True)
    report=json.loads(run.stdout)
    assert run.returncode==0 and report['schema_version'] is None
    assert report['checks']['migration']=='unsupported' and '9988' not in run.stdout
    assert ledger.store.path.read_bytes()==before
    ledger.store.path.write_bytes(b'SYNTHETIC_CORRUPT_DATABASE_9988')
    run=subprocess.run(command,capture_output=True,text=True)
    assert run.returncode==0 and '9988' not in run.stdout+run.stderr
    assert json.loads(run.stdout)['checks']['database']=='invalid_or_unavailable'
    assert ledger.store.path.read_bytes()==b'SYNTHETIC_CORRUPT_DATABASE_9988'


def test_schema_four_reports_available_migration_without_writing(tmp_path):
    import sqlite3
    database = tmp_path/'utilityos.sqlite3'
    with sqlite3.connect(database) as db:
        db.executescript((ROOT/'tests/fixtures/schema_v4.sql').read_text())
        db.executemany('INSERT INTO settings VALUES (?,?)', [('schema_version','4'),('mode','demo')])
    before = database.read_bytes()
    result = diagnostics.report(tmp_path, 'demo')
    assert result['schema_version'] == 4
    assert result['checks']['migration'] == 'explicit_upgrade_available'
    assert database.read_bytes() == before


def test_port_and_permission_checks_are_local_and_bounded(ledger):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        result=diagnostics.report(ledger.store.directory,'demo',port)
        assert result['checks']['loopback_port']=='in_use_or_unavailable'
    if os.name!='nt':
        ledger.store.path.chmod(0o644)
        assert diagnostics.report(ledger.store.directory,'demo')['checks']['permissions']=='review_required'
    assert diagnostics.report(ledger.store.directory,'demo',running=True)['checks']['loopback_port']=='serving_this_app'


def test_release_integrity_flags_modified_missing_and_unlisted_code(tmp_path):
    from test_release import release
    import zipfile
    archive=tmp_path/'release.zip';release.build(ROOT,archive)
    with zipfile.ZipFile(archive) as z:z.extractall(tmp_path/'unpacked')
    root=tmp_path/'unpacked/SKS-UtilityOS'
    assert diagnostics.release_integrity(root)=='matches_unsigned_manifest'
    extra=root/'utilityos/extra.py';extra.write_text('SYNTHETIC_EXTRA_CODE')
    assert diagnostics.release_integrity(root)=='changed_or_invalid'
    extra.unlink()
    (root/'run.py').write_text('SYNTHETIC_CHANGED_CODE')
    assert diagnostics.release_integrity(root)=='changed_or_invalid'
    (root/'RELEASE-MANIFEST.json').unlink()
    assert diagnostics.release_integrity(root)=='manifest_missing'
