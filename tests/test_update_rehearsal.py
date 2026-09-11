"""The developer rehearsal must never select existing operator data."""
from copy import deepcopy
from pathlib import Path
import json
import os
import time
import pytest
from scripts.rehearse_update import Release, prepare_work, snapshot, preserved, supervise, write_report
from scripts.release import build
from utilityos.operations import backup


def test_existing_work_is_refused_without_touching_its_contents(tmp_path):
    existing = tmp_path / 'existing'
    existing.mkdir()
    sentinel = existing / 'staff-records.txt'
    sentinel.write_bytes(b'SYNTHETIC_DO_NOT_TOUCH')
    with pytest.raises(ValueError, match='REQUIRES_NEW_DIRECTORY'):
        prepare_work(existing, [])
    assert sentinel.read_bytes() == b'SYNTHETIC_DO_NOT_TOUCH'
    assert list(existing.iterdir()) == [sentinel]


def test_work_cannot_contain_or_be_inside_a_release(tmp_path):
    code = tmp_path / 'release'
    release = Release(code, Path('unused'), '0.5.0', 5)
    for work in [code, code / 'evidence', tmp_path]:
        with pytest.raises(ValueError, match='SEPARATE_EXTERNAL_DIRECTORY'):
            prepare_work(work, [release])
    assert not code.exists()


def test_rehearsal_rejects_symlink_work_parent(tmp_path):
    actual = tmp_path / 'actual'
    actual.mkdir()
    alias = tmp_path / 'alias'
    alias.symlink_to(actual, target_is_directory=True)
    with pytest.raises(ValueError, match='SYMLINK_REJECTED'):
        prepare_work(alias / 'new', [])
    assert list(actual.iterdir()) == []


def test_snapshot_refuses_staff_mode_even_for_synthetic_database(store):
    with store.connect() as db:
        db.execute("UPDATE settings SET value='staff' WHERE key='mode'")
    before = store.path.read_bytes()
    with pytest.raises(ValueError, match='DEMO_ONLY'):
        snapshot(store.directory)
    assert store.path.read_bytes() == before


def test_backup_audit_can_advance_without_hiding_financial_changes(ledger, raw_csv):
    staged = ledger.import_file('synthetic.csv', raw_csv)['staged_ids'][0]
    ledger.approve_bill(staged, ledger.stage(staged)['payload'], True)
    before = snapshot(ledger.store.directory)
    backup(ledger.store)
    preserved(before, snapshot(ledger.store.directory))
    corrupted = deepcopy(before)
    corrupted['tables']['bills']['sha256'] = 'different'
    with pytest.raises(ValueError, match='RETAINED_RECORDS_CHANGED'):
        preserved(before, corrupted)
    source = next(ledger.store.sources.iterdir())
    source.write_bytes(b'SYNTHETIC_CORRUPTION')
    with pytest.raises(ValueError, match='SOURCE_MISMATCH'):
        snapshot(ledger.store.directory)


def test_rehearsal_detects_configuration_and_source_changes(store):
    before = snapshot(store.directory)
    changed = deepcopy(before)
    changed['sources']['synthetic.csv'] = 'different'
    with pytest.raises(ValueError, match='ORIGINALS_CHANGED'):
        preserved(before, changed)
    with store.connect() as db:
        db.execute("INSERT INTO settings VALUES ('inbox_directory','SYNTHETIC_CHANGED')")
    with pytest.raises(ValueError, match='CONFIGURATION_CHANGED'):
        preserved(before, snapshot(store.directory))


def test_release_inspection_requires_matching_manifest_and_installed_runtime(tmp_path):
    source = tmp_path / 'release'
    source.mkdir()
    for name in ['run.py', 'README.md', 'AGENTS.md', 'MASTER_PROMPT.md']:
        (source / name).write_text('Synthetic source')
    (source / 'utilityos').mkdir()
    (source / 'utilityos/__init__.py').write_text('__version__="0.5.0"\nSCHEMA_VERSION=5\n')
    archive = tmp_path / 'release.zip'
    build(source, archive)
    import zipfile
    with zipfile.ZipFile(archive) as zipped:
        (source / 'RELEASE-MANIFEST.json').write_bytes(zipped.read('SKS-UtilityOS/RELEASE-MANIFEST.json'))
    with pytest.raises(ValueError, match='INSTALL_EACH_RELEASE_FIRST'):
        Release.inspect(source)
    python = source / ('.venv/Scripts/python.exe' if os.name == 'nt' else '.venv/bin/python')
    python.parent.mkdir(parents=True)
    python.write_bytes(b'SYNTHETIC_RUNTIME_PLACEHOLDER_NOT_EXECUTED')
    assert Release.inspect(source).schema == 5
    (source / 'run.py').write_text('Changed source')
    with pytest.raises(ValueError, match='MANIFEST_MISMATCH'):
        Release.inspect(source)


