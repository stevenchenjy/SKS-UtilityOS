#!/usr/bin/env python3
"""Deterministic synthetic campus v1. Creates a NEW external demo workspace only."""
from pathlib import Path
from datetime import date, timedelta
from decimal import Decimal
import argparse
import csv
import io
import json
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
COLUMNS = ['provider','account_alias','invoice_number','bill_date','meter_code','building','commodity','period_start','period_end','usage','unit','current_charge','usage_role','read_type','current_total']
ELECTRIC = [120,115,105,90,80,85,90,90,95,100,110,125]
HEAT = [190,175,145,100,60,30,20,25,65,110,155,185]
OCCUPANCY = [100,100,100,100,100,75,60,65,100,100,100,100]


def csv_bytes(rows):
    out = io.StringIO(newline='')
    writer = csv.DictWriter(out, fieldnames=COLUMNS)
    writer.writeheader(); writer.writerows(rows)
    return out.getvalue().encode()


def money(cents):
    return format(Decimal(cents)/100, '.2f')


def month_start(index):
    return date(2024 + (8+index)//12, (8+index)%12+1, 1)


def monthly_rows(index):
    start, end = month_start(index), month_start(index+1)
    rows = []
    for building in range(20):
        heat = 'natural_gas' if building < 10 else 'heating_oil' if building < 15 else 'propane'
        for commodity,unit,base,season,rate in [
            ('electricity','kWh',3000+building*100,ELECTRIC,12),
            ('water','gal',5000+building*250,OCCUPANCY,1),
            (heat,'therm' if heat=='natural_gas' else 'gal',350+building*20,HEAT,137 if heat=='natural_gas' else 360 if heat=='heating_oil' else 260)]:
            usage = base*season[start.month-1]//100
            if (index,building,commodity) in {(20,2,'water'),(14,8,'electricity')}:
                usage *= 4
            charges = usage*rate+3500
            row = dict(zip(COLUMNS, [f'Synthetic {commodity} vendor',f'SYN-{building+1:02}-{commodity} account',
                f'SYN-{index:02}-{building+1:02}-{commodity}',str(end-timedelta(days=1)),f'SYN-{building+1:02}-{commodity}',
                f'Synthetic {"Residence" if building<12 else "Campus building"} {building+1:02}',commodity,str(start),str(end),str(usage),unit,
                money(charges),'delivery' if commodity in {'heating_oil','propane'} else 'consumption','actual',money(charges)]))
            rows.append(row)
            if commodity=='electricity':
                supply={**row,'provider':'Synthetic electricity supply vendor','account_alias':f'SYN-{building+1:02}-supply account',
                        'invoice_number':row['invoice_number']+'-supply','usage':'0','usage_role':'charges_only',
                        'current_charge':money(usage*7),'current_total':money(usage*7)}
                rows.append(supply)
    return rows


def seed(ledger):
    """Public ledger APIs exercise import/approval instead of bulk SQL insertion."""
    with ledger.store.connect() as db:
        if dict(db.execute('SELECT key,value FROM settings')).get('mode') != 'demo' or db.execute('SELECT 1 FROM documents').fetchone():
            raise ValueError('SYNTHETIC_CAMPUS_REQUIRES_EMPTY_DEMO')
    expected = {}; anomaly_checks = []
    for index in range(24):
        rows = monthly_rows(index)
        expected[rows[0]['bill_date'][:7]] = sum(int(Decimal(r['current_charge'])*100) for r in rows)
        result=ledger.import_file(f'synthetic-campus-{index:02}.csv',csv_bytes(rows))
        for staged_id in result['staged_ids']:
            item=ledger.stage(staged_id)
            if item['payload']['invoice_number'] in {'SYN-20-03-water','SYN-14-09-electricity'}:
                assert any(f['code']=='DAILY_USAGE_ABOVE_150_PERCENT_OF_RECENT_MEDIAN' for f in item['flags'])
                anomaly_checks.append(item['payload']['invoice_number'])
            ledger.approve_bill(staged_id,item['payload'],True)
    bills = {b['invoice_number']:b for b in ledger.bills()}
    for index in [5,13,20]:
        bill = bills[f'SYN-{index:02}-01-electricity']
        item_id=ledger.create_correction(bill['id'],'Synthetic transcription correction drill')['staged_id']
        item=ledger.stage(item_id);payload=item['payload']
        payload['current_total']=payload['lines'][0]['current_charge']=money(bill['current_total_cents']-1234)
        ledger.approve_bill(item_id,payload,True)
        expected[bill['bill_date'][:7]]-=1234
    replacement=next(r for r in monthly_rows(23) if r['invoice_number']=='SYN-23-02-electricity')
    bill=bills[replacement['invoice_number']]
    replacement['current_total']=replacement['current_charge']=money(bill['current_total_cents']-2500)
    item_id=ledger.import_file('synthetic-supplier-rebill.csv',csv_bytes([replacement]))['staged_ids'][0]
    item=ledger.stage(item_id)
    saved=ledger.save_draft(item_id,item['payload'],0,bill['id'],'Synthetic supplier rebill')
    ledger.approve_bill(item_id,saved['payload'],True,revision=saved['revision'])
    expected[bill['bill_date'][:7]]-=2500
    credits=[]
    for index in [6,15,23]:
        row=monthly_rows(index)[0]
        credits.append({**row,'invoice_number':row['invoice_number']+'-credit','usage':'0','usage_role':'charges_only','current_total':'-45.00','current_charge':'-45.00'})
        expected[row['bill_date'][:7]]-=4500
    for item_id in ledger.import_file('synthetic-credits.csv',csv_bytes(credits))['staged_ids']:
        ledger.approve_bill(item_id,ledger.stage(item_id)['payload'],True)
    xml=(ROOT/'samples/demo-intervals.xml').read_bytes()
    for index in [1,2,3]:
        raw=xml.replace(b'DEMO-ONLY',f'SYN-CAMPUS-{index}'.encode())
        staged=ledger.import_file(f'synthetic-intervals-{index}.xml',raw)['staged_ids'][0]
        ledger.approve_intervals(staged,f'SYN-{index:02}-electricity')
    pending=monthly_rows(24)[2]
    pending['invoice_number']='SYN-CAMPUS-PENDING'
    pending['usage']='90000';pending['current_charge']=pending['current_total']='935.00'
    ledger.import_file('synthetic-pending.csv',csv_bytes([pending]))
    with ledger.store.connect() as db:
        db.execute("INSERT INTO settings VALUES ('demo_seed_complete','yes')")
        db.execute("INSERT INTO settings VALUES ('synthetic_campus_version','1')")
    actual={r['month']:r['cents'] for r in ledger.overview()['monthly']}
    assert actual==expected, 'Synthetic report reconciliation failed'
    return {'fixture':'synthetic-campus-v1','buildings':20,'meters':60,'service_months':24,'active_invoices':1923,
            'retained_invoice_versions':1927,'interval_readings':288,'deliberate_anomalies_checked':len(anomaly_checks),
            'expected_monthly_cents':expected}


def main():
    sys.path.insert(0,str(ROOT))
    from utilityos.config import Config
    from utilityos.db import Store
    from utilityos.service import Ledger
    from utilityos.security import set_password, DEMO_PASSWORD
    from utilityos.operations import instance_lock
    from utilityos.audit import acting_as
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',type=Path,required=True)
    args=parser.parse_args()
    directory=args.data_dir.expanduser().resolve()
    Config(directory,'demo').validate()
    if directory.exists():
        raise SystemExit('SYNTHETIC_CAMPUS_REQUIRES_NEW_DIRECTORY')
    started=time.perf_counter()
    with instance_lock(directory),acting_as('synthetic_generator'):
        ledger=Ledger(Store(directory,'demo'));set_password(ledger.store,DEMO_PASSWORD)
        result=seed(ledger)
    result['build_seconds']=round(time.perf_counter()-started,3)
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    main()
