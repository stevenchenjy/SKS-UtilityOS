from copy import deepcopy
import csv
import io
import json
import pytest
from utilityos.parsers import ValidationError


def approve(ledger, raw, payload=None):
    item = ledger.import_file('synthetic.csv', raw)['staged_ids'][0]
    return ledger.approve_bill(item, payload or ledger.stage(item)['payload'], True)['id'], item


def correction(ledger, bill_id, reason='Synthetic transcription correction'):
    item = ledger.create_correction(bill_id, reason)['staged_id']
    return item, ledger.stage(item)['payload']


def test_same_number_rebill_preserves_original_and_counts_latest(ledger, raw_csv):
    original, stage = approve(ledger, raw_csv)
    item, payload = correction(ledger, original)
    payload['current_total'] = payload['lines'][0]['current_charge'] = '123.45'
    payload['lines'][0]['usage'] = '1234.123456789'
    assert ledger.overview()['total_cents'] == 57980
    replacement = ledger.approve_bill(item, payload, True)['id']
    overview = ledger.overview()
    assert overview['total_cents'] == 12345
    assert overview['stats']['approved_bills'] == 1
    assert overview['quantities'][0]['value'] == '1234.123456789'
    original_view = ledger.stage(stage)
    assert original_view['payload']['current_total'] == '579.8'
    assert original_view['bill']['status'] == 'superseded'
    assert [v['id'] for v in original_view['bill']['versions']] == [original, replacement]
    assert original_view['bill']['history'][-1]['action'] == 'superseded'
    assert ledger.stage(item)['document_id'] == original_view['document_id']
    exported = list(csv.DictReader(io.StringIO(ledger.export_csv().decode('utf-8-sig'))))
    assert len(exported) == 1 and exported[0]['current_total'] == '123.45'
    again, payload = correction(ledger, replacement)
    ledger.approve_bill(again, payload, True)
    assert ledger.overview()['total_cents'] == 12345


def test_imported_rebill_attaches_new_source_and_reject_retains_old(ledger, raw_csv):
    original, original_stage = approve(ledger, raw_csv)
    original_document=ledger.stage(original_stage)['document_id']
    item = ledger.import_file('rebill.csv', raw_csv + b'\n')['staged_ids'][0]
    draft = ledger.stage(item)
    draft = ledger.save_draft(item, draft['payload'], draft['revision'], original, 'Rebill from synthetic source')
    assert not any(flag['blocking'] for flag in draft['flags'])
    ledger.reject(item)
    assert ledger.overview()['total_cents'] == 57980
    assert len(list(ledger.store.sources.iterdir())) == 2
    new_item = ledger.import_file('rebill-again.csv', raw_csv + b'\n\n')['staged_ids'][0]
    draft = ledger.stage(new_item)
    ledger.save_draft(new_item, draft['payload'], 0, original, 'Replacement source')
    ledger.approve_bill(new_item, draft['payload'], True, revision=1)
    assert ledger.stage(new_item)['document_id'] != original_document
    assert len(ledger.bills()) == 2


def test_replacement_overlap_with_unrelated_invoice_is_atomic(ledger, raw_csv):
    original, _ = approve(ledger, raw_csv)
    other = ledger.stage(1)['payload']
    other['invoice_number'] = 'SYN-NEXT'
    other['lines'][0].update(period_start='2026-09-01', period_end='2026-10-01')
    approve(ledger, raw_csv + b'\n', other)
    item, payload = correction(ledger, original)
    payload['lines'][0]['period_end'] = '2026-09-15'
    with pytest.raises(ValidationError, match='APPROVED_CONSUMPTION_PERIOD_OVERLAP'):
        ledger.approve_bill(item, payload, True)
    assert ledger.stage(item)['status'] == 'pending'
    assert all(b['status'] == 'active' for b in ledger.bills())
    assert ledger.overview()['total_cents'] == 115960


def test_cancel_requires_review_keeps_history_and_blocks_stale_replacement(ledger, raw_csv):
    original, stage = approve(ledger, raw_csv)
    item, payload = correction(ledger, original)
    with pytest.raises(ValidationError, match='CONFIRM_CANCELLATION'):
        ledger.cancel_bill(original, 'Duplicate synthetic posting')
    ledger.cancel_bill(original, 'Duplicate synthetic posting', True)
    assert ledger.overview()['total_cents'] == 0
    assert ledger.overview()['quantities'] == []
    assert ledger.stage(stage)['bill']['status'] == 'cancelled'
    assert ledger.stage(stage)['bill']['history'][-1]['reason'] == 'Duplicate synthetic posting'
    with pytest.raises(ValidationError, match='ACTIVE_ORIGINAL'):
        ledger.approve_bill(item, payload, True)
    with pytest.raises(ValidationError, match='ACTIVE_ORIGINAL'):
        ledger.cancel_bill(original, 'Again', True)
    ledger.reject(item)
    other = ledger.import_file('retry.csv', raw_csv + b'\n')['staged_ids'][0]
    with pytest.raises(ValidationError, match='DUPLICATE_INVOICE'):
        ledger.approve_bill(other, payload, True)


