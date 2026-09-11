"""Public-field-informed fictional PDFs exercise existing private layout rules.

Successful cases establish local contracts only, never real-provider support.
Municipal non-water charges remain a deliberately unpostable retained source.
"""
from copy import deepcopy
from datetime import date
from hashlib import sha256
import json

import pytest

from utilityos.config import ROOT
from utilityos.parsers import ValidationError, validate_bill
from provider_helpers import post

CORPUS = ROOT / 'samples/provider-semantics'
CASES = {case['name']: case for case in json.loads((CORPUS / 'expected.json').read_text())['documents']}


def upload(client, name):
    case = CASES[name]
    response = client.post('/api/import', content=(CORPUS / case['file']).read_bytes(), headers={
        'content-type': 'application/octet-stream', 'x-filename': case['file'], 'x-synthetic-data': 'true'})
    assert response.status_code == 200, response.text
    return client.get(f'/api/staged/{response.json()["staged_ids"][0]}').json()


def details(name):
    case = CASES[name]
    result = {'document_kind': 'invoice', 'currency': 'USD',
              'previous_balance': case['prior_balance'], 'amount_due': case['amount_due']}
    if case['demand'] is not None:
        result.update({'services.0.demand_quantity': case['demand'], 'services.0.demand_unit': 'kW'})
    if name == 'electricity-supply':
        result['supplier_only'] = 'yes'
    return result


def approve(client, item, name, payload=None, expected=200):
    return post(client, f'/api/staged/{item["id"]}/approve', {
        'payload': payload if payload is not None else CASES[name]['bill'],
        'revision': item['revision'], 'acknowledge': True, 'intake_details': details(name)}, expected=expected)


def definition(name):
    case = CASES[name]
    mapping = {
        'invoice_number': 'Statement reference', 'account_identifier': 'Account reference',
        'invoice_date': 'Issued', 'invoice_total': 'Current statement charges',
        'previous_balance': 'Prior account balance', 'amount_due': 'Account amount due',
        'services.*.meter_identifier': 'Meter reference', 'services.*.period_start': 'Service start',
        'services.*.period_end': 'Service end exclusive', 'services.*.consumption_unit': 'Usage unit',
        'services.*.current_charge': 'Meter current charge'}
    if name != 'electricity-supply':
        mapping['services.*.consumption_quantity'] = 'Printed usage quantity'
    if case['demand'] is not None:
        mapping.update({'services.*.demand_quantity': 'Peak demand quantity', 'services.*.demand_unit': 'Peak demand unit'})
    rules = [{'field': field, 'label': label, 'mode': 'inline', 'required': True,
              'expected_unit': 'kW' if field.endswith('demand_unit') else
                               ('therm' if name == 'gas-ambiguous' else case['printed_unit']) if field.endswith('consumption_unit') else None}
             for field, label in mapping.items()]
    return {'format': 1, 'provider_anchor': {'literal': case['bill']['provider'], 'page': 1, 'region': [0, 0, 612, 50]},
            'layout_anchor': {'literal': 'Original synthetic semantics layout 1', 'page': 1, 'region': [0, 65, 612, 95]},
            'section_prefix': 'Meter service ', 'document_kind': 'invoice',
            'quantity_treatment': case['bill']['lines'][0]['usage_role'], 'end_date_inclusive': False, 'rules': rules}


def setup(client, name):
    case = CASES[name]
    provider = post(client, '/api/providers', {'label': case['bill']['provider'], 'commodity': case['bill']['lines'][0]['commodity']})
    layout = post(client, f'/api/providers/{provider["id"]}/layouts', {'definition': definition(name), 'expected_version': 0})
    return provider, layout


def preview(client, layout, item):
    return post(client, f'/api/provider-layouts/{layout["id"]}/preview', {'document_id': item['document_id']})


