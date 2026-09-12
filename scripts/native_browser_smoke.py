#!/usr/bin/env python3
"""Native Chrome/Chromium checks. Use --exercise-imports only on a fresh demo.

Browser plugin not available in the development session; uses the existing
Playwright development dependency, an isolated profile, and real localhost HTTP.
No transport bridge, mocked API, staff browser profile, or private workspace.
"""
import argparse
import csv
import io
import json
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit
import httpx
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--url', default='http://127.0.0.1:8765')
    p.add_argument('--browser-executable', type=Path)
    p.add_argument('--evidence-dir', type=Path)
    p.add_argument('--exercise-imports', action='store_true')
    p.add_argument('--milestone', action='store_true')
    p.add_argument('--headed', action='store_true')
    a = p.parse_args()
    u = urlsplit(a.url)
    if u.scheme != 'http' or u.hostname not in {'127.0.0.1', 'localhost'} or u.username or u.password:
        raise SystemExit('Only an explicitly local HTTP demo is supported.')
    if httpx.get(a.url + '/api/meta', timeout=10).json().get('mode') != 'demo':
        raise SystemExit('Refusing to run against a staff installation.')
    if a.evidence_dir:
        if a.evidence_dir.resolve().is_relative_to(ROOT):
            raise SystemExit('Keep test screenshots outside the source folder.')
        a.evidence_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        kwargs = {'headless': not a.headed}
        if a.browser_executable:
            kwargs['executable_path'] = str(a.browser_executable)
        browser = pw.chromium.launch(**kwargs)
        context = browser.new_context(viewport={'width': 1440, 'height': 1000}, accept_downloads=True)
        page = context.new_page()
        errors, responses, expected_failures = [], [], []
        page.on('pageerror', lambda err: errors.append(str(err)))
        page.on('console', lambda msg: errors.append(msg.text) if msg.type in {'error', 'warning'} else None)
        page.on('response', lambda r: responses.append((r.url, r.status)) if r.status >= 400 else None)
        page.on('dialog', lambda dialog: dialog.accept())
        def screenshot(name):
            assert not page.evaluate('document.documentElement.scrollWidth > innerWidth'), name
            if a.evidence_dir:
                page.screenshot(path=str(a.evidence_dir / (name + '.png')), full_page=True)
        def nav(label, heading):
            page.locator('nav').get_by_role('button', name=label).click()
            page.get_by_role('heading', name=heading, exact=True).wait_for()
            expect(page.locator('#content')).to_be_focused()
        def check_skip_link():
            # Navigation intentionally focuses main. Check the first available
            # keyboard target, then exercise the skip link's native activation.
            first = page.locator('a[href], button:not([disabled]), input:not([disabled]):not([type=hidden]), select:not([disabled]), textarea:not([disabled]), [tabindex="0"]').first
            expect(first).to_have_attribute('href', '#content')
            first.focus()
            expect(first).to_be_in_viewport()
            page.keyboard.press('Enter')
            expect(page.locator('#content')).to_be_focused()
        def check_import_dialog_keyboard():
            opener = page.get_by_role('button', name='Import a bill', exact=True)
            opener.click()
            dialog = page.get_by_role('dialog', name='Import a source file', exact=True)
            expect(dialog).to_be_visible()
            expect(dialog.locator('#import-error')).to_have_attribute('aria-live', 'polite')
            close = dialog.get_by_role('button', name='Close import', exact=True)
            last = dialog.get_by_role('link', name='New provider future bill', exact=True)
            # Let showModal provide the focus boundary and Escape behavior.
            # Do not require redundant application-level keyboard handlers.
            last.focus()
            page.keyboard.press('Tab')
            # Chrome may offer browser chrome before re-entering the modal.
            # The background page must never receive document focus.
            if not page.evaluate('document.hasFocus()'):
                page.keyboard.press('Tab')
            expect(close).to_be_focused()
            page.keyboard.press('Shift+Tab')
            if not page.evaluate('document.hasFocus()'):
                page.keyboard.press('Shift+Tab')
            expect(last).to_be_focused()
            page.keyboard.press('Escape')
            expect(dialog).to_have_count(0)
            expect(opener).to_be_focused()
        def download(label):
            with page.expect_download() as event:
                page.get_by_role('link', name=label, exact=True).click()
            return Path(event.value.path()).read_bytes()
        def upload(name, raw=None):
            nav('Overview', 'Campus utilities')
            page.get_by_role('button', name='Import a bill', exact=True).click()
            if raw is None and name=='demo-import.csv':
                for label,sample in [('CSV invoice','demo-import.csv'),('Electricity XML','demo-intervals.xml'),('PDF invoice','demo-invoice.pdf'),('Blank template','blank-bill-template.csv')]:
                    assert download(label)==(ROOT/'samples'/sample).read_bytes()
            if raw is None:
                page.get_by_label('Source file', exact=True).set_input_files(ROOT / 'samples' / name)
            else:
                page.get_by_label('Source file', exact=True).set_input_files({'name': name, 'mimeType': 'application/octet-stream', 'buffer': raw})
            page.locator('#synthetic-confirm').check()
            page.get_by_role('button', name='Import for review', exact=True).click()
        def approve():
            page.locator('#acknowledge').check()
            with page.expect_response(lambda response: '/api/staged/' in response.url and response.url.endswith('/approve')) as pending:
                page.get_by_role('button', name='Approve into ledger', exact=True).click()
            response = pending.value
            posted = response.request.post_data_json
            assert posted['acknowledge'] is True
            assert type(posted['revision']) is int and posted['revision'] >= 0
            assert response.status == 200
            page.get_by_role('heading', name='Review queue', exact=True).wait_for()
        page.goto(a.url, wait_until='networkidle')
        page.get_by_role('button', name='Open synthetic demo').click()
        page.get_by_role('heading', name='Campus utilities').wait_for()
        expect(page).to_have_title('Overview | SKS UtilityOS')
        assert page.url.rstrip('/') == a.url.rstrip('/')
        expect(page.locator('#content')).to_be_focused()
        check_skip_link()
        check_import_dialog_keyboard()
        assert all(c['httpOnly'] and c['sameSite'] == 'Strict' for c in context.cookies() if c['name'] == 'utilityos_session')
        assert page.evaluate("async () => {const {quantity}=await import('/modules/ui.js'); return [quantity('0.000000001'),quantity('1234.123456789'),quantity('1E-9')];}") == ['0.000000001','1,234.123456789','0.000000001']
        screenshot('desktop')
        if a.exercise_imports:
            upload('demo-import.csv')
            page.get_by_role('heading', name='SYN-NEW-WORKSHOP').wait_for()
            assert download('Download original locally') == (ROOT / 'samples/demo-import.csv').read_bytes()
            expect(page.locator('#flags')).to_have_attribute('aria-live', 'polite')
            page.get_by_role('button', name='Check fields', exact=True).click()
            expect(page.locator('#flags')).not_to_contain_text('must equal')
            approve()
            upload('demo-import.csv')
            expect(page.locator('#import-error')).to_contain_text('exact file is already')
            expected_failures.append(('/api/import', 422))
            page.get_by_role('button', name='Close import').click()
            upload('demo-invoice.pdf')
            page.get_by_role('heading', name='Enter the source invoice').wait_for()
            assert download('Download original locally') == (ROOT / 'samples/demo-invoice.pdf').read_bytes()
            # Values transcribed from the supplied synthetic PDF, not extracted
            # by the product. The fixture explicitly prints end-exclusive dates.
            fields = {'provider': 'Example Water', 'account_alias': 'DEMO-W03 account',
                      'invoice_number': 'SYN-PDF-W03-202608', 'bill_date': '2026-09-05', 'current_total': '125.80',
                      'meter_code': 'DEMO-W03', 'building': 'Demo Workshop',
                      'period_start': '2026-08-01', 'period_end': '2026-09-01', 'usage': '6200', 'current_charge': '125.80'}
            page.locator('#bill-editor [name=commodity]').select_option('water')
            page.locator('#bill-editor [name=unit]').select_option('gal')
            page.locator('#bill-editor [name=read_type]').select_option('actual')
            for name, value in fields.items():
                page.locator(f'#bill-editor [name={name}]').fill(value)
            page.get_by_role('button', name='Check fields', exact=True).click()
            screenshot('pdf-review')
            if a.milestone:
                page.get_by_role('button', name='Save draft', exact=True).click()
                page.get_by_role('heading', name='SYN-PDF-W03-202608', exact=True).wait_for()
                expect(page.locator('[name=usage]')).to_have_value('6200')
            approve()
            nav('Review queue', 'Review queue')
            page.get_by_role('button', name='All imports', exact=True).click()
            # The review list must show the staff-entered PDF reference and total.
            if a.milestone:
                expect(page.locator('#review-list')).to_contain_text('SYN-PDF-W03-202608')
            upload('demo-intervals.xml')
            page.get_by_role('heading', name='Review interval readings').wait_for()
            assert download('Download original locally') == (ROOT/'samples/demo-intervals.xml').read_bytes()
            page.locator('[name=meter_code]').select_option('DEMO-E01')
            page.locator('#interval-ack').check()
            page.get_by_role('button', name='Approve interval import').click()
            page.get_by_role('heading', name='Interval data', exact=True).wait_for()
            screenshot('intervals')
            upload('reject.csv', (ROOT / 'samples/demo-import.csv').read_bytes().replace(b'SYN-NEW-WORKSHOP', b'SYN-REJECT'))
            page.get_by_role('heading', name='SYN-REJECT').wait_for()
            page.get_by_role('button', name='Reject draft', exact=True).click()
            page.get_by_role('heading', name='Review queue', exact=True).wait_for()
            page.get_by_role('button', name='All imports', exact=True).click()
            expect(page.get_by_role('row').filter(has_text='SYN-REJECT')).to_contain_text('Rejected')
            upload('reject.xml', (ROOT / 'samples/demo-intervals.xml').read_bytes() + b'\n')
            page.get_by_role('heading', name='Review interval readings').wait_for()
            page.get_by_role('button', name='Reject draft', exact=True).click()
            page.get_by_role('heading', name='Review queue', exact=True).wait_for()
            if a.milestone:
                nav('Invoice ledger', 'Invoice ledger')
                page.get_by_role('row').filter(has_text='SYN-NEW-WORKSHOP').get_by_role('button', name='Open invoice').click()
                page.get_by_role('button', name='Correct approved invoice').click()
                page.get_by_label('Reason', exact=True).fill('Synthetic transcription correction')
                page.get_by_role('button', name='Create correction draft').click()
                page.get_by_role('button', name='Save draft', exact=True).wait_for()
                page.locator('[name=current_total]').fill('500.00')
                page.locator('[name=current_charge]').fill('500.00')
                page.locator('[name=usage]').fill('2000')
                page.get_by_role('button', name='Save draft', exact=True).click()
                expect(page.locator('[name=current_total]')).to_have_value('500.00')
                page.get_by_role('button', name='Check fields', exact=True).click()
                expect(page.locator('#flags')).to_contain_text('pass the pilot')
                screenshot('correction-review')
                approve()
                nav('Invoice ledger', 'Invoice ledger')
                expect(page.get_by_role('row').filter(has_text='SYN-NEW-WORKSHOP')).to_contain_text('$500.00')
                page.get_by_role('row').filter(has_text='SYN-NEW-WORKSHOP').get_by_role('button', name='Open invoice').click()
                expect(page.get_by_role('heading', name='Invoice history · Active')).to_be_visible()
                expect(page.locator('#content')).to_contain_text('Superseded')
                screenshot('invoice-history')
                # A separate supplier rebill retains its own original source.
                upload('synthetic-rebill.csv', (ROOT / 'samples/demo-import.csv').read_bytes().replace(b'579.80', b'499.80'))
                page.get_by_role('button', name='Use as replacement / rebill').click()
                page.get_by_label('Original active invoice').select_option(label='Example Electric · DEMO-E05 account · SYN-NEW-WORKSHOP-202608 · $500.00')
                page.get_by_label('Reason for replacement').fill('Synthetic supplier rebill')
                page.get_by_role('button', name='Save replacement link').click()
                expect(page.get_by_role('button', name='Change replacement link')).to_be_visible()
                approve()
                credit=(ROOT / 'samples/demo-import.csv').read_bytes().replace(b'SYN-NEW-WORKSHOP',b'SYN-CREDIT').replace(b'2026-09-05',b'2026-10-05').replace(b'2860,kWh',b'0,kWh').replace(b'579.80',b'-50.00').replace(b'consumption',b'charges_only')
                upload('synthetic-credit.csv',credit)
                page.get_by_role('heading',name='SYN-CREDIT-202608',exact=True).wait_for()
                approve()
                nav('Overview','Campus utilities')
                page.locator('#month-filter').select_option('2026-10')
                expect(page.locator('.metrics')).to_contain_text('-$50')
                axis_y=page.locator('.trend .chart-axis').evaluate_all("nodes => nodes.map(n=>Number(n.getAttribute('y'))).sort((a,b)=>a-b)")
                assert all(b-a>=18 for a,b in zip(axis_y,axis_y[1:])),axis_y
                screenshot('negative-credit-chart')
                # Mobile correction rejection and cancellation both preserve history.
                page.set_viewport_size({'width':390,'height':844})
                nav('Invoice ledger', 'Invoice ledger')
                page.get_by_role('row').filter(has_text='SYN-NEW-WORKSHOP').get_by_role('button', name='Open invoice').click()
                page.get_by_role('button', name='Correct approved invoice').click()
                page.get_by_label('Reason', exact=True).fill('Synthetic abandoned draft')
                page.get_by_role('button', name='Create correction draft').click()
                page.get_by_role('button', name='Reject draft', exact=True).click()
                page.get_by_role('heading', name='Review queue', exact=True).wait_for()
                nav('Invoice ledger', 'Invoice ledger')
                expect(page.get_by_role('row').filter(has_text='SYN-NEW-WORKSHOP')).to_contain_text('$499.80')
                page.get_by_role('row').filter(has_text='SYN-PDF-W03').get_by_role('button', name='Open invoice').click()
                page.get_by_role('button', name='Cancel invoice', exact=True).click()
                page.get_by_label('Reason', exact=True).fill('Synthetic cancellation drill')
                page.locator('#cancel-confirm').check()
                page.get_by_role('button', name='Confirm cancellation').click()
                expect(page.get_by_role('heading', name='Invoice history · Cancelled')).to_be_visible()
                screenshot('mobile-cancelled-invoice')
                nav('Utility inventory', 'Utility inventory')
                page.get_by_role('row').filter(has_text='DEMO-E05').get_by_role('button', name='Edit mapping').click()
                page.get_by_label('Building label', exact=True).fill('Synthetic corrected workshop')
                page.get_by_label('Reason', exact=True).fill('Synthetic mapping drill')
                page.locator('#mapping-ack').check()
                page.get_by_role('button', name='Save mapping change').click()
                expect(page.get_by_role('row').filter(has_text='DEMO-E05').filter(has=page.get_by_role('button',name='Edit mapping'))).to_contain_text('Synthetic corrected workshop')
                page.locator('p').filter(has_text='Synthetic corrected workshop').get_by_role('button',name='Rename building').click()
                page.get_by_label('Building label',exact=True).fill('Synthetic renamed workshop')
                page.get_by_label('Reason',exact=True).fill('Synthetic label correction')
                page.locator('#mapping-ack').check()
                page.get_by_role('button',name='Save mapping change').click()
                expect(page.get_by_role('row').filter(has_text='DEMO-E05').filter(has=page.get_by_role('button',name='Edit mapping'))).to_contain_text('Synthetic renamed workshop')
                screenshot('mobile-mapping-history')
                nav('Overview', 'Campus utilities')
                page.locator('#month-filter').select_option('2026-09')
                expect(page.locator('#content')).to_contain_text('$499.80')
                screenshot('mobile-corrected-overview')
                page.set_viewport_size({'width':1440,'height':1000})
        nav('Privacy & support', 'Privacy & support')
        diagnostic = json.loads(download('Download diagnostic JSON'))
        assert set(diagnostic) == {'app', 'version', 'schema_version', 'mode', 'runtime', 'features', 'checks', 'support_instructions'}
        exported = download('Export approved ledger CSV')
        assert len(list(csv.DictReader(io.StringIO(exported.decode('utf-8-sig'))))) >= 45
        if a.milestone:
            page.locator('#backup-ack').check()
            page.get_by_role('button',name='Create local backup',exact=True).click()
            page.get_by_role('link',name='Download private backup ZIP').wait_for()
            backup_bytes=download('Download private backup ZIP')
            assert backup_bytes.startswith(b'PK')
            if a.evidence_dir:
                (a.evidence_dir/'browser-backup.zip').write_bytes(backup_bytes)
            expect(page.locator('#content')).to_contain_text('Restore with the app stopped')
        screenshot('support')
        page.set_viewport_size({'width': 390, 'height': 844})
        for label, heading in [('Overview', 'Campus utilities'), ('Review queue', 'Review queue'), ('Invoice ledger','Invoice ledger'), ('Utility inventory', 'Utility inventory'), ('Interval data', 'Interval data'), ('Privacy & support', 'Privacy & support')]:
            nav(label, heading)
            if label == 'Overview':
                check_skip_link()
                check_import_dialog_keyboard()
            screenshot('mobile-' + label.split()[0].lower())
        assert len(download('Export approved ledger CSV')) > 0
        if a.exercise_imports and a.milestone:
            rows=list(csv.DictReader(io.StringIO(download('Export approved ledger CSV').decode('utf-8-sig'))))
            september=sum(Decimal(r['current_charge']) for r in rows if r['bill_date'].startswith('2026-09'))
            assert september==Decimal('499.80'),september
            assert not any(r['invoice_number']=='SYN-PDF-W03-202608' for r in rows)
        page.get_by_role('button', name='Lock workspace').click()
        page.get_by_role('button', name='Open synthetic demo').wait_for()
        assert not any(c['name'] == 'utilityos_session' for c in context.cookies())
        # Negative checks intentionally return 422. Browser resource errors for
        # those requests are expected, but page errors and all other errors fail.
        actual = [(urlsplit(url).path, code) for url, code in responses]
        assert sorted(actual) == sorted(expected_failures), actual
        expected_console = 'Failed to load resource: the server responded with a status of 422 (Unprocessable Entity)'
        unexpected = [e for e in errors if e not in {expected_console, expected_console.replace('Unprocessable Entity', 'Unprocessable Content')}]
        assert not unexpected, unexpected
        assert len(errors) <= len(expected_failures), errors
        print(json.dumps({'result': 'passed', 'browser': browser.version, 'native_http': True, 'viewports': ['1440x1000', '390x844'], 'imports_exercised': a.exercise_imports, 'unexpected_console_or_runtime_errors': 0, 'expected_rejections': actual}, indent=2))
        browser.close()

if __name__ == '__main__':
    main()