def test_correction_multiple_meters_and_supply_credit(ledger, raw_csv):
    item = ledger.import_file('multi.csv', raw_csv)['staged_ids'][0]
    bill = ledger.stage(item)['payload']
    second = deepcopy(bill['lines'][0])
    second.update(meter_code='SYN-SECOND-METER', building='', current_charge='20.00')
    bill['lines'].append(second)
    bill['current_total'] = '599.80'
    original = ledger.approve_bill(item, bill, True)['id']
    # Supply charges for the same physical meters add no repeated consumption.
    supply = deepcopy(bill)
    supply.update(provider='Synthetic supply', account_alias='Supply', invoice_number='SYN-SUPPLY', current_total='-10.00')
    for line in supply['lines']:
        line.update(usage='0', usage_role='charges_only', current_charge='-5.00')
    supply_id, _ = approve(ledger, raw_csv + b'\n', supply)
    item, bill = correction(ledger, original)
    bill['current_total'] = '120.00'
    bill['lines'][0]['current_charge'] = '100.00'
    ledger.approve_bill(item, bill, True)
    assert ledger.overview()['total_cents'] == 11000
    assert ledger.overview()['quantities'][0]['value'] == '5720'
    credit_item, supply = correction(ledger, supply_id)
    supply['current_total'] = '-20.00'
    for line in supply['lines']:
        line['current_charge'] = '-10.00'
    ledger.approve_bill(credit_item, supply, True)
    assert ledger.overview()['total_cents'] == 10000
    assert ledger.overview()['quantities'][0]['value'] == '5720'


def test_incomplete_draft_save_reload_and_stale_tab_protection(ledger, raw_csv):
    item = ledger.import_file('entry.csv', raw_csv)['staged_ids'][0]
    bill = ledger.stage(item)['payload']
    bill['invoice_number'] = ''
    saved = ledger.save_draft(item, bill, 0)
    assert saved['revision'] == 1
    assert saved['payload']['invoice_number'] == ''
    with pytest.raises(ValidationError, match='DRAFT_CHANGED'):
        ledger.save_draft(item, bill, 0)
    bill['invoice_number'] = 'SYN-FINISHED'
    with pytest.raises(ValidationError, match='DRAFT_CHANGED'):
        ledger.approve_bill(item, bill, True, revision=0)
    ledger.approve_bill(item, bill, True, revision=1)
    with ledger.store.connect() as db:
        history = db.execute('SELECT * FROM draft_history ORDER BY revision').fetchall()
    assert len(history) == 2
    assert json.loads(history[0]['payload'])['invoice_number'] == ''
    assert ledger.overview()['total_cents'] == 57980


def test_one_pending_correction_and_no_closed_draft_edit(ledger, raw_csv):
    original, stage = approve(ledger, raw_csv)
    item, bill = correction(ledger, original)
    with pytest.raises(ValidationError, match='PENDING_CORRECTION_ALREADY_EXISTS'):
        correction(ledger, original)
    with pytest.raises(ValidationError, match='PENDING_BILL_REQUIRED'):
        ledger.save_draft(stage, bill, 1)
    ledger.reject(item)
    assert correction(ledger, original)[0] > item


def test_correction_reason_and_mapping_history_never_enter_diagnostics(ledger, raw_csv):
    original, _ = approve(ledger, raw_csv)
    item, bill = correction(ledger, original, 'SECRET-REASON-9988')
    ledger.approve_bill(item, bill, True)
    meter = ledger.inventory()['meters'][0]
    ledger.edit_inventory('meter', meter['id'], meter['building'], 'SECRET-BUILDING-9988', 'SECRET-MAPPING-9988', True)
    exported = json.dumps(ledger.diagnostics('demo'))
    for sentinel in ['9988', '579.8', str(ledger.store.directory), 'demo.csv']:
        assert sentinel not in exported


def test_mapping_edits_change_reporting_keep_review_snapshot_and_reject_stale(ledger, raw_csv):
    _, stage = approve(ledger, raw_csv)
    meter = ledger.inventory()['meters'][0]
    with pytest.raises(ValidationError, match='CONFIRM_MAPPING'):
        ledger.edit_inventory('meter', meter['id'], meter['building'], '', 'Shared meter')
    ledger.edit_inventory('meter', meter['id'], meter['building'], '', 'Shared meter', True)
    assert ledger.overview()['cost_by_building'][0]['building'] == 'Unassigned / shared'
    assert ledger.stage(stage)['payload']['lines'][0]['building'] == meter['building']
    with pytest.raises(ValidationError, match='MAPPING_CHANGED'):
        ledger.edit_inventory('meter', meter['id'], meter['building'], 'Wrong stale edit', 'Stale', True)
    ledger.edit_inventory('meter', meter['id'], '', 'Synthetic confirmed location', 'Confirmed', True)
    building = next(b for b in ledger.inventory()['buildings'] if b['name'] == 'Synthetic confirmed location')
    ledger.edit_inventory('building', building['id'], building['name'], 'Synthetic renamed location', 'Spelling', True)
    assert ledger.overview()['cost_by_building'][0]['building'] == 'Synthetic renamed location'
    assert len(ledger.inventory()['history']) == 3
