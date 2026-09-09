"""Synthetic cross-building accounting and report drill-down regressions."""
from copy import deepcopy
import pytest
from utilityos.parsers import ValidationError


def post(ledger, raw_csv, payload):
    staged = ledger.import_file('synthetic-building.csv', raw_csv + b'\n' * (len(ledger.stages()) + 1))['staged_ids'][0]
    return ledger.approve_bill(staged, payload, True)['id']


@pytest.fixture
def campus(ledger, bill, raw_csv):
    bill.update(invoice_number='SYN-SPLIT', current_total='170.00')
    first = bill['lines'][0]
    first.update(building='Synthetic Hall A', current_charge='100.00', usage='12.123456789')
    second = deepcopy(first)
    second.update(meter_code='SYN-B', building='Synthetic Hall B', current_charge='50.00', usage='5')
    shared = deepcopy(first)
    shared.update(meter_code='SYN-SHARED', building='', current_charge='20.00', usage='2')
    bill['lines'] = [first, second, shared]
    original = post(ledger, raw_csv, bill)
    supply = deepcopy(bill)
    supply.update(invoice_number='SYN-SUPPLY', provider='Synthetic Supplier', account_alias='Supply A', current_total='-10.00')
    supply['lines'] = [deepcopy(first)]
    supply['lines'][0].update(usage='0', usage_role='charges_only', current_charge='-10.00')
    post(ledger, raw_csv, supply)
    fuel = deepcopy(bill)
    fuel.update(invoice_number='SYN-FUEL', bill_date='2026-10-05', current_total='30.00')
    fuel['lines'] = [dict(first, meter_code='SYN-OIL', commodity='heating_oil', unit='gal', usage_role='delivery', usage='10.25', current_charge='30.00')]
    post(ledger, raw_csv, fuel)
    ids = {b['name']: str(b['id']) for b in ledger.inventory()['buildings']}
    return ids, original


def test_building_scope_reconciles_split_invoice_supply_credit_and_shared(ledger, campus):
    ids, _ = campus
    all_data = ledger.overview('2026-09')
    a = ledger.overview('2026-09', ids['Synthetic Hall A'])
    b = ledger.overview('2026-09', ids['Synthetic Hall B'])
    shared = ledger.overview('2026-09', 'unassigned')
    assert [a['total_cents'], b['total_cents'], shared['total_cents']] == [9000, 5000, 2000]
    assert all_data['total_cents'] == sum(d['total_cents'] for d in [a,b,shared]) == 16000
    assert a['invoice_count'] == 2  # Split invoice counted once, plus supply credit.
    assert a['scope_stats'] == {'meters':2, 'accounts':2, 'approved_bills':3}
    assert a['quantities'] == [{'commodity':'electricity','unit':'kWh','role':'consumption','value':'12.123456789'}]
    assert a['monthly'] == [{'month':'2026-09','cents':9000,'bills':2},{'month':'2026-10','cents':3000,'bills':1}]
    invoices = ledger.bills(ids['Synthetic Hall A'], '2026-09')
    assert sum(b['matched_total_cents'] for b in invoices if b['status']=='active') == a['total_cents']
    split = next(b for b in invoices if b['invoice_number']=='SYN-SPLIT')
    assert split['matched_total_cents'] == 10000 and split['current_total_cents'] == 17000
    assert len(ledger.bills('unassigned','2026-09')) == 1
    oil = next(p for p in a['service_points'] if p['code']=='SYN-OIL')
    assert oil['invoices'] == 0 and oil['quantities'] == []
    october = ledger.overview('2026-10', ids['Synthetic Hall A'])
    assert october['quantities'] == [{'commodity':'heating_oil','unit':'gal','role':'delivery','value':'10.25'}]


def test_empty_month_never_falls_back_and_retains_inventory(ledger, campus):
    ids, _ = campus
    for month in ['2026-10','2025-01']:
        data = ledger.overview(month, ids['Synthetic Hall B'])
        assert data['selected_month'] == month and month in data['months']
        assert data['total_cents'] == data['invoice_count'] == 0
        assert data['quantities'] == data['cost_by_building'] == data['cost_by_commodity'] == []
        assert data['scope_stats']['meters'] == 1
        assert ledger.bills(ids['Synthetic Hall B'],month) == []


