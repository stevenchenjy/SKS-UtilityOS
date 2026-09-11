"""Fictional mapped operational data: provenance, semantics and reconciliation."""
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
import sqlite3
import pytest
from utilityos.config import ROOT
from utilityos.db import Store
from utilityos.operations import backup, check, restore, instance_lock
from utilityos.usage import UsageImport, timestamp
from utilityos.usage_storage import verify
from zoneinfo import ZoneInfo

RAW = (ROOT/'samples/generic-water-usage.csv').read_bytes()
MAPPING = {'meter_code':'SYN-W','commodity':'water','unit':'US_gal','semantics':'delta','timezone':'',
           'meter_column':'source_meter','source_meter':'SYN-WATER-01','start_column':'start','end_column':'end',
           'value_column':'value','unit_column':'unit','quality_column':'quality'}


@pytest.fixture
def usage(ledger):
    with ledger.store.connect() as db:
        db.execute("INSERT INTO meters(code,commodity,unit) VALUES ('SYN-W','water','gal')")
        db.execute("INSERT INTO meters(code,commodity,unit) VALUES ('SYN-G','natural_gas','therm')")
        db.execute("INSERT INTO meters(code,commodity,unit) VALUES ('SYN-E','electricity','kWh')")
    return UsageImport(ledger)


def ready(usage, raw=RAW, mapping=None):
    identifier = usage.import_file('fictional.csv',raw)['import_id']
    usage.preview(identifier, {'revision':0,'mapping':mapping or MAPPING})
    return identifier


def approve(usage, identifier, revision=1):
    return usage.approve(identifier, {'revision':revision,'acknowledge':True})


def withdraw(usage, identifier):
    return usage.close(identifier, {'revision':1,'acknowledge':True,'reason':'Synthetic corrected export reconciliation'}, withdraw=True)


def test_mapping_original_bytes_and_no_financial_posting(usage, ledger, raw_csv):
    item = ledger.import_file('financial.csv',raw_csv)['staged_ids'][0]
    ledger.approve_bill(item,ledger.stage(item)['payload'],True)
    before = ledger.overview()
    identifier = ready(usage)
    preview = usage.detail(identifier)
    assert preview['state'] == 'pending' and preview['preview']['reading_count'] == 3
    assert preview['preview']['mapping'] == MAPPING
    assert preview['preview']['readings'][0]['quantity'] == '12.5'
    assert preview['preview']['readings'][0]['start_utc'] == 1785556800
    assert preview['preview']['readings'][0]['end_utc']-preview['preview']['readings'][0]['start_utc'] == 3600
    assert usage.listing()['active_reading_count'] == 0
    assert approve(usage,identifier)['reading_count'] == 3
    assert ledger.overview() == before  # Entire arbitrary invoice month/period remains separate.
    with usage.store.connect() as db:
        assert db.execute('SELECT building_id FROM meters WHERE code="SYN-W"').fetchone()[0] is None
        assert db.execute('SELECT COUNT(*) FROM bills').fetchone()[0] == 1
    assert (usage.store.sources/(sha256(RAW).hexdigest()+'.csv')).read_bytes() == RAW
    assert check(usage.store)['sources'] == 'ok'


def test_repeat_exports_share_active_measurements_and_retain_all_evidence(usage):
    first = ready(usage)
    approve(usage,first)
    assert usage.import_file('renamed.csv',RAW) == {'import_id':first,'duplicate_source':True}
    second = ready(usage,RAW.replace(b'12.50',b'12.500'))
    assert usage.detail(second)['duplicate_readings'] == 3
    assert approve(usage,second)['duplicate_readings'] == 3
    assert usage.listing()['active_reading_count'] == 3
    with usage.store.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM usage_readings').fetchone()[0] == 3
        assert db.execute('SELECT COUNT(*) FROM usage_evidence').fetchone()[0] == 6
    withdraw(usage,first)
    assert usage.listing()['active_reading_count'] == 3
    withdraw(usage,second)
    assert usage.listing()['active_reading_count'] == 0
    assert check(usage.store)['audit'] == 'ok'


