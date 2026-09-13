#!/usr/bin/env python3
"""New synthetic code/workspace installation rehearsal; never a staff updater.

Uses real loopback HTTP, a fresh venv installed from the reviewed offline
wheelhouse, and only processes/workspaces created here. Browser acceptance is a
separate check. No school records, external APIs or application network calls.
"""
import argparse
from hashlib import sha256
import http.cookiejar
import io
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.release import build, verify
from scripts.rehearse_update import Release, server, snapshot


def require(condition, code):
    if not condition:
        raise ValueError(code)


class Client:
    def __init__(self, url):
        self.url = url
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies))
        self.csrf = ''
        self.csrf = self.request('/api/login', {'password': 'synthetic-demo-only'})['csrf']

    def request(self, path, body=None, *, raw=None, filename=None, binary=False):
        headers = {'Origin': self.url, 'X-CSRF-Token': self.csrf}
        data = None
        if body is not None:
            data = json.dumps(body).encode(); headers['Content-Type'] = 'application/json'
        if raw is not None:
            data = raw
            headers.update({'Content-Type': 'application/octet-stream', 'X-Filename': filename, 'X-Synthetic-Data': 'true'})
        request = urllib.request.Request(self.url + path, data=data, headers=headers)
        with self.opener.open(request, timeout=45) as response:
            content = response.read()
        return content if binary else json.loads(content)

    def logout(self):
        self.request('/api/logout', {})
        try:
            self.request('/api/overview')
        except urllib.error.HTTPError as error:
            require(error.code == 401, 'PORTABLE_LOGOUT_NOT_REVOKED')
        else:
            raise ValueError('PORTABLE_LOGOUT_NOT_REVOKED')


