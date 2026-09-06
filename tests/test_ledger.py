from copy import deepcopy
from decimal import Decimal
import json
import pytest
from utilityos.parsers import ValidationError
from utilityos.operations import backup,restore,instance_lock
from utilityos.config import Config,ROOT
from utilityos.db import Store


def staged_bill(ledger,raw):
    identifier=ledger.import_file('demo.csv',raw)['staged_ids'][0]
    return identifier,ledger.stage(identifier)['payload']

def test_pending_excluded_and_approval_updates_totals(ledger,raw_csv):
    identifier,bill=staged_bill(ledger,raw_csv)
    assert ledger.overview()['total_cents']==0
    ledger.approve_bill(identifier,bill,True)
    assert ledger.overview()['total_cents']==57980
    assert ledger.overview()['stats']['meters']==1
    assert ledger.overview()['stats']['approved_bills']==1

def test_exact_document_duplicate_is_rejected(ledger,raw_csv):
    ledger.import_file('a.csv',raw_csv)
    with pytest.raises(ValidationError,match='DUPLICATE_SOURCE_DOCUMENT'):ledger.import_file('b.csv',raw_csv)

def test_invoice_duplicate_different_source_is_rejected(ledger,raw_csv):
    identifier,bill=staged_bill(ledger,raw_csv);ledger.approve_bill(identifier,bill,True)
    other=ledger.import_file('changed.csv',raw_csv+b'\n')['staged_ids'][0]
    with pytest.raises(ValidationError,match='DUPLICATE_INVOICE'):ledger.approve_bill(other,bill,True)

def test_approved_period_overlap_is_rejected(ledger,raw_csv):
    identifier,bill=staged_bill(ledger,raw_csv);ledger.approve_bill(identifier,bill,True)
    other=ledger.import_file('other.csv',raw_csv.replace(b'SYN-NEW-WORKSHOP',b'SYN-OTHER'))['staged_ids'][0]
    with pytest.raises(ValidationError,match='APPROVED_CONSUMPTION_PERIOD_OVERLAP'):
        ledger.approve_bill(other,ledger.stage(other)['payload'],True)

def test_split_supplier_charge_does_not_duplicate_usage(ledger,raw_csv):
    identifier,bill=staged_bill(ledger,raw_csv);ledger.approve_bill(identifier,bill,True)
    other=ledger.import_file('supply.csv',raw_csv+b'\n')['staged_ids'][0]
    bill.update(provider='Example Supply',account_alias='Supply label',invoice_number='SYN-SUPPLY',current_total='30.00')
    bill['lines'][0].update(usage='0',usage_role='charges_only',current_charge='30.00')
    ledger.approve_bill(other,bill,True)
    overview=ledger.overview()
    assert overview['total_cents']==60980
    assert overview['quantities'][0]['value']=='2860'
    assert overview['stats']['meters']==1
    assert overview['stats']['accounts']==2

def test_rejected_source_is_preserved(ledger,raw_csv):
    identifier,_=staged_bill(ledger,raw_csv);ledger.reject(identifier)
    assert ledger.stage(identifier)['status']=='rejected'
    assert len(list(ledger.store.sources.iterdir()))==1
    assert ledger.overview()['total_cents']==0

def test_original_payload_preserved_when_review_corrects_fields(ledger,raw_csv):
    identifier,bill=staged_bill(ledger,raw_csv)
    bill['provider']='Corrected provider'
    ledger.approve_bill(identifier,bill,True)
    with ledger.store.connect() as db:
        row=db.execute('SELECT payload,review_payload FROM staged WHERE id=?',(identifier,)).fetchone()
    assert json.loads(row['payload'])['provider']=='Example Electric'
    assert json.loads(row['review_payload'])['provider']=='Corrected provider'

def test_intervals_have_no_effect_on_bill_totals(ledger,raw_csv,raw_xml):
    identifier,bill=staged_bill(ledger,raw_csv);ledger.approve_bill(identifier,bill,True)
    item=ledger.import_file('intervals.xml',raw_xml)['staged_ids'][0]
    result=ledger.approve_intervals(item,'DEMO-E05')
    assert result['inserted']==96
    assert ledger.overview()['total_cents']==57980
    assert ledger.overview()['quantities'][0]['value']=='2860'