def test_conflicting_corrected_export_requires_all_active_sources_withdrawn(usage):
    first = ready(usage)
    approve(usage,first)
    repeated = ready(usage, RAW.replace(b'12.50',b'12.500'))
    approve(usage,repeated)
    corrected = ready(usage,RAW.replace(b'12.50',b'15.50'))
    assert {c['import_id'] for c in usage.detail(corrected)['conflicts']} == {first,repeated}
    with pytest.raises(ValueError,match='USAGE_CONFLICT_RECONCILE'):
        approve(usage,corrected)
    assert usage.detail(corrected)['state'] == 'pending'
    assert usage.listing()['active_reading_count'] == 3
    withdraw(usage,first)
    with pytest.raises(ValueError,match='USAGE_CONFLICT_RECONCILE'):
        approve(usage,corrected)
    withdraw(usage,repeated)
    assert approve(usage,corrected)['reading_count'] == 3
    assert usage.listing()['active_reading_count'] == 3
    assert usage.detail(first)['state'] == 'withdrawn'
    assert usage.detail(first)['withdrawal']['reason'] == 'Synthetic corrected export reconciliation'
    assert check(usage.store)['sources'] == 'ok'


def test_partially_overlapping_intervals_cannot_post_new_tail(usage):
    first = ready(usage)
    approve(usage,first)
    changed = RAW.replace(b'T00:00:00',b'T00:30:00').replace(b'T01:00:00',b'T01:30:00').replace(b'T02:00:00',b'T02:30:00').replace(b'T03:00:00',b'T03:30:00')
    second = ready(usage,changed)
    with pytest.raises(ValueError,match='USAGE_CONFLICT_RECONCILE'):
        approve(usage,second)
    assert usage.listing()['active_reading_count'] == 3


def test_preview_does_not_lock_conflicts_and_concurrent_export_dedup_is_transactional(usage):
    first = ready(usage)
    second = ready(usage,RAW.replace(b'12.50',b'12.500'))
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda identifier:approve(usage,identifier), [first,second]))
    assert sum(r['duplicate_readings'] for r in results) == 3
    assert usage.listing()['active_reading_count'] == 3
    assert check(usage.store)['audit'] == 'ok'


@pytest.mark.parametrize('value',[None,False,True,-1,'1',1.0])
def test_strict_revision_does_not_mutate_pending(usage,value):
    identifier = ready(usage)
    with pytest.raises(ValueError,match='USAGE_REVISION_REQUIRED'):
        usage.approve(identifier,{'revision':value,'acknowledge':True})
    assert usage.detail(identifier)['state'] == 'pending'
    assert usage.listing()['active_reading_count'] == 0


@pytest.mark.parametrize('value',[None,False,1,'true',[],{}])
def test_literal_acknowledgement_required(usage,value):
    identifier = ready(usage)
    with pytest.raises(ValueError,match='USAGE_MAPPING_ACKNOWLEDGEMENT_REQUIRED'):
        usage.approve(identifier,{'revision':1,'acknowledge':value})
    assert usage.listing()['active_reading_count'] == 0


def test_stale_mapping_requires_reopen_and_old_preview_stays_immutable(usage):
    identifier = ready(usage)
    usage.preview(identifier,{'revision':1,'mapping':{**MAPPING,'timezone':'America/New_York'}})
    with pytest.raises(ValueError,match='USAGE_CHANGED_REOPEN'):
        approve(usage,identifier)
    with usage.store.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM usage_previews').fetchone()[0] == 2
    approve(usage,identifier,2)
    assert check(usage.store)['audit'] == 'ok'


