#!/usr/bin/env python3
"""Review, fetch, verify and install exact public dependency artifacts.

Only the explicit ``review`` command resolves candidates and writes receipts.
Normal installation reads checked-in receipts and verifies every byte before
creating a new environment. This script never opens a UtilityOS workspace.
"""
from __future__ import annotations
import argparse
from email.parser import BytesParser
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import sysconfig
import tempfile
import urllib.request
from urllib.parse import urlparse
import venv
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RECEIPTS = ROOT / 'docs' / 'dependency-receipts'
TARGETS = {
    'macos-arm64': {'system': 'Darwin', 'machine': 'arm64', 'platforms': ['macosx_13_0_arm64'], 'minimum_os': '13'},
    'macos-x64': {'system': 'Darwin', 'machine': 'x86_64', 'platforms': ['macosx_13_0_x86_64'], 'minimum_os': '13'},
    'windows-x64': {'system': 'Windows', 'machine': 'AMD64', 'platforms': ['win_amd64'], 'minimum_os': 'Windows 11 (school-supported edition)'},
    'linux-x64': {'system': 'Linux', 'machine': 'x86_64', 'platforms': ['manylinux_2_28_x86_64', 'manylinux_2_17_x86_64'], 'minimum_os': 'glibc 2.28'},
}
PYTHON_MINOR = (3, 13)
QUALIFICATION_PYTHON = '3.13.15'
MAX_WHEEL = 150 * 1024 * 1024


def canonical(name):
    return re.sub(r'[-_.]+', '-', name).lower()


def native_target():
    if platform.python_implementation() != 'CPython' or sys.version_info[:2] != PYTHON_MINOR or sysconfig.get_config_var('Py_GIL_DISABLED'):
        raise ValueError('REVIEWED_CPYTHON_313_GIL_RUNTIME_REQUIRED')
    machine = platform.machine().lower()
    for target, settings in TARGETS.items():
        if platform.system() == settings['system'] and machine == settings['machine'].lower():
            if settings['system'] == 'Darwin' and int(platform.mac_ver()[0].split('.')[0]) < 13:
                raise ValueError('REVIEWED_MACOS_13_OR_NEWER_REQUIRED')
            return target
    raise ValueError('PLATFORM_HAS_NO_REVIEWED_RECEIPT')


def receipt_path(target, profile='base'):
    if target not in TARGETS or profile not in {'base', 'ocr'}:
        raise ValueError('DEPENDENCY_TARGET_OR_PROFILE_INVALID')
    return RECEIPTS / f'{target}-cp313-{profile}.json'


def validate(receipt):
    if not isinstance(receipt, dict) or receipt.get('format') != 'utilityos-wheel-receipt-v1':
        raise ValueError('DEPENDENCY_RECEIPT_INVALID')
    target, profile = receipt.get('target'), receipt.get('profile')
    receipt_path(target, profile)
    if receipt.get('python_abi') != 'cp313' or receipt.get('python_minor') != '3.13':
        raise ValueError('DEPENDENCY_RECEIPT_RUNTIME_INVALID')
    artifacts = receipt.get('artifacts')
    if not isinstance(artifacts, list) or not 1 <= len(artifacts) <= 80:
        raise ValueError('DEPENDENCY_RECEIPT_ARTIFACTS_INVALID')
    names, files = set(), set()
    for item in artifacts:
        if not isinstance(item, dict):
            raise ValueError('DEPENDENCY_RECEIPT_ARTIFACT_INVALID')
        name, filename = item.get('name', ''), item.get('filename', '')
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', name) or name in names:
            raise ValueError('DEPENDENCY_RECEIPT_PACKAGE_INVALID')
        if not isinstance(filename, str) or not re.fullmatch(r'[A-Za-z0-9_.+-]+\.whl', filename) or filename in files:
            raise ValueError('DEPENDENCY_RECEIPT_FILENAME_INVALID')
        if not isinstance(item.get('version'), str) or not re.fullmatch(r'[0-9][A-Za-z0-9_.+!-]*', item['version']):
            raise ValueError('DEPENDENCY_RECEIPT_VERSION_INVALID')
        if not isinstance(item.get('sha256'), str) or not re.fullmatch(r'[a-f0-9]{64}', item['sha256']):
            raise ValueError('DEPENDENCY_RECEIPT_HASH_INVALID')
        if type(item.get('size')) is not int or not 1 <= item['size'] <= MAX_WHEEL:
            raise ValueError('DEPENDENCY_RECEIPT_SIZE_INVALID')
        url = urlparse(item.get('url', ''))
        if url.scheme != 'https' or url.hostname != 'files.pythonhosted.org' or url.username or url.password or url.query or url.fragment or Path(url.path).name != filename:
            raise ValueError('DEPENDENCY_RECEIPT_URL_INVALID')
        names.add(name); files.add(filename)
    return receipt


