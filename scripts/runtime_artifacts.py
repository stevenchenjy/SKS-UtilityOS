#!/usr/bin/env python3
"""Fetch/verify reviewed official Python installers; never execute installers."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def verify(path, artifact):
    if path.is_symlink() or not path.is_file() or path.stat().st_size != artifact['size']:
        raise ValueError('PYTHON_INSTALLER_SIZE_OR_LOCATION_INVALID')
    if hashlib.sha256(path.read_bytes()).hexdigest() != artifact['sha256']:
        raise ValueError('PYTHON_INSTALLER_HASH_MISMATCH')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['fetch', 'verify'])
    parser.add_argument('--target', choices=['macos-arm64', 'windows-x64'], required=True)
    parser.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args()
    receipt = json.loads((ROOT / 'docs/dependency-receipts/python-runtime.json').read_bytes())
    artifact = next(row for row in receipt['artifacts'] if row['target'] == args.target)
    if not re.fullmatch(r'python-3\.13\.15-(macos11\.pkg|amd64\.exe)', artifact['filename']):
        raise ValueError('PYTHON_INSTALLER_RECEIPT_INVALID')
    if artifact['url'] != 'https://www.python.org/ftp/python/3.13.15/' + artifact['filename']:
        raise ValueError('PYTHON_INSTALLER_RECEIPT_INVALID')
    directory = args.directory.expanduser().resolve()
    if directory.is_relative_to(ROOT):
        raise ValueError('PYTHON_STAGING_MUST_BE_OUTSIDE_SOURCE')
    target = directory / artifact['filename']
    if args.action == 'fetch' and not target.exists():
        directory.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(artifact['url'], timeout=60) as response:
            if response.url != artifact['url']:
                raise ValueError('PYTHON_INSTALLER_REDIRECT_REJECTED')
            raw = response.read(artifact['size'] + 1)
        with tempfile.TemporaryDirectory(prefix='utilityos-python-', dir=directory) as temporary:
            staged = Path(temporary) / artifact['filename']; staged.write_bytes(raw)
            verify(staged, artifact)
            staged.rename(target)
    verify(target, artifact)
    print(json.dumps({'python': receipt['python'], 'target': args.target, 'sha256': 'matches_reviewed_receipt',
                      'installer_executed': False, 'publisher_signature': 'verify_under_school_OS_policy'}, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError) as exc:
        code = str(exc) if isinstance(exc, ValueError) and re.fullmatch(r'[A-Z][A-Z0-9_]{1,100}', str(exc)) else 'PYTHON_ARTIFACT_ACTION_FAILED'
        print('Action stopped: ' + code, file=sys.stderr)
        sys.exit(1)
