#!/usr/bin/env python3
"""Generate visibly fictional, deterministic PDF fixtures and independent truth.

No real branding, data, fonts, or template implementation is read by this script.
ReportLab is development-only. Run with an explicit output directory.
"""
import argparse
from copy import deepcopy
from hashlib import sha256
import io
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

HEADER = dict(zip(
    ('provider','invoice_number','account_identifier','service_address','invoice_date','due_date','currency',
     'invoice_total','previous_balance','amount_due','document_kind','supplier_only','delivery_only'),
    ('Provider','Invoice reference','Account','Service address','Invoice date','Due date','Currency',
     'Current charges','Previous balance','Amount due','Document kind','Supplier only','Delivery only')))
SERVICE = dict(zip(
    ('meter_identifier','building','utility_type','period_start','period_end','consumption_quantity','consumption_unit',
     'demand_quantity','demand_unit','delivery_quantity','quantity_treatment','reading_type','previous_reading','current_reading',
     'current_charge','supply_charge','delivery_charge','demand_charge','taxes','fees','credits'),
    ('Meter','Building','Utility','Period start','End (exclusive)','Usage','Usage unit','Demand','Demand unit','Delivered volume',
     'Quantity treatment','Reading type','Previous reading','Current reading','Service charge','Supply charge',
     'Delivery charge','Demand charge','Taxes','Fees','Credits')))


def cases():
    header = {'provider':'Example Valley Electric', 'invoice_number':'SYN-ELECTRIC-001', 'account_identifier':'SYN-ACCOUNT-E01',
              'service_address':'100 Imaginary Lane, Fictional Campus', 'invoice_date':'2026-09-01', 'due_date':'2026-09-21',
              'currency':'USD', 'invoice_total':'100.00', 'previous_balance':'40.00', 'amount_due':'140.00',
              'document_kind':'invoice', 'supplier_only':'no', 'delivery_only':'no'}
    service = {'meter_identifier':'SYN-METER-E01', 'building':'Fictional Science Hall', 'utility_type':'electricity',
               'period_start':'2026-08-01', 'period_end':'2026-09-01', 'consumption_quantity':'100.25', 'consumption_unit':'kWh',
               'quantity_treatment':'consumption', 'reading_type':'actual', 'previous_reading':'1000', 'current_reading':'1100.25',
               'current_charge':'100.00', 'supply_charge':'50.00', 'delivery_charge':'40.00', 'demand_charge':'0.00',
               'taxes':'7.00', 'fees':'3.00', 'credits':'0.00'}
    result = []
    def add(name, **options):
        item = {'name':name,'header':deepcopy(header),'services':[deepcopy(service)],'layout':1,**options}
        # Distinct identities keep this corpus usable as a batch in an empty ledger.
        index = len(result) + 1
        item['header']['invoice_number'] = f'SYN-DOC-{index:03}'
        item['header']['account_identifier'] = f'SYN-ACCOUNT-{index:03}'
        item['services'][0]['meter_identifier'] = f'SYN-METER-{index:03}'
        result.append(item)
        return item
    add('electricity-digital')
    add('electricity-scan', scan=True)
    for name, provider, commodity, unit in (
        ('water','Fictional Springs Water','water','gal'),
        ('natural-gas','Sample Flame Gas','natural_gas','therm'),
        ('heating-oil','Imaginary Fuels Cooperative','heating_oil','gal'),
        ('propane','Imaginary Fuels Cooperative','propane','gal')):
        item = add(name)
        item['header']['provider'] = provider
        item['services'][0].update(utility_type=commodity, consumption_unit=unit)
        if commodity in ('heating_oil','propane'):
            item['services'][0].update(quantity_treatment='delivery', delivery_quantity='100.25')
            for key in ('consumption_quantity','previous_reading','current_reading'):
                item['services'][0].pop(key)
            item['header']['delivery_only'] = 'yes'
    item=add('supply-only');item['header'].update(provider='Example Supply Company',supplier_only='yes')
    item['services'][0]['quantity_treatment']='charges_only'
    # Printed usage remains evidence; the proposed ledger quantity must be zero.
    item=add('demand-charge');item['services'][0].update(demand_quantity='12.75',demand_unit='kW',demand_charge='20.00',supply_charge='30.00')
    item=add('estimated');item['services'][0]['reading_type']='estimated'
    add('corrected-invoice')['header']['document_kind']='corrected_invoice'
    item=add('credit');item['header'].update(invoice_total='-20.00',amount_due='20.00',document_kind='credit')
    item['services'][0].update(quantity_treatment='charges_only',consumption_quantity='0',current_charge='-20.00',supply_charge='0.00',delivery_charge='0.00',taxes='0.00',fees='0.00',credits='-20.00')
    add('rebill')['header']['document_kind']='rebill'
    add('multipage',extra_page=True)
    item=add('multiple-meters');item['services'].append(deepcopy(item['services'][0]));item['services'][1]['meter_identifier']='SYN-SECOND-METER'
    item['header'].update(invoice_total='200.00',amount_due='240.00')
    item=add('unusual-period');item['services'][0].update(period_start='2026-06-13',period_end='2026-08-29')
    add('missing-total')['header'].pop('invoice_total')
    add('scan-rotated',scan=True,rotation=90)
    add('scan-low-quality',scan=True,low_quality=True)
    add('layout-v1')
    add('layout-v2',layout=2)
    add('drift-missing-anchor',omit_anchor=True)
    add('drift-relocated-field',relocated=True)
    add('drift-renamed-label',rename=True)
    item=add('supporting-document');item['header']['document_kind']='supporting_document'
    item=add('unknown-provider');item['header']['provider']='Imaginary Unregistered Energy'
    item=add('reading-conflict');item['services'][0]['current_reading']='1800'
    item=add('wrong-unit');item['services'][0]['consumption_unit']='miles'
    item=add('negative-quantity');item['services'][0]['consumption_quantity']='-100.25'
    return result