@pytest.mark.parametrize('mapping,code',[
    ({'unit':'gal'},'USAGE_COMMODITY_UNIT'),
    ({'commodity':'gas','unit':'therm'},'USAGE_COMMODITY_UNIT'),
    ({'commodity':'natural_gas','unit':'therm'},'USAGE_CONFIRMED_METER_COMMODITY'),
    ({'unit':'kW'},'USAGE_COMMODITY_UNIT'),
    ({'semantics':'demand'},'USAGE_DELTA_OR_CUMULATIVE'),
    ({'meter_code':'NO-CONFIRMED-METER'},'USAGE_CONFIRMED_METER'),
    ({'value_column':'start'},'USAGE_COLUMN_MAPPING'),
    ({'source_meter':'WRONG-METER'},'USAGE_ONE_SOURCE_METER'),
    ({'unit':'L'},'USAGE_SOURCE_UNIT_DIFFERS'),
    ({'timezone':'Unverified/Place'},'USAGE_IANA_TIMEZONE'),
])
def test_ambiguous_units_semantics_and_mappings_rejected_but_source_retained(usage,mapping,code):
    identifier = usage.import_file('synthetic.csv',RAW)['import_id']
    with pytest.raises(ValueError,match=code):
        usage.preview(identifier,{'revision':0,'mapping':{**MAPPING,**mapping}})
    assert usage.detail(identifier)['revision'] == 0
    assert usage.detail(identifier)['preview'] is None
    assert check(usage.store)['sources'] == 'ok'


@pytest.mark.parametrize('replacement', [b'=1+1',b'+123',b'-2',b'@SUM(A1)',b'  =HYPERLINK("https://example.invalid")'])
def test_formula_like_source_cells_are_never_evaluated_or_accepted(usage,replacement):
    with pytest.raises(ValueError,match='USAGE_FORMULA_LIKE|USAGE_REQUIRES_UTF8|USAGE_CSV_ROW'):
        usage.import_file('synthetic.csv',RAW.replace(b'12.50',replacement))
    assert usage.listing()['items'] == []


def test_timestamp_timezone_dst_and_explicit_offsets():
    zone = ZoneInfo('America/New_York')
    assert timestamp('2026-08-01T00:00:00',zone) == timestamp('2026-08-01T00:00:00-04:00',None)
    for value in ('2026-11-01T01:30:00','2026-03-08T02:30:00'):
        with pytest.raises(ValueError,match='USAGE_DST_AMBIGUOUS_OR_NONEXISTENT'):
            timestamp(value,zone)
    assert timestamp('2026-11-01T01:30:00-05:00',None)-timestamp('2026-11-01T01:30:00-04:00',None) == 3600
    with pytest.raises(ValueError,match='USAGE_NAIVE_TIMESTAMP_NEEDS_TIMEZONE'):
        timestamp('2026-08-01T00:00:00',None)
    with pytest.raises(ValueError,match='USAGE_TIMESTAMP_REQUIRES_ISO'):
        timestamp('2026-08-01',zone)


def test_raw_cumulative_gas_counters_are_retained_without_derived_consumption(usage):
    raw = b'meter,time,counter,units\nGAS-SYN,2026-08-01T00:00Z,100.25,CCF\nGAS-SYN,2026-08-02T00:00Z,110.50,CCF\n'
    mapping = {**MAPPING,'meter_code':'SYN-G','commodity':'natural_gas','unit':'CCF','source_meter':'GAS-SYN',
               'semantics':'cumulative','meter_column':'meter','start_column':'time','end_column':'','value_column':'counter','unit_column':'units','quality_column':''}
    identifier = ready(usage,raw,mapping)
    approve(usage,identifier)
    readings = usage.listing()['readings']
    assert {r['quantity'] for r in readings} == {'100.25','110.5'}
    assert all(r['semantics']=='cumulative' and r['start_utc']==r['end_utc'] and r['unit']=='CCF' and r['quality']=='unknown' for r in readings)
    with usage.store.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM bills').fetchone()[0] == 0
        assert db.execute('SELECT COUNT(*) FROM interval_readings').fetchone()[0] == 0
    second = usage.import_file('counter-reset.csv',raw.replace(b'110.50',b'1.50'))['import_id']
    with pytest.raises(ValueError,match='USAGE_CUMULATIVE_RESET'):
        usage.preview(second,{'revision':0,'mapping':mapping})


