"""A health report contains fixed categories, never workspace values."""
import json
import os
import subprocess
import sys
from pathlib import Path

from utilityos.config import Config, ROOT
from utilityos.health import report


def test_health_covers_retained_sources_and_acquisition_without_values(ledger, raw_csv, tmp_path):
    ledger.import_file('SYNTHETIC_PRIVATE_FILENAME_9988.csv', raw_csv)
    folder = tmp_path / 'SYNTHETIC_PRIVATE_FOLDER_9988'; folder.mkdir()
    with ledger.store.connect() as db:
        db.execute("INSERT INTO settings VALUES ('inbox_directory',?)", (str(folder),))
        db.execute("INSERT INTO settings VALUES ('connector_password','SYNTHETIC_SECRET_9988')")
    config = Config(ledger.store.directory, 'demo')
    health = report(config)
    assert health['checks']['retained_sources'] == 'ok'
    assert health['checks']['acquisition_folder'] == 'available'
    assert health['checks']['optional_ocr'] == 'disabled_model_not_configured'
    assert health['checks']['backup_access'] == 'created_on_first_backup'
    encoded = json.dumps(health)
    for sentinel in ('9988', 'DEMO-E05', 'Example Electric', str(folder), str(ledger.store.directory), '579.80', 'connector_password'):
        assert sentinel not in encoded
    next(ledger.store.sources.iterdir()).write_bytes(b'SYNTHETIC_DAMAGE')
    assert report(config)['checks']['retained_sources'] == 'missing_or_changed'
    folder.rmdir()
    assert report(config)['checks']['acquisition_folder'] == 'unavailable'


def test_health_checks_incompatible_database_without_modifying(ledger):
    with ledger.store.connect() as db:
        db.execute("UPDATE settings SET value='9988' WHERE key='schema_version'")
    before = ledger.store.path.read_bytes()
    result = subprocess.run([sys.executable, str(ROOT / 'run.py'), 'health', '--mode', 'demo',
                             '--data-dir', str(ledger.store.directory)], capture_output=True, text=True)
    assert result.returncode == 0
    assert json.loads(result.stdout)['checks']['migration'] == 'unsupported'
    assert '9988' not in result.stdout + result.stderr
    assert ledger.store.path.read_bytes() == before


def test_noninteractive_directory_choice_does_not_create_workspace(tmp_path):
    result = subprocess.run([sys.executable, str(ROOT / 'run.py'), 'staff', '--choose-data-dir'],
                            input='', capture_output=True, text=True)
    assert result.returncode == 1
    assert 'DIRECTORY_SELECTION_REQUIRES_INTERACTIVE_TERMINAL' in result.stderr
