#!/usr/bin/env python3
"""Account cadence browser checks on a NEW synthetic demo; no portal retrieval."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from playwright.sync_api import sync_playwright, expect
from scripts.native_readiness_smoke import server
from utilityos.config import Config
from utilityos.db import Store
from utilityos.operations import backup, restore, check
from utilityos.completeness import Completeness


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir',required=True,type=Path)
    parser.add_argument('--browser-executable',required=True,type=Path)
    args=parser.parse_args();work=args.work_dir.resolve();Config(work,'demo').validate()
    if work.exists():raise SystemExit('SCHEDULE_CHECK_REQUIRES_NEW_DIRECTORY')
    work.mkdir(parents=True,mode=0o700)
    errors=[]
    with server(work/'demo','demo',work) as url, sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path=str(args.browser_executable),headless=True)
        context=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
        page=context.new_page()
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('console',lambda msg:errors.append(msg.text) if msg.type in {'error','warning'} else None)
        page.goto(url);page.get_by_role('button',name='Open synthetic demo').click()
        page.get_by_role('heading',name='Campus utilities',exact=True).wait_for()
        before=page.evaluate("fetch('/api/overview').then(r=>r.json())")['total_cents']
        page.locator('nav').get_by_role('button',name='Bill completeness',exact=True).click()
        page.get_by_role('heading',name='Bill completeness',exact=True).wait_for()
        page.get_by_text('Confirm an expected account and service cadence',exact=True).click()
        page.locator('[name=coverage-account]').select_option(index=1)
        page.locator('[name=cadence]').select_option('every_two_months')
        page.locator('[name=anchor_month]').select_option('1')
        page.locator('[name=issue_day]').fill('15');page.locator('[name=grace_days]').fill('7')
        page.locator('[name=effective_from]').fill('2025-01-01')
        page.locator('[name=retrieval_cadence]').select_option('on_issue')
        page.locator('[name=coverage-reason]').fill('Synthetic odd-month water-style account schedule')
        page.locator('#coverage-ack').check();page.get_by_role('button',name='Save expectation',exact=True).click()
        expect(page.locator('#coverage-config')).not_to_be_visible()
        page.locator('[name=coverage-month]').fill('2025-03');page.get_by_role('button',name='Show month',exact=True).click()
        expect(page.locator('#content')).to_contain_text('2025-03-15')
        expect(page.locator('#content')).to_contain_text('Missing after 2025-03-22')
        data=page.evaluate("fetch('/api/completeness?month=2025-03').then(r=>r.json())")
        assert data['counts']['expected']==data['counts']['missing']==1
        assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
        page.screenshot(path=str(work/'desktop-schedule.png'),full_page=True)
        page.set_viewport_size({'width':390,'height':844})
        page.locator('[name=coverage-month]').fill('2025-04');page.get_by_role('button',name='Show month',exact=True).click()
        expect(page.locator('tbody')).to_contain_text('Not Scheduled')
        assert page.evaluate("fetch('/api/completeness?month=2025-04').then(r=>r.json())")['counts']['missing']==0
        page.get_by_text('Confirm an expected account and service cadence',exact=True).click()
        page.locator('[name=coverage-account]').select_option(index=1)
        expect(page.locator('[name=cadence]')).to_have_value('every_two_months')
        page.get_by_text('Account-specific month exceptions',exact=True).click()
        page.get_by_role('button',name='Add month exception',exact=True).click()
        page.locator('[name=exception-month-0]').fill('2025-05')
        page.locator('[name=exception-reason-0]').fill('Synthetic month skipped by account agreement')
        page.locator('[name=coverage-reason]').fill('Synthetic explicit account exception')
        page.locator('#coverage-ack').check();page.get_by_role('button',name='Save expectation',exact=True).click()
        expect(page.locator('#coverage-config')).not_to_be_visible()
        page.locator('[name=coverage-month]').fill('2025-05');page.get_by_role('button',name='Show month',exact=True).click()
        expect(page.locator('tbody')).to_contain_text('Not Scheduled')
        assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
        page.screenshot(path=str(work/'mobile-schedule.png'),full_page=True)
        after=page.evaluate("fetch('/api/overview').then(r=>r.json())")['total_cents'];assert before==after
        page.get_by_role('button',name='Lock workspace').click()
        page.get_by_role('button',name='Open synthetic demo').wait_for()
        assert context.request.get(url+'/api/completeness').status==401
        context.close();browser.close()
    original=Store(work/'demo','demo');saved=backup(original);target=Store(work/'restored','demo');restore(target,saved,'demo')
    assert Completeness(original).report('2025-05')==Completeness(target).report('2025-05')
    assert check(target)['schema_version']==6
    assert not errors,errors
    result={'result':'passed','viewports':['1440x1000','390x844'],'native_http':True,'console_errors':errors,
            'checks':['odd-month issue and grace','quiet month','mobile exception save','unchanged charges','logout','backup restore']}
    (work/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))


if __name__=='__main__':main()