def test_rejection_requires_reason_and_leaves_source_and_preview(usage):
    identifier = ready(usage)
    with pytest.raises(ValueError,match='USAGE_RECONCILIATION_REASON'):
        usage.close(identifier,{'revision':1,'acknowledge':True,'reason':''})
    usage.close(identifier,{'revision':1,'acknowledge':True,'reason':'Synthetic export had unsupported meter meaning'})
    assert usage.detail(identifier)['state'] == 'rejected'
    assert usage.detail(identifier)['preview']['reading_count'] == 3
    assert usage.listing()['active_reading_count'] == 0
    assert check(usage.store)['sources'] == 'ok'


def test_backup_restore_includes_pending_approved_withdrawn_sources_and_history(usage,tmp_path):
    first = ready(usage)
    approve(usage,first)
    withdraw(usage,first)
    second = ready(usage,RAW.replace(b'12.50',b'15.50'))
    approve(usage,second)
    pending = ready(usage,RAW.replace(b'12.50',b'20.50'))
    saved = backup(usage.store)
    recovered = Store(tmp_path/'recovered','demo')
    with instance_lock(recovered.directory):
        restore(recovered,saved,'demo')
    from utilityos.service import Ledger
    restored = UsageImport(Ledger(recovered))
    assert restored.listing()['active_reading_count'] == 3
    assert restored.detail(first)['state'] == 'withdrawn'
    assert restored.detail(pending)['state'] == 'pending'
    assert len(list(recovered.sources.glob('*.csv'))) == 3
    assert check(recovered)['sources'] == 'ok'


def test_immutable_history_and_tampering_detection(usage):
    identifier = ready(usage)
    approve(usage,identifier)
    with usage.store.connect() as db:
        with pytest.raises(sqlite3.IntegrityError,match='USAGE_HISTORY_IMMUTABLE'):
            db.execute('DELETE FROM usage_evidence')
    with usage.store.connect() as db:
        db.execute('DROP TRIGGER usage_evidence_no_delete')
    with pytest.raises(ValueError,match='USAGE_HISTORY_DAMAGED'):
        check(usage.store)


def test_source_storage_failure_rolls_back_document_and_retry_uses_atomic_original(usage,monkeypatch):
    import utilityos.usage as module
    real = module.publish_source
    def failed(target,raw):
        real(target,raw)
        raise OSError('SYNTHETIC_INTERRUPTION_AFTER_SOURCE_PUBLICATION')
    monkeypatch.setattr(module,'publish_source',failed)
    with pytest.raises(OSError):
        usage.import_file('synthetic.csv',RAW)
    assert usage.listing()['items'] == []
    monkeypatch.setattr(module,'publish_source',real)
    assert ready(usage) == 1
    assert check(usage.store)['sources'] == 'ok'


def test_usage_api_boundaries_download_and_strict_approval(authenticated):
    client = authenticated
    with client.app.state.store.connect() as db:
        db.execute("INSERT INTO meters(code,commodity,unit) VALUES ('SYN-W','water','gal')")
    headers = {'content-type':'application/octet-stream','x-filename':'fictional.csv','x-synthetic-data':'true'}
    assert client.post('/api/usage/import',content=RAW,headers={**headers,'x-synthetic-data':'false'}).status_code == 422
    assert client.post('/api/usage/import',content=RAW,headers={**headers,'x-csrf-token':'wrong'}).status_code == 403
    response = client.post('/api/usage/import',content=RAW,headers=headers)
    assert response.status_code == 200,response.text
    identifier = response.json()['import_id']
    assert client.post(f'/api/usage/{identifier}/preview',json={'revision':0,'mapping':MAPPING}).status_code == 200
    for value in (None,False,True,'1',-1):
        assert client.post(f'/api/usage/{identifier}/approve',json={'revision':value,'acknowledge':True}).status_code == 422
    for value in (None,False,1,'true'):
        assert client.post(f'/api/usage/{identifier}/approve',json={'revision':1,'acknowledge':value}).status_code == 422
    assert client.get('/api/usage').json()['active_reading_count'] == 0
    assert client.post(f'/api/usage/{identifier}/approve',json={'revision':1,'acknowledge':True}).status_code == 200
    info = client.get(f'/api/usage/{identifier}').json()
    original = client.get(f'/api/sources/{info["document_id"]}')
    assert original.content == RAW
    assert 'attachment' in original.headers['content-disposition']
    assert client.get('/api/overview').json()['total_cents'] == 0
    client.post('/api/logout',json={})
    assert client.get('/api/usage').status_code == 401
    assert client.get(f'/api/sources/{info["document_id"]}').status_code == 401


