#!/usr/bin/env python3
"""Public-source-only integrity and digital extraction checks. No runtime input."""
import json
from pathlib import Path
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.check_source_control import main as source_check
from scripts.release import build, verify
from scripts.benchmark_extraction import benchmark


def main():
    source_check()
    with tempfile.TemporaryDirectory(prefix='utilityos-synthetic-ci-') as temporary:
        target=Path(temporary)
        first,second=target/'first.zip',target/'second.zip'
        build(ROOT,first,source_date_epoch=1788739200)
        build(ROOT,second,source_date_epoch=1788739200)
        assert first.read_bytes()==second.read_bytes(),'SOURCE_ARCHIVE_NOT_REPRODUCIBLE'
        result=verify(first)
    score=benchmark(include_ocr=False)
    assert score['groups'] and all(group['exact']==group['expected_fields'] and
        not any(group[key] for key in ('missing','incorrect','false_extraction','incorrect_units'))
        for group in score['groups'].values()),'SYNTHETIC_DIGITAL_BENCHMARK_FAILED'
    assert all(row['layout_expected']==row['layout_actual'] for row in score['outcomes'])
    print(json.dumps({'source_files_verified':result['verified_files'],'reproducible_archive':True,
                      'synthetic_digital_groups':score['groups'],
                      'native_school_machine_acceptance':'separate; not run in CI'},indent=2))


if __name__=='__main__':main()