def load(target, profile='base'):
    path = receipt_path(target, profile)
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 1024 * 1024:
        raise ValueError('REVIEWED_DEPENDENCY_RECEIPT_REQUIRED')
    receipt = validate(json.loads(path.read_bytes()))
    if receipt['target'] != target or receipt['profile'] != profile:
        raise ValueError('DEPENDENCY_RECEIPT_TARGET_MISMATCH')
    return receipt


def checked_bytes(path, item):
    if path.is_symlink() or not path.is_file() or path.stat().st_size != item['size']:
        raise ValueError('DEPENDENCY_ARTIFACT_MISSING_OR_SIZE_MISMATCH')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != item['sha256']:
        raise ValueError('DEPENDENCY_ARTIFACT_HASH_MISMATCH')
    return raw


def verify(directory, receipt):
    validate(receipt)
    directory = Path(directory)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError('DEPENDENCY_WHEELHOUSE_REQUIRED')
    expected = {item['filename'] for item in receipt['artifacts']}
    if {p.name for p in directory.iterdir()} != expected:
        raise ValueError('DEPENDENCY_WHEELHOUSE_MEMBERS_MISMATCH')
    for item in receipt['artifacts']:
        checked_bytes(directory / item['filename'], item)
    return {'target': receipt['target'], 'profile': receipt['profile'], 'verified_wheels': len(expected),
            'sha256': 'all_match_reviewed_receipt', 'bytes': sum(item['size'] for item in receipt['artifacts'])}


def outside_source(path):
    path = Path(path).expanduser().resolve()
    if path.is_relative_to(ROOT):
        raise ValueError('DEPENDENCY_STAGING_MUST_BE_OUTSIDE_SOURCE')
    return path


def fetch(directory, receipt):
    directory = outside_source(directory)
    if directory.exists():
        return verify(directory, receipt)
    directory.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='utilityos-wheels-', dir=directory.parent) as temporary:
        staging = Path(temporary) / 'wheels'; staging.mkdir()
        for item in receipt['artifacts']:
            with urllib.request.urlopen(item['url'], timeout=60) as response:
                if urlparse(response.url).hostname != 'files.pythonhosted.org':
                    raise ValueError('DEPENDENCY_DOWNLOAD_REDIRECT_REJECTED')
                raw = response.read(item['size'] + 1)
            path = staging / item['filename']; path.write_bytes(raw)
            checked_bytes(path, item)
        result = verify(staging, receipt)
        staging.rename(directory)
    return result


def installer_command(python, requirements, wheelhouse):
    # Ignore environment/user pip configuration and indices. Every dependency is
    # pinned and hashed; a source install, resolver fallback or extra dependency
    # fails instead of silently expanding the reviewed closure.
    return [str(python), '-I', '-m', 'pip', '--isolated', '--disable-pip-version-check',
            'install', '--no-cache-dir', '--no-index', '--no-deps', '--find-links', str(wheelhouse),
            '--only-binary=:all:', '--require-hashes', '-r', str(requirements)]


def pip_environment():
    # --isolated still reads an explicit PIP_CONFIG_FILE and machine/site pip
    # configuration. A hostile target/find-links entry could redirect writes or
    # network access. os.devnull disables ALL config-file loading on each OS.
    environment = {key: value for key, value in os.environ.items() if not key.upper().startswith('PIP_')}
    environment['PIP_CONFIG_FILE'] = os.devnull
    return environment


