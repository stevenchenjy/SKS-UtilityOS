#!/usr/bin/env python3
"""Bundle verified public source, wheels and Python installer for offline handoff.

Never installs Python, runs a release, or opens a UtilityOS data directory.
Use a separately trusted verifier and school-approved distribution channel.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import dependency_artifacts, runtime_artifacts, release

MANIFEST = 'KIT-MANIFEST.json'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def artifact_set(target):
    if target not in {'macos-arm64', 'windows-x64'}:
        raise ValueError('DEPLOYMENT_KIT_TARGET_INVALID')
    wheel_receipt = dependency_artifacts.load(target)
    runtime_receipt = json.loads((ROOT / 'docs/dependency-receipts/python-runtime.json').read_bytes())
    runtime = next(i for i in runtime_receipt['artifacts'] if i['target'] == target)
    return wheel_receipt, runtime_receipt, runtime


def build(source, wheelhouse, runtime_directory, output, target):
    if output.resolve().is_relative_to(ROOT) or output.exists():
        raise ValueError('DEPLOYMENT_KIT_REQUIRES_NEW_EXTERNAL_OUTPUT')
    source_result = release.verify(source)
    wheels, runtimes, runtime = artifact_set(target)
    dependency_artifacts.verify(wheelhouse, wheels)
    runtime_artifacts.verify(runtime_directory / runtime['filename'], runtime)
    # Refuse a source archive with receipts different from the verifier's
    # reviewed artifact set. No dynamic lock substitution during packaging.
    with zipfile.ZipFile(source) as archive:
        for name in (f'{target}-cp313-base.json', 'python-runtime.json'):
            relative = 'docs/dependency-receipts/' + name
            if archive.read(release.PREFIX + relative) != (ROOT / relative).read_bytes():
                raise ValueError('DEPLOYMENT_SOURCE_DEPENDENCY_RECEIPT_MISMATCH')
    source_name = 'SKS-UtilityOS-' + source_result['version'] + '.zip'
    files = {source_name: source.read_bytes(),
             'receipts/dependencies.json': dependency_artifacts.receipt_path(target).read_bytes(),
             'receipts/python-runtime.json': (ROOT / 'docs/dependency-receipts/python-runtime.json').read_bytes(),
             'python/' + runtime['filename']: (runtime_directory / runtime['filename']).read_bytes()}
    for artifact in wheels['artifacts']:
        files['wheelhouse/' + artifact['filename']] = (wheelhouse / artifact['filename']).read_bytes()
    files['START-HERE.txt'] = (
        'SKS UtilityOS offline installation kit\n\n'
        'Unsigned release candidate. Obtain this kit and its verifier through the separately approved school channel.\n'
        'Verify the kit with a trusted copy of scripts/deployment_kit.py verify before extracting.\n'
        'Verify the Python installer publisher signature under school OS policy; installer execution is a separate IT step.\n'
        'Extract the nested source ZIP into a NEW code folder and read docs/PORTABLE_DEPLOYMENT.md.\n'
        'Keep previous code/environment and all private workspaces/backups in separate locations.\n'
        'Use the included matching wheelhouse with scripts/setup.sh or scripts/setup.ps1.\n'
        'Launch staff with directory selection, create a LOCAL app passphrase, inspect health, and test the browser.\n'
        'No portal, school data, credentials or runtime configuration is included. No automatic updates.\n'
        'Hashes establish integrity, not school/provider acceptance or publisher authenticity.\n'
    ).encode()
    manifest = {'format': 'utilityos-deployment-kit-v1', 'version': source_result['version'], 'target': target,
                'python': runtimes['python'], 'authenticity': 'unsigned; separately trusted distribution required',
                'files': {name: digest(raw) for name, raw in sorted(files.items())}}
    files[MANIFEST] = (json.dumps(manifest, indent=2) + '\n').encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', zipfile.ZIP_DEFLATED) as archive:
        for name, raw in sorted(files.items()):
            info = zipfile.ZipInfo(name); info.create_system = 3
            info.external_attr = 0o100644 << 16; info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, raw)
    return verify(output)


def verify(path):
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        if not 1 <= len(infos) <= 100 or sum(i.file_size for i in infos) > 500_000_000:
            raise ValueError('DEPLOYMENT_KIT_SIZE_LIMIT')
        names = [i.filename for i in infos]
        if len(names) != len(set(names)):
            raise ValueError('DEPLOYMENT_KIT_DUPLICATE_MEMBER')
        for info in infos:
            name = PurePosixPath(info.filename)
            if name.is_absolute() or '..' in name.parts or '\\' in info.filename or info.is_dir() or stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError('DEPLOYMENT_KIT_UNSAFE_MEMBER')
        manifest = json.loads(archive.read(MANIFEST))
        if not isinstance(manifest, dict) or manifest.get('format') != 'utilityos-deployment-kit-v1' or not isinstance(manifest.get('files'), dict):
            raise ValueError('DEPLOYMENT_KIT_MANIFEST_INVALID')
        if set(names) != set(manifest['files']) | {MANIFEST}:
            raise ValueError('DEPLOYMENT_KIT_MEMBERS_MISMATCH')
        for name, expected in manifest['files'].items():
            if digest(archive.read(name)) != expected:
                raise ValueError('DEPLOYMENT_KIT_HASH_MISMATCH')
        wheels, runtimes, runtime = artifact_set(manifest.get('target'))
        source_name = 'SKS-UtilityOS-' + manifest['version'] + '.zip'
        expected = {source_name, MANIFEST, 'START-HERE.txt', 'receipts/dependencies.json', 'receipts/python-runtime.json',
                    'python/' + runtime['filename']} | {'wheelhouse/' + i['filename'] for i in wheels['artifacts']}
        if set(names) != expected:
            raise ValueError('DEPLOYMENT_KIT_ARTIFACT_SET_MISMATCH')
        if archive.read('receipts/dependencies.json') != dependency_artifacts.receipt_path(manifest['target']).read_bytes() or archive.read('receipts/python-runtime.json') != (ROOT / 'docs/dependency-receipts/python-runtime.json').read_bytes():
            raise ValueError('DEPLOYMENT_KIT_REVIEWED_RECEIPT_MISMATCH')
        for artifact in wheels['artifacts'] + [runtime]:
            member = ('python/' if artifact is runtime else 'wheelhouse/') + artifact['filename']
            if archive.getinfo(member).file_size != artifact['size'] or digest(archive.read(member)) != artifact['sha256']:
                raise ValueError('DEPLOYMENT_KIT_ARTIFACT_HASH_MISMATCH')
        with tempfile.TemporaryDirectory(prefix='utilityos-kit-verification-') as temporary:
            source = Path(temporary) / 'source.zip'; source.write_bytes(archive.read(source_name))
            source_result = release.verify(source)
            if source_result['version'] != manifest['version']:
                raise ValueError('DEPLOYMENT_KIT_SOURCE_VERSION_MISMATCH')
    return {'version': manifest['version'], 'target': manifest['target'], 'python': manifest['python'],
            'verified_members': len(names), 'sha256': digest(path.read_bytes()), 'bytes': path.stat().st_size,
            'source_archive_sha256': source_result['sha256'], 'authenticity': 'unsigned; separate school approval required'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['build', 'verify'])
    parser.add_argument('--output', type=Path, required=True, help='New output kit, or existing kit to verify')
    parser.add_argument('--source', type=Path)
    parser.add_argument('--wheelhouse', type=Path)
    parser.add_argument('--runtime-directory', type=Path)
    parser.add_argument('--target', choices=['macos-arm64', 'windows-x64'])
    args = parser.parse_args()
    if args.action == 'build':
        if not all((args.source, args.wheelhouse, args.runtime_directory, args.target)):
            parser.error('build requires --source, --wheelhouse, --runtime-directory and --target')
        result = build(args.source, args.wheelhouse, args.runtime_directory, args.output, args.target)
    else:
        result = verify(args.output)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
