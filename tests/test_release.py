from pathlib import Path
import importlib.util
import json
import zipfile
import pytest

spec=importlib.util.spec_from_file_location('release',Path(__file__).resolve().parents[1]/'scripts/release.py')
release=importlib.util.module_from_spec(spec);spec.loader.exec_module(release)

@pytest.fixture
def project(tmp_path):
    root=tmp_path/'source';root.mkdir()
    for name in ['README.md','AGENTS.md','MASTER_PROMPT.md','run.py']:(root/name).write_text('Synthetic test source')
    (root/'utilityos').mkdir();(root/'utilityos/__init__.py').write_text('"""module"""\n__version__ = "0.1.0"\n')
    (root/'private-data').mkdir();(root/'private-data/private.csv').write_text('DO_NOT_PACKAGE')
    (root/'secret.db').write_text('DO_NOT_PACKAGE')
    (root/'.env').write_text('DO_NOT_PACKAGE')
    return root

def test_release_source_only_and_version(project,tmp_path):
    archive=tmp_path/'release.zip';result=release.build(project,archive)
    assert result['version']=='0.1.0'
    with zipfile.ZipFile(archive) as z:
        assert not any('private' in n or n.endswith('.db') or n.endswith('.env') for n in z.namelist())
        assert all(b'DO_NOT_PACKAGE' not in z.read(n) for n in z.namelist())

def test_tampered_release_fails(project,tmp_path):
    archive=tmp_path/'release.zip';release.build(project,archive)
    with zipfile.ZipFile(archive) as z:files={n:z.read(n) for n in z.namelist()}
    files['SKS-UtilityOS/run.py']=b'changed'
    with zipfile.ZipFile(archive,'w') as z:
        for n,b in files.items():z.writestr(n,b)
    with pytest.raises(ValueError,match='HASH_MISMATCH'):release.verify(archive)

def test_unlisted_archive_member_fails(project,tmp_path):
    archive=tmp_path/'release.zip';release.build(project,archive)
    with zipfile.ZipFile(archive,'a') as z:z.writestr('SKS-UtilityOS/extra.py','unlisted')
    with pytest.raises(ValueError,match='MEMBERS'):release.verify(archive)

def test_archive_traversal_fails(project,tmp_path):
    archive=tmp_path/'release.zip';release.build(project,archive)
    with zipfile.ZipFile(archive,'a') as z:z.writestr('SKS-UtilityOS/../bad','bad')
    with pytest.raises(ValueError,match='UNSAFE'):release.verify(archive)

def test_release_output_inside_source_rejected(project):
    with pytest.raises(ValueError,match='OUTSIDE_SOURCE'):release.build(project,project/'release.zip')


def test_release_preserves_native_launcher_modes_and_bootstrap(tmp_path):
    archive=tmp_path/'release.zip'
    release.build(release.ROOT,archive)
    with zipfile.ZipFile(archive) as z:
        for name in ['Launch-Demo.command','Launch-Staff.command','scripts/setup.sh']:
            assert z.getinfo(release.PREFIX+name).external_attr>>16 & 0o111
        assert release.PREFIX+'requirements-bootstrap.txt' in z.namelist()
        assert release.PREFIX+'tests/fixtures/schema_v1.sql' in z.namelist()
        assert not any('MEETING_BRIEF' in name for name in z.namelist())


def test_nested_local_configuration_and_secrets_are_never_packaged(project,tmp_path):
    for name in ['utilityos/secrets.json','utilityos/local-config.json','docs/private-records.txt','scripts/credentials.json']:
        path=project/name;path.parent.mkdir(exist_ok=True,parents=True);path.write_text('SYNTHETIC_NEVER_PACKAGE_9988')
    archive=tmp_path/'release.zip';release.build(project,archive)
    with zipfile.ZipFile(archive) as z:
        assert all(b'SYNTHETIC_NEVER_PACKAGE_9988' not in z.read(n) for n in z.namelist())


def test_gitignore_covers_runtime_export_and_secret_paths(tmp_path):
    import subprocess
    import shutil
    if not shutil.which('git'):pytest.skip('Git is required for development index checks')
    subprocess.run(['git','init','--quiet',str(tmp_path)],check=True)
    (tmp_path/'.gitignore').write_bytes((release.ROOT/'.gitignore').read_bytes())
    names=['private-workspace-one/records.json','secrets.json','utilityos/secrets.json','new-export.csv','new-source.pdf','new-source.xml','build/release.zip','generated.zip','new.db','new.sqlite3-wal','.env.secret','key.pem','credentials.json','.venv/a.py','browser.log']
    result=subprocess.run(['git','check-ignore','--stdin'],cwd=tmp_path,input='\n'.join(names)+'\n',capture_output=True,text=True,check=True)
    assert set(result.stdout.splitlines())==set(names)
