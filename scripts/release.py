#!/usr/bin/env python3
"""Create and verify source-only release archives. Hashes prove integrity only.

Authenticate releases through a separately trusted school distribution process.
This script never installs updates or opens a private utility workspace.
"""
from __future__ import annotations
import argparse
import ast
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import stat
import zipfile

ROOT=Path(__file__).resolve().parents[1]
PREFIX='SKS-UtilityOS/'
MANIFEST='RELEASE-MANIFEST.json'
ROOT_FILES={'README.md','AGENTS.md','MASTER_PROMPT.md','LICENSE','NOTICE.md','.gitignore',
            'run.py','requirements-bootstrap.txt','requirements.txt','requirements-dev.txt','constraints-tested.txt',
            'Launch-Demo.command','Launch-Staff.command'}
FOLDERS={'utilityos','web','samples','tests','scripts','docs','.agents'}
SUFFIXES={'.py','.js','.css','.html','.md','.json','.csv','.xml','.pdf','.sh','.ps1','.txt','.sql'}
SKIP={'__pycache__','.pytest_cache','.venv','.git','node_modules'}

def source_files(root:Path):
    for path in sorted(root.rglob('*')):
        relative=path.relative_to(root)
        if any(part in SKIP for part in relative.parts):continue
        if path.is_symlink():raise ValueError('RELEASE_SYMLINK_REJECTED')
        if not path.is_file():continue
        if len(relative.parts)==1:
            if relative.name not in ROOT_FILES:continue
        elif relative.parts[0] not in FOLDERS or path.suffix not in SUFFIXES:continue
        if path.suffix.lower() in {'.pdf','.csv','.xml'} and relative.parts[0]!='samples':
            raise ValueError('ONLY_REVIEWED_SYNTHETIC_SAMPLE_DOCUMENTS_MAY_BE_PACKAGED')
        yield relative.as_posix(),path.read_bytes()

def build(root:Path,destination:Path):
    if destination.resolve().is_relative_to(root.resolve()):
        raise ValueError('RELEASE_OUTPUT_MUST_BE_OUTSIDE_SOURCE')
    files=dict(source_files(root))
    if not {'run.py','README.md','AGENTS.md','MASTER_PROMPT.md'}.issubset(files):
        raise ValueError('REQUIRED_RELEASE_FILES_MISSING')
    version=None
    for node in ast.parse((root/'utilityos/__init__.py').read_text()).body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='__version__' for t in node.targets):
            version=ast.literal_eval(node.value)
    if not isinstance(version,str) or not version:raise ValueError('RELEASE_VERSION_MISSING')
    manifest={'format':1,'product':'SKS UtilityOS','version':version,
              'created_utc':datetime.now(timezone.utc).isoformat(),
              'data_classification':'source code and synthetic fixtures only',
              'authenticity':'Unsigned. Authenticate using school-approved distribution.',
              'files':{name:sha256(data).hexdigest() for name,data in files.items()}}
    destination.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in files.items():
            info=zipfile.ZipInfo(PREFIX+name)
            info.create_system=3
            info.external_attr=(0o100755 if name.endswith(('.command','.sh')) else 0o100644)<<16
            info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,data)
        z.writestr(PREFIX+MANIFEST,json.dumps(manifest,indent=2)+'\n')
    return verify(destination)

def verify(archive:Path):
    with zipfile.ZipFile(archive) as z:
        infos=z.infolist()
        if len(infos)>2000 or sum(i.file_size for i in infos)>100_000_000:
            raise ValueError('RELEASE_SIZE_LIMIT')
        names=[i.filename for i in infos]
        if len(names)!=len(set(names)):raise ValueError('DUPLICATE_ARCHIVE_MEMBER')
        for info in infos:
            name=info.filename;p=PurePosixPath(name)
            if (not name.startswith(PREFIX) or p.is_absolute() or '..' in p.parts or '\\' in name
                or stat.S_ISLNK(info.external_attr>>16)):
                raise ValueError('UNSAFE_ARCHIVE_MEMBER')
        manifest=json.loads(z.read(PREFIX+MANIFEST))
        if manifest.get('format')!=1 or not isinstance(manifest.get('files'),dict):
            raise ValueError('RELEASE_MANIFEST_INVALID')
        expected={PREFIX+n for n in manifest['files']}|{PREFIX+MANIFEST}
        if set(names)!=expected:raise ValueError('ARCHIVE_MEMBERS_DO_NOT_MATCH_MANIFEST')
        for name,digest in manifest['files'].items():
            if sha256(z.read(PREFIX+name)).hexdigest()!=digest:
                raise ValueError('RELEASE_HASH_MISMATCH')
    return {'version':manifest['version'],'verified_files':len(manifest['files']),
            'sha256':sha256(archive.read_bytes()).hexdigest(),
            'authenticity':'Unsigned; separate trusted provenance check required.'}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['build','verify']);p.add_argument('archive',type=Path)
    args=p.parse_args()
    print(json.dumps(build(ROOT,args.archive) if args.action=='build' else verify(args.archive),indent=2))

if __name__=='__main__':main()