def test_identical_intervals_are_idempotent(ledger,raw_csv,raw_xml):
    identifier,bill=staged_bill(ledger,raw_csv);ledger.approve_bill(identifier,bill,True)
    first=ledger.import_file('a.xml',raw_xml)['staged_ids'][0];ledger.approve_intervals(first,'DEMO-E05')
    second=ledger.import_file('b.xml',raw_xml+b'\n')['staged_ids'][0]
    result=ledger.approve_intervals(second,'DEMO-E05')
    assert result=={'inserted':0,'identical_readings_skipped':96}

def test_interval_revision_conflict_leaves_no_partial_changes(ledger,raw_csv,raw_xml):
    identifier,bill=staged_bill(ledger,raw_csv);ledger.approve_bill(identifier,bill,True)
    first=ledger.import_file('a.xml',raw_xml)['staged_ids'][0];ledger.approve_intervals(first,'DEMO-E05')
    second=ledger.import_file('b.xml',raw_xml.replace(b'<value>6500',b'<value>6600',1))['staged_ids'][0]
    with pytest.raises(ValidationError,match='INTERVAL_REVISION_CONFLICT'):ledger.approve_intervals(second,'DEMO-E05')
    assert ledger.stage(second)['status']=='pending'
    assert ledger.intervals()['total_readings']==96

def test_ambiguous_second_interval_stream_is_rejected(ledger,raw_csv,raw_xml):
    identifier,bill=staged_bill(ledger,raw_csv);ledger.approve_bill(identifier,bill,True)
    first=ledger.import_file('a.xml',raw_xml)['staged_ids'][0];ledger.approve_intervals(first,'DEMO-E05')
    second=ledger.import_file('b.xml',raw_xml.replace(b'/MeterReading/1',b'/MeterReading/2'))['staged_ids'][0]
    with pytest.raises(ValidationError,match='ANOTHER_INTERVAL_STREAM'):ledger.approve_intervals(second,'DEMO-E05')

def test_diagnostics_allowlist_has_no_school_data(ledger,raw_csv):
    identifier,bill=staged_bill(ledger,raw_csv)
    bill.update(provider='CONFIDENTIAL_PROVIDER',account_alias='PRIVATE_ACCOUNT_7654')
    ledger.approve_bill(identifier,bill,True)
    export=json.dumps(ledger.diagnostics('staff'))
    for secret in ['CONFIDENTIAL_PROVIDER','PRIVATE_ACCOUNT_7654','579.8','demo.csv',str(ledger.store.directory),'password']:
        assert secret not in export
    assert set(ledger.diagnostics('staff'))=={'app','version','schema_version','mode','runtime','features','checks','support_instructions'}

def test_csv_export_protects_formula_text(ledger,raw_csv):
    identifier,bill=staged_bill(ledger,raw_csv);bill['provider']='=1+1'
    ledger.approve_bill(identifier,bill,True)
    output=ledger.export_csv().decode('utf-8-sig')
    assert "'=1+1" in output

def test_backup_restore_preserves_database_and_source(ledger,raw_csv,tmp_path):
    identifier,bill=staged_bill(ledger,raw_csv);ledger.approve_bill(identifier,bill,True)
    saved=backup(ledger.store)
    other=ledger.import_file('second.csv',raw_csv.replace(b'SYN-NEW-WORKSHOP',b'SYN-SECOND'))['staged_ids'][0]
    assert len(ledger.stages())==2
    with instance_lock(ledger.store.directory):restore(ledger.store,saved,'demo')
    assert len(ledger.stages())==1
    assert ledger.overview()['total_cents']==57980

def test_staff_mode_cannot_open_demo_directory(store):
    with pytest.raises(ValueError,match='MODE_DATA_MISMATCH'):Store(store.directory,'staff')

def test_staff_data_in_source_tree_is_rejected():
    with pytest.raises(ValueError,match='OUTSIDE_SOURCE'):Config(ROOT/'data','staff').validate()

