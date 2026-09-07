#!/usr/bin/env python3
"""Install an already downloaded, reviewed English OCR model for offline use.

This command has no network client. It never reads a utility workspace.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from utilityos.pdf_worker import MODEL_SHA256, MODEL_BYTES
from utilityos.storage import publish_source


def prepare(source,destination):
    source=Path(source);destination=Path(destination).expanduser()
    if destination.resolve().is_relative_to(ROOT) or any(p.is_symlink() for p in [destination,*destination.parents]):
        raise ValueError('MODEL_DIRECTORY_MUST_BE_EXTERNAL_WITHOUT_SYMLINKS')
    if source.is_symlink() or not source.is_file() or source.stat().st_size!=MODEL_BYTES:
        raise ValueError('REVIEWED_ENGLISH_MODEL_REQUIRED')
    raw=source.read_bytes()
    if sha256(raw).hexdigest()!=MODEL_SHA256:
        raise ValueError('MODEL_HASH_DOES_NOT_MATCH_REVIEWED_RELEASE')
    destination.mkdir(parents=True,exist_ok=True,mode=0o700)
    publish_source(destination/'eng.traineddata',raw)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-file',required=True,type=Path);parser.add_argument('--destination',required=True,type=Path)
    args=parser.parse_args()
    try:prepare(args.model_file,args.destination)
    except (OSError,ValueError):raise SystemExit('MODEL_PREPARATION_FAILED_CHECK_REVIEWED_FILE_AND_LOCAL_DIRECTORY') from None
    print('Reviewed English model prepared for local offline OCR. No network request was made.')
