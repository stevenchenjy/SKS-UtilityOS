from copy import deepcopy
from datetime import date
import json
import sqlite3
import pytest
from utilityos.completeness import Completeness
from utilityos.db import Store
from utilityos.operations import backup, restore, check, migrate
from utilityos.config import ROOT


def configured(ledger, raw_csv):
    item=ledger.import_file('fictional.csv',raw_csv)['staged_ids'][0]
    ledger.approve_bill(item,ledger.stage(item)['payload'],True)
    return {'scope':'account','account_id':ledger.inventory()['accounts'][0]['id'],'revision':0,
            'cadence':'every_two_months','anchor_month':1,'issue_day':15,'grace_days':7,
            'effective_from':'2026-01-01','effective_to':None,'enabled':True,'retrieval_cadence':'weekly',
            'exceptions':[],'reason':'Fictional odd-month statement schedule','acknowledge':True}


def test_odd_month_issue_grace_and_quiet_month(ledger,raw_csv):
    value=configured(ledger,raw_csv);coverage=Completeness(ledger.store);coverage.configure(value)
    for when,state in [(date(2026,11,1),'not_due'),(date(2026,11,22),'not_due'),(date(2026,11,23),'missing')]:
        report=coverage.report('2026-11',as_of=when)
        assert report['rows'][0]['state']==state
        assert report['rows'][0]['issue_date']=='2026-11-15'
        assert report['counts']['expected']==1
    quiet=coverage.report('2026-10',as_of=date(2026,12,1))
    assert quiet['counts']['expected']==quiet['counts']['missing']==0
    assert quiet['rows'][0]['state']=='not_scheduled'
    assert ledger.overview()['total_cents']==57980


def test_anchor_month_end_leap_year_effective_dates_and_exceptions(ledger,raw_csv):
    value=configured(ledger,raw_csv)
    value.update(anchor_month=2,issue_day=31,grace_days=0,effective_from='2024-02-01',effective_to='2024-12-31')
    value['exceptions']=[{'month':'2024-04','expected':False,'issue_date':None,'reason':'Fictional suspension'},
                         {'month':'2024-05','expected':True,'issue_date':'2024-05-10','reason':'Fictional special statement'}]
    coverage=Completeness(ledger.store);coverage.configure(value)
    assert coverage.report('2024-02',as_of=date(2024,3,1))['rows'][0]['issue_date']=='2024-02-29'
    assert coverage.report('2024-04')['counts']['expected']==0
    assert coverage.report('2024-05')['rows'][0]['issue_date']=='2024-05-10'
    assert coverage.report('2025-02')['counts']['expected']==0
    assert coverage.report('2023-12')['counts']['expected']==0


def test_account_statement_not_one_per_meter_and_legacy_retention(ledger,raw_csv,bill):
    value=configured(ledger,raw_csv)
    newer=deepcopy(bill);newer.update(invoice_number='SYN-MULTI-SERVICE',bill_date='2026-07-15',current_total='20')
    first=deepcopy(newer['lines'][0]);first.update(period_start='2026-05-01',period_end='2026-07-01',current_charge='10')
    second=deepcopy(first);second['meter_code']='SYN-SECOND-METER';newer['lines']=[first,second]
    item=ledger.import_file('synthetic-multi.csv',raw_csv.replace(b'SYN-NEW-WORKSHOP',b'SYN-MULTI-SERVICE'))['staged_ids'][0]
    ledger.approve_bill(item,newer,True)
    coverage=Completeness(ledger.store)
    for meter in ledger.inventory()['meters']:
        coverage.configure({'account_id':value['account_id'],'meter_id':meter['id'],'revision':0,'cadence':'monthly',
                            'first_month':'2026-01','last_month':None,'enabled':True,'reason':'Legacy fiction','acknowledge':True})
    assert coverage.report('2026-07')['counts']['expected']==1
    coverage.configure(value)
    result=coverage.report('2026-07')
    assert result['counts']['expected']==result['counts']['approved']==1
    assert len(result['configuration'])==2
    assert len(result['rows'])==1
    assert len(result['rows'][0]['meter_code'].split(', '))==2


@pytest.mark.parametrize('patch',[{'revision':None},{'revision':True},{'issue_day':0},{'grace_days':-1},
    {'anchor_month':13},{'acknowledge':'true'},{'effective_to':'2025-01-01'},
    {'exceptions':[{'month':'2026-10','expected':True,'issue_date':'2026-11-01','reason':'Wrong month'}]}])
def test_invalid_configuration_is_atomic(ledger,raw_csv,patch):
    value=configured(ledger,raw_csv);value.update(patch)
    with ledger.store.connect() as db:before=db.execute('SELECT COUNT(*) FROM audit_events').fetchone()[0]
    with pytest.raises(ValueError):Completeness(ledger.store).configure(value)
    with ledger.store.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM billing_schedule_versions').fetchone()[0]==0
        assert db.execute('SELECT COUNT(*) FROM audit_events').fetchone()[0]==before


def test_schedule_backup_history_privacy_and_stale_revision(ledger,raw_csv,tmp_path):
    value=configured(ledger,raw_csv);value['reason']='SYNTHETIC_PRIVATE_SCHEDULE_SENTINEL'
    coverage=Completeness(ledger.store);coverage.configure(value)
    with pytest.raises(ValueError,match='CHANGED'):coverage.configure(value)
    original=coverage.report('2026-11')
    target=Store(tmp_path/'restored','demo');restore(target,backup(ledger.store),'demo')
    assert Completeness(target).report('2026-11')==original
    assert check(target)['schema_version']==6
    assert value['reason'] not in json.dumps(ledger.diagnostics('demo'))
    with target.connect() as db:
        with pytest.raises(sqlite3.IntegrityError):db.execute('DELETE FROM billing_schedule_versions')