def run(work, wheelhouse):
    work = work.expanduser().resolve()
    require(not work.exists() and not work.is_relative_to(ROOT) and not ROOT.is_relative_to(work),
            'PORTABLE_REHEARSAL_REQUIRES_NEW_EXTERNAL_DIRECTORY')
    work.mkdir(parents=True, mode=0o700)
    first, second = work / 'first.zip', work / 'second.zip'
    built = build(ROOT, first, source_date_epoch=1789257600)
    build(ROOT, second, source_date_epoch=1789257600)
    require(first.read_bytes() == second.read_bytes(), 'PORTABLE_SOURCE_BUILD_NOT_REPRODUCIBLE')
    verified = verify(first)
    with zipfile.ZipFile(first) as archive:
        archive.extractall(work / 'installed')
    code = work / 'installed/SKS-UtilityOS'
    # Run from an unrelated current directory to reject repository assumptions.
    with (work / 'install.log').open('w') as output:
        subprocess.run([sys.executable, str(code / 'scripts/dependency_artifacts.py'), 'install',
                        '--directory', str(wheelhouse.resolve())], cwd=work, check=True,
                       stdout=output, stderr=output, timeout=240)
    release = Release.inspect(code)
    workspace = work / 'synthetic-workspace'
    incoming = work / 'synthetic-incoming'; incoming.mkdir()
    originals = {}
    with server(release, workspace, work, 'first-launch') as url:
        client = Client(url)
        health = client.request('/api/health')
        require(health['checks']['dependencies'] == 'versions_match_recorded_install', 'PORTABLE_ENVIRONMENT_NOT_RECORDED')
        require(health['checks']['release_integrity'] == 'matches_unsigned_manifest', 'PORTABLE_RELEASE_INTEGRITY_FAILED')
        baseline = client.request('/api/overview?month=2026-09')['total_cents']
        source = code / 'samples/demo-import.csv'
        imported = client.request('/api/import', raw=source.read_bytes(), filename=source.name)
        draft = client.request('/api/staged/' + str(imported['staged_ids'][0]))
        require(client.request('/api/overview?month=2026-09')['total_cents'] == baseline, 'PORTABLE_IMPORT_POSTED_FINANCES')
        client.request(f"/api/staged/{draft['id']}/approve", {'payload': draft['payload'], 'acknowledge': True, 'revision': draft['revision']})
        require(client.request('/api/overview?month=2026-09')['total_cents'] == baseline + 57980, 'PORTABLE_EXPLICIT_APPROVAL_FAILED')
        require(client.request(f"/api/sources/{draft['document_id']}", binary=True) == source.read_bytes(), 'PORTABLE_SOURCE_DOWNLOAD_CHANGED')
        client.request('/api/intake/configuration', {'directory': str(incoming), 'acknowledge': True})
        client.request('/api/acquisition/control', {'action': 'enable', 'directory': str(incoming), 'acknowledge': True, 'synthetic': True})
        for relative in ('samples/intake/electricity-digital.pdf', 'samples/demo-intervals.xml', 'samples/generic-water-usage.xlsx'):
            source = code / relative
            target = incoming / source.name
            # Browser-style partial name + completed rename: the partial must
            # never be treated as a completed provider document.
            partial = target.with_suffix(target.suffix + '.crdownload')
            partial.write_bytes(source.read_bytes())
            partial.rename(target)
            originals[target.name] = source.read_bytes()
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            history = client.request('/api/acquisition')['history']
            completed = {row['filename'] for row in history if row.get('document_id') and row.get('state') != 'processing'}
            if set(originals).issubset(completed):
                break
            time.sleep(.5)
        else:
            raise ValueError('PORTABLE_WATCHER_TIMEOUT')
        stages = client.request('/api/staged')
        intervals = next((row for row in stages if row.get('extension') == '.xml' and row.get('status') == 'pending'), None)
        require(intervals is not None, 'PORTABLE_WATCHED_XML_NOT_PENDING')
        interval_draft = client.request('/api/staged/' + str(intervals['id']))
        client.request('/api/staged/' + str(intervals['id']) + '/approve', {'meter_code': 'DEMO-E01', 'acknowledge': True})
        require(client.request('/api/overview?month=2026-09')['total_cents'] == baseline + 57980, 'PORTABLE_OPERATIONAL_IMPORT_CHANGED_CHARGES')
        require(client.request(f"/api/sources/{interval_draft['document_id']}", binary=True) == originals['demo-intervals.xml'],
                'PORTABLE_XML_SOURCE_CHANGED')
        usage = client.request('/api/usage')['items'][0]
        usage_id = usage['id']
        meter = next(row['code'] for row in client.request('/api/inventory')['meters'] if row['commodity'] == 'water')
        region = {'sheet': 'Water export', 'header_row': 3, 'first_column': 2, 'last_column': 7, 'end_row': 6}
        mapping = {'meter_code': meter, 'commodity': 'water', 'unit': 'US_gal', 'semantics': 'delta', 'timezone': '',
                   'meter_column': 'source_meter', 'source_meter': 'SYN-WATER-01', 'start_column': 'start',
                   'end_column': 'end', 'value_column': 'value', 'unit_column': 'unit', 'quality_column': 'quality'}
        client.request(f'/api/usage/{usage_id}/preview', {'revision': 0, 'source_region': region, 'reuse_layout': True, 'mapping': mapping})
        client.request(f'/api/usage/{usage_id}/approve', {'revision': 1, 'acknowledge': True})
        usage_detail = client.request(f'/api/usage/{usage_id}')
        require(client.request(f"/api/sources/{usage_detail['document_id']}", binary=True) == originals['generic-water-usage.xlsx'],
                'PORTABLE_WORKBOOK_SOURCE_CHANGED')
        require(client.request('/api/usage')['active_reading_count'] == 3, 'PORTABLE_WORKBOOK_APPROVAL_FAILED')
        require(client.request('/api/overview?month=2026-09')['total_cents'] == baseline + 57980, 'PORTABLE_WORKBOOK_CHANGED_CHARGES')
        client.request('/api/acquisition/control', {'action': 'pause', 'directory': str(incoming), 'acknowledge': True, 'synthetic': True})
        client.logout()
    stopped = json.loads(release.maintenance('check', workspace))
    require(stopped['sources'] == 'ok', 'PORTABLE_SOURCE_CHECK_FAILED')
    with server(release, workspace, work, 'restart') as url:
        client = Client(url)
        require(client.request('/api/overview?month=2026-09')['total_cents'] == baseline + 57980, 'PORTABLE_RESTART_CHANGED_CHARGES')
        require(client.request('/api/acquisition')['state'] == 'disabled', 'PORTABLE_RESTART_ENABLED_WATCHER')
        # Derive a second explicitly fictional period without touching the
        # original download. Workbook parsing still runs only inside UtilityOS.
        output = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(originals['generic-water-usage.xlsx'])) as original, zipfile.ZipFile(output, 'w') as variant:
            for info in original.infolist():
                raw = original.read(info.filename)
                if info.filename.startswith('xl/worksheets/'):
                    raw = raw.replace(b'2026-08-01', b'2026-09-01')
                variant.writestr(info, raw)
        second_usage = client.request('/api/usage/import', raw=output.getvalue(), filename='synthetic-next-period.xlsx')['import_id']
        details = client.request(f'/api/usage/{second_usage}')
        suggestion = details['suggested_mapping']
        require(suggestion and suggestion['meter_reused'] and suggestion['mapping']['meter_code'] == meter,
                'PORTABLE_RESTART_MAPPING_NOT_REUSED')
        client.request(f'/api/usage/{second_usage}/preview', {'revision': 0, 'source_region': suggestion['region'],
                       'reuse_layout': True, 'mapping': suggestion['mapping']})
        client.request(f'/api/usage/{second_usage}/approve', {'revision': 1, 'acknowledge': True})
        require(client.request('/api/usage')['active_reading_count'] == 6, 'PORTABLE_SECOND_WORKBOOK_APPROVAL_FAILED')
        require(client.request('/api/overview?month=2026-09')['total_cents'] == baseline + 57980, 'PORTABLE_REUSED_WORKBOOK_CHANGED_CHARGES')
        backup = client.request('/api/backups', {'acknowledge': True})
        archive = work / 'synthetic-backup.zip'
        archive.write_bytes(client.request(backup['download_url'], binary=True))
        client.logout()
    before = snapshot(workspace)
    for name, raw in originals.items():
        require((incoming / name).read_bytes() == raw, 'PORTABLE_WATCHER_CHANGED_DOWNLOAD')
    recovered = work / 'synthetic-recovered'
    release.maintenance('restore', recovered, '--archive', archive, '--confirm-restore', '--restore-to-new-workspace')
    require(json.loads(release.maintenance('check', recovered))['sources'] == 'ok', 'PORTABLE_RESTORE_CHECK_FAILED')
    after = snapshot(recovered)
    require(before['sources'] == after['sources'] and before['tables'] == after['tables'], 'PORTABLE_RESTORE_RECORDS_CHANGED')
    result = {'format': 'utilityos-portable-rehearsal-v1', 'version': release.version, 'schema': release.schema,
              'platform': platform.system(), 'architecture': platform.machine(), 'python': platform.python_version(),
              'source_archive_sha256': built['sha256'], 'verified_source_files': verified['verified_files'],
              'source_rebuild': 'byte_identical', 'offline_install': 'reviewed_artifacts_verified',
              'environment_receipt': health['checks']['dependencies'], 'loopback_http': 'passed',
              'watcher_pdf_xml_xlsx': 'queued_without_financial_approval', 'original_downloads': 'unchanged',
              'financial_approval': 'explicit', 'interval_approval': 'operational_only',
              'restart': 'passed', 'backup_restore': 'records_and_sources_preserved', 'logout': 'session_revoked',
              'spreadsheet_mapping_reuse': 'approved_relationship_reused_after_restart',
              'stop': 'owned_server_stopped_cleanly', 'browser': 'separate_native_check_required',
              'school_or_provider_data': 'none'}
    (work / 'portable-receipt.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', type=Path, required=True)
    parser.add_argument('--wheelhouse', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.work_dir, args.wheelhouse), indent=2))


if __name__ == '__main__':
    main()