def test_source_meter_cannot_silently_move_to_different_local_meter(usage):
    with usage.store.connect() as db:
        db.execute("INSERT INTO meters(code,commodity,unit) VALUES ('SYN-OTHER-W','water','gal')")
    first = ready(usage)
    approve(usage,first)
    moved = ready(usage, RAW.replace(b'12.50',b'12.500'),{**MAPPING,'meter_code':'SYN-OTHER-W'})
    assert usage.detail(moved)['conflicts'] == [{'import_id':first,'code':'USAGE_SOURCE_METER_ALREADY_MAPPED_ELSEWHERE'}]
    with pytest.raises(ValueError,match='USAGE_CONFLICT_RECONCILE'):
        approve(usage,moved)
    withdraw(usage,first)
    approve(usage,moved)
    assert {r['code'] for r in usage.listing()['readings']} == {'SYN-OTHER-W'}


@pytest.mark.parametrize('table',['usage_previews','usage_decisions','usage_withdrawals'])
def test_deleted_history_even_with_restored_trigger_is_detected(usage,table):
    identifier = ready(usage)
    if table != 'usage_previews':
        approve(usage,identifier)
    if table == 'usage_withdrawals':
        withdraw(usage,identifier)
    with usage.store.connect() as db:
        trigger = db.execute("SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?", (table+'_no_delete',)).fetchone()[0]
        db.execute('DROP TRIGGER '+table+'_no_delete')
        db.execute('DELETE FROM '+table)
        db.execute(trigger)
    with pytest.raises(ValueError,match='USAGE_HISTORY_DAMAGED'):
        check(usage.store)


def test_xml_and_generic_electricity_overlap_rejected_in_both_orders(usage,ledger,raw_xml):
    from utilityos.parsers import parse_greenbutton
    from datetime import datetime, timezone
    reading = parse_greenbutton(raw_xml)[0]['readings'][0]
    start = datetime.fromtimestamp(reading['start_utc'],timezone.utc).isoformat()
    end = datetime.fromtimestamp(reading['start_utc']+reading['duration_s'],timezone.utc).isoformat()
    raw = f'meter,start,end,value,unit\nSYN-E-EXPORT,{start},{end},1,kWh\n'.encode()
    mapping = {**MAPPING,'meter_code':'SYN-E','commodity':'electricity','unit':'kWh','source_meter':'SYN-E-EXPORT',
               'meter_column':'meter','quality_column':''}
    generic = ready(usage,raw,mapping)
    approve(usage,generic)
    xml = ledger.import_file('synthetic.xml',raw_xml)['staged_ids'][0]
    with pytest.raises(ValueError,match='INTERVAL_OVERLAPS_MAPPED_USAGE'):
        ledger.approve_intervals(xml,'SYN-E')
    withdraw(usage,generic)
    ledger.approve_intervals(xml,'SYN-E')
    retry = ready(usage,raw.replace(b',1,',b',1.0,'),mapping)
    assert usage.detail(retry)['conflicts'] == [{'import_id':None,'code':'USAGE_OVERLAPS_EXISTING_XML_EVIDENCE'}]
    with pytest.raises(ValueError,match='USAGE_CONFLICT_RECONCILE'):
        approve(usage,retry)


