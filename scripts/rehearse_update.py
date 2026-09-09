#!/usr/bin/env python3
"""Rehearse an update using NEW synthetic data only; never a staff updater.

Both code folders must be separately installed, trusted source releases with
intact manifests. Only processes started here are stopped. Every workspace,
backup, downloaded source and screenshot remains in the new external work folder.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import argparse
import ast
import json
import os
import signal
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.release import source_files


def require(condition, code):
    if not condition:
        raise ValueError(code)


def digest(raw):
    return sha256(raw).hexdigest()


@dataclass(frozen=True)
class Release:
    code: Path
    python: Path
    version: str
    schema: int

    @classmethod
    def inspect(cls, folder):
        code = folder.expanduser().resolve()
        manifest = json.loads((code / 'RELEASE-MANIFEST.json').read_text())
        actual = {name: digest(raw) for name, raw in source_files(code)}
        require(actual == manifest['files'], 'REHEARSAL_RELEASE_MANIFEST_MISMATCH')
        constants = {}
        for node in ast.parse((code / 'utilityos/__init__.py').read_text()).body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in {'__version__', 'SCHEMA_VERSION'}:
                        constants[target.id] = ast.literal_eval(node.value)
        require(constants['__version__'] == manifest['version'], 'REHEARSAL_RELEASE_VERSION_MISMATCH')
        python = code / ('.venv/Scripts/python.exe' if os.name == 'nt' else '.venv/bin/python')
        require(python.is_file(), 'REHEARSAL_INSTALL_EACH_RELEASE_FIRST')
        return cls(code, python, constants['__version__'], constants['SCHEMA_VERSION'])

    def command(self, action, workspace, *options):
        return [str(self.python), str(self.code / 'run.py'), action,
                '--mode', 'demo', '--data-dir', str(workspace), *map(str, options)]

    def maintenance(self, action, workspace, *options, expected_error=None):
        result = subprocess.run(self.command(action, workspace, *options), cwd=self.code,
                                capture_output=True, text=True, timeout=120)
        if expected_error:
            require(result.returncode != 0 and expected_error in result.stderr,
                    'REHEARSAL_EXPECTED_REFUSAL_MISSING')
        else:
            require(result.returncode == 0, 'REHEARSAL_MAINTENANCE_FAILED')
        return result.stdout


def prepare_work(path, releases):
    original = path.expanduser()
    require(not any(p.is_symlink() for p in [original, *original.parents]),
            'REHEARSAL_WORK_SYMLINK_REJECTED')
    work = original.resolve()
    for code in [ROOT, *(r.code for r in releases)]:
        require(not work.is_relative_to(code) and not code.is_relative_to(work),
                'REHEARSAL_REQUIRES_SEPARATE_EXTERNAL_DIRECTORY')
    require(not work.exists(), 'REHEARSAL_REQUIRES_NEW_DIRECTORY')
    work.mkdir(parents=True, mode=0o700)
    return work


def snapshot(workspace):
    """Hash synthetic state without exporting labels/values in the result file."""
    database = workspace / 'utilityos.sqlite3'
    require(database.is_file() and not database.is_symlink(), 'REHEARSAL_DATABASE_MISSING')
    with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as db:
        settings = dict(db.execute('SELECT key,value FROM settings'))
        require(settings['mode'] == 'demo', 'REHEARSAL_DEMO_ONLY')
        tables = {}
        for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
            if name in {'settings', 'audit_events'} or name.startswith('sqlite_'):
                continue
            quoted = '"' + name.replace('"', '""') + '"'
            columns = [r[1] for r in db.execute(f'PRAGMA table_info({quoted})')]
            rows = db.execute(f'SELECT * FROM {quoted} ORDER BY rowid').fetchall()
            tables[name] = {'columns': columns, 'rows': len(rows),
                            'sha256': digest(json.dumps(rows, separators=(',', ':')).encode())}
        originals = {}
        for sha, extension in db.execute('SELECT sha256,extension FROM documents'):
            name = sha + extension
            source = workspace / 'sources' / name
            require(source.is_file() and not source.is_symlink() and digest(source.read_bytes()) == sha,
                    'REHEARSAL_SOURCE_MISMATCH')
            originals[name] = sha
    db.close()
    stable_settings = {k: v for k, v in settings.items() if k not in {'schema_version', 'audit_head'}}
    return {'schema': int(settings['schema_version']), 'tables': tables, 'sources': originals,
            'settings_sha256': digest(json.dumps(stable_settings, sort_keys=True).encode())}


def preserved(before, after):
    require(before['sources'] == after['sources'], 'REHEARSAL_ORIGINALS_CHANGED')
    require(before['settings_sha256'] == after['settings_sha256'], 'REHEARSAL_CONFIGURATION_CHANGED')
    require(all(after['tables'].get(name) == value for name, value in before['tables'].items()),
            'REHEARSAL_RETAINED_RECORDS_CHANGED')


@contextmanager
def server(release, workspace, work, label):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    options = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == 'nt' else {}
    with (work / (label + '-server.log')).open('w') as log:
        process = subprocess.Popen(release.command('demo', workspace, '--port', port),
                                   cwd=release.code, stdout=log, stderr=log, **options)
        url = f'http://127.0.0.1:{port}'
        try:
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                require(process.poll() is None, 'REHEARSAL_SERVER_EXITED')
                try:
                    with urllib.request.urlopen(url + '/api/meta', timeout=1) as response:
                        meta = json.load(response)
                    require(meta['mode'] == 'demo' and meta['version'] == release.version,
                            'REHEARSAL_WRONG_SERVER')
                    break
                except OSError:
                    time.sleep(.1)
            else:
                raise ValueError('REHEARSAL_START_TIMEOUT')
            yield url
        finally:
            if process.poll() is None:
                process.send_signal(signal.CTRL_BREAK_EVENT if os.name == 'nt' else signal.SIGINT)
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                    raise ValueError('REHEARSAL_GRACEFUL_STOP_FAILED') from None


def browser_checkpoint(browser, url, release, work, label, *, import_pdf=False, expected=None):
    from playwright.sync_api import expect
    context = browser.new_context(viewport={'width': 1440, 'height': 1000}, accept_downloads=True)
    try:
        page = context.new_page()
        errors, failures = [], []
        page.on('pageerror', lambda error: errors.append(type(error).__name__))
        page.on('console', lambda msg: errors.append(msg.type) if msg.type in {'error', 'warning'} else None)
        page.on('response', lambda response: failures.append(response.status) if response.status >= 400 else None)

        def nav(name, heading=None):
            # Review queue's accessible name includes its changing pending count.
            page.locator('nav').get_by_role('button', name=name, exact=False).click()
            page.get_by_role('heading', name=heading or name, exact=True).wait_for()

        def download(name, filename):
            with page.expect_download() as pending:
                page.get_by_role('link', name=name, exact=True).click()
            destination = work / (label + '-' + filename)
            pending.value.save_as(str(destination))
            return destination.read_bytes()

        def shot(name):
            require(not page.evaluate('document.documentElement.scrollWidth > innerWidth'),
                    'REHEARSAL_BROWSER_OVERFLOW')
            page.screenshot(path=str(work / (label + '-' + name + '.png')))

        page.goto(url)
        page.get_by_role('button', name='Open synthetic demo', exact=True).click()
        page.get_by_role('heading', name='Campus utilities', exact=True).wait_for()
        expect(page).to_have_title('Overview | SKS UtilityOS')
        shot('desktop')
        if import_pdf:
            nav('Utility Inbox')
            page.get_by_role('button', name='Import files', exact=True).click()
            page.get_by_label('Source file', exact=True).set_input_files(
                release.code / 'samples/intake/electricity-digital.pdf')
            page.locator('#synthetic-confirm').check()
            page.get_by_role('button', name='Import for review', exact=True).click()
            page.locator('#bill-editor').wait_for()
        else:
            staged = page.evaluate('fetch("/api/staged").then(r=>r.json())')
            pdf = next(s for s in staged if s['extension'] == '.pdf' and s['status'] == 'pending')
            nav('Review queue')
            page.get_by_role('row').filter(has_text=pdf['label']).get_by_role('button', name='Review', exact=True).click()
            page.locator('#bill-editor').wait_for()
        expect(page.locator('#source-canvas')).to_be_visible()
        # A new HTML canvas already has a default width; wait for actual pixels.
        expect(page.locator('#evidence-error')).to_contain_text('Page rendered locally')
        source = download('Download original locally', 'original.pdf')
        require(source == (release.code / 'samples/intake/electricity-digital.pdf').read_bytes(),
                'REHEARSAL_BROWSER_ORIGINAL_CHANGED')
        page.locator('#evidence-zoom').select_option('1')
        page.locator('#source-scroll').scroll_into_view_if_needed()
        shot('source')
        nav('Privacy & support')
        ledger = download('Export approved ledger CSV', 'ledger.csv')
        result = {'ledger_sha256': digest(ledger), 'original_sha256': digest(source)}
        if expected:
            require(result == expected, 'REHEARSAL_BROWSER_LEDGER_CHANGED')
        page.set_viewport_size({'width': 390, 'height': 844})
        nav('Invoice ledger')
        require(page.get_by_role('button', name='Open invoice', exact=True).count() > 0,
                'REHEARSAL_EMPTY_LEDGER')
        shot('mobile')
        page.get_by_role('button', name='Open invoice', exact=True).first.scroll_into_view_if_needed()
        shot('mobile-ledger')
        page.get_by_role('button', name='Lock workspace', exact=True).click()
        page.get_by_role('button', name='Open synthetic demo', exact=True).wait_for()
        require(not errors and not failures, 'REHEARSAL_BROWSER_ERRORS')
        require(context.request.get(url + '/api/ledger/export').status == 401,
                'REHEARSAL_LOGOUT_FAILED')
        return result
    except Exception:
        # This harness creates all data itself; this is local synthetic evidence,
        # never an application diagnostic or a report to run on staff records.
        import traceback
        (work / (label + '-browser-failure.txt')).write_text(traceback.format_exc())
        try:
            page.screenshot(path=str(work / (label + '-failed.png')))
        except Exception:
            pass
        raise
    finally:
        context.close()


def rehearse(old, new, work, browser):
    workspace, rollback = work / 'synthetic-workspace', work / 'rollback-workspace'
    report = {'classification': 'synthetic update rehearsal; not a staff support bundle',
              'old_version': old.version, 'new_version': new.version, 'steps': [], 'status': 'running'}

    def record(step):
        report['steps'].append(step)
        (work / 'result.json').write_text(json.dumps(report, indent=2) + '\n')

    try:
        record('verified_separately_installed_release_manifests')
        # Candidate starts with separate, fresh data before it ever opens old data.
        with server(new, work / 'candidate-demo', work, 'candidate-demo') as url:
            browser_checkpoint(browser, url, new, work, 'candidate-demo', import_pdf=True)
        record('candidate_fresh_demo_verified_and_stopped')
        with server(old, workspace, work, 'old') as url:
            expected = browser_checkpoint(browser, url, old, work, 'old', import_pdf=True)
            old.maintenance('backup', workspace, expected_error='WORKSPACE_ALREADY_RUNNING_STOP_APP_FIRST')
            require(not (workspace / 'backups').exists(), 'REHEARSAL_RUNNING_BACKUP_WROTE_FILES')
        record('old_demo_verified_running_maintenance_refused_and_stopped')
        before = snapshot(workspace)
        old.maintenance('check', workspace)
        old.maintenance('backup', workspace)
        backups = list((workspace / 'backups').glob('*.zip'))
        require(len(backups) == 1, 'REHEARSAL_BACKUP_NOT_FOUND')
        backup = backups[0]
        report['pre_switch_backup_sha256'] = digest(backup.read_bytes())
        record('old_version_backup_retained')
        require(before['schema'] == old.schema and old.schema <= new.schema,
                'REHEARSAL_SCHEMA_DIRECTION_INVALID')
        if old.schema != new.schema:
            original_database = digest((workspace / 'utilityos.sqlite3').read_bytes())
            new.maintenance('check', workspace, expected_error='SCHEMA_VERSION_UNSUPPORTED')
            require(digest((workspace / 'utilityos.sqlite3').read_bytes()) == original_database,
                    'REHEARSAL_SCHEMA_CHECK_MUTATED_DATABASE')
            new.maintenance('migrate', workspace, '--confirm-migrate')
            record('incompatible_start_refused_then_explicit_migration_completed')
        else:
            record('same_schema_no_migration_needed')
        new.maintenance('check', workspace)
        after = snapshot(workspace)
        preserved(before, after)
        require(after['schema'] == new.schema, 'REHEARSAL_TARGET_SCHEMA_MISMATCH')
        record('candidate_schema_records_configuration_and_originals_verified')
        with server(new, workspace, work, 'switched') as url:
            browser_checkpoint(browser, url, new, work, 'switched', expected=expected)
        preserved(before, snapshot(workspace))
        record('switched_version_ledger_download_original_desktop_mobile_logout_verified')
        old.maintenance('restore', rollback, '--archive', backup, '--confirm-restore', '--restore-to-new-workspace')
        old.maintenance('check', rollback)
        restored = snapshot(rollback)
        preserved(before, restored)
        require(restored['schema'] == old.schema, 'REHEARSAL_ROLLBACK_SCHEMA_MISMATCH')
        with server(old, rollback, work, 'rollback') as url:
            browser_checkpoint(browser, url, old, work, 'rollback', expected=expected)
        require(digest(backup.read_bytes()) == report['pre_switch_backup_sha256'],
                'REHEARSAL_BACKUP_CHANGED')
        # A failed/abandoned source edit cannot silently become the next release.
        Release.inspect(old.code)
        Release.inspect(new.code)
        report.update(status='passed', schema_before=old.schema, schema_after=new.schema,
                      retained_tables=len(before['tables']), retained_sources=len(before['sources']),
                      browser=expected, all_rehearsal_servers_stopped=True)
        record('old_code_backup_and_separate_rollback_retained_and_verified')
        return report
    except Exception:
        report['status'] = 'failed_preserved_for_local_inspection'
        record('stopped_at_failed_check_no_automatic_overwrite_or_cleanup')
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--old-code', type=Path, required=True)
    parser.add_argument('--new-code', type=Path, required=True)
    parser.add_argument('--work-dir', type=Path, required=True)
    parser.add_argument('--browser-executable', type=Path, required=True)
    args = parser.parse_args()
    old, new = Release.inspect(args.old_code), Release.inspect(args.new_code)
    require(old.code != new.code, 'REHEARSAL_REQUIRES_TWO_CODE_FOLDERS')
    require(args.browser_executable.is_file(), 'REHEARSAL_BROWSER_REQUIRED')
    work = prepare_work(args.work_dir, [old, new])
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=str(args.browser_executable), headless=True)
        try:
            result = rehearse(old, new, work, browser)
        finally:
            browser.close()
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        code = str(exc) if isinstance(exc, ValueError) and str(exc).startswith('REHEARSAL_') else 'REHEARSAL_FAILED_REVIEW_LOCAL_EVIDENCE'
        print(code, file=sys.stderr)
        sys.exit(1)
