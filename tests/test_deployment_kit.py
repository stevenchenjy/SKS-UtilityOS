"""Public synthetic kit bytes exercise integrity without shipping dependencies."""
import hashlib
import json
from pathlib import Path
import zipfile

import pytest

from scripts import deployment_kit as kit
from scripts import release


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    source = tmp_path / 'source'; source.mkdir()
    for name in ('README.md', 'AGENTS.md', 'MASTER_PROMPT.md', 'run.py'):
        (source / name).write_text('Synthetic code')
    (source / 'utilityos').mkdir()
    (source / 'utilityos/__init__.py').write_text('__version__ = "0.1.0"\n')
    receipts = source / 'docs/dependency-receipts'; receipts.mkdir(parents=True)
    wheel = b'SYNTHETIC_WHEEL'; runtime = b'SYNTHETIC_RUNTIME'
    item = {'name': 'example', 'version': '1.0', 'filename': 'example-1.0-py3-none-any.whl',
            'size': len(wheel), 'sha256': hashlib.sha256(wheel).hexdigest(),
            'url': 'https://files.pythonhosted.org/example-1.0-py3-none-any.whl'}
    receipt = {'format': 'utilityos-wheel-receipt-v1', 'target': 'macos-arm64', 'profile': 'base',
               'python_minor': '3.13', 'python_abi': 'cp313', 'artifacts': [item]}
    runtime_receipt = {'python': '3.13.15', 'artifacts': [{'target': 'macos-arm64', 'filename': 'python.pkg',
                        'size': len(runtime), 'sha256': hashlib.sha256(runtime).hexdigest()}]}
    (receipts / 'macos-arm64-cp313-base.json').write_text(json.dumps(receipt))
    (receipts / 'python-runtime.json').write_text(json.dumps(runtime_receipt))
    monkeypatch.setattr(kit, 'ROOT', source)
    monkeypatch.setattr(kit.dependency_artifacts, 'RECEIPTS', receipts)
    wheels = tmp_path / 'wheels'; wheels.mkdir(); (wheels / item['filename']).write_bytes(wheel)
    python = tmp_path / 'python'; python.mkdir(); (python / 'python.pkg').write_bytes(runtime)
    archive = tmp_path / 'source.zip'; release.build(source, archive, source_date_epoch=1789257600)
    return archive, wheels, python


def test_kit_is_reproducible_and_verifies_all_artifacts(inputs, tmp_path):
    first, second = tmp_path / 'kit1.zip', tmp_path / 'kit2.zip'
    result = kit.build(*inputs, first, 'macos-arm64')
    kit.build(*inputs, second, 'macos-arm64')
    assert first.read_bytes() == second.read_bytes()
    assert result['verified_members'] == 7
    assert kit.verify(first)['sha256'] == result['sha256']


@pytest.mark.parametrize('damage', ['tamper', 'rehash_tamper', 'extra', 'traversal'])
def test_kit_rejects_tampered_or_unlisted_inputs(inputs, tmp_path, damage):
    path = tmp_path / 'kit.zip'; kit.build(*inputs, path, 'macos-arm64')
    with zipfile.ZipFile(path) as archive:
        files = {n: archive.read(n) for n in archive.namelist()}
    member = next(n for n in files if n.startswith('wheelhouse/'))
    if damage in {'tamper', 'rehash_tamper'}:
        files[member] = b'SYNTHETIC_CHANGED'
        if damage == 'rehash_tamper':
            manifest = json.loads(files[kit.MANIFEST])
            manifest['files'][member] = hashlib.sha256(files[member]).hexdigest()
            files[kit.MANIFEST] = json.dumps(manifest).encode()
    else:
        files['../escape' if damage == 'traversal' else 'extra.py'] = b'SYNTHETIC_EXTRA'
    with zipfile.ZipFile(path, 'w') as archive:
        for name, raw in files.items():
            archive.writestr(name, raw)
    with pytest.raises(ValueError):
        kit.verify(path)
