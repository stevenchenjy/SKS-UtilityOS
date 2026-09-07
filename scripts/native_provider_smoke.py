#!/usr/bin/env python3
"""Real Chrome setup/review test. Writes only NEW external synthetic workspaces."""
import argparse
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
from playwright.sync_api import sync_playwright, expect
from scripts.native_readiness_smoke import server
from utilityos.config import Config
from utilityos.db import Store
from utilityos.operations import restore, check
from provider_helpers import CASES, CORPUS, author


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', type=Path, required=True)
    parser.add_argument('--browser-executable', type=Path, required=True)
    parser.add_argument('--ocr-model-dir', type=Path, required=True)
    parser.add_argument('--headed', action='store_true');args=parser.parse_args()
    work=args.work_dir.resolve();Config(work,'demo').validate()
    if work.exists():raise SystemExit('NATIVE_PROVIDER_CHECK_REQUIRES_NEW_EXTERNAL_DIRECTORY')
    work.mkdir(parents=True,mode=0o700)
    errors, failures, outcomes=[],[],[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path=str(args.browser_executable),headless=not args.headed)
        with server(work/'demo','demo',work,args.ocr_model_dir) as url:
            context=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
            page=context.new_page()
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.on('console',lambda msg:errors.append(msg.text) if msg.type in {'error','warning'} else None)
            page.on('response',lambda response:failures.append((response.status,response.url)) if response.status>=400 else None)
            page.on('dialog',lambda d:d.accept())
            def get(path):return page.evaluate('(p)=>fetch("/api"+p).then(r=>r.json())',path)
            def nav(label):
                page.locator('nav').get_by_role('button',name=label).click()
                page.get_by_role('heading',name=label,exact=True).wait_for()
                assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
            def stage(name):return next(row for row in get('/staged') if row['filename']==name+'.pdf')
            def upload(name):
                nav('Utility Inbox');page.get_by_role('button',name='Import files',exact=True).click()
                page.get_by_label('Source file',exact=True).set_input_files(str(CORPUS/(name+'.pdf')))
                page.locator('#synthetic-confirm').check();page.get_by_role('button',name='Import for review',exact=True).click()
                page.locator('#bill-editor').wait_for()
                return get('/staged/'+str(stage(name)['id']))
            def approve(name,manual=True):
                if manual:
                    bill=CASES[name]['bill']
                    for key in ('provider','account_alias','invoice_number','bill_date','current_total'):
                        page.locator(f'[name="{key}"]').fill(bill[key])
                    while page.locator('[data-line]').count()<len(bill['lines']):page.get_by_role('button',name='Add a service line',exact=True).click()
                    for index,line in enumerate(bill['lines']):
                        scope=page.locator(f'[data-line="{index}"]')
                        for key,value in line.items():
                            node=scope.locator(f'[name="{key}"]')
                            if key in {'commodity','unit','usage_role','read_type'}:node.select_option(value)
                            else:node.fill(value)
                    page.locator('summary').filter(has_text='Additional extracted bill details').click()
                    page.locator('[name="detail-due_date"]').fill('2026-09-21' if CASES[name]['optional'] else '')
                    page.locator('[name="detail-currency"]').fill('USD')
                    page.locator('[name="detail-document_kind"]').fill('invoice')
                    if bill['lines'][0]['commodity']=='electricity':
                        for index in range(len(bill['lines'])):
                            page.locator(f'[name="detail-services.{index}.demand_quantity"]').fill('12.25')
                            page.locator(f'[name="detail-services.{index}.demand_unit"]').fill('kW')
                page.locator('#acknowledge').check();page.get_by_role('button',name='Approve into ledger',exact=True).click()
                page.get_by_role('heading',name='Review queue',exact=True).wait_for()
                return get('/staged/'+str(stage(name)['id']))
            def candidate(text):
                page.get_by_label('Filter source candidates',exact=True).fill(text)
                page.locator('.candidate-line').filter(has_text=text).first.click()
            def add_rule(rule,observed):
                line=next(line for line in observed['lines'] if line['text'].startswith(rule['label']+':'))
                candidate(line['text'])
                page.get_by_role('combobox',name='Semantic field',exact=True).select_option(rule['field'])
                page.get_by_label('Literal label',exact=True).fill(rule['label'])
                page.get_by_role('combobox',name='Date format',exact=True).select_option(rule['date_format'])
                page.get_by_role('combobox',name='Expected unit (unit fields only)',exact=True).select_option(rule['expected_unit'] or '')
                page.locator('#rule-region').set_checked(rule['region'] is not None)
                page.locator('#rule-required').set_checked(rule['required'])
                page.get_by_role('button',name='Add or replace field rule',exact=True).click()
            def inspect_layout(index=0):
                nav('Provider Management');page.get_by_role('button',name='Inspect layout',exact=True).nth(index).click()
                page.get_by_role('heading',name='Immutable layout version',exact=True).wait_for()
            def validate_and_activate(ids):
                for id in ids:page.locator(f'[data-validation-document="{id}"]').check()
                page.get_by_role('button',name='Validate selected bills',exact=True).click()
                expect(page.locator('#local-validation-result')).to_contain_text('Eligible for explicit activation.',timeout=120000)
                page.locator('#layout-state-ack').check();page.get_by_role('button',name='Activate validated layout',exact=True).click()
                expect(page.locator('.page-heading p')).to_contain_text('Active')
            def shot(name):
                assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
                page.screenshot(path=str(work/(name+'.png')))
            try:
                page.goto(url);assert page.title()=='SKS UtilityOS | Local utility ledger';page.get_by_role('button',name='Open synthetic demo',exact=True).click()
                page.get_by_role('heading',name='Campus utilities',exact=True).wait_for()
                first=upload('first')
                expect(page.locator('.source-evidence')).to_contain_text('Unknown Provider')
                page.get_by_role('button',name='Set up or inspect provider layout',exact=True).click()
                page.get_by_role('heading',name='Provider Setup Wizard',exact=True).wait_for()
                page.get_by_label('Local provider label',exact=True).fill(CASES['first']['bill']['provider'])
                page.get_by_role('button',name='Create local provider',exact=True).click()
                expect(page.get_by_role('combobox',name='Local provider',exact=True)).not_to_have_value('')
                observed=get(f'/providers/documents/{first["document_id"]}/observations')
                definition=author(observed,'first')
                candidate(definition['provider_anchor']['literal']);page.get_by_role('button',name='Use as provider identifier',exact=True).click()
                candidate('Local statement design 1');page.get_by_role('button',name='Use as layout marker',exact=True).click()
                candidate('Service block 1');page.get_by_role('button',name='Use as service section start',exact=True).click()
                for rule in definition['rules']:add_rule(rule,observed)
                candidate('Invoice charges: 124.50');page.get_by_role('combobox',name='Semantic field',exact=True).select_option('invoice_total')
                page.locator('#selected-candidate').scroll_into_view_if_needed();shot('desktop-provider-source-selection')
                page.get_by_role('button',name='Preview extraction',exact=True).click()
                page.get_by_role('heading',name='Candidate preview · Known',exact=True).wait_for(timeout=90000)
                expect(page.locator('#studio-preview')).to_contain_text('124.50');shot('desktop-draft-preview')
                page.get_by_role('button',name='Save new draft layout',exact=True).click()
                page.get_by_role('heading',name='Immutable layout version',exact=True).wait_for()
                assert get('/providers')['layouts'][0]['state']=='draft'
                expect(page.get_by_role('button',name='Activate validated layout',exact=True)).to_be_disabled()
                nav('Review queue');page.locator(f'[data-review="{first["id"]}"]').click();first=approve('first')
                upload('second');second=approve('second')
                inspect_layout();validate_and_activate([first['document_id'],second['document_id']]);shot('desktop-local-acceptance')
                outcomes.append('Unknown PDF → source candidate selection → immutable draft → two UI-reviewed sources → validation and explicit activation')
                future=upload('future');expect(page.locator('[name=invoice_number]')).to_have_value(CASES['future']['bill']['invoice_number'])
                assert future['status']=='pending';approve('future',manual=False)
                page.set_viewport_size({'width':390,'height':844})
                scan=upload('scan');expect(page.locator('[name=current_total]')).to_have_value('124.50')
                page.locator('[data-evidence=invoice_total]').click();expect(page.locator('#evidence-error')).to_contain_text('Page rendered locally')
                expect(page.locator('#evidence-description')).to_be_in_viewport();shot('mobile-local-ocr-review')
                approve('scan',manual=False);outcomes.append('Future local candidates remain pending; mobile scanned-source evidence and ordinary approval')
                page.set_viewport_size({'width':1440,'height':1000})
                changed=upload('layout-change');expect(page.locator('.source-evidence')).to_contain_text('Known Provider Unknown Layout')
                changed=approve('layout-change');upload('layout-change-second');changed2=approve('layout-change-second')
                inspect_layout();page.get_by_role('button',name='Create a new version',exact=True).click()
                page.get_by_role('heading',name='Provider Setup Wizard',exact=True).wait_for()
                page.get_by_role('combobox',name='Source PDF',exact=True).select_option(str(changed['document_id']))
                page.get_by_role('heading',name='Provider Setup Wizard',exact=True).wait_for()
                observed=get(f'/providers/documents/{changed["document_id"]}/observations')
                candidate('Local statement design 2');page.get_by_role('button',name='Use as layout marker',exact=True).click();expect(page.get_by_label('Layout marker text (optional)',exact=True)).to_have_value('Local statement design 2')
                for rule in author(observed,'layout-change')['rules']:
                    if rule['field'] in {'account_identifier','services.*.consumption_quantity'}:add_rule(rule,observed)
                page.get_by_role('button',name='Preview extraction',exact=True).click()
                page.get_by_role('heading',name='Candidate preview · Known',exact=True).wait_for(timeout=90000)
                page.get_by_role('button',name='Save new draft layout',exact=True).click()
                page.get_by_role('heading',name='Immutable layout version',exact=True).wait_for()
                validate_and_activate([changed['document_id'],changed2['document_id']])
                inspect_layout(0);page.locator('#layout-state-ack').check();page.get_by_role('button',name='Retire this version',exact=True).click()
                expect(page.locator('.page-heading p')).to_contain_text('Retired')
                assert get(f'/staged/{future["id"]}')['intake']['extraction']['template_version']==get('/providers')['layouts'][0]['id']
                outcomes.append('Known-provider layout drift → new independently validated version → retirement with original extraction retained')
                upload('single-first');single_first=approve('single-first')
                upload('single-second');single_second=approve('single-second')
                inspect_layout(0);page.get_by_role('button',name='Create a new version',exact=True).click()
                page.get_by_role('heading',name='Provider Setup Wizard',exact=True).wait_for()
                page.get_by_role('combobox',name='Service layout',exact=True).select_option('single')
                page.get_by_role('button',name='Preview extraction',exact=True).click()
                page.get_by_role('heading',name='Candidate preview · Known',exact=True).wait_for(timeout=90000)
                page.get_by_role('button',name='Save new draft layout',exact=True).click()
                page.get_by_role('heading',name='Immutable layout version',exact=True).wait_for()
                validate_and_activate([single_first['document_id'],single_second['document_id']])
                outcomes.append('Single-service layout setup without numbered sections, validated against two independently reviewed sources')
                inspect_layout(0)
                page.get_by_role('button',name='Preview safe bundle',exact=True).click()
                page.locator('#support-exact-preview').wait_for();preview=page.locator('#support-exact-preview').text_content()
                page.locator('#support-preview-ack').check()
                with page.expect_download() as pending:page.get_by_role('button',name='Download previewed safe bundle',exact=True).click()
                pending.value.save_as(str(work/'provider-support.json'))
                assert (work/'provider-support.json').read_text()==preview
                for sentinel in ('Fictional Northstar','Customer key','SYN-LOCAL','124.50','250.75','first.pdf','2026-09-01'):assert sentinel not in preview
                nav('Provider Management');shot('desktop-provider-management')
                nav('Privacy & support');page.locator('#backup-ack').check();page.get_by_role('button',name='Create local backup',exact=True).click()
                with page.expect_download() as pending:page.get_by_role('link',name='Download private backup ZIP',exact=True).click()
                pending.value.save_as(str(work/'private-backup.zip'))
                page.get_by_role('button',name='Lock workspace').click();page.get_by_role('button',name='Open synthetic demo').wait_for()
                assert not errors,errors;assert not failures,failures
            finally:
                # Synthetic-only failure evidence stays in the new external run.
                page.screenshot(path=str(work/'last-desktop-state.png'))
                (work/'last-desktop-state.txt').write_text(page.locator('body').inner_text())
                (work/'browser-errors.json').write_text(json.dumps({'errors':errors,'http_failures':failures},indent=2)+'\n')
                context.close()
        recovered=Store(work/'restored','demo');restore(recovered,work/'private-backup.zip','demo');check(recovered)
        with server(recovered.directory,'demo',work,args.ocr_model_dir) as url:
            context=browser.new_context(viewport={'width':390,'height':844});page=context.new_page()
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.on('console',lambda msg:errors.append(msg.text) if msg.type in {'error','warning'} else None)
            page.goto(url);page.get_by_role('button',name='Open synthetic demo').click()
            nav('Provider Management');expect(page.locator('#content')).to_contain_text('Retired');expect(page.locator('#content')).to_contain_text('Active');shot('mobile-restored-provider-management')
            page.get_by_role('button',name='Lock workspace').click();context.close()
        browser.close()
    assert not errors,errors
    outcomes.append('Exact previewed support download, private backup download, logout and restored provider versions in native mobile Chrome')
    result={'result':'passed','workflows':outcomes,'unexpected_console_or_runtime_errors':len(errors),'unexpected_http_failures':len(failures)}
    (work/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