def test_current_charges_balance_and_amount_due_remain_distinct_after_activation(authenticated):
    c = authenticated
    first, second = upload(c, 'water-first'), upload(c, 'water-second')
    approve(c, first, 'water-first')
    approve(c, second, 'water-second')
    provider, layout = setup(c, 'water-first')
    checked = post(c, f'/api/provider-layouts/{layout["id"]}/validate', {'document_ids': [first['document_id'], second['document_id']]})
    assert checked['summary']['eligible']
    post(c, f'/api/provider-layouts/{layout["id"]}/activate', {
        'state_id': layout['state_id'], 'validation_id': checked['id'], 'acknowledge': True})
    future = upload(c, 'water-future')
    evidence = future['intake']['extraction']
    assert evidence['template_version'] == layout['id']
    assert future['payload'] == CASES['water-future']['bill']
    fields = evidence['fields']
    assert [fields[k]['value'] for k in ('invoice_total', 'previous_balance', 'amount_due')] == ['58.40', '210.15', '268.55']
    assert all(fields[k]['raw'] is not None and fields[k]['bbox'] for k in ('invoice_total', 'previous_balance', 'amount_due'))
    wrong = deepcopy(future['payload'])
    wrong['current_total'] = '268.55'
    rejected = approve(c, future, 'water-future', wrong, expected=422)
    assert rejected['error'] == 'CURRENT_TOTAL_DOES_NOT_MATCH_LINE_CHARGES'
    assert c.get(f'/api/staged/{future["id"]}').json()['revision'] == future['revision']
    approve(c, future, 'water-future', future['payload'])
    month = c.get('/api/overview?month=2026-11').json()
    assert month['total_cents'] == 5840
    assert month['quantities'] == [{'commodity': 'water', 'unit': 'gal', 'role': 'consumption', 'value': '4250'}]
    saved = c.get(f'/api/staged/{future["id"]}').json()
    assert saved['intake']['reviewed_values']['previous_balance'] == '210.15'
    assert saved['intake']['reviewed_values']['amount_due'] == '268.55'
    assert c.get(f'/api/sources/{future["document_id"]}').content == (CORPUS / 'water-future.pdf').read_bytes()


def test_amount_due_rule_cannot_pass_against_independently_reviewed_current_charges(authenticated):
    c = authenticated
    first, second = upload(c, 'water-first'), upload(c, 'water-second')
    approve(c, first, 'water-first')
    approve(c, second, 'water-second')
    provider = post(c, '/api/providers', {'label': CASES['water-first']['bill']['provider'], 'commodity': 'water'})
    wrong = definition('water-first')
    next(rule for rule in wrong['rules'] if rule['field'] == 'invoice_total')['label'] = 'Account amount due'
    layout = post(c, f'/api/providers/{provider["id"]}/layouts', {'definition': wrong, 'expected_version': 0})
    result = post(c, f'/api/provider-layouts/{layout["id"]}/validate', {'document_ids': [first['document_id'], second['document_id']]})
    assert not result['summary']['eligible']
    assert result['summary']['fields']['invoice_total']['exact'] == 0
    post(c, f'/api/provider-layouts/{layout["id"]}/activate', {
        'state_id': layout['state_id'], 'validation_id': result['id'], 'acknowledge': True}, expected=422)


def test_combined_municipal_statement_is_retained_unposted_without_dropping_other_services(authenticated):
    c = authenticated
    item = upload(c, 'municipal-combined')
    _, layout = setup(c, 'municipal-combined')
    candidate = preview(c, layout, item)
    assert candidate['payload']['current_total'] == '219.35'
    assert candidate['payload']['lines'][0]['current_charge'] == '58.40'
    rejected = approve(c, item, 'municipal-combined', candidate['payload'], expected=422)
    assert rejected['error'] == 'CURRENT_TOTAL_DOES_NOT_MATCH_LINE_CHARGES'
    complete = deepcopy(candidate['payload'])
    for commodity, charge in CASES['municipal-combined']['extra_charges'].items():
        complete['lines'].append(dict(complete['lines'][0], commodity=commodity, meter_code='SYN-' + commodity,
                                      current_charge=charge, usage='0', usage_role='charges_only'))
    rejected = approve(c, item, 'municipal-combined', complete, expected=422)
    assert rejected['error'] == 'UNSUPPORTED_COMMODITY_UNIT'
    retained = c.get(f'/api/staged/{item["id"]}').json()
    assert retained['status'] == 'pending' and retained['revision'] == item['revision']
    assert c.get('/api/overview').json()['stats']['approved_bills'] == 0
    assert c.get(f'/api/sources/{item["document_id"]}').content == (CORPUS / 'municipal-combined.pdf').read_bytes()


def test_supply_only_and_demand_preserve_one_shared_energy_meter_without_extra_consumption(authenticated):
    c = authenticated
    for name in ('electricity-demand', 'electricity-supply'):
        item = upload(c, name)
        _, layout = setup(c, name)
        candidate = preview(c, layout, item)
        assert candidate['payload'] == CASES[name]['bill']
        fields = candidate['extraction']['fields']
        if name == 'electricity-demand':
            assert fields['services.0.demand_quantity']['value'] == '18.75'
            assert fields['services.0.demand_unit']['value'] == 'kW'
            assert candidate['payload']['lines'][0]['usage'] == '876.5'
            wrong = deepcopy(candidate['payload'])
            wrong['lines'][0]['unit'] = 'kW'
            assert approve(c, item, name, wrong, expected=422)['error'] == 'UNSUPPORTED_COMMODITY_UNIT'
        else:
            assert candidate['payload']['lines'][0]['usage'] == '0'
            wrong = deepcopy(candidate['payload'])
            wrong['lines'][0]['usage'] = '876.5'
            assert approve(c, item, name, wrong, expected=422)['error'] == 'CHARGES_ONLY_USAGE_MUST_BE_ZERO'
        approve(c, item, name, candidate['payload'])
    data = c.get('/api/overview?month=2026-09&building=unassigned').json()
    assert data['total_cents'] == 23805 and data['invoice_count'] == 2
    assert data['quantities'] == [{'commodity': 'electricity', 'unit': 'kWh', 'role': 'consumption', 'value': '876.5'}]
    inventory = c.get('/api/inventory').json()
    assert len(inventory['meters']) == 1 and len(inventory['accounts']) == 2
    assert inventory['buildings'] == []
    assert data['service_points'][0]['building_id'] is None


