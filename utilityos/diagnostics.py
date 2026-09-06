"""Bounded operational checks. This module never serializes workspace records."""
from pathlib import Path, PurePosixPath
import hashlib
import json
import os
import platform
import shutil
import socket
import sqlite3
import sys
from . import __version__, SCHEMA_VERSION
from .config import ROOT
from .audit import verify


def release_integrity(root=ROOT):
    manifest_path = root / 'RELEASE-MANIFEST.json'
    if not manifest_path.is_file():
        return 'manifest_missing'
    try:
        if manifest_path.is_symlink() or manifest_path.stat().st_size > 1024 * 1024:
            return 'invalid'
        manifest = json.loads(manifest_path.read_bytes())
        if manifest['format'] != 1 or manifest['version'] != __version__ or not isinstance(manifest['files'], dict) or not 1 <= len(manifest['files']) <= 2000:
            return 'changed_or_invalid'
        for name, sha in manifest['files'].items():
            p = PurePosixPath(name)
            if p.is_absolute() or '..' in p.parts or '\\' in name:
                return 'invalid'
            path = root / name
            if not path.parent.resolve().is_relative_to(root.resolve()) or path.is_symlink() or not path.is_file():
                return 'changed_or_invalid'
            if hashlib.sha256(path.read_bytes()).hexdigest() != sha:
                return 'changed_or_invalid'
        # An extra executable module must not be hidden by a matching manifest.
        for folder in ['utilityos', 'web']:
            for path in (root / folder).rglob('*'):
                if path.suffix in {'.py', '.js', '.html', '.css'} and path.relative_to(root).as_posix() not in manifest['files']:
                    return 'changed_or_invalid'
        return 'matches_unsigned_manifest'
    except (OSError, ValueError, TypeError, KeyError):
        return 'invalid'


def operational_checks(directory, port=8765, *, running=False, root=ROOT):
    directory = Path(directory)
    database = directory / 'utilityos.sqlite3'
    result = {'python_compatible': sys.version_info >= (3, 11), 'database': 'unavailable',
              'migration': 'unknown', 'disk_space': 'unknown', 'backup_location': 'not_created',
              'permissions': 'unknown', 'loopback_port': 'serving_this_app' if running else 'unavailable',
              'release_integrity': release_integrity(root), 'audit': 'unavailable',
              'interrupted_source_files': False}
    schema = None
    try:
        if database.is_file() and not database.is_symlink():
            with sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True, timeout=2) as db:
                value = db.execute("SELECT value FROM settings WHERE key='schema_version'").fetchone()
                version = int(value[0]) if value else -1
                schema = version if version in {1, 2, SCHEMA_VERSION} else None
                result['database'] = 'accessible' if db.execute('PRAGMA quick_check').fetchone()[0] == 'ok' else 'invalid'
                result['migration'] = 'current' if version == SCHEMA_VERSION else 'explicit_upgrade_available' if version in {1, 2} else 'unsupported'
                result['audit'] = verify(db)
            db.close()
    except (OSError, sqlite3.Error, ValueError, TypeError):
        result['database'] = 'invalid_or_unavailable'
    try:
        free = shutil.disk_usage(directory).free
        result['disk_space'] = 'below_256_mib' if free < 256*1024**2 else 'below_1_gib' if free < 1024**3 else 'at_least_1_gib'
        backup = directory / 'backups'
        result['backup_location'] = 'unsafe_link' if backup.is_symlink() else 'workspace_subdirectory' if backup.is_dir() else 'not_created'
        paths = [directory, database, directory / 'sources'] + ([backup] if backup.exists() else [])
        result['permissions'] = 'not_checked_on_windows' if os.name == 'nt' else 'review_required' if any(p.is_symlink() or p.stat().st_mode & 0o077 for p in paths) else 'restricted'
        result['interrupted_source_files'] = any((directory / 'sources').glob('.source-*.pending'))
    except OSError:
        pass
    if not running:
        try:
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', port))
            result['loopback_port'] = 'available'
        except OSError:
            result['loopback_port'] = 'in_use_or_unavailable'
    return schema, result


def report(directory, mode, port=8765, *, running=False, root=ROOT):
    schema, checks = operational_checks(directory, port, running=running, root=root)
    return {'app': 'SKS UtilityOS', 'version': __version__, 'schema_version': schema,
            'mode': mode if mode in {'demo', 'staff'} else 'unknown',
            'runtime': {'python': platform.python_version(), 'os_family': platform.system()},
            'features': {'csv_template': True, 'green_button_electricity_subset': True, 'pdf_attachment_only': True,
                         'portal_access': False, 'outbound_connectors': False, 'telemetry': False},
            'checks': checks,
            'support_instructions': 'Review this file before sharing. Reproduce data issues with synthetic samples.'}