def install(directory=None, profile='base'):
    target = native_target()
    receipt = load(target, profile)
    environment = ROOT / '.venv'
    if environment.exists() or environment.is_symlink():
        raise ValueError('ENVIRONMENT_EXISTS_PREPARE_NEW_CODE_FOLDER')
    with tempfile.TemporaryDirectory(prefix='utilityos-install-') as temporary:
        temporary = Path(temporary)
        wheels = Path(directory).expanduser().resolve() if directory else temporary / 'wheels'
        if directory:
            verify(wheels, receipt)
        else:
            fetch(wheels, receipt)
        # The new venv is created only after all reviewed artifacts match.
        venv.EnvBuilder(with_pip=True).create(environment)
        python = environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        for scope in ('bootstrap', 'runtime'):
            requirements = temporary / f'{scope}.txt'
            items = [i for i in receipt['artifacts'] if (i['name'] == 'pip') == (scope == 'bootstrap')]
            requirements.write_text(''.join(f"{i['name']}=={i['version']} --hash=sha256:{i['sha256']}\n" for i in items))
            subprocess.run(installer_command(python, requirements, wheels), check=True, env=pip_environment())
        subprocess.run([str(python), '-I', '-m', 'pip', '--isolated', 'check'], check=True, env=pip_environment())
        installed = json.loads(subprocess.check_output([str(python), '-I', '-m', 'pip', '--isolated',
                                                       '--disable-pip-version-check', 'list', '--format=json'], text=True, env=pip_environment()))
        expected = {i['name']: i['version'] for i in receipt['artifacts']}
        if {canonical(i['name']): i['version'] for i in installed} != expected:
            raise ValueError('INSTALLED_DEPENDENCY_CLOSURE_MISMATCH')
        record = {'format': 'utilityos-install-receipt-v1', 'target': target, 'profile': profile,
                  'python': platform.python_version(), 'python_abi': 'cp313',
                  'dependency_receipt_sha256': hashlib.sha256(receipt_path(target, profile).read_bytes()).hexdigest(),
                  'artifacts': {i['filename']: i['sha256'] for i in receipt['artifacts']}}
        (environment / 'utilityos-install-receipt.json').write_text(json.dumps(record, indent=2) + '\n')
    return {'environment': 'new_local_venv', 'target': target, 'profile': profile,
            'python': platform.python_version(), 'verified_wheels': len(receipt['artifacts'])}