def test_ambiguous_gas_units_are_not_silently_treated_as_energy_or_volume(authenticated):
    c = authenticated
    item = upload(c, 'gas-ambiguous')
    _, layout = setup(c, 'gas-ambiguous')
    candidate = preview(c, layout, item)
    evidence = candidate['extraction']['fields']['services.0.consumption_unit']
    assert evidence['raw'] == 'units' and evidence['value'] is None
    assert evidence['state'] == 'conflict'
    assert 'LOCAL_REQUIRED_FIELD_FAILED' in candidate['extraction']['codes']
    assert approve(c, item, 'gas-ambiguous', expected=422)['error'] == 'UNSUPPORTED_COMMODITY_UNIT'
    assert c.get(f'/api/staged/{item["id"]}').json()['status'] == 'pending'
    assert c.get('/api/overview').json()['stats']['approved_bills'] == 0


@pytest.mark.parametrize('unit', ['CCF', 'Mcf', 'therm', 'MMBtu'])
def test_explicit_gas_units_remain_distinct_without_implicit_conversion(unit):
    payload = deepcopy(CASES['gas-ambiguous']['bill'])
    payload['lines'][0]['unit'] = unit
    validated = validate_bill(payload)
    assert validated['lines'][0]['unit'] == unit
    assert validated['lines'][0]['usage'] == '120'
    # These are independent validation cases, not inferred corrections to a bill.
    with pytest.raises(ValidationError, match='UNSUPPORTED_COMMODITY_UNIT'):
        validate_bill(CASES['gas-ambiguous']['bill'])


def test_synthetic_periods_preserve_actual_boundaries_and_invoice_month():
    days = []
    for name in ('water-first', 'water-second', 'water-future'):
        bill = validate_bill(CASES[name]['bill'])
        line = bill['lines'][0]
        days.append((date.fromisoformat(line['period_end']) - date.fromisoformat(line['period_start'])).days)
        assert line['period_end'] != bill['bill_date']
    assert days == [62, 60, 62]


def test_original_corpus_is_visibly_synthetic_and_reproducible():
    import io
    import pdfplumber
    from scripts.synthetic_provider_semantics import cases, pdf_bytes
    for case in cases():
        raw = (CORPUS / (case['name'] + '.pdf')).read_bytes()
        assert sha256(raw).hexdigest() == CASES[case['name']]['sha256']
        assert raw == pdf_bytes(case)
        with pdfplumber.open(io.BytesIO(raw)) as document:
            assert len(document.pages) == 1
            text = document.pages[0].extract_text()
            assert 'FICTIONAL SOFTWARE TEST - NO PAYMENT REQUESTED' in text
            assert 'No school records or real provider artwork.' in text


def test_original_provider_corpus_is_included_in_source_only_package(tmp_path):
    import subprocess
    import zipfile
    from scripts.release import build, source_allowed
    archive = tmp_path / 'synthetic-source.zip'
    build(ROOT, archive, source_date_epoch=1788739200)
    # Source distributions intentionally contain no Git metadata. Exercise only
    # the shipped ignore rules in an isolated repository, independent of the
    # developer's index and global exclusion settings.
    ignore_repo = tmp_path / 'ignore-rules'
    ignore_repo.mkdir()
    subprocess.run(['git', 'init', '--quiet', str(ignore_repo)], check=True, capture_output=True)
    (ignore_repo / '.gitignore').write_bytes((ROOT / '.gitignore').read_bytes())
    global_excludes = tmp_path / 'empty-global-excludes'
    global_excludes.write_text('')
    with zipfile.ZipFile(archive) as package:
        for case in CASES.values():
            path = CORPUS / case['file']
            relative = path.relative_to(ROOT)
            assert source_allowed(relative)
            assert package.read('SKS-UtilityOS/' + relative.as_posix()) == path.read_bytes()
            assert subprocess.run(['git', '-c', f'core.excludesFile={global_excludes}', 'check-ignore',
                                   '--no-index', '-q', '--', str(relative)], cwd=ignore_repo).returncode == 1