def test_explicit_v5_migration_retains_old_state(tmp_path):
    directory=tmp_path/'old';directory.mkdir();(directory/'sources').mkdir()
    with sqlite3.connect(directory/'utilityos.sqlite3') as db:db.executescript((ROOT/'tests/fixtures/schema_v5.sql').read_text())
    before=(directory/'utilityos.sqlite3').read_bytes()
    with pytest.raises(ValueError,match='SCHEMA_VERSION_UNSUPPORTED'):Store(directory,'demo')
    assert (directory/'utilityos.sqlite3').read_bytes()==before
    saved=migrate(directory,'demo')
    assert saved.exists() and check(Store(directory,'demo'))['schema_version']==6


@pytest.mark.parametrize('operation', ['report', 'backup', 'reopen'])
def test_removed_schedule_revision_cannot_reactivate_prior_decision(ledger, raw_csv, operation):
    value = configured(ledger, raw_csv)
    coverage = Completeness(ledger.store)
    coverage.configure(value)
    coverage.configure({**value, 'revision': 1, 'enabled': False, 'reason': 'Fictional confirmed suspension'})
    assert coverage.report('2026-11')['counts']['expected'] == 0
    # Simulate storage damage with the integrity guard itself restored. The
    # retained audit hash must still expose the removed decision.
    with ledger.store.connect() as db:
        db.execute('DROP TRIGGER billing_schedule_no_delete')
        db.execute('DELETE FROM billing_schedule_versions WHERE revision=2')
        db.execute("CREATE TRIGGER billing_schedule_no_delete BEFORE DELETE ON billing_schedule_versions BEGIN SELECT RAISE(ABORT,'SCHEDULE_HISTORY_IMMUTABLE'); END")
    actions = {'report': lambda: coverage.report('2026-11'),
               'backup': lambda: backup(ledger.store),
               'reopen': lambda: Store(ledger.store.directory, 'demo')}
    with pytest.raises(ValueError, match='BILLING_SCHEDULE_HISTORY_DAMAGED'):
        actions[operation]()
    assert not (ledger.store.directory / 'backups').exists()


@pytest.mark.parametrize('first_cadence', ['monthly', 'delivery'])
def test_conflicting_legacy_meter_cadences_do_not_establish_account_expectation(
        ledger, raw_csv, bill, first_cadence):
    value = configured(ledger, raw_csv)
    payload = deepcopy(bill)
    payload.update(invoice_number='SYN-SECOND-RELATIONSHIP', bill_date='2026-09-05')
    payload['lines'][0]['meter_code'] = 'ZZ-SYN-SECOND-METER'
    item = ledger.import_file('second-meter.csv', raw_csv + b'\n')['staged_ids'][0]
    ledger.approve_bill(item, payload, True)
    coverage = Completeness(ledger.store)
    meters = sorted(ledger.inventory()['meters'], key=lambda meter: meter['code'])
    for meter, cadence in zip(meters, [first_cadence, 'delivery' if first_cadence == 'monthly' else 'monthly']):
        coverage.configure({'account_id': value['account_id'], 'meter_id': meter['id'], 'revision': 0,
                            'cadence': cadence, 'first_month': '2026-01', 'last_month': None,
                            'enabled': True, 'reason': 'Fictional conflicting legacy expectation', 'acknowledge': True})
    report = coverage.report('2026-09')
    assert len(report['rows']) == 1
    assert report['counts']['expected'] == 0
    assert report['counts']['missing'] == 0
    assert report['rows'][0]['state'] == 'needs_confirmation'


def test_grace_period_crosses_year_boundary_without_changing_invoice_month(ledger, raw_csv):
    value = configured(ledger, raw_csv)
    value.update(cadence='monthly', issue_day=31, grace_days=7)
    coverage = Completeness(ledger.store)
    coverage.configure(value)
    not_due = coverage.report('2026-12', as_of=date(2027, 1, 7))
    assert not_due['month'] == '2026-12'
    assert not_due['rows'][0]['missing_after'] == '2027-01-07'
    assert not_due['rows'][0]['state'] == 'not_due'
    assert coverage.report('2026-12', as_of=date(2027, 1, 8))['rows'][0]['state'] == 'missing'


def test_effective_dates_apply_to_issue_day_and_delivery_can_have_explicit_exception(ledger, raw_csv):
    value = configured(ledger, raw_csv)
    value.update(cadence='delivery', effective_from='2026-11-16', effective_to='2026-12-20',
                 exceptions=[{'month': '2026-11', 'expected': True, 'issue_date': '2026-11-15', 'reason': 'Before service starts'},
                             {'month': '2026-12', 'expected': True, 'issue_date': '2026-12-20', 'reason': 'Confirmed final delivery'}])
    coverage = Completeness(ledger.store)
    coverage.configure(value)
    assert coverage.report('2026-11')['counts']['expected'] == 0
    final = coverage.report('2026-12', as_of=date(2026, 12, 28))
    assert final['counts']['expected'] == final['counts']['missing'] == 1
    assert final['rows'][0]['issue_date'] == '2026-12-20'
    assert coverage.report('2027-01')['counts']['expected'] == 0