def test_replacement_cancellation_and_current_mapping_apply_to_every_scope(ledger, campus):
    ids, original = campus
    a, b = ids['Synthetic Hall A'], ids['Synthetic Hall B']
    staged = ledger.create_correction(original, 'Synthetic correction')['staged_id']
    payload = ledger.stage(staged)['payload']
    payload['lines'][0]['current_charge'] = '80.00'
    payload['current_total'] = '150.00'
    replacement = ledger.approve_bill(staged, payload, True)['id']
    assert ledger.overview('2026-09',a)['total_cents'] == 7000
    assert len(ledger.bills(a,'2026-09')) == 3  # Full retained history, including superseded original.
    ledger.cancel_bill(replacement, 'Synthetic cancellation', True)
    assert ledger.overview('2026-09',a)['total_cents'] == -1000
    assert ledger.overview('2026-09',b)['invoice_count'] == 0
    meter = next(m for m in ledger.inventory()['meters'] if m['code']=='DEMO-E05')
    ledger.edit_inventory('meter', meter['id'], 'Synthetic Hall A', 'Synthetic Hall B', 'Synthetic mapping', True)
    assert ledger.overview('2026-09',a)['total_cents'] == 0
    assert ledger.overview('2026-09',b)['total_cents'] == -1000
    ledger.edit_inventory('building',int(b),'Synthetic Hall B','Synthetic renamed','Synthetic label',True)
    assert ledger.overview('2026-09',b)['scope']['name'] == 'Synthetic renamed'
    assert len(ledger.bills(b,'2026-09')) == 3


def test_building_label_cannot_merge_with_unassigned_bucket(ledger, bill, raw_csv):
    bill['lines'][0]['building'] = 'Unassigned / shared'
    post(ledger,raw_csv,bill)
    second=deepcopy(bill)
    second['invoice_number']='SYN-UNASSIGNED'
    second['lines'][0].update(meter_code='SYN-OTHER',building='')
    post(ledger,raw_csv,second)
    data=ledger.overview()
    assert len(data['cost_by_building']) == 2
    assert {r['building_id'] for r in data['cost_by_building']} == {'1','unassigned'}
    assert ledger.overview(building='unassigned')['invoice_count'] == 1


@pytest.mark.parametrize('building',['0','-1','missing','99999',"1 OR 1=1",''])
def test_invalid_scope_never_returns_campus_totals(ledger,building):
    for fn in [lambda:ledger.overview(building=building),lambda:ledger.bills(building=building)]:
        with pytest.raises(ValidationError,match='BUILDING_FILTER_INVALID'):fn()


@pytest.mark.parametrize('month',['2026-13','2026-1','0000-01','2026-09-01',"2026-09'",''])
def test_invalid_month_rejected(ledger,month):
    with pytest.raises(ValidationError,match='INVOICE_MONTH_INVALID'):ledger.overview(month)
    with pytest.raises(ValidationError,match='INVOICE_MONTH_INVALID'):ledger.bills(month=month)


def test_empty_ledger_and_authenticated_http_filters(authenticated):
    data=authenticated.get('/api/overview?building=unassigned&month=2026-09').json()
    assert data['total_cents'] == 0 and data['selected_month'] == '2026-09'
    assert data['scope']['id'] == 'unassigned' and data['invoice_count'] == 0
    for route in ['overview','bills']:
        assert authenticated.get(f'/api/{route}?building=999999').status_code == 422
        assert authenticated.get(f'/api/{route}?month=2026-13').status_code == 422
        assert authenticated.get(f'/api/{route}?building=all&month=2026-09').status_code == 200
    authenticated.post('/api/logout',json={})
    assert authenticated.get('/api/overview?building=unassigned').status_code == 401


def test_http_dashboard_and_invoice_drill_down_share_scope(authenticated, bill, raw_csv):
    ledger=authenticated.app.state.ledger
    bill['lines'][0]['building']='Synthetic HTTP Hall'
    post(ledger,raw_csv,bill)
    building=str(ledger.inventory()['buildings'][0]['id'])
    data=authenticated.get('/api/overview',params={'building':building,'month':'2026-09'}).json()
    invoices=authenticated.get('/api/bills',params={'building':building,'month':'2026-09'}).json()
    assert data['scope']['id']==building
    assert data['total_cents']==sum(b['matched_total_cents'] for b in invoices)==57980
    assert authenticated.get('/api/bills?building=unassigned&month=2026-09').json()==[]
