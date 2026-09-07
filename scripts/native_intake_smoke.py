#!/usr/bin/env python3
"""Native desktop/mobile intake check; creates a NEW synthetic workspace only."""
import argparse
import json
import os
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from playwright.sync_api import sync_playwright,expect
from scripts.native_readiness_smoke import server
from utilityos.config import Config
from utilityos.db import Store
from utilityos.operations import restore,check
from utilityos.service import Ledger


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir',type=Path,required=True)
    parser.add_argument('--browser-executable',type=Path,required=True)
    parser.add_argument('--ocr-model-dir',type=Path,required=True)
    parser.add_argument('--headed',action='store_true');args=parser.parse_args()
    work=args.work_dir.resolve();Config(work,'demo').validate()
    if work.exists():raise SystemExit('INTAKE_CHECK_REQUIRES_NEW_EXTERNAL_DIRECTORY')
    work.mkdir(parents=True,mode=0o700);directory=work/'demo';inbox=work/'UtilityOS Inbox';inbox.mkdir()
    fixture=ROOT/'samples/intake'
    (inbox/'folder-propane.pdf').write_bytes((fixture/'propane.pdf').read_bytes())
    old=time.time()-10;os.utime(inbox/'folder-propane.pdf',(old,old))
    results=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path=str(args.browser_executable),headless=not args.headed)
        with server(directory,'demo',work,args.ocr_model_dir) as url:
            context=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
            page=context.new_page();errors=[];failures=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.on('console',lambda msg:errors.append(msg.text) if msg.type in {'error','warning'} else None)
            page.on('response',lambda response:failures.append((response.status,response.url)) if response.status>=400 else None)
            page.on('dialog',lambda dialog:dialog.accept())
            def nav(label):
                page.locator('nav').get_by_role('button',name=label,exact=True).click()
                page.get_by_role('heading',name=label,exact=True).wait_for()
                assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
            def get(path):return page.evaluate('(path)=>fetch("/api"+path).then(r=>r.json())',path)
            def upload(name):
                nav('Utility Inbox');page.get_by_role('button',name='Import files',exact=True).click()
                page.get_by_label('Source file',exact=True).set_input_files(str(fixture/name))
                page.locator('#synthetic-confirm').check();page.get_by_role('button',name='Import for review',exact=True).click()
                page.locator('#bill-editor').wait_for()
            def shot(name):page.screenshot(path=str(work/(name+'.png')))
            def download(name,destination):
                with page.expect_download() as pending:page.get_by_role('link',name=name,exact=True).click()
                pending.value.save_as(str(destination));assert destination.stat().st_size>0
            page.goto(url);page.get_by_role('button',name='Open synthetic demo',exact=True).click()
            page.get_by_role('heading',name='Campus utilities',exact=True).wait_for()
            upload('electricity-digital.pdf')
            expect(page.locator('[name=current_total]')).to_have_value('100.00')
            page.locator('[data-evidence=invoice_total]').click()
            expect(page.locator('#evidence-error')).to_contain_text('Page rendered locally')
            assert page.locator('#source-canvas').evaluate('(c)=>c.width>0 && c.height>0')
            shot('desktop-evidence')
            download('Download original locally',work/'unchanged-source.pdf')
            assert (work/'unchanged-source.pdf').read_bytes()==(fixture/'electricity-digital.pdf').read_bytes()
            page.locator('[name=current_total]').fill('110.00');page.locator('[name=current_charge]').fill('110.00')
            page.locator('summary').filter(has_text='Additional extracted bill details').click()
            page.locator('[name="detail-due_date"]').fill('2026-09-22')
            page.get_by_role('button',name='Add a service line',exact=True).click()
            page.get_by_role('button',name='Remove service line 2',exact=True).click()
            expect(page.locator('[name="detail-due_date"]')).to_have_value('2026-09-22')
            page.get_by_role('button',name='Save draft',exact=True).click()
            expect(page.locator('[name=current_total]')).to_have_value('110.00')
            expect(page.locator('[data-evidence=invoice_total]')).to_contain_text('Manually corrected')
            expect(page.locator('[data-evidence=due_date]')).to_contain_text('Manually corrected')
            page.locator('#acknowledge').check();page.get_by_role('button',name='Approve into ledger',exact=True).click()
            page.get_by_role('heading',name='Review queue',exact=True).wait_for()
            item=next(row for row in get('/staged') if row['filename']=='electricity-digital.pdf')
            approved=get(f'/staged/{item["id"]}')
            assert approved['intake']['extraction']['fields']['invoice_total']['value']=='100.00'
            assert approved['intake']['reviewed_values']['due_date']=='2026-09-22'
            nav('Utility Inbox')
            page.get_by_role('button',name=f'Open draft {item["id"]}',exact=True).click()
            page.locator('[data-evidence=invoice_total]').click() # Evidence remains usable after approval.
            page.get_by_role('button',name='Correct approved invoice',exact=True).click()
            page.locator('[name=reason]').fill('Synthetic follow-up correction')
            page.get_by_role('button',name='Create correction draft',exact=True).click()
            page.locator('[name=current_total]').fill('120.00');page.locator('[name=current_charge]').fill('120.00')
            page.locator('#acknowledge').check();page.get_by_role('button',name='Approve into ledger',exact=True).click()
            page.get_by_role('heading',name='Review queue',exact=True).wait_for()
            results.append('source evidence, saved correction, approval and immutable replacement history')

            # Batch picker: one new invoice, one duplicate and one malformed CSV.
            nav('Utility Inbox');page.get_by_role('button',name='Import files',exact=True).click()
            bad=work/'synthetic-invalid.csv';bad.write_text('not,canonical\n1,2\n')
            page.get_by_label('Source file',exact=True).set_input_files([str(fixture/'water.pdf'),str(fixture/'electricity-digital.pdf'),str(bad)])
            page.locator('#synthetic-confirm').check();page.get_by_role('button',name='Import for review',exact=True).click()
            page.get_by_role('button',name='Open Utility Inbox',exact=True).wait_for()
            expect(page.locator('#import-error')).to_contain_text('duplicate');expect(page.locator('#import-error')).to_contain_text('failed safely')
            shot('batch-results');page.get_by_role('button',name='Open Utility Inbox',exact=True).click()
            page.get_by_role('heading',name='Utility Inbox',exact=True).wait_for()
            water=next(row for row in get('/staged') if row['filename']=='water.pdf')
            page.get_by_role('button',name=f'Open draft {water["id"]}',exact=True).click()
            page.get_by_role('button',name='Reject draft',exact=True).click()
            results.append('isolated batch success, duplicate protection, safe failure and rejection')

            # Native drag/drop with synthetic File objects carried by DataTransfer.
            nav('Utility Inbox');page.get_by_role('button',name='Import files',exact=True).click()
            transfer=page.evaluate_handle('([bytes,name])=>{const data=new DataTransfer();data.items.add(new File([new Uint8Array(bytes)],name,{type:"application/pdf"}));return data;}',[list((fixture/'layout-v2.pdf').read_bytes()),'layout-v2.pdf'])
            page.locator('#dropzone').dispatch_event('drop',{'dataTransfer':transfer})
            page.locator('#synthetic-confirm').check();page.get_by_role('button',name='Import for review',exact=True).click()
            expect(page.locator('[name=current_total]')).to_have_value('100.00')
            expect(page.locator('.source-evidence')).to_contain_text('example_valley_v2')
            page.get_by_role('button',name='Reject draft',exact=True).click()
            upload('drift-missing-anchor.pdf')
            expect(page.locator('.source-evidence')).to_contain_text('Known Provider Unknown Layout')
            expect(page.locator('[data-evidence=invoice_total]')).to_contain_text('Requires review')
            shot('unknown-layout');page.get_by_role('button',name='Reject draft',exact=True).click()
            results.append('drag/drop, layout v2 and explicit layout drift')

            page.set_viewport_size({'width':390,'height':844})
            upload('scan-rotated.pdf')
            expect(page.locator('[name=current_total]')).to_have_value('100.00')
            page.locator('[data-evidence=invoice_total]').click()
            expect(page.locator('#evidence-error')).to_contain_text('Page rendered locally')
            assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
            expect(page.locator('#evidence-description')).to_be_in_viewport()
            shot('mobile-ocr-evidence')
            page.get_by_role('button',name='Hide source preview',exact=True).click()
            page.locator('#acknowledge').check();page.get_by_role('button',name='Approve into ledger',exact=True).click()
            page.get_by_role('heading',name='Review queue',exact=True).wait_for()
            results.append('mobile rotated OCR, evidence navigation and approval')

            nav('Utility Inbox');page.locator('summary').filter(has_text='Optional local inbox directory').click()
            page.locator('[name=directory]').fill(str(inbox));page.locator('#inbox-location-ack').check()
            page.get_by_role('button',name='Save inbox location',exact=True).click()
            page.locator('#inbox-scan-ack').check();page.get_by_role('button',name='Scan Inbox',exact=True).click()
            expect(page.locator('#scan-results')).to_contain_text('folder-propane.pdf')
            page.get_by_role('button',name='Refresh intake history',exact=True).click()
            propane=next(row for row in get('/staged') if row['filename']=='folder-propane.pdf')
            page.get_by_role('button',name=f'Open draft {propane["id"]}',exact=True).click()
            expect(page.locator('[name=usage_role]')).to_have_value('delivery')
            page.locator('#acknowledge').check();page.get_by_role('button',name='Approve into ledger',exact=True).click()
            page.get_by_role('heading',name='Review queue',exact=True).wait_for()
            results.append('explicit configured folder scan and delivered-fuel approval')

            nav('Bill completeness');page.locator('summary').filter(has_text='Confirm an expected').click()
            page.locator('[name=coverage-link]').select_option('0');page.locator('[name=first_month]').fill('2026-09')
            page.locator('[name=coverage-reason]').fill('Synthetic monthly expectation');page.locator('#coverage-ack').check()
            page.get_by_role('button',name='Save expectation',exact=True).click()
            page.locator('[name=coverage-month]').fill('2026-10');page.get_by_role('button',name='Show month',exact=True).click()
            expect(page.locator('.coverage-counts')).to_contain_text('Missing')
            assert get('/completeness?month=2026-10')['counts']['missing']==1
            shot('mobile-completeness');results.append('explicit cadence and experimental missing-bill view')

            page.set_viewport_size({'width':1440,'height':1000});nav('Utility Inbox')
            page.locator('#quality-panel summary').click();page.get_by_role('button',name='Show quality counts',exact=True).click()
            expect(page.locator('#quality-counts')).to_contain_text('Field Correction')
            download('Download extraction quality counts',work/'quality.json')
            nav('Privacy & support');download('Export approved ledger CSV',work/'ledger.csv');download('Download diagnostic JSON',work/'diagnostics.json')
            for sentinel in ('SYN-ACCOUNT','Imaginary Lane','bbox','folder-propane.pdf',str(inbox)):
                assert sentinel not in (work/'diagnostics.json').read_text()
            page.locator('#backup-ack').check();page.get_by_role('button',name='Create local backup',exact=True).click()
            download('Download private backup ZIP',work/'browser-backup.zip')
            page.get_by_role('button',name='Lock workspace').click();page.get_by_role('button',name='Open synthetic demo').wait_for()
            assert not errors,errors
            assert not failures,failures
            context.close()
        recovered=Store(work/'restored','demo');restore(recovered,work/'browser-backup.zip','demo')
        assert Ledger(recovered).export_csv()==(work/'ledger.csv').read_bytes();check(recovered)
        with server(recovered.directory,'demo',work,args.ocr_model_dir) as url:
            context=browser.new_context(viewport={'width':390,'height':844},accept_downloads=True);page=context.new_page()
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.on('console',lambda msg:errors.append(msg.text) if msg.type in {'error','warning'} else None)
            page.on('response',lambda response:failures.append((response.status,response.url)) if response.status>=400 else None)
            page.goto(url);page.get_by_role('button',name='Open synthetic demo').click()
            page.locator('nav').get_by_role('button',name='Utility Inbox',exact=True).click()
            page.get_by_role('heading',name='Utility Inbox',exact=True).wait_for()
            page.get_by_role('button',name=f'Open draft {item["id"]}',exact=True).first.click()
            expect(page.locator('[name=current_total]')).to_have_value('110')
            page.locator('[data-evidence=invoice_total]').click()
            expect(page.locator('#evidence-error')).to_contain_text('Page rendered locally')
            page.get_by_role('button',name='Lock workspace').click();context.close()
            assert not errors,errors
            assert not failures,failures
        results.append('private downloads, diagnostics, logout and restored evidence in native mobile Chrome')
        browser.close()
    print(json.dumps({'result':'passed','workflows':results,'unexpected_console_or_runtime_errors':0},indent=2))


if __name__=='__main__':main()
