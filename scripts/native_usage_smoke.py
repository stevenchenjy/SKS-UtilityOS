#!/usr/bin/env python3
"""Native mapped usage check with NEW synthetic data, local HTTP and owned Chrome.

Browser plugin/browser skill not available; project Playwright is used with an
isolated browser profile, no transport bridge or mocked application API.
A success receipt is written only after browser, driver and server shutdown.
"""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from playwright.sync_api import sync_playwright, expect
from utilityos.config import Config
from utilityos.db import Store
from utilityos.operations import check


@contextmanager
def synthetic_server(work):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0))
        port = sock.getsockname()[1]
    with (work/'server.log').open('w') as output:
        process = subprocess.Popen([sys.executable,str(ROOT/'run.py'),'demo','--data-dir',str(work/'demo'),'--port',str(port)],stdout=output,stderr=output)
        url = f'http://127.0.0.1:{port}'
        try:
            for _ in range(150):
                if process.poll() is not None:
                    raise RuntimeError('SYNTHETIC_APP_FAILED_TO_START')
                try:
                    with urllib.request.urlopen(url+'/api/meta',timeout=1) as response:
                        assert json.load(response)['mode'] == 'demo'
                    break
                except OSError:
                    time.sleep(.1)
            else:
                raise RuntimeError('SYNTHETIC_APP_START_TIMEOUT')
            yield url
        finally:
            if process.poll() is None:
                process.send_signal(signal.SIGINT)
            try:
                code = process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                raise RuntimeError('SYNTHETIC_APP_STOP_TIMEOUT') from None
            if code != 0:
                raise RuntimeError('SYNTHETIC_APP_NONZERO_EXIT')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir',type=Path,required=True)
    parser.add_argument('--browser-executable',type=Path,required=True)
    args = parser.parse_args()
    work = args.work_dir.resolve()
    Config(work,'demo').validate()
    if work.exists():
        raise SystemExit('USAGE_CHECK_REQUIRES_NEW_EXTERNAL_DIRECTORY')
    work.mkdir(parents=True,mode=0o700)
    errors, failures = [], []
    raw = (ROOT/'samples/generic-water-usage.csv').read_bytes()
    with synthetic_server(work) as url:
        with sync_playwright() as driver:
            browser = driver.chromium.launch(executable_path=str(args.browser_executable),headless=True)
            try:
                version = browser.version
                context = browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
                try:
                    page = context.new_page()
                    page.on('pageerror',lambda error:errors.append(str(error)))
                    page.on('console',lambda msg:errors.append(msg.text) if msg.type in {'warning','error'} else None)
                    page.on('response',lambda response:failures.append((response.status,response.url)) if response.status>=400 else None)
                    def get(path):
                        return page.evaluate('(path)=>fetch("/api"+path).then(r=>r.json())',path)
                    def no_overflow():
                        assert not page.evaluate('document.documentElement.scrollWidth>innerWidth'),page.url
                    def listing():
                        page.locator('nav').get_by_role('button',name='Mapped usage files',exact=True).click()
                        page.get_by_role('heading',name='Mapped usage files',exact=True).wait_for()
                        no_overflow()
                    def upload(name,contents):
                        listing()
                        page.get_by_label('Usage CSV file',exact=True).set_input_files({'name':name,'mimeType':'text/csv','buffer':contents})
                        page.locator('#usage-synthetic').check()
                        page.get_by_role('button',name='Upload usage CSV for mapping',exact=True).click()
                        page.get_by_role('heading',name='Retained source',exact=True).wait_for()
                        no_overflow()
                        return get('/usage')['items'][0]['id']
                    def mapping():
                        for name,value in {'meter_code':meter,'commodity':'water','unit':'US_gal','semantics':'delta','meter_column':'source_meter',
                                           'start_column':'start','end_column':'end','value_column':'value','unit_column':'unit','quality_column':'quality'}.items():
                            page.locator(f'[name={name}]').select_option(value)
                        page.locator('[name=source_meter]').fill('SYN-WATER-01')
                        page.get_by_role('button',name='Save mapping and preview readings',exact=True).click()
                        page.get_by_role('heading',name='Saved mapping preview',exact=False).wait_for()
                        no_overflow()
                    def approve():
                        page.locator('#usage-ack').check()
                        page.get_by_role('button',name='Approve operational readings',exact=True).click()
                        page.get_by_role('heading',name='Recorded decision',exact=True).wait_for()
                        expect(page.locator('#content')).to_contain_text('Approved')
                        no_overflow()
                    def withdraw():
                        page.locator('summary').filter(has_text='Withdraw this approved source').click()
                        page.locator('[name=usage-reason]').fill('Synthetic source correction after review')
                        page.locator('#usage-close-ack').check()
                        page.get_by_role('button',name='Withdraw approved usage source',exact=True).click()
                        page.get_by_role('heading',name='Review this retained source again',exact=True).wait_for()
                        no_overflow()
                    page.goto(url)
                    page.get_by_role('button',name='Open synthetic demo',exact=True).click()
                    page.get_by_role('heading',name='Campus utilities',exact=True).wait_for()
                    baseline = get('/overview')
                    meter = next(m['code'] for m in get('/inventory')['meters'] if m['commodity']=='water')
                    first = upload('fictional-water.csv',raw)
                    mapping()
                    page.get_by_role('heading',name='Saved mapping preview',exact=False).scroll_into_view_if_needed()
                    page.screenshot(path=str(work/'desktop-preview.png'))
                    approve()
                    assert get('/usage')['active_reading_count'] == 3
                    assert get('/overview') == baseline
                    upload('renamed-same-source.csv',raw)
                    assert len(get('/usage')['items']) == 1
                    with page.expect_download() as download:
                        page.get_by_role('link',name='Download original CSV',exact=True).click()
                    destination = work/'original.csv'
                    download.value.save_as(str(destination))
                    assert destination.read_bytes() == raw
                    page.set_viewport_size({'width':390,'height':844})
                    withdraw()
                    assert get('/usage')['active_reading_count'] == 0
                    page.locator('[name=usage-reattempt-reason]').fill('Synthetic review of unchanged original')
                    page.locator('#usage-reattempt-ack').check()
                    page.get_by_role('button',name='Start new mapping review',exact=True).click()
                    page.get_by_role('heading',name='Explicit mapping',exact=True).wait_for()
                    second = get('/usage')['items'][0]['id']
                    assert get(f'/usage/{second}')['document_id'] == get(f'/usage/{first}')['document_id']
                    mapping()
                    page.get_by_role('heading',name='Saved mapping preview',exact=False).scroll_into_view_if_needed()
                    page.screenshot(path=str(work/'mobile-preview.png'))
                    approve()
                    correction = upload('fictional-corrected.csv',raw.replace(b'12.50',b'15.50'))
                    mapping()
                    expect(page.get_by_role('button',name='Approve operational readings',exact=True)).to_be_disabled()
                    page.get_by_role('button',name=f'Inspect import {second}',exact=True).click()
                    page.get_by_role('heading',name='Recorded decision',exact=True).wait_for()
                    withdraw()
                    listing()
                    page.get_by_role('button',name=f'Inspect import {correction}',exact=True).click()
                    page.get_by_role('heading',name='Explicit mapping',exact=True).wait_for()
                    mapping()
                    approve()
                    assert get('/usage')['active_reading_count'] == 3
                    assert get('/overview') == baseline
                    listing()
                    page.get_by_role('heading',name='Active operational readings',exact=True).scroll_into_view_if_needed()
                    page.screenshot(path=str(work/'mobile-readings.png'))
                    assert page.url == url+'/'
                    assert page.title() == 'Mapped usage files | SKS UtilityOS'
                    assert not page.locator('body').filter(has_text='Internal Server Error').count()
                    page.get_by_role('button',name='Lock workspace',exact=True).click()
                    page.get_by_role('button',name='Open synthetic demo',exact=True).wait_for()
                    assert not any(c['name']=='utilityos_session' for c in context.cookies())
                    assert errors == [],errors
                    assert failures == [],failures
                finally:
                    context.close()
            finally:
                browser.close()
    integrity = check(Store(work/'demo','demo',initialize=False))
    result = {'result':'passed','browser':version,'native_http':True,'viewports':['1440x1000','390x844'],
              'workflows':['mapping preview','literal confirmation approval','same-source deduplication','exact original download',
                           'withdrawal and same-source reattempt','conflicting correction reconciliation','invoice totals unchanged','logout'],
              'unexpected_console_or_runtime_errors':len(errors),'unexpected_http_failures':failures,
              'owned_browser_driver_shutdown':'completed','server_exit_code':0,'integrity':integrity}
    (work/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