def review(target, directory, profile='base'):
    """Explicit maintainer action: download candidates and record metadata.

    This produces reviewable source changes, never approves a school install.
    Pip's packaging module is used only in this staging/development command.
    """
    from pip._vendor.packaging.markers import default_environment
    from pip._vendor.packaging.requirements import Requirement
    directory = outside_source(directory)
    if directory.exists():
        raise ValueError('REVIEW_REQUIRES_NEW_STAGING_DIRECTORY')
    if profile == 'ocr' and target != 'macos-arm64':
        raise ValueError('OPTIONAL_OCR_PLATFORM_NOT_QUALIFIED')
    inventory = json.loads((ROOT / 'docs/DEPENDENCY_INVENTORY.json').read_bytes())
    licenses = {canonical(i['name']): i['license'] for i in inventory['components']}
    pins = {canonical(line.split('==')[0]): line.split('==')[1]
            for line in (ROOT / 'constraints-tested.txt').read_text().splitlines() if '==' in line and not line.startswith('#')}
    pins['pip'] = (ROOT / 'requirements-bootstrap.txt').read_text().split('pip==')[1].splitlines()[0]
    names = {canonical(i['name']) for i in inventory['components'] if i.get('scope') not in {'optional_ocr', 'development'}}
    names |= {'pip', 'openpyxl', 'et-xmlfile'}
    if profile == 'ocr':
        names |= {'tesserocr', 'cysignals'}
    licenses.update({'pip': 'MIT', 'openpyxl': 'MIT', 'et-xmlfile': 'MIT'})
    command = [sys.executable, '-I', '-m', 'pip', '--isolated', '--disable-pip-version-check', 'download',
               '--only-binary=:all:', '--no-deps', '--python-version', '3.13', '--implementation', 'cp', '--abi', 'cp313',
               '--dest', str(directory)]
    settings = TARGETS[target]
    platforms = ['macosx_15_0_arm64'] if profile == 'ocr' else settings['platforms']
    for tag in platforms:
        command.extend(['--platform', tag])
    command += [f'{name}=={pins[name]}' for name in sorted(names)]
    subprocess.run(command, check=True, env=pip_environment())
    artifacts = []
    environment = default_environment()
    environment.update({'os_name': 'nt' if target == 'windows-x64' else 'posix',
                        'sys_platform': {'Darwin': 'darwin', 'Windows': 'win32', 'Linux': 'linux'}[settings['system']],
                        'platform_system': settings['system'], 'platform_machine': settings['machine'],
                        'python_version': '3.13', 'python_full_version': QUALIFICATION_PYTHON, 'extra': ''})
    for wheel in sorted(directory.iterdir()):
        with zipfile.ZipFile(wheel) as archive:
            metadata_names = [n for n in archive.namelist() if n.endswith('.dist-info/METADATA')]
            if len(metadata_names) != 1:
                raise ValueError('WHEEL_METADATA_INVALID')
            metadata = BytesParser().parsebytes(archive.read(metadata_names[0]))
            license_files = [n for n in archive.namelist() if any(word in n.lower() for word in ('license', 'copying', 'notice'))]
        name, version = canonical(metadata['Name']), metadata['Version']
        if name not in names or version != pins[name]:
            raise ValueError('WHEEL_PACKAGE_NOT_PINNED')
        dependencies = []
        for raw in metadata.get_all('Requires-Dist', []):
            requirement = Requirement(raw)
            if requirement.marker is None or requirement.marker.evaluate(environment):
                if requirement.url or requirement.extras:
                    raise ValueError('TARGET_DEPENDENCY_URL_OR_EXTRA_REQUIRES_REVIEW')
                dependency = canonical(requirement.name)
                if dependency not in names or not requirement.specifier.contains(pins[dependency]):
                    raise ValueError('TARGET_DEPENDENCY_CLOSURE_INCOMPLETE_' + dependency.upper().replace('-', '_'))
                dependencies.append(raw)
        with urllib.request.urlopen(f'https://pypi.org/pypi/{name}/{version}/json', timeout=60) as response:
            upstream = json.load(response)
        candidates = [item for item in upstream['urls'] if item['filename'] == wheel.name and not item.get('yanked')]
        digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
        if len(candidates) != 1 or candidates[0]['digests']['sha256'] != digest or candidates[0]['size'] != wheel.stat().st_size:
            raise ValueError('UPSTREAM_ARTIFACT_METADATA_MISMATCH')
        artifacts.append({'name': name, 'version': version, 'filename': wheel.name, 'sha256': digest,
                          'size': wheel.stat().st_size, 'url': candidates[0]['url'],
                          'license': licenses.get(name, metadata.get('License-Expression', 'REVIEW_REQUIRED')),
                          'license_reference': f'https://pypi.org/project/{name}/{version}/',
                          'wheel_license_files': license_files, 'target_dependencies': dependencies})
    receipt = {'format': 'utilityos-wheel-receipt-v1', 'target': target, 'profile': profile,
               'python_minor': '3.13', 'python_abi': 'cp313', 'qualification_python': QUALIFICATION_PYTHON,
               'reviewed_on': '2026-09-13', 'platform': settings, 'artifact_selection_platforms': platforms,
               'status': 'artifact hashes and target metadata reviewed; native acceptance recorded separately',
               'artifacts': sorted(artifacts, key=lambda item: item['name'])}
    validate(receipt)
    RECEIPTS.mkdir(parents=True, exist_ok=True)
    receipt_path(target, profile).write_text(json.dumps(receipt, indent=2) + '\n')
    return verify(directory, receipt)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['review', 'fetch', 'verify', 'install', 'target'])
    parser.add_argument('--target', choices=['auto', *TARGETS], default='auto')
    parser.add_argument('--profile', choices=['base', 'ocr'], default='base')
    parser.add_argument('--directory', type=Path, help='External wheelhouse; installation downloads exact artifacts when omitted')
    args = parser.parse_args()
    target = native_target() if args.target == 'auto' else args.target
    if args.action == 'target':
        print(target); return
    if args.action == 'install':
        if target != native_target():
            raise ValueError('DEPENDENCY_INSTALL_PLATFORM_MISMATCH')
        result = install(args.directory, args.profile)
    else:
        if args.directory is None:
            raise ValueError('DEPENDENCY_WHEELHOUSE_DIRECTORY_REQUIRED')
        if args.action == 'review':
            result = review(target, args.directory, args.profile)
        else:
            receipt = load(target, args.profile)
            result = fetch(args.directory, receipt) if args.action == 'fetch' else verify(args.directory, receipt)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.SubprocessError, zipfile.BadZipFile) as exc:
        code = str(exc) if isinstance(exc, ValueError) and re.fullmatch(r'[A-Z][A-Z0-9_]{1,100}', str(exc)) else 'DEPENDENCY_ACTION_FAILED'
        print('Action stopped: ' + code, file=sys.stderr)
        sys.exit(1)