@pytest.mark.parametrize('version,valid', [
    ('0.5.0', True), ('0.6.0-rc1', True), ('0.6.0-rc999', True),
    ('0.6.0-PRIVATE_ACCOUNT', False), ('0.6.0-rc0', False), ('0.6.0-rc1000', False),
    ('0.6.0+secret', False), ('0.6.0-rc1\n', False), ('０.６.０', False),
])
def test_candidate_support_version_remains_a_bounded_category(version, valid):
    from pydantic import ValidationError
    from utilityos.provider_support import SupportBundle
    data = dict(application_version=version, anonymous_provider='a'*32,
                anonymous_layout='b'*32, template_version=1, template_hash='c'*64,
                state='draft', validation_status='needs_validation', documents_tested=0,
                fields=[], evidence_states={}, drift='none_observed', drift_count=0)
    if valid:
        assert SupportBundle(**data).application_version == version
    else:
        with pytest.raises(ValidationError):
            SupportBundle(**data)


def synthetic_receipt_worker(behavior, _new, work, _browser):
    """A real owned process reproduces a pass-looking receipt before shutdown."""
    if os.name != 'nt':
        os.setsid()
    write_report(work, {
        'status': 'passed' if behavior == 'premature_pass' else 'checks_passed_awaiting_runner_exit',
        'steps': ['synthetic_application_checks'],
        'all_rehearsal_servers_stopped': True,
        'all_browser_checkpoints_closed': True,
    })
    if behavior == 'nonzero':
        raise SystemExit(3)
    if behavior == 'timeout':
        time.sleep(60)


def test_rehearsal_success_is_published_only_after_owned_runner_exits_zero(tmp_path):
    result = supervise('zero', None, tmp_path, None, worker=synthetic_receipt_worker, timeout=10)
    assert result['status'] == 'passed'
    assert result['runner_exit_code'] == 0
    assert result['steps'][-1] == 'owned_runner_and_browser_drivers_exited_zero'
    assert json.loads((tmp_path / 'result.json').read_text()) == result


@pytest.mark.parametrize('behavior,code', [
    ('nonzero', 'REHEARSAL_RUNNER_EXIT_NONZERO'),
    ('premature_pass', 'REHEARSAL_COMPLETED_CHECKS_RECEIPT_REQUIRED'),
    ('timeout', 'REHEARSAL_RUNNER_TIMEOUT'),
])
def test_success_looking_receipt_cannot_hide_runner_failure(tmp_path, behavior, code):
    with pytest.raises(ValueError, match=code):
        supervise(behavior, None, tmp_path, None, worker=synthetic_receipt_worker,
                  timeout=1 if behavior == 'timeout' else 10)
    report = json.loads((tmp_path / 'result.json').read_text())
    assert report['status'] == 'failed_preserved_for_local_inspection'
    assert report['failure_code'] == code
    assert 'owned_runner_and_browser_drivers_exited_zero' not in report['steps']
    if behavior != 'premature_pass':
        assert report['runner_exit_code'] != 0


@pytest.mark.parametrize('failure', [None, 'checkpoint', 'browser_close'])
def test_browser_and_driver_close_on_checkpoint_success_or_failure(monkeypatch, tmp_path, failure):
    from types import SimpleNamespace
    from scripts import rehearse_update
    events = []

    class Browser:
        def close(self):
            events.append('browser_closed')
            if failure == 'browser_close':
                raise ValueError('SYNTHETIC_CLOSE_FAILURE')

    class Driver:
        def __enter__(self):
            return SimpleNamespace(chromium=SimpleNamespace(launch=lambda **_: Browser()))

        def __exit__(self, *_):
            events.append('driver_stopped')

    def checkpoint(*_, **__):
        events.append('checkpoint')
        if failure == 'checkpoint':
            raise ValueError('SYNTHETIC_CHECKPOINT_FAILURE')
        return {'synthetic': True}

    monkeypatch.setattr('playwright.sync_api.sync_playwright', Driver)
    monkeypatch.setattr(rehearse_update, 'browser_checkpoint', checkpoint)
    if failure:
        with pytest.raises(ValueError, match='SYNTHETIC_'):
            rehearse_update.native_checkpoint('synthetic-browser', 'unused', None, tmp_path, 'synthetic')
    else:
        assert rehearse_update.native_checkpoint('synthetic-browser', 'unused', None, tmp_path, 'synthetic') == {'synthetic': True}
    assert events == ['checkpoint', 'browser_closed', 'driver_stopped']
