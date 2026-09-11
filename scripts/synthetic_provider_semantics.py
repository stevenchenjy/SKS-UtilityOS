#!/usr/bin/env python3
"""Original synthetic statements inspired only by public field distinctions.

No provider artwork, sample identities, school records, or layout rules are
copied. These are deliberately simple fictional documents for Provider Studio
and accounting refusal tests, not evidence of compatibility with a provider.
"""
import argparse
from copy import deepcopy
from decimal import Decimal
from hashlib import sha256
import io
import json
from pathlib import Path


def cases():
    base = {
        'provider': 'Fictional Alder Municipal Water', 'account_alias': 'SYN-MUNICIPAL-ACCOUNT',
        'invoice_number': 'SYN-WATER-01', 'bill_date': '2026-07-15', 'current_total': '58.40',
        'lines': [{'meter_code': 'SYN-MASTER-WATER', 'building': '', 'commodity': 'water',
                   'period_start': '2026-05-11', 'period_end': '2026-07-12', 'usage': '4250',
                   'unit': 'gal', 'current_charge': '58.40', 'usage_role': 'consumption',
                   'read_type': 'unknown'}]}
    result = []
    for name, number, bill_date, start, end in (
        ('water-first', '01', '2026-07-15', '2026-05-11', '2026-07-12'),
        ('water-second', '02', '2026-09-15', '2026-07-12', '2026-09-10'),
        ('water-future', '03', '2026-11-15', '2026-09-10', '2026-11-11'),
        ('municipal-combined', '04', '2027-01-15', '2026-11-11', '2027-01-09')):
        bill = deepcopy(base)
        bill.update(invoice_number='SYN-WATER-' + number, bill_date=bill_date)
        bill['lines'][0].update(period_start=start, period_end=end)
        extras = {'sewer': '41.25', 'garbage': '88.70', 'sewer_capital': '31.00'} if name == 'municipal-combined' else {}
        bill['current_total'] = format(Decimal('58.40') + sum(map(Decimal, extras.values())), '.2f')
        result.append({'name': name, 'bill': bill, 'extra_charges': extras, 'prior_balance': '210.15',
                       'amount_due': format(Decimal(bill['current_total']) + Decimal('210.15'), '.2f'),
                       'printed_unit': 'gal', 'demand': None,
                       'expected': 'hold_combined_services' if extras else 'reviewable'})
    for name, supply in (('electricity-demand', False), ('electricity-supply', True)):
        bill = deepcopy(base)
        bill.update(provider='Imaginary Birch Supply' if supply else 'Fictional Aspen Electric',
                    account_alias='SYN-SUPPLY-ACCOUNT' if supply else 'SYN-ELECTRIC-ACCOUNT',
                    invoice_number='SYN-ELECTRIC-SUPPLY' if supply else 'SYN-ELECTRIC-DELIVERY',
                    bill_date='2026-09-15', current_total='64.80' if supply else '173.25')
        bill['lines'][0].update(meter_code='SYN-MASTER-ELECTRIC', commodity='electricity', unit='kWh',
                               period_start='2026-08-09', period_end='2026-09-12',
                               usage='0' if supply else '876.5', usage_role='charges_only' if supply else 'consumption',
                               current_charge=bill['current_total'])
        result.append({'name': name, 'bill': bill, 'extra_charges': {}, 'prior_balance': '92.10',
                       'amount_due': format(Decimal(bill['current_total']) + Decimal('92.10'), '.2f'),
                       'printed_unit': 'kWh', 'demand': None if supply else '18.75', 'expected': 'reviewable'})
    bill = deepcopy(base)
    bill.update(provider='Fictional Larch Gas', account_alias='SYN-GAS-ACCOUNT',
                invoice_number='SYN-GAS-AMBIGUOUS', bill_date='2026-09-15', current_total='87.50')
    bill['lines'][0].update(meter_code='SYN-MASTER-GAS', commodity='natural_gas', unit='units',
                           usage='120', current_charge='87.50')
    result.append({'name': 'gas-ambiguous', 'bill': bill, 'extra_charges': {}, 'prior_balance': '0.00',
                   'amount_due': '87.50', 'printed_unit': 'units', 'demand': None,
                   'expected': 'hold_ambiguous_unit'})
    return result


def pdf_bytes(case):
    from reportlab.pdfgen import canvas
    stream = io.BytesIO()
    pdf = canvas.Canvas(stream, pagesize=(612, 792), invariant=1, pageCompression=1)
    bill, service = case['bill'], case['bill']['lines'][0]
    pdf.setTitle('Synthetic provider semantics - ' + case['name'])
    pdf.setFont('Helvetica-Bold', 15)
    pdf.drawString(36, 756, bill['provider'])
    pdf.setFont('Helvetica-Bold', 10)
    pdf.drawString(36, 733, 'FICTIONAL SOFTWARE TEST - NO PAYMENT REQUESTED')
    pdf.setFont('Helvetica', 11)
    pdf.drawString(36, 710, 'Original synthetic semantics layout 1')
    y = 679
    def line(label, value):
        nonlocal y
        pdf.setFont('Helvetica', 10)
        pdf.drawString(42, y, f'{label}: {value}')
        y -= 21
    for label, value in (
        ('Statement reference', bill['invoice_number']), ('Account reference', bill['account_alias']),
        ('Issued', bill['bill_date']), ('Current statement charges', bill['current_total']),
        ('Prior account balance', case['prior_balance']), ('Account amount due', case['amount_due'])):
        line(label, value)
    y -= 10
    pdf.setFont('Helvetica-Bold', 11)
    pdf.drawString(42, y, 'Meter service 1')
    y -= 25
    for label, value in (
        ('Meter reference', service['meter_code']), ('Service start', service['period_start']),
        ('Service end exclusive', service['period_end']), ('Printed usage quantity', '876.5' if service['usage_role'] == 'charges_only' else service['usage']),
        ('Usage unit', case['printed_unit']), ('Meter current charge', service['current_charge'])):
        line(label, value)
    if case['demand'] is not None:
        line('Peak demand quantity', case['demand'])
        line('Peak demand unit', 'kW')
    if service['usage_role'] == 'charges_only':
        line('Quantity note', 'Repeated supplier reference; not additional consumption')
    if case['extra_charges']:
        y -= 8
        for name, charge in case['extra_charges'].items():
            line('Other service ' + name.replace('_', ' '), charge)
    pdf.setFont('Helvetica', 9)
    pdf.drawString(36, 43, 'All providers, references, amounts, dates and readings are invented.')
    pdf.drawString(36, 28, 'No school records or real provider artwork. No provider compatibility claim.')
    pdf.save()
    return stream.getvalue()


def generate(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    documents = []
    for case in cases():
        raw = pdf_bytes(case)
        name = case['name'] + '.pdf'
        (directory / name).write_bytes(raw)
        documents.append({**case, 'file': name, 'sha256': sha256(raw).hexdigest()})
    (directory / 'expected.json').write_text(json.dumps({
        'corpus': 'original-fictional-provider-semantics-v1',
        'note': 'Combined/ambiguous cases are refusal fixtures, not approved bill truth.',
        'documents': documents}, indent=2) + '\n')
    return documents


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(f'Generated {len(generate(args.output))} original synthetic PDFs.')
