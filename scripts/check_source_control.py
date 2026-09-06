#!/usr/bin/env python3
"""Check the Git index for source-only membership without printing private paths."""
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from release import source_allowed, ROOT


def main():
    result=subprocess.run(['git','ls-files','-z'],cwd=ROOT,capture_output=True,check=True)
    files=result.stdout.decode().split('\0')
    forbidden=[p for p in files if p and p!='RELEASE-MANIFEST.json' and not source_allowed(Path(p))]
    if forbidden:
        raise SystemExit('INDEX_CONTAINS_NON_SOURCE_FILES_REVIEW_LOCALLY')
    print('Git index contains only allowed source paths. Review contents before committing.')

if __name__=='__main__':main()
