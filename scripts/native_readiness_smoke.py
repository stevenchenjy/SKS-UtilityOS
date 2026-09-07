#!/usr/bin/env python3
"""Native 0.3 checks in NEW, developer-created synthetic workspaces only.

Creates its own local demo, larger campus and synthetic staff fixture. It never
accepts an existing data directory, staff profile, external URL or credentials.
"""
from contextlib import contextmanager
from pathlib import Path
import argparse
import csv
import io
import json
import signal
import socket
import subprocess
import sys
import time
import urllib.request
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from playwright.sync_api import sync_playwright,expect
from utilityos.config import Config
from utilityos.db import Store
from utilityos.service import Ledger
from utilityos.security import set_password,DEMO_PASSWORD
from utilityos.operations import check
from utilityos.audit import acting_as
from run import seed_demo
from scripts.synthetic_campus import seed


@contextmanager
def server(directory,mode,work,ocr_model_dir=None):
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    with (work/(directory.name+'-server.log')).open('w') as output:
        command=[sys.executable,str(ROOT/'run.py'),mode,'--data-dir',str(directory),'--port',str(port)]
        if ocr_model_dir:command+=['--ocr-model-dir',str(ocr_model_dir)]
        process=subprocess.Popen(command,stdout=output,stderr=output)
        url=f'http://127.0.0.1:{port}'
        try:
            for _ in range(150):
                if process.poll() is not None:raise RuntimeError('Synthetic app did not start')
                try:
                    with urllib.request.urlopen(url+'/api/meta',timeout=1) as response:
                        assert json.load(response)['mode']==mode
                    break
                except OSError:time.sleep(.1)
            else:raise RuntimeError('Synthetic app start timed out')
            yield url
        finally:
            process.send_signal(signal.SIGINT)
            try:process.wait(timeout=15)
            except subprocess.TimeoutExpired:process.kill();process.wait()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir',required=True,type=Path)
    parser.add_argument('--browser-executable',required=True,type=Path)
    parser.add_argument('--headed',action='store_true')
    args=parser.parse_args();work=args.work_dir.expanduser().resolve()
    Config(work,'demo').validate()
    Config(work/'staff','staff').validate()
    if work.exists():raise SystemExit('READINESS_CHECK_REQUIRES_NEW_EXTERNAL_DIRECTORY')
    work.mkdir(parents=True,mode=0o700)
    results=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path=str(args.browser_executable),headless=not args.headed)
        for scenario in ['recovery','campus','staff']:
            directory=work/scenario;mode='staff' if scenario=='staff' else 'demo'
            ledger=Ledger(Store(directory,mode));password='synthetic-readiness-passphrase' if mode=='staff' else DEMO_PASSWORD
            set_password(ledger.store,password)
            raw=(ROOT/'samples/demo-import.csv').read_bytes()
            if scenario=='recovery':
                seed_demo(ledger)
                raw=raw.replace(b'SYN-NEW-WORKSHOP',b'SYN-RECOVERY').replace(b'2026-09-01',b'2026-10-01').replace(b'2026-08-01',b'2026-09-01').replace(b'2026-09-05',b'2026-10-05')
                item=ledger.import_file('synthetic-recovery.csv',raw)['staged_ids'][0]
                payload=ledger.stage(item)['payload'];payload['current_total']=payload['lines'][0]['current_charge']='50.00'
                ledger.save_draft(item,payload,0)
                with ledger.store.connect() as db:db.execute('UPDATE staged SET review_payload=? WHERE id=?',('{synthetically damaged',item))
            elif scenario=='campus':
                with acting_as('synthetic_generator'):seed(ledger)
            else:
                item=ledger.import_file('synthetic-staff.csv',raw)['staged_ids'][0]
                ledger.approve_bill(item,ledger.stage(item)['payload'],True)
            with server(directory,mode,work) as url:
                context=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
                page=context.new_page();errors=[];failed=[];expected_failures=0;times=[]
                page.on('pageerror',lambda e:errors.append(e.stack or str(e)))
                page.on('console',lambda msg:errors.append(msg.text) if msg.type in {'error','warning'} else None)
                page.on('response',lambda r:failed.append(r.status) if r.status>=400 else None)
                page.on('dialog',lambda d:d.accept())
                def nav(label,heading):
                    start=time.perf_counter()
                    page.locator('nav').get_by_role('button',name=label).click()
                    page.get_by_role('heading',name=heading,exact=True).wait_for()
                    times.append(time.perf_counter()-start)
                    assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
                def shot(name):page.screenshot(path=str(work/(scenario+'-'+name+'.png')))
                # Deliver an unchanged real audit response after a short delay.
                # This exercises logout/navigation while a view is still loading;
                # no API payload or server/authentication behavior is mocked.
                page.add_init_script("""const localFetch=window.fetch;window.fetch=async(...args)=>{
                  const result=await localFetch(...args);
                  if(String(args[0]).startsWith('/api/audit'))await new Promise(resolve=>setTimeout(resolve,350));
                  return result;
                };""")
                page.goto(url)
                if mode=='staff':page.get_by_label('Local app passphrase',exact=True).fill(password)
                page.get_by_role('button',name='Unlock local workspace' if mode=='staff' else 'Open synthetic demo',exact=True).click()
                page.get_by_role('heading',name='Campus utilities',exact=True).wait_for()
                if scenario=='recovery':
                    nav('Review queue','Review queue')
                    page.get_by_role('row').filter(has_text='Damaged review data').get_by_role('button',name='Review',exact=True).click()
                    page.get_by_role('heading',name='Review data needs recovery',exact=True).wait_for();shot('damaged')
                    expect(page.get_by_role('button',name='Recover saved draft')).to_be_disabled()
                    page.locator('#recover-ack').check();page.get_by_role('button',name='Recover saved draft').click()
                    page.get_by_role('heading',name='SYN-RECOVERY-202608',exact=True).wait_for()
                    expect(page.locator('[name=current_total]')).to_have_value('50.00')
                    expect(page.locator('#acknowledge')).not_to_be_checked()
                    page.locator('summary').filter(has_text='Source provenance').click();shot('recovered')
                    page.locator('#acknowledge').check();page.get_by_role('button',name='Approve into ledger',exact=True).click()
                    page.get_by_role('heading',name='Review queue',exact=True).wait_for()
                elif scenario=='campus':
                    assert page.locator('#month-filter option').count()==24
                    nav('Invoice ledger','Invoice ledger')
                    expect(page.locator('#invoice-page')).to_have_text('1–100 of 1923')
                    page.get_by_role('button',name='Next invoices').click();expect(page.locator('#invoice-page')).to_have_text('101–200 of 1923')
                    page.get_by_role('button',name='Previous invoices').click()
                    page.get_by_label('Find an invoice').fill('SYN-00-01-electricity')
                    expect(page.locator('#invoice-page')).to_have_text('1–2 of 2')
                    page.get_by_role('row').filter(has=page.get_by_text('SYN-00-01-electricity',exact=True)).get_by_role('button',name='Open invoice',exact=True).click()
                    page.get_by_role('heading',name='Invoice history · Active',exact=True).wait_for();shot('old-invoice')
                else:
                    nav('Invoice ledger','Invoice ledger')
                    page.get_by_role('button',name='Open invoice',exact=True).click()
                    page.get_by_role('button',name='Correct approved invoice').click()
                    page.get_by_label('Reason',exact=True).fill('Synthetic staff correction')
                    page.get_by_role('button',name='Create correction draft').click()
                    page.get_by_label('Confirm local app passphrase',exact=True).wait_for()
                    page.locator('[name=current_total]').fill('500.00');page.locator('[name=current_charge]').fill('500.00')
                    page.locator('#acknowledge').check();page.get_by_role('button',name='Approve into ledger',exact=True).click()
                    expect(page.locator('#flags')).to_contain_text('Current passphrase required');expected_failures=1
                    page.get_by_label('Confirm local app passphrase',exact=True).fill(password)
                    page.get_by_role('button',name='Approve into ledger',exact=True).click()
                    page.get_by_role('heading',name='Review queue',exact=True).wait_for()
                    page.set_viewport_size({'width':390,'height':844})
                    nav('Invoice ledger','Invoice ledger');page.get_by_role('button',name='Open invoice',exact=True).click()
                    page.get_by_role('button',name='Cancel invoice',exact=True).click()
                    page.get_by_label('Reason',exact=True).fill('Synthetic staff cancellation')
                    page.locator('#cancel-confirm').check();page.get_by_label('Confirm local app passphrase',exact=True).fill(password);shot('confirm')
                    page.get_by_role('button',name='Confirm cancellation').click()
                    page.get_by_role('heading',name='Invoice history · Cancelled',exact=True).wait_for()
                nav('Privacy & support','Privacy & support')
                page.get_by_role('heading',name='Local audit history',exact=True).scroll_into_view_if_needed()
                if scenario=='recovery':expect(page.locator('#audit-events')).to_contain_text('Recover Draft')
                if scenario=='staff':expect(page.locator('#audit-events')).to_contain_text('passphrase confirmed')
                shot('audit')
                if scenario=='campus':
                    first=page.locator('#audit-events tbody tr').first.inner_text()
                    page.get_by_role('button',name='Load older audit events').click()
                    expect(page.locator('#audit-events tbody tr').first).not_to_have_text(first)
                for width,height in [(1440,1000),(390,844)]:
                    page.set_viewport_size({'width':width,'height':height})
                    for label,heading in [('Overview','Campus utilities'),('Invoice ledger','Invoice ledger'),('Review queue','Review queue'),('Utility inventory','Utility inventory'),('Interval data','Interval data'),('Privacy & support','Privacy & support')]:nav(label,heading)
                    with page.expect_download() as download:page.get_by_role('link',name='Export approved ledger CSV',exact=True).click()
                    rows=list(csv.DictReader(io.StringIO(Path(download.value.path()).read_bytes().decode('utf-8-sig'))))
                    assert len(rows)==(1923 if scenario=='campus' else 46 if scenario=='recovery' else 0)
                    if scenario=='campus':
                        nav('Overview','Campus utilities');shot('overview-'+str(width))
                page.get_by_role('button',name='Lock workspace').click()
                page.get_by_role('button',name='Unlock local workspace' if mode=='staff' else 'Open synthetic demo',exact=True).wait_for()
                page.wait_for_timeout(450) # Observe completion of the delayed real response after logout.
                assert not context.cookies()
                assert failed==[422]*expected_failures,failed
                unexpected=[e for e in errors if not (e.startswith('Failed to load resource:') and '422' in e)]
                assert not unexpected,unexpected
                assert len(errors)<=expected_failures,errors
                context.close()
            assert check(ledger.store)['audit']=='ok'
            results.append({'scenario':scenario,'result':'passed','unexpected_runtime_errors':0,'expected_rejections':expected_failures,'max_navigation_seconds':round(max(times),3)})
        browser.close()
    (work/'results.json').write_text(json.dumps(results,indent=2))
    print(json.dumps(results,indent=2))

if __name__=='__main__':main()
