#!/usr/bin/env python3
"""Foreground acquisition handoff in a fresh synthetic desktop/mobile browser.

Browser plugin not available: use the existing Playwright/owned Chrome path.
No mocked HTTP, staff session, portal or external service is used.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from playwright.sync_api import sync_playwright, expect
from scripts.native_usage_smoke import synthetic_server
from utilityos import SCHEMA_VERSION
from utilityos.config import Config
from utilityos.db import Store
from utilityos.operations import backup,restore,check


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir',required=True,type=Path)
    parser.add_argument('--browser-executable',required=True,type=Path)
    args=parser.parse_args();work=args.work_dir.resolve();Config(work,'demo').validate()
    if work.exists():raise SystemExit('ACQUISITION_CHECK_REQUIRES_NEW_DIRECTORY')
    work.mkdir(parents=True,mode=0o700);incoming=work/'incoming';incoming.mkdir()
    errors=[]
    sources={'watched-invoice.pdf':ROOT/'samples/intake/electricity-digital.pdf',
             'watched-water.xlsx':ROOT/'samples/generic-water-usage.xlsx',
             'watched-water.xml':ROOT/'samples/demo-water-intervals.xml'}
    with synthetic_server(work) as url, sync_playwright() as driver:
        browser=driver.chromium.launch(executable_path=str(args.browser_executable),headless=True)
        version=browser.version
        context=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
        try:
            page=context.new_page()
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.on('console',lambda msg:errors.append(msg.text) if msg.type in {'error','warning'} else None)
            def get(path):return page.evaluate('(path)=>fetch("/api"+path).then(r=>r.json())',path)
            def nav(name):page.locator('nav').get_by_role('button',name=name,exact=True).click()
            def fit():assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
            page.goto(url);page.get_by_role('button',name='Open synthetic demo',exact=True).click()
            page.get_by_role('heading',name='Campus utilities',exact=True).wait_for()
            baseline=get('/overview?month=2026-09')['total_cents']
            nav('Acquisition');expect(page.locator('#watcher-state')).to_contain_text('Disabled')
            page.get_by_label('Local acquisition folder',exact=True).fill(str(incoming))
            page.locator('#acquisition-folder-ack').check()
            page.get_by_role('button',name='Save acquisition folder',exact=True).click()
            expect(page.get_by_role('button',name='Enable watching',exact=True)).to_be_enabled()
            page.locator('#watcher-ack').check();page.get_by_role('button',name='Enable watching',exact=True).click()
            expect(page.locator('#watcher-state')).to_contain_text('Watching')
            page.get_by_role('button',name='Pause watching',exact=True).click()
            expect(page.locator('#watcher-state')).to_contain_text('Paused')
            for filename,source in sources.items():(incoming/filename).write_bytes(source.read_bytes())
            assert get('/acquisition')['history']==[]
            page.locator('#watcher-ack').check();page.get_by_role('button',name='Resume watching',exact=True).click()
            deadline=time.monotonic()+60
            while time.monotonic()<deadline:
                history=get('/acquisition')['history']
                if len(history)==3 and all(r['document_id'] for r in history):break
                page.wait_for_timeout(500)
            else:raise AssertionError('WATCHED_FILES_DID_NOT_REACH_REVIEW')
            assert get('/overview?month=2026-09')['total_cents']==baseline
            page.get_by_role('button',name='Refresh status',exact=True).click();fit()
            page.screenshot(path=str(work/'desktop-acquisition.png'),full_page=True)
            invoice=next(row for row in history if row['adapter']=='pdf_invoice')
            usage=next(row for row in history if row['adapter']=='usage_xlsx')
            xml=next(row for row in history if row['adapter']=='green_button')
            nav('Utility Inbox');page.locator(f'[data-intake-stage="{invoice["staged_ids"][0]}"]').click()
            page.locator('#acknowledge').check();page.get_by_role('button',name='Approve into ledger',exact=True).click()
            page.get_by_role('heading',name='Review queue',exact=True).wait_for()
            assert get('/overview?month=2026-09')['total_cents']==baseline+10000
            assert get(f'/staged/{xml["staged_ids"][0]}')['status']=='pending'
            nav('Utility Inbox');page.locator(f'[data-intake-usage="{usage["usage_ids"][0]}"]').click()
            page.get_by_role('heading',name='Retained source',exact=True).wait_for()
            page.locator('[name=sheet]').select_option('Water export')
            for key,value in {'header_row':3,'first_column':2,'last_column':7,'end_row':6}.items():page.locator(f'[name={key}]').fill(str(value))
            page.get_by_role('button',name='Inspect selected region',exact=True).click()
            expect(page.locator('[name=meter_column]')).to_contain_text('source_meter')
            meter=next(m['code'] for m in get('/inventory')['meters'] if m['commodity']=='water')
            for key,value in {'meter_code':meter,'commodity':'water','unit':'US_gal','semantics':'delta','meter_column':'source_meter',
                              'start_column':'start','end_column':'end','value_column':'value','unit_column':'unit','quality_column':'quality'}.items():
                page.locator(f'[name={key}]').select_option(value)
            page.locator('[name=source_meter]').fill('SYN-WATER-01');page.locator('#usage-reuse-layout').check()
            page.get_by_role('button',name='Save mapping and preview readings',exact=True).click()
            page.get_by_role('heading',name='Saved mapping preview',exact=False).wait_for()
            page.locator('#usage-ack').check();page.get_by_role('button',name='Approve operational readings',exact=True).click()
            page.get_by_role('heading',name='Recorded decision',exact=True).wait_for()
            assert get('/usage')['active_reading_count']==3
            assert get('/overview?month=2026-09')['total_cents']==baseline+10000
            with page.expect_download() as download:page.get_by_role('link',name='Download original workbook',exact=True).click()
            download.value.save_as(str(work/'retained-workbook.xlsx'))
            assert (work/'retained-workbook.xlsx').read_bytes()==sources['watched-water.xlsx'].read_bytes()
            nav('Utility Inbox');page.locator(f'[data-intake-stage="{xml["staged_ids"][0]}"]').click()
            page.get_by_role('heading',name='Review interval readings',exact=True).wait_for()
            expect(page.locator('#content')).to_contain_text('US_gal')
            page.get_by_role('combobox',name='Local water meter',exact=True).select_option(meter)
            page.locator('#interval-ack').check();page.get_by_role('button',name='Approve interval import',exact=True).click()
            page.get_by_role('heading',name='Interval data',exact=True).wait_for()
            page.locator('#meter-select').select_option(meter)
            expect(page.locator('#content')).to_contain_text('Values are interval quantities (US_gal)')
            fit();page.screenshot(path=str(work/'desktop-water-intervals.png'),full_page=True)
            assert get('/overview?month=2026-09')['total_cents']==baseline+10000
            page.set_viewport_size({'width':390,'height':844});nav('Acquisition');fit()
            page.get_by_role('button',name='Check installation health',exact=True).click()
            expect(page.locator('#acquisition-health-result')).to_contain_text('utilityos-health-v1')
            fit();page.screenshot(path=str(work/'mobile-acquisition.png'),full_page=True)
            page.get_by_role('button',name='Disable watching',exact=True).click()
            expect(page.locator('#watcher-state')).to_contain_text('Disabled')
            page.get_by_role('button',name='Lock workspace',exact=True).click()
            page.get_by_role('button',name='Open synthetic demo',exact=True).wait_for()
            assert context.request.get(url+'/api/acquisition').status==401
        finally:
            context.close();browser.close()
    assert all((incoming/name).read_bytes()==path.read_bytes() for name,path in sources.items())
    original=Store(work/'demo','demo');saved=backup(original);recovered=Store(work/'restored','demo');restore(recovered,saved,'demo')
    assert check(recovered)['schema_version']==SCHEMA_VERSION
    from utilityos.usage import UsageImport
    from utilityos.service import Ledger
    from utilityos.intake import Intake
    from utilityos.acquisition import Acquisition
    assert Acquisition(Intake(Ledger(recovered),'demo')).status()['state']=='disabled'
    # Workbook layout/meter reuse is independently exercised across two XLSX
    # files in native_usage_smoke; backup must retain the approved mapping too.
    with recovered.connect() as db:
        assert '"reuse_layout":true' in db.execute('SELECT payload FROM usage_previews LIMIT 1').fetchone()[0]
    with synthetic_server(work) as restarted_url:
        import urllib.request
        with urllib.request.urlopen(restarted_url+'/api/meta') as response:assert json.load(response)['version']=='0.6.0-rc3'
    assert not errors,errors
    result={'status':'passed','schema':SCHEMA_VERSION,'browser':version,'viewports':['1440x1000','390x844'],
            'browser_plugin':'not_available','native_http':True,'console_errors':errors,'servers_stopped':True,
            'checks':['watcher controls','stable PDF/XLSX/XML arrival','financial approval','separate operational approval',
                      'exact workbook download','water XML unit and separate approval','desktop/mobile no overflow','health','logout','source preservation','restart','backup restore']}
    (work/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
