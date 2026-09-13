"""Invented water fields retain independent evidence, never school screenshots."""
from copy import deepcopy
from decimal import Decimal
import io
import json
import pytest
from reportlab.pdfgen import canvas
from utilityos.extraction_schema import Extraction
from utilityos.operations import backup, restore
from utilityos.db import Store
from utilityos.service import Ledger


def source():
    output=io.BytesIO();pdf=canvas.Canvas(output,invariant=1)
    for index,line in enumerate((
        'FICTIONAL WATER SEMANTICS - synthetic development only',
        'Service from 2026-07-01; service to 2026-09-01 exclusive; days 62',
        'Previous cumulative reading 1000; present cumulative reading 1100',
        'Billed-period usage 120 US gallons; adjusted for fictional meter replacement',
        'Water current charge 60.00; current charges due 60.00',
        'Previous balance 200.00; payments received 150.00; adjustment -10.00',
        'Total due 100.00',
        'FICTIONAL PAYMENT STAMP: 9999.00; handwritten note: 7777; chart label: 8888')):
        pdf.drawString(35,760-index*23,line)
    pdf.save();return output.getvalue()


def test_review_retains_water_semantics_without_deriving_authoritative_quantities(ledger,bill,tmp_path):
    raw=source();identifier=ledger.import_file('fictional-water.pdf',raw)['staged_ids'][0]
    item=ledger.stage(identifier)
    assert not any(field['value'] in {'9999.00','7777','8888'} for field in item['intake']['extraction']['fields'].values())
    bill.update(provider='Fictional Water',account_alias='SYN-WATER',invoice_number='SYN-W-202609',bill_date='2026-09-10',current_total='60.00')
    bill['lines']=[dict(bill['lines'][0],meter_code='SYN-W',building='Fictional Hall',commodity='water',
                        period_start='2026-07-01',period_end='2026-09-01',usage='120',unit='gal',current_charge='60.00')]
    values={'document_kind':'invoice','currency':'USD','previous_balance':'200.00',
            'payments_received':'150.00','balance_adjustments':'-10.00','amount_due':'100.00',
            'services.0.previous_reading':'1000','services.0.current_reading':'1100','services.0.service_days':'62'}
    ledger.save_draft(identifier,bill,0,intake_details=values)
    pending=ledger.stage(identifier)
    assert any(flag['code']=='READING_DIFFERENCE_REQUIRES_REVIEW' and not flag['blocking'] for flag in pending['flags'])
    assert pending['payload']['lines'][0]['usage']=='120'
    with pytest.raises(ValueError,match='ACKNOWLEDGE'):
        ledger.approve_bill(identifier,bill,False,revision=1)
    ledger.approve_bill(identifier,bill,True,revision=1)
    final=ledger.stage(identifier)
    assert all(final['intake']['reviewed_values'][key]==value for key,value in values.items())
    assert ledger.overview()['total_cents']==6000
    assert Decimal(final['intake']['reviewed_values']['invoice_total'])==Decimal('60.00')
    assert final['intake']['extraction']==item['intake']['extraction']
    saved=backup(ledger.store);recovered=Store(tmp_path/'recovered','demo');restore(recovered,saved,'demo')
    assert Ledger(recovered).stage(identifier)['intake']==final['intake']


def test_unknown_water_unit_and_invalid_day_count_require_review(ledger,bill):
    identifier=ledger.import_file('synthetic.pdf',source())['staged_ids'][0]
    unknown=deepcopy(bill);unknown['lines'][0].update(commodity='water',unit='')
    with pytest.raises(ValueError):
        ledger.approve_bill(identifier,unknown,True,revision=0)
    for value in ('0','62.5','401','estimated'):
        with pytest.raises(ValueError,match='EXTRACTION_REVIEW_VALUE_INVALID'):
            ledger.save_draft(identifier,bill,0,intake_details={'services.0.service_days':value})
    assert ledger.overview()['total_cents']==0


def test_legacy_extraction_does_not_require_new_optional_water_fields(ledger):
    identifier=ledger.import_file('synthetic.pdf',source())['staged_ids'][0]
    evidence=ledger.stage(identifier)['intake']['extraction']
    evidence['fields'].pop('payments_received',None)
    evidence['fields'].pop('balance_adjustments',None)
    assert Extraction.model_validate(evidence)