def pdf_bytes(case):
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    buffer=io.BytesIO()
    pdf=canvas.Canvas(buffer,pagesize=(612,792),invariant=1,pageCompression=1)
    def page_header():
        pdf.setFillColorRGB(.08,.20,.27);pdf.setFont('Helvetica-Bold',15)
        pdf.drawString(36,758,case['header']['provider'])
        pdf.setFont('Helvetica-Bold',10);pdf.drawString(36,737,'FICTIONAL TEST DOCUMENT - NOT A REAL UTILITY BILL')
        pdf.setFont('Helvetica',11)
        if not case.get('omit_anchor'):pdf.drawString(36,713,f'Utility statement layout {case["layout"]}')
        pdf.setFillColorRGB(.15,.15,.15);pdf.setFont('Helvetica',10)
        pdf.drawString(36,24,'SYNTHETIC ONLY | Values are examples for software testing | No payment requested')
    page_header();y=687
    headers,services=HEADER.copy(),SERVICE.copy()
    if case['layout']==2:
        headers.update(invoice_number='Bill reference',account_identifier='Customer account',invoice_date='Issued on',invoice_total='New charges')
        services.update(meter_identifier='Service identifier',period_start='Service from',period_end='Service until (exclusive)',consumption_quantity='Billed quantity',current_charge='Line total')
    if case.get('rename'):headers['account_identifier']='Subscription identifier'
    def write(label,value,x=42):
        nonlocal y
        if y<58:
            pdf.showPage();page_header();y=687
        pdf.setFont('Courier' if case['layout']==2 else 'Helvetica',10)
        pdf.drawString(x,y,f'{label}: {value}');y-=15
    for key,label in headers.items():
        if key not in case['header']:continue
        if case.get('relocated') and key=='account_identifier':continue
        write(label,case['header'][key],72 if case['layout']==2 else 42)
    for index,service in enumerate(case['services']):
        if y-15*len(service)<55:
            pdf.showPage();page_header();y=687
        pdf.setFont('Helvetica-Bold',11);pdf.drawString(42,y,f'Service point {index+1}');y-=19
        for key,label in services.items():
            if key in service:write(label,service[key],72 if case['layout']==2 else 42)
    if case.get('relocated'):write(headers['account_identifier'],case['header']['account_identifier'])
    if case.get('extra_page'):
        pdf.showPage();page_header();pdf.setFont('Helvetica',12)
        pdf.drawString(42,680,'Fictional usage notes: this extra page contains no new invoice or service point.')
        pdf.drawString(42,657,'No duplicate account fields, no additional current charges, no payment instructions.')
    pdf.save();raw=buffer.getvalue()
    if case.get('scan'):
        import pypdfium2 as pdfium
        from PIL import ImageFilter
        result=io.BytesIO();scanned=canvas.Canvas(result,pagesize=(612,792),invariant=1,pageCompression=1)
        with pdfium.PdfDocument(raw) as document:
            for page in document:
                bitmap=page.render(scale=1.3 if case.get('low_quality') else 2.5)
                image=bitmap.to_pil().copy();bitmap.close();page.close()
                if case.get('low_quality'):image=image.filter(ImageFilter.GaussianBlur(.4))
                if case.get('rotation'):image=image.rotate(case['rotation'],expand=True)
                width,height=(792,612) if case.get('rotation') else (612,792)
                scanned.setPageSize((width,height));scanned.drawImage(ImageReader(image),0,0,width,height);scanned.showPage();image.close()
        scanned.save();raw=result.getvalue()
    return raw


def generate(destination):
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    truth=[]
    for case in cases():
        raw=pdf_bytes(case);name=case['name']+'.pdf';(destination/name).write_bytes(raw)
        fields=case['header'].copy()
        for index,service in enumerate(case['services']):
            fields.update({f'services.{index}.{key}':value for key,value in service.items()})
        # Unsupported units are intentionally not normalized into an accepted unit.
        if case['name']=='wrong-unit':fields['services.0.consumption_unit']=None
        if case.get('rename'):fields['account_identifier']=None
        truth.append({'file':name,'sha256':sha256(raw).hexdigest(),'fields':fields,
                      'layout':'known_provider_unknown_layout' if any(case.get(k) for k in ('omit_anchor','relocated','rename')) else 'unknown_provider' if case['name']=='unknown-provider' else 'known',
                      'path':'ocr' if case.get('scan') else 'native_text' if any(case.get(k) for k in ('omit_anchor','relocated','rename')) or case['name']=='unknown-provider' else 'template'})
    (destination/'expected.json').write_text(json.dumps({'corpus':'fictional-utility-pdf-v1','documents':truth},indent=2)+'\n')
    return truth


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(f'Generated {len(generate(args.output))} fictional PDFs.')
