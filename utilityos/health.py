"""Staff-visible health using fixed categories, never private record values."""
from importlib import metadata, util
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import sqlite3
import subprocess
import sys

from . import __version__, SCHEMA_VERSION
from .config import ROOT
from .diagnostics import operational_checks
from .pdf_worker import model_available


def dependency_health(root=ROOT):
    """Attest installation recipe and current versions, not mutable package bytes."""
    path = Path(sys.prefix) / 'utilityos-install-receipt.json'
    if path.is_symlink() or not path.is_file():
        return 'installation_receipt_missing'
    try:
        if path.stat().st_size > 1024 * 1024:
            return 'invalid'
        installed = json.loads(path.read_bytes())
        if installed.get('format') != 'utilityos-install-receipt-v1':
            return 'invalid'
        target, profile = installed.get('target'), installed.get('profile')
        if target not in {'macos-arm64', 'macos-x64', 'windows-x64', 'linux-x64'} or profile not in {'base', 'ocr'}:
            return 'invalid'
        receipt_path = root / 'docs/dependency-receipts' / f'{target}-cp313-{profile}.json'
        if receipt_path.is_symlink() or not receipt_path.is_file():
            return 'reviewed_receipt_missing'
        if hashlib.sha256(receipt_path.read_bytes()).hexdigest() != installed.get('dependency_receipt_sha256'):
            return 'receipt_changed'
        receipt = json.loads(receipt_path.read_bytes())
        if installed.get('artifacts') != {i['filename']: i['sha256'] for i in receipt['artifacts']}:
            return 'receipt_changed'
        actual = {re.sub(r'[-_.]+', '-', item.metadata['Name']).lower(): item.version for item in metadata.distributions()}
        expected = {i['name']: i['version'] for i in receipt['artifacts']}
        return 'versions_match_recorded_install' if actual == expected else 'environment_changed'
    except (OSError, ValueError, TypeError, KeyError):
        return 'invalid'


def _source_and_folder(directory, mode):
    source_status, folder_status = 'unavailable', 'not_configured'
    database = directory / 'utilityos.sqlite3'
    if database.is_symlink() or not database.is_file():
        return source_status, folder_status
    try:
        with sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True, timeout=2) as db:
            row = db.execute("SELECT value FROM settings WHERE key='mode'").fetchone()
            if not row or row[0] != mode:
                return 'workspace_mode_mismatch', 'unavailable'
            documents = db.execute('SELECT sha256,extension FROM documents').fetchall()
            row = db.execute("SELECT value FROM settings WHERE key='inbox_directory'").fetchone()
        db.close()
        source_status = 'ok'
        for digest, extension in documents:
            if not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest) or extension not in {'.csv', '.xml', '.pdf', '.xlsx'}:
                source_status = 'invalid_reference'; break
            path = directory / 'sources' / (digest + extension)
            if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                source_status = 'missing_or_changed'; break
        if row and row[0]:
            folder = Path(row[0])
            if not folder.is_absolute() or any(p.is_symlink() for p in [folder, *folder.parents]):
                folder_status = 'unsafe_location'
            else:
                folder_status = 'available' if folder.is_dir() and os.access(folder, os.R_OK | os.X_OK) else 'unavailable'
    except (OSError, ValueError, sqlite3.Error):
        source_status = 'invalid_or_unavailable'
    return source_status, folder_status


def report(config, *, running=False):
    schema, checks = operational_checks(config.data_dir, config.port, running=running)
    if os.name == 'nt':
        try:
            result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-File',
                                     str(ROOT / 'scripts/check-workspace-acl.ps1'), '-Directory', str(config.data_dir)],
                                    capture_output=True, text=True, timeout=8)
            category = result.stdout.strip()
            checks['permissions'] = category if result.returncode == 0 and category in {
                'review_required', 'no_broad_acl_grants_found', 'acl_check_unavailable'} else 'acl_check_unavailable'
        except (OSError, subprocess.SubprocessError):
            checks['permissions'] = 'acl_check_unavailable'
    sources, folder = _source_and_folder(config.data_dir, config.mode)
    try:
        ocr = ('disabled_model_not_configured' if not config.ocr_model_dir else
               'model_missing_or_unreviewed' if not model_available(config.ocr_model_dir) else
               'library_not_installed' if util.find_spec('tesserocr') is None else 'reviewed_model_and_library_available')
    except (OSError, ValueError, ImportError):
        ocr = 'unavailable'
    backup = config.data_dir / 'backups'
    checks.update({'retained_sources': sources, 'acquisition_folder': folder,
                   'optional_ocr': ocr, 'dependencies': dependency_health(),
                   'backup_access': 'unsafe_link' if backup.is_symlink() else
                       'available' if backup.is_dir() and os.access(backup, os.W_OK | os.X_OK) else
                       'created_on_first_backup' if not backup.exists() and os.access(config.data_dir, os.W_OK) else 'unavailable',
                   'runtime_patch': 'qualification_version' if sys.version_info[:3] == (3, 13, 15) else
                       'update_review_required' if sys.version_info[:3] < (3, 13, 15) else 'qualification_required'})
    return {'format': 'utilityos-health-v1', 'app': 'SKS UtilityOS', 'version': __version__,
            'schema_version': schema, 'expected_schema_version': SCHEMA_VERSION,
            'runtime': {'python': platform.python_version(), 'os_family': platform.system(),
                        'architecture': platform.machine()}, 'checks': checks,
            'acceptance': 'Synthetic checks do not establish school-machine or provider acceptance.'}
