#!/usr/bin/env python3
"""Independent fictional provider-studio corpus; no application rules are read.

Rules for these sources must be built through the authenticated setup API/UI.
This file generates documents and final reviewed truth, not registry records.
"""
from copy import deepcopy
from hashlib import sha256
import io
import json
from pathlib import Path
import argparse


def cases():
    result = []
    for index, name in enumerate(('first', 'second', 'future', 'page-two', 'two-meters',
            'layout-change', 'layout-change-second', 'repeated-label', 'relocated-account',
            'renamed-usage', 'missing-optional', 'scan', 'supply-first', 'supply-second',
            'fuel-first', 'fuel-second', 'single-first', 'single-second'), 1):
        commodity = 'propane' if name.startswith('fuel') else 'electricity'
        provider = 'Fictional Cedar Fuel' if commodity == 'propane' else 'Imaginary Juniper Supply' if name.startswith('supply') else 'Fictional Northstar Utility'
        treatment = 'delivery' if commodity == 'propane' else 'charges_only' if name.startswith('supply') else 'consumption'
        bill = {'provider': provider, 'account_alias': f'SYN-LOCAL-ACCOUNT-{index:02}',
                'invoice_number': f'SYN-LOCAL-{index:02}', 'bill_date': '2026-09-01', 'current_total': '124.50',
                'lines': [{'meter_code': f'SYN-LOCAL-METER-{index:02}', 'building': '', 'commodity': commodity,
                    'period_start': '2026-08-01', 'period_end': '2026-09-01',
                    'usage': '0' if treatment == 'charges_only' else '250.75',
                    'unit': 'gal' if commodity == 'propane' else 'kWh', 'current_charge': '124.50',
                    'usage_role': treatment, 'read_type': 'unknown'}]}
        if name == 'two-meters':
            bill['lines'].append({**bill['lines'][0], 'meter_code': 'SYN-LOCAL-SECOND-METER'})
            bill['current_total'] = '249.00'
        result.append({'name': name, 'bill': bill, 'layout': 2 if name.startswith('layout-change') else 1,
                       'optional': name != 'missing-optional', 'scan': name == 'scan', 'single': name.startswith('single')})
    return result


def pdf_bytes(case):
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    stream = io.BytesIO()
    pdf = canvas.Canvas(stream, pagesize=(612, 792), invariant=1, pageCompression=1)
    bill = case['bill']
    def heading():
        pdf.setFillColorRGB(.06, .24, .26)
        pdf.setFont('Helvetica-Bold', 16); pdf.drawString(36, 756, bill['provider'])
        pdf.setFont('Helvetica-Bold', 10)
        pdf.drawString(36, 734, 'FICTIONAL SOFTWARE TEST - NO PAYMENT REQUESTED')
        pdf.setFont('Helvetica', 11); pdf.drawString(36, 712, f'Local statement design {case["layout"]}')
        pdf.setFillColorRGB(.15, .15, .15)
        pdf.setFont('Helvetica', 9); pdf.drawString(36, 24, 'Synthetic fixtures only. No real provider or school records.')
    heading()
    y = 684
    def line(label, value):
        nonlocal y
        pdf.setFont('Helvetica', 11); pdf.drawString(42, y, f'{label}: {value}'); y -= 22
    line('Statement ID', bill['invoice_number'])
    account_label = 'Client key' if case['layout'] == 2 else 'Customer key'
    if case['name'] != 'relocated-account': line(account_label, bill['account_alias'])
    line('Issued', '09/01/2026')
    line('Invoice charges', bill['current_total'])
    if case['optional']: line('Pay by', '09/21/2026')
    if case['name'] == 'repeated-label': line('Customer key', 'SYN-AMBIGUOUS-SECOND-ACCOUNT')
    if case['name'] == 'relocated-account':
        y -= 45; line(account_label, bill['account_alias'])
    if case['name'] == 'page-two':
        pdf.showPage(); heading(); y = 684
    y -= 12
    for i, service in enumerate(bill['lines'], 1):
        if y < 285:
            pdf.showPage(); heading(); y = 684
        if not case.get('single'):
            pdf.setFont('Helvetica-Bold', 12); pdf.drawString(42, y, f'Service block {i}'); y -= 25
        line('Service key', service['meter_code'])
        line('Start date', '08/01/2026'); line('Finish exclusive', '09/01/2026')
        label = 'Fuel dropped' if service['usage_role'] == 'delivery' else 'Energy delivered' if case['layout'] == 2 or case['name'] == 'renamed-usage' else 'Measured units'
        line(label, '250.75'); line('Measure', service['unit']); line('Line charges', service['current_charge'])
        if service['commodity'] == 'electricity': line('Peak load', '12.25'); line('Peak measure', 'kW')
        y -= 18
    pdf.save(); raw = stream.getvalue()
    if case['scan']:
        import pypdfium2 as pdfium
        stream = io.BytesIO(); raster = canvas.Canvas(stream, pagesize=(612, 792), invariant=1, pageCompression=1)
        with pdfium.PdfDocument(raw) as document:
            for page in document:
                bitmap = page.render(scale=2.5); image = bitmap.to_pil().copy(); bitmap.close(); page.close()
                raster.drawImage(ImageReader(image), 0, 0, 612, 792); raster.showPage(); image.close()
        raster.save(); raw = stream.getvalue()
    return raw


def generate(directory):
    directory = Path(directory); directory.mkdir(parents=True, exist_ok=True)
    truth = []
    for case in cases():
        raw = pdf_bytes(case); name = case['name'] + '.pdf'; (directory / name).write_bytes(raw)
        truth.append({**case, 'file': name, 'sha256': sha256(raw).hexdigest()})
    (directory / 'expected.json').write_text(json.dumps({'corpus': 'fictional-local-onboarding-v1', 'documents': truth}, indent=2) + '\n')
    return truth


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); print(f'Generated {len(generate(args.output))} fictional onboarding PDFs.')
