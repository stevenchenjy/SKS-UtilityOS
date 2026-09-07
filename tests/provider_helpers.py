"""Synthetic operators use public HTTP routes, never inject registry fixtures."""
import json
from utilityos.config import ROOT

CORPUS = ROOT / 'samples/onboarding'
CASES = {c['name']: c for c in json.loads((CORPUS / 'expected.json').read_text())['documents']}


def post(client, path, data, expected=200):
    response = client.post(path, json=data)
    assert response.status_code == expected, response.text
    return response.json()


def upload(client, name):
    response = client.post('/api/import', content=(CORPUS / CASES[name]['file']).read_bytes(),
        headers={'content-type': 'application/octet-stream', 'x-filename': CASES[name]['file'], 'x-synthetic-data': 'true'})
    assert response.status_code == 200, response.text
    item = client.get('/api/staged/' + str(response.json()['staged_ids'][0])).json()
    return item


def reviewed(client, name):
    item = upload(client, name)
    details = {'due_date': '2026-09-21' if CASES[name]['optional'] else '',
               'document_kind': 'invoice', 'currency': 'USD'}
    bill = CASES[name]['bill']
    if bill['lines'][0]['commodity'] == 'electricity':
        for index in range(len(bill['lines'])):
            details.update({f'services.{index}.demand_quantity': '12.25', f'services.{index}.demand_unit': 'kW'})
    post(client, f'/api/staged/{item["id"]}/approve', {'payload': bill, 'intake_details': details,
                                                      'revision': item['revision'], 'acknowledge': True})
    return item


def setup(client, name='first', *, sample=None, parent=None, wrong=False):
    sample = sample or reviewed(client, name)
    bill = CASES[name]['bill']
    provider = post(client, '/api/providers', {'label': bill['provider'], 'commodity': bill['lines'][0]['commodity']}) if parent is None else parent['provider']
    observations = client.get(f'/api/providers/documents/{sample["document_id"]}/observations').json()
    definition = author(observations, name, wrong=wrong)
    existing = [row for row in client.get('/api/providers').json()['layouts'] if row['provider_id'] == provider['id']]
    layout = post(client, f'/api/providers/{provider["id"]}/layouts', {'definition': definition,
        'expected_version': max((row['version'] for row in existing), default=0), 'parent_layout_id': parent['layout']['id'] if parent else None})
    return {'provider': provider, 'layout': layout, 'sample': sample, 'definition': definition}


def author(observations, name, wrong=False):
    case, rules = CASES[name], []
    lines = observations['lines']
    mapping = {'invoice_number': 'Statement ID', 'account_identifier': 'Client key' if case['layout'] == 2 else 'Customer key',
               'invoice_date': 'Issued', 'invoice_total': 'Invoice charges', 'due_date': 'Pay by',
               'services.*.meter_identifier': 'Service key', 'services.*.period_start': 'Start date',
               'services.*.period_end': 'Finish exclusive', 'services.*.consumption_unit': 'Measure',
               'services.*.current_charge': 'Line charges'}
    treatment = case['bill']['lines'][0]['usage_role']
    if treatment == 'delivery': mapping['services.*.delivery_quantity'] = 'Fuel dropped'
    elif treatment == 'consumption': mapping['services.*.consumption_quantity'] = 'Energy delivered' if case['layout'] == 2 else 'Measured units'
    if case['bill']['lines'][0]['commodity'] == 'electricity':
        mapping.update({'services.*.demand_quantity': 'Peak load', 'services.*.demand_unit': 'Peak measure'})
    for field, label in mapping.items():
        line = next((line for line in lines if line['text'].startswith(label + ':')), None)
        region = [0, line['bbox'][1] - 8, 612, line['bbox'][3] + 8] if line and not field.startswith('services.') else None
        rules.append({'field': field, 'label': 'Amount due' if wrong and field == 'invoice_total' else label,
                      'mode': 'inline', 'page': 1 if region else None, 'region': region, 'distance': 60,
                      'required': field != 'due_date',
                      'date_format': 'mdy' if field in {'invoice_date', 'due_date', 'services.*.period_start', 'services.*.period_end'} else 'iso',
                      'expected_unit': case['bill']['lines'][0]['unit'] if field.endswith('consumption_unit') else 'kW' if field.endswith('demand_unit') else None})
    return {'format': 1, 'provider_anchor': {'literal': case['bill']['provider'], 'page': 1, 'region': [0, 0, 612, 45]},
            'layout_anchor': {'literal': f'Local statement design {case["layout"]}', 'page': 1, 'region': [0, 65, 612, 90]},
            'section_prefix': None if case.get('single') else 'Service block ', 'document_kind': 'invoice', 'quantity_treatment': treatment,
            'end_date_inclusive': False, 'rules': rules}


def validate(client, built, *samples):
    return post(client, f'/api/provider-layouts/{built["layout"]["id"]}/validate',
                {'document_ids': [sample['document_id'] for sample in samples]})


def activate(client, built, validation):
    built['layout'] = post(client, f'/api/provider-layouts/{built["layout"]["id"]}/activate',
        {'state_id': built['layout']['state_id'], 'validation_id': validation['id'], 'acknowledge': True})
    return built
