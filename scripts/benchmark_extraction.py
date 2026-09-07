#!/usr/bin/env python3
"""Exact-field benchmark of the checked-in fictional corpus, never staff data."""
import argparse
from collections import defaultdict
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from utilityos.extraction_schema import CRITICAL, MONEY_FIELDS, NUMBER_FIELDS
from utilityos.pdf_extract import task


def equal(key, expected, actual):
    if expected is None or actual is None:
        return expected is actual
    if key.split('.')[-1] in MONEY_FIELDS | NUMBER_FIELDS:
        return Decimal(expected)==Decimal(actual)
    return expected==actual


def benchmark(model_dir=None, *, include_ocr=True):
    corpus=ROOT/'samples/intake'
    expected=json.loads((corpus/'expected.json').read_text())
    assert expected['corpus']=='fictional-utility-pdf-v1'
    groups=defaultdict(lambda:{'documents':0,'expected_fields':0,'exact':0,'missing':0,'incorrect':0,'false_extraction':0,'incorrect_units':0,'seconds':0.0})
    by_field=defaultdict(lambda:{'expected':0,'exact':0,'missing':0,'incorrect':0})
    outcomes=[]
    for case in expected['documents']:
        if not include_ocr and case['path']=='ocr':continue
        path=corpus/case['file'];raw=path.read_bytes()
        assert sha256(raw).hexdigest()==case['sha256']
        start=time.perf_counter();result=task(raw,model_dir=model_dir);elapsed=time.perf_counter()-start
        group=groups[case['path']];group['documents']+=1;group['seconds']+=elapsed
        faults=[]
        keys=set(case['fields'])|set(result['fields'])
        for key in sorted(keys):
            if key.split('.')[-1] not in CRITICAL:continue
            truth=case['fields'].get(key);actual=result['fields'].get(key,{}).get('value')
            if truth is None:
                if actual is not None:
                    group['false_extraction']+=1;faults.append({'field':key,'issue':'false_extraction'})
                continue
            group['expected_fields']+=1;field=by_field[key.split('.')[-1]];field['expected']+=1
            kind='exact' if equal(key,truth,actual) else 'missing' if actual is None else 'incorrect'
            group[kind]+=1;field[kind]+=1
            if kind!='exact':faults.append({'field':key,'issue':kind})
            if kind=='incorrect' and key.endswith('_unit'):group['incorrect_units']+=1
        outcomes.append({'fixture':case['file'],'layout_expected':case['layout'],'layout_actual':result['layout_state'],
                         'codes':result['codes'],'faults':faults,'seconds':round(elapsed,3)})
    for group in groups.values():
        group['seconds']=round(group['seconds'],3)
        group['exact_percent']=round(group['exact']/group['expected_fields']*100,3) if group['expected_fields'] else None
    return {'corpus':expected['corpus'],'schema':1,'ocr_model_supplied':bool(model_dir),'groups':dict(groups),
            'by_field':dict(by_field),'outcomes':outcomes,'scope':'Synthetic fixture accuracy only; no real provider validation.'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--ocr-model-dir',type=Path)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if args.output.resolve().is_relative_to(ROOT):raise SystemExit('BENCHMARK_OUTPUT_MUST_BE_EXTERNAL')
    result=benchmark(args.ocr_model_dir);args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result['groups'],indent=2))
