"""Synthetic artifact tampering and platform receipt installation contracts."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest

from utilityos.config import ROOT

spec = importlib.util.spec_from_file_location('dependency_artifacts', ROOT / 'scripts/dependency_artifacts.py')
artifacts = importlib.util.module_from_spec(spec); spec.loader.exec_module(artifacts)


@pytest.fixture
def receipt(tmp_path):
    raw = b'SYNTHETIC_WHEEL_BYTES_9988'
    item = {'name': 'example', 'version': '1.0', 'filename': 'example-1.0-py3-none-any.whl',
            'size': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
            'url': 'https://files.pythonhosted.org/example-1.0-py3-none-any.whl'}
    directory = tmp_path / 'wheels'; directory.mkdir()
    (directory / item['filename']).write_bytes(raw)
    return directory, {'format': 'utilityos-wheel-receipt-v1', 'target': 'macos-arm64',
                       'profile': 'base', 'python_abi': 'cp313', 'python_minor': '3.13', 'artifacts': [item]}


@pytest.mark.parametrize('damage', ['bytes', 'extra', 'missing', 'symlink', 'traversal', 'url', 'unhashed'])
def test_offline_artifacts_fail_closed(receipt, tmp_path, damage):
    directory, document = receipt
    item = document['artifacts'][0]
    path = directory / item['filename']
    if damage == 'bytes':
        path.write_bytes(b'X' * item['size'])
    elif damage == 'extra':
        (directory / 'extra.whl').write_bytes(b'X')
    elif damage == 'missing':
        path.unlink()
    elif damage == 'symlink':
        if sys.platform == 'win32':
            pytest.skip('Symlink creation needs Windows privilege; native ACL acceptance remains separate')
        real = tmp_path / 'synthetic-wheel'; path.rename(real); path.symlink_to(real)
    elif damage == 'traversal':
        item['filename'] = '../example.whl'
    elif damage == 'url':
        item['url'] = 'https://example.invalid/example-1.0-py3-none-any.whl'
    else:
        item.pop('sha256')
    with pytest.raises(ValueError):
        artifacts.verify(directory, document)


def test_tampering_is_rejected_before_creating_environment(receipt, tmp_path, monkeypatch):
    directory, document = receipt
    (directory / document['artifacts'][0]['filename']).write_bytes(b'tampered')
    source = tmp_path / 'source'; source.mkdir()
    monkeypatch.setattr(artifacts, 'ROOT', source)
    monkeypatch.setattr(artifacts, 'native_target', lambda: 'macos-arm64')
    monkeypatch.setattr(artifacts, 'load', lambda *args: document)
    with pytest.raises(ValueError):
        artifacts.install(directory)
    assert not (source / '.venv').exists()


def test_install_ignores_indexes_and_requires_all_hashes():
    command = artifacts.installer_command('/synthetic/python', '/synthetic/requirements.txt', '/synthetic/wheels')
    assert all(option in command for option in ['--isolated', '--no-index', '--no-deps', '--no-cache-dir', '--only-binary=:all:', '--require-hashes'])


def test_pip_cannot_redirect_install_or_add_remote_links_from_configuration(tmp_path, monkeypatch):
    import os
    import subprocess
    config = tmp_path / 'hostile-pip.ini'
    config.write_text('[install]\ntarget=/synthetic-outside-environment\nfind-links=https://example.invalid/synthetic-wheels\n')
    monkeypatch.setenv('PIP_CONFIG_FILE', str(config))
    monkeypatch.setenv('PIP_TARGET', '/synthetic-other-environment')
    environment = artifacts.pip_environment()
    assert environment['PIP_CONFIG_FILE'] == os.devnull and 'PIP_TARGET' not in environment
    # Parse actual installer arguments with synthetic global/site/user files
    # registered in pip's own configuration loader. Never install or contact a URL.
    config_files = {}
    for scope in ('global','site','user'):
        path = tmp_path / (scope+'-pip.ini')
        path.write_text(config.read_text())
        config_files[scope] = [str(path)]
    command = artifacts.installer_command('/synthetic/python','/synthetic/requirements.txt','/synthetic/reviewed-wheels')
    probe = """
import json, sys
from pip._internal import configuration
from pip._internal.commands import create_command
configuration.get_configuration_files = lambda: json.loads(sys.argv[1])
options, args = create_command('install', isolated=True).parse_args(sys.argv[3:])
if sys.argv[2] == 'isolated':
    assert options.target_dir is None
    assert options.find_links == ['/synthetic/reviewed-wheels']
else:
    assert options.target_dir == '/synthetic-outside-environment'
    assert 'https://example.invalid/synthetic-wheels' in options.find_links
"""
    arguments = [sys.executable,'-I','-c',probe,json.dumps(config_files)]
    install_arguments = command[command.index('install')+1:]
    for mode,env in (('inherited',dict(os.environ)),('isolated',environment)):
        result = subprocess.run([*arguments,mode,*install_arguments],env=env,capture_output=True)
        assert result.returncode == 0, result.stderr.decode()


def test_reviewed_target_closures_include_exact_runtime_and_spreadsheet_pins():
    for target in ('macos-arm64', 'windows-x64', 'linux-x64'):
        receipt = artifacts.load(target)
        assert len(receipt['artifacts']) == 26
        pins = {row['name']: row['version'] for row in receipt['artifacts']}
        assert pins['openpyxl'] == '3.1.5' and pins['et-xmlfile'] == '2.0.0'
        assert pins['tzdata'] == '2026.4'
        for line in (ROOT / 'requirements.txt').read_text().splitlines():
            if '==' in line and not line.startswith('#'):
                name, version = line.split('==')
                assert pins[artifacts.canonical(name)] == version
        assert all(row['license_reference'].startswith('https://pypi.org/project/') for row in receipt['artifacts'])
    with pytest.raises(ValueError, match='REVIEWED_DEPENDENCY_RECEIPT_REQUIRED'):
        artifacts.load('macos-x64')


def test_timezone_data_available_without_a_system_database():
    import subprocess
    # Windows has no default IANA directory. Reproduce that exact dependency
    # requirement in a separate interpreter without modifying process globals.
    command = [sys.executable, '-I', '-c',
               "import zoneinfo; from datetime import datetime; zoneinfo.reset_tzpath([]); "
               "zone=zoneinfo.ZoneInfo('America/New_York'); "
               "assert datetime(2026,8,1,tzinfo=zone).utcoffset().total_seconds()==-14400"]
    assert subprocess.run(command, capture_output=True).returncode == 0