def test_cumulative_discontinuity_across_separate_and_interleaving_exports(usage):
    mapping = {**MAPPING,'meter_code':'SYN-G','commodity':'natural_gas','unit':'CCF','source_meter':'GAS-SYN',
               'semantics':'cumulative','meter_column':'meter','start_column':'time','end_column':'','value_column':'counter','unit_column':'units','quality_column':''}
    def row(day,value):
        return f'meter,time,counter,units\nGAS-SYN,2026-08-{day:02d}T00:00Z,{value},CCF\n'.encode()
    first = ready(usage,row(1,100),mapping)
    approve(usage,first)
    final = ready(usage,row(3,120),mapping)
    approve(usage,final)
    for day,value in ((2,90),(2,130),(4,1)):
        identifier = ready(usage,row(day,value),mapping)
        assert any(c['code']=='USAGE_CUMULATIVE_RESET_REQUIRES_RECONCILIATION' for c in usage.detail(identifier)['conflicts'])
        with pytest.raises(ValueError,match='USAGE_CONFLICT_RECONCILE'):
            approve(usage,identifier)
    middle = ready(usage,row(2,110),mapping)
    approve(usage,middle)
    assert usage.listing()['active_reading_count'] == 3


@pytest.mark.parametrize('state',['withdrawn','rejected'])
def test_mapping_only_reattempt_preserves_identical_source_and_prior_decision(usage,state):
    identifier = ready(usage)
    if state == 'withdrawn':
        approve(usage,identifier)
        withdraw(usage,identifier)
    else:
        usage.close(identifier,{'revision':1,'acknowledge':True,'reason':'Synthetic wrong mapping'})
    new = usage.reattempt(identifier,{'revision':1,'acknowledge':True,'reason':'Synthetic source mapping corrected'})['import_id']
    assert usage.detail(new)['document_id'] == usage.detail(identifier)['document_id']
    assert usage.detail(new)['source_sha256'] == sha256(RAW).hexdigest()
    assert usage.detail(new)['source_history']['reattempt_of'] == identifier
    assert usage.detail(identifier)['state'] == state
    assert usage.import_file('same-original.csv',RAW)['import_id'] == new
    with pytest.raises(ValueError,match='USAGE_SOURCE_ALREADY_HAS_ACTIVE_REVIEW'):
        usage.reattempt(identifier,{'revision':1,'acknowledge':True,'reason':'Repeated click'})
    usage.preview(new,{'revision':0,'mapping':MAPPING})
    approve(usage,new)
    assert usage.listing()['active_reading_count'] == 3
    assert len(list(usage.store.sources.glob('*.csv'))) == 1
    assert check(usage.store)['audit'] == 'ok'


def test_row_cap_is_enforced_before_materializing_unbounded_rows(usage):
    raw = b'meter,value\n'+b'SYNTHETIC,1\n'*5000
    assert usage.import_file('limit.csv',raw)['import_id'] == 1
    with pytest.raises(ValueError,match='USAGE_REQUIRES_1_TO_5000_ROWS'):
        usage.import_file('over-limit.csv',raw+b'SYNTHETIC,1\n')


def test_same_water_meter_billing_period_and_partial_operational_evidence_are_not_added(usage,ledger,raw_csv):
    water = raw_csv.replace(b'Example Electric',b'Fictional Water').replace(b'DEMO-E05',b'SYN-W').replace(b'Demo Workshop',b'').replace(b'electricity',b'water').replace(b'kWh',b'gal')
    item = ledger.import_file('fictional-water-bill.csv',water)['staged_ids'][0]
    ledger.approve_bill(item,ledger.stage(item)['payload'],True)
    before = ledger.overview()
    identifier = ready(usage)
    approve(usage,identifier)
    assert ledger.overview() == before
    with usage.store.connect() as db:
        bill_line = db.execute('SELECT period_start,period_end,usage FROM bill_lines').fetchone()
        assert tuple(bill_line) == ('2026-08-01','2026-09-01','2860')
        assert {r[0] for r in db.execute('SELECT meter_id FROM bill_lines')} == {r[0] for r in db.execute('SELECT meter_id FROM usage_readings')}
    assert usage.listing()['active_reading_count'] == 3  # Three hourly rows do not establish coverage of the bill's month.