def test_staff_synced_folder_is_rejected(tmp_path):
    with pytest.raises(ValueError,match='LOCAL_UNSYNCED'):Config(tmp_path/'Desktop'/'data','staff').validate()

def test_unknown_schema_fails_closed(store):
    with store.connect() as db:db.execute("UPDATE settings SET value='999' WHERE key='schema_version'")
    with pytest.raises(ValueError,match='SCHEMA_VERSION_UNSUPPORTED'):Store(store.directory,'demo')

def test_pdf_is_attachment_and_manual_entry(ledger):
    raw=(ROOT/'samples/demo-invoice.pdf').read_bytes()
    item=ledger.import_file('invoice.pdf',raw)['staged_ids'][0]
    payload=ledger.stage(item)['payload']
    assert payload['provider']==''
    assert ledger.overview()['total_cents']==0
    assert next(ledger.store.sources.iterdir()).read_bytes()==raw

def test_credit_only_invoice_reduces_cost_without_negative_consumption(ledger,raw_csv):
    identifier,bill=staged_bill(ledger,raw_csv);ledger.approve_bill(identifier,bill,True)
    other=ledger.import_file('credit.csv',raw_csv+b'\n')['staged_ids'][0]
    bill.update(invoice_number='SYN-CREDIT',current_total='-50.00')
    bill['lines'][0].update(usage='0',usage_role='charges_only',current_charge='-50.00')
    ledger.approve_bill(other,bill,True)
    assert ledger.overview()['total_cents']==52980
    assert ledger.overview()['quantities'][0]['value']=='2860'


def test_review_list_uses_staff_reviewed_fields(ledger,raw_csv):
    item,payload=staged_bill(ledger,raw_csv)
    payload.update(invoice_number='SYN-REVIEWED',provider='Reviewed label',current_total='1.23')
    payload['lines'][0]['current_charge']='1.23'
    ledger.approve_bill(item,payload,True)
    row=ledger.stages()[0]
    assert row['label']=='SYN-REVIEWED'
    assert row['provider']=='Reviewed label'
    assert row['current_total']=='1.23'


def test_closed_interval_summary_keeps_original_readings(ledger,raw_csv,raw_xml):
    item,payload=staged_bill(ledger,raw_csv)
    ledger.approve_bill(item,payload,True)
    interval=ledger.import_file('interval.xml',raw_xml)['staged_ids'][0]
    ledger.approve_intervals(interval,'DEMO-E05')
    assert ledger.stages()[0]['interval_count']==96


def test_interval_stream_cannot_be_counted_under_second_meter(ledger,raw_csv,raw_xml):
    item,payload=staged_bill(ledger,raw_csv)
    ledger.approve_bill(item,payload,True)
    payload['invoice_number']='SYN-SECOND-METER'
    payload['lines'][0]['meter_code']='SYN-SECOND'
    other=ledger.import_file('second.csv',raw_csv+b'\n')['staged_ids'][0]
    ledger.approve_bill(other,payload,True)
    first=ledger.import_file('first.xml',raw_xml)['staged_ids'][0]
    ledger.approve_intervals(first,'DEMO-E05')
    second=ledger.import_file('second.xml',raw_xml+b'\n')['staged_ids'][0]
    with pytest.raises(ValidationError,match='STREAM_ALREADY_MAPPED_TO_ANOTHER_METER'):
        ledger.approve_intervals(second,'SYN-SECOND')
    assert ledger.stage(second)['status']=='pending'
    assert len(ledger.intervals()['channels'])==1


def test_small_quantity_survives_review_and_report_round_trip(ledger,raw_csv):
    item,payload=staged_bill(ledger,raw_csv.replace(b'2860,kWh',b'0.000000001,kWh'))
    assert payload['lines'][0]['usage']=='0.000000001'
    saved=ledger.save_draft(item,payload,0)
    ledger.approve_bill(item,saved['payload'],True,revision=1)
    assert ledger.overview()['quantities'][0]['value']=='0.000000001'
    assert '0.000000001' in ledger.export_csv().decode('utf-8-sig')
