from copy import deepcopy
from hashlib import sha256
import json
import sqlite3
import time
import zipfile
import pytest
from utilityos import SCHEMA_VERSION
from utilityos.config import ROOT
from utilityos.db import Store
from utilityos.operations import backup, restore, check, migrate
from utilityos.service import Ledger
from utilityos.provider_studio import ProviderStudio
from utilityos.provider_rules import Definition, Observations, Rule, locate, extract_layout
from utilityos.provider_support import SupportBundle
from utilityos.provider_storage import records
from provider_helpers import CASES, CORPUS, post, upload, reviewed, setup, validate, activate, author


def test_onboard_validate_activate_and_preserve_original_extraction(authenticated):
    c = authenticated
    first, second = reviewed(c, 'first'), reviewed(c, 'second')
    original = c.get(f'/api/staged/{first["id"]}').json()['intake']['extraction']
    built = setup(c, sample=first)
    assert built['layout']['state'] == 'draft'
    validation = validate(c, built, first, second)
    assert validation['summary']['eligible']
    assert all(row['exact'] == row['tested'] for row in validation['summary']['fields'].values())
    activate(c, built, validation)
    future = upload(c, 'future')
    assert future['status'] == 'pending'
    assert future['intake']['extraction']['template_version'] == built['layout']['id']
    assert future['payload'] == CASES['future']['bill']
    assert c.get(f'/api/staged/{first["id"]}').json()['intake']['extraction'] == original
    assert c.get('/api/overview').json()['stats']['approved_bills'] == 2
    post(c, f'/api/staged/{future["id"]}/approve', {'payload': future['payload'], 'revision': 0}, expected=422)
    post(c, f'/api/staged/{future["id"]}/approve', {'payload': future['payload'], 'revision': 0, 'acknowledge': True})
    assert c.get('/api/overview').json()['stats']['approved_bills'] == 3


@pytest.mark.parametrize('names', [('supply-first','supply-second'), ('fuel-first','fuel-second')])
def test_supply_and_delivered_fuel_semantics_through_local_setup(authenticated, names):
    c = authenticated
    first, second = [reviewed(c, name) for name in names]
    built = setup(c, names[0], sample=first)
    validation = validate(c, built, first, second)
    assert validation['summary']['eligible']
    activate(c, built, validation)
    candidate = post(c, f'/api/provider-layouts/{built["layout"]["id"]}/preview', {'document_id': first['document_id']})
    assert candidate['payload'] == CASES[names[0]]['bill']
    assert candidate['payload']['lines'][0]['usage'] == ('0' if names[0].startswith('supply') else '250.75')


def test_second_page_and_repeated_service_sections(authenticated):
    c = authenticated
    first = reviewed(c, 'first'); built = setup(c, sample=first)
    samples = [reviewed(c, name) for name in ('page-two', 'two-meters', 'missing-optional')]
    result = validate(c, built, first, *samples)
    assert result['summary']['eligible']
    assert result['summary']['fields']['services.*.meter_identifier']['exact'] == 5
    for sample in samples:
        preview = post(c, f'/api/provider-layouts/{built["layout"]["id"]}/preview', {'document_id': sample['document_id']})
        if sample is samples[0]:
            assert preview['extraction']['fields']['services.0.meter_identifier']['page'] == 2


def test_wrong_template_gate_and_versioned_correction(authenticated):
    c = authenticated
    first, second = reviewed(c, 'first'), reviewed(c, 'second')
    wrong = setup(c, sample=first, wrong=True)
    result = validate(c, wrong, first, second)
    assert not result['summary']['eligible']
    post(c, f'/api/provider-layouts/{wrong["layout"]["id"]}/activate',
         {'state_id': wrong['layout']['state_id'], 'validation_id': result['id'], 'acknowledge': True}, expected=422)
    fixed = setup(c, sample=first, parent=wrong)
    assert fixed['layout']['version'] == 2
    assert fixed['layout']['parent_layout_id'] == wrong['layout']['id']
    activate(c, fixed, validate(c, fixed, first, second))
    retained = c.get(f'/api/provider-layouts/{wrong["layout"]["id"]}').json()['layout']
    assert retained['definition'] == wrong['layout']['definition']
    assert retained['state'] == 'draft'


def test_new_layout_drift_retire_replacement_and_history(authenticated):
    c = authenticated
    first, second = reviewed(c, 'first'), reviewed(c, 'second')
    built = setup(c, sample=first); activate(c, built, validate(c, built, first, second))
    unchanged = upload(c, 'future')
    for name in ('relocated-account', 'renamed-usage'):
        item = upload(c, name)
        assert item['intake']['extraction']['template_version'] is None
        assert 'LOCAL_LAYOUT_DRIFT' in item['intake']['extraction']['codes']
    changed, changed_second = reviewed(c, 'layout-change'), reviewed(c, 'layout-change-second')
    assert changed['intake']['extraction']['template_version'] is None
    replacement = setup(c, 'layout-change', sample=changed, parent=built)
    activate(c, replacement, validate(c, replacement, changed, changed_second))
    retired = post(c, f'/api/provider-layouts/{built["layout"]["id"]}/retire',
                   {'state_id': built['layout']['state_id'], 'acknowledge': True})
    assert retired['state'] == 'retired'
    old = c.get(f'/api/staged/{unchanged["id"]}').json()['intake']['extraction']
    assert old['template_version'] == built['layout']['id']
    post(c, f'/api/provider-layouts/{built["layout"]["id"]}/activate',
         {'state_id': retired['state_id'], 'acknowledge': True}, expected=422)
    preview = post(c, f'/api/provider-layouts/{replacement["layout"]["id"]}/preview', {'document_id': changed['document_id']})
    assert preview['extraction']['layout_state'] == 'known'
    assert c.get(f'/api/provider-layouts/{built["layout"]["id"]}').json()['layout']['quality']['investigate']


def test_repeated_label_and_conflicting_active_versions_abstain(authenticated):
    c = authenticated
    first, second = reviewed(c, 'first'), reviewed(c, 'second')
    built = setup(c, sample=first); activate(c, built, validate(c, built, first, second))
    ambiguous = upload(c, 'repeated-label')
    definition = deepcopy(built['definition'])
    next(rule for rule in definition['rules'] if rule['field'] == 'account_identifier')['region'] = None
    preview = post(c, '/api/providers/preview', {'provider_id': built['provider']['id'], 'document_id': ambiguous['document_id'], 'definition': definition})
    assert preview['extraction']['fields']['account_identifier']['state'] == 'conflict'
    assert preview['extraction']['fields']['account_identifier']['value'] is None
    duplicate = setup(c, sample=first, parent=built)
    activate(c, duplicate, validate(c, duplicate, first, second))
    future = upload(c, 'future')
    assert future['intake']['extraction']['template_version'] is None
    assert 'AMBIGUOUS_LAYOUT' in future['intake']['extraction']['codes']


def test_stale_actions_and_changed_approved_truth_require_revalidation(authenticated):
    c = authenticated
    first, second = reviewed(c, 'first'), reviewed(c, 'second')
    built = setup(c, sample=first)
    weak = validate(c, built, first)
    assert not weak['summary']['eligible']
    checked = validate(c, built, first, second)
    post(c, f'/api/providers/{built["provider"]["id"]}/layouts',
         {'definition': built['definition'], 'expected_version': 0}, expected=422)
    item = c.get(f'/api/staged/{first["id"]}').json()
    correction = post(c, f'/api/bills/{item["bill"]["id"]}/correct', {'reason': 'Synthetic corrected final truth'})
    draft = c.get(f'/api/staged/{correction["staged_id"]}').json()
    draft['payload']['current_total'] = draft['payload']['lines'][0]['current_charge'] = '130.00'
    post(c, f'/api/staged/{draft["id"]}/approve', {'payload': draft['payload'], 'revision': draft['revision'], 'acknowledge': True})
    result = post(c, f'/api/provider-layouts/{built["layout"]["id"]}/activate',
         {'state_id': built['layout']['state_id'], 'validation_id': checked['id'], 'acknowledge': True}, expected=422)
    assert result['error'] == 'LOCAL_VALIDATION_REVIEW_CHANGED_RETRY'


def test_corpus_cannot_include_unapproved_duplicate_or_other_provider_sources(authenticated):
    c = authenticated
    first = reviewed(c, 'first'); built = setup(c, sample=first)
    pending = upload(c, 'second'); other = reviewed(c, 'fuel-first')
    for ids in ([first['document_id'], first['document_id']], [pending['document_id']], [other['document_id']], [True], list(range(11))):
        post(c, f'/api/provider-layouts/{built["layout"]["id"]}/validate', {'document_ids': ids}, expected=422)
    response = c.post('/api/import',content=(CORPUS/'first.pdf').read_bytes(),headers={'content-type':'application/octet-stream','x-filename':'renamed.pdf','x-synthetic-data':'true'})
    assert response.status_code == 422 and response.json()['error'] == 'DUPLICATE_SOURCE_DOCUMENT'


def test_private_support_preview_matches_strict_schema_and_excludes_sentinels(authenticated):
    c = authenticated
    first, second = reviewed(c, 'first'), reviewed(c, 'second')
    built = setup(c, sample=first)
    definition = deepcopy(built['definition'])
    secret = 'PRIVATE_19999_ACCOUNT_ADDRESS_PASSPHRASE_813249'
    definition['rules'].append({'field': 'service_address', 'label': secret, 'required': False})
    layout = post(c, f'/api/providers/{built["provider"]["id"]}/layouts', {'definition': definition,'expected_version':1})
    built['layout'] = layout
    validate(c, built, first, second)
    result = c.get(f'/api/provider-layouts/{layout["id"]}/support').json()
    bundle = SupportBundle.model_validate_json(result['text'])
    assert sha256(result['text'].encode()).hexdigest() == result['sha256']
    for value in (secret, 'Fictional Northstar', 'Customer key', 'SYN-LOCAL', '124.50', '250.75', '2026-09-01',
                  '09/01/2026', 'first.pdf', str(c.app.state.store.directory), 'region', 'bbox', 'created_at'):
        assert value not in result['text']
    assert bundle.documents_tested == 2
    assert secret not in c.get('/api/diagnostics').text
    assert secret not in c.get('/api/intake/quality').text
    local = c.get(f'/api/provider-layouts/{layout["id"]}').text
    assert secret in local # Private definition exists locally, not in support.
    assert json.loads((ROOT/'docs/provider-support-schema.json').read_text()) == SupportBundle.model_json_schema()
    assert json.loads((ROOT/'docs/local-layout-schema.json').read_text()) == Definition.model_json_schema()


def test_approved_correction_counts_never_mutate_rules(authenticated):
    c = authenticated
    first, second = reviewed(c, 'first'), reviewed(c, 'second')
    built = setup(c, sample=first); activate(c, built, validate(c, built, first, second))
    for name in ('future', 'page-two'):
        item = upload(c, name)
        payload = item['payload']; payload['current_total'] = payload['lines'][0]['current_charge'] = '130.00'
        for _ in range(2):
            post(c, f'/api/staged/{item["id"]}/draft', {'payload': payload,'revision':item['revision']})
            item = c.get(f'/api/staged/{item["id"]}').json()
        post(c,f'/api/staged/{item["id"]}/approve',{'payload':payload,'revision':item['revision'],'acknowledge':True})
    layout = c.get(f'/api/provider-layouts/{built["layout"]["id"]}').json()['layout']
    assert layout['quality']['field_corrections']['invoice_total'] == 2
    assert layout['quality']['investigate']
    assert layout['hash'] == built['layout']['hash'] and layout['definition'] == built['layout']['definition']


def test_private_backup_restore_and_future_migration_preserve_definitions(authenticated,tmp_path):
    c = authenticated
    first, second = reviewed(c,'first'), reviewed(c,'second'); built=setup(c,sample=first)
    activate(c,built,validate(c,built,first,second)); upload(c,'future')
    original=c.app.state.store; saved=backup(original)
    target=Store(tmp_path/'restored','demo');restore(target,saved,'demo')
    restored=ProviderStudio(Ledger(target)).inspect(built['layout']['id'])
    assert restored==c.app.state.provider_studio.inspect(built['layout']['id'])
    assert check(target)['schema_version']==5
    from utilityos.migrations import upgrade_copy,STEPS
    future=tmp_path/'future.sqlite3'
    upgrade_copy(target,future,6,{**STEPS,5:lambda db:db.execute('CREATE TABLE synthetic_future(id INTEGER)')})
    with target.connect() as before, sqlite3.connect(future) as after:
        assert [tuple(r) for r in before.execute('SELECT * FROM local_provider_records')]==after.execute('SELECT * FROM local_provider_records').fetchall()
    with pytest.raises(ValueError,match='SCHEMA_VERSION_UNSUPPORTED'):
        Store(target.directory,'demo',expected_schema=4)


@pytest.mark.parametrize('damage',['json','hash','delete','state','trigger'])
def test_corrupt_local_templates_quarantine_without_blocking_manual_review(authenticated,tmp_path,damage):
    c=authenticated; first=reviewed(c,'first');built=setup(c,sample=first);store=c.app.state.store
    with store.connect() as db:
        with pytest.raises(sqlite3.IntegrityError):db.execute('UPDATE local_provider_records SET payload=?',('{}',))
        db.execute('DROP TRIGGER local_provider_no_update');db.execute('DROP TRIGGER local_provider_no_delete')
        if damage=='json':db.execute('UPDATE local_provider_records SET payload=? WHERE id=?',('{broken',built['layout']['id']))
        elif damage=='hash':db.execute('UPDATE local_provider_records SET payload_sha256=? WHERE id=?',('1'*64,built['layout']['id']))
        elif damage=='delete':db.execute('DELETE FROM local_provider_records WHERE kind=\'state\'')
        elif damage=='state':db.execute('UPDATE local_provider_records SET payload=? WHERE kind=\'state\'',('{"state":"active"}',))
        if damage!='trigger':
            from utilityos.provider_storage import STATEMENTS
            for sql in STATEMENTS[-2:]:db.execute(sql)
    assert c.get('/api/providers').json()['damaged']
    new=upload(c,'second');assert new['status']=='pending'
    assert 'LOCAL_TEMPLATE_DAMAGED_MANUAL_REVIEW' in new['intake']['extraction']['codes']
    post(c,f'/api/staged/{new["id"]}/approve',{'payload':CASES['second']['bill'],'revision':0,'acknowledge':True})
    assert Store(store.directory,'demo') # App launch/manual review stays available.
    with pytest.raises(ValueError,match='LOCAL_TEMPLATE_DAMAGED'):
        backup(store)
    assert c.get('/api/providers').status_code==200


def test_missing_ocr_allows_source_retention_and_manual_approval(authenticated):
    c=authenticated; item=upload(c,'scan')
    assert 'OCR_UNAVAILABLE_MANUAL_ENTRY' in item['intake']['extraction']['codes']
    result=c.get(f'/api/providers/documents/{item["document_id"]}/observations')
    assert result.status_code==200 and result.json()['lines']==[]
    post(c,f'/api/staged/{item["id"]}/approve',{'payload':CASES['scan']['bill'],'revision':0,'acknowledge':True})


@pytest.mark.parametrize('mutation',[
    lambda d:d.update(python='exec("bad")'),
    lambda d:d['rules'][0].update(regex='(a+)+$'),
    lambda d:d['rules'][0].update(field='__dict__'),
    lambda d:d['rules'][0].update(mode='shell'),
    lambda d:d['rules'][0].update(distance=201),
    lambda d:d['rules'][0].update(region=[0,100,1,0]),
    lambda d:d['rules'][0].update(expected_unit='USD'),
    lambda d:d['rules'][0].update(label='a'*121),
    lambda d:d.update(rules=d['rules'][:3]),
    lambda d:d.update(section_prefix='\x00'),
])
def test_template_language_rejects_unsupported_or_unbounded_rules(authenticated,mutation):
    c=authenticated; first=reviewed(c,'first'); built=setup(c,sample=first)
    value=deepcopy(built['definition']);mutation(value)
    result=post(c,f'/api/providers/{built["provider"]["id"]}/layouts',{'definition':value,'expected_version':1},expected=422)
    assert result['error']=='LOCAL_LAYOUT_DEFINITION_INVALID'


def test_literal_code_like_content_has_no_execution_semantics():
    label='__import__("os").system("touch SHOULD_NOT_EXIST")'
    rule=Rule(field='invoice_number',label=label)
    line={'text':label+': SYNTHETIC','page':1,'bbox':[1,1,500,20]}
    started=time.monotonic()
    assert locate([line],rule)[0][0]=='SYNTHETIC'
    assert time.monotonic()-started<.1
    assert not (ROOT/'SHOULD_NOT_EXIST').exists()


def test_bounded_nearby_rules_fail_on_ambiguity_and_enforce_regions():
    label={'text':'Customer key','page':1,'bbox':[10,10,90,20]}
    below={'text':'SYN-ONE','page':1,'bbox':[10,30,80,40]}
    other={'text':'SYN-TWO','page':1,'bbox':[10,50,80,60]}
    rule=Rule(field='account_identifier',label='Customer key',mode='below',distance=20)
    assert locate([label,below,other],rule)==[('SYN-ONE',below)]
    assert len(locate([label,below,other],rule.model_copy(update={'distance':60})))==2
    right={'text':'SYN-RIGHT','page':1,'bbox':[100,10,150,20]}
    assert locate([label,right],Rule(field='account_identifier',label='Customer key',mode='right'))==[('SYN-RIGHT',right)]


@pytest.mark.parametrize('path',['/api/providers','/api/providers/documents','/api/providers/documents/1/observations','/api/provider-layouts/'+'a'*32,'/api/provider-layouts/'+'a'*32+'/support'])
def test_provider_private_gets_require_login(client,path):
    assert client.get(path).status_code==401


def test_provider_writes_require_existing_origin_and_csrf(authenticated):
    c=authenticated
    assert c.post('/api/providers',json={'label':'synthetic','commodity':'electricity'},headers={'x-csrf-token':''}).status_code==403
    assert c.post('/api/providers',json={'label':'synthetic','commodity':'electricity'},headers={'origin':'https://untrusted.invalid'}).status_code==403


@pytest.mark.parametrize('operation',['save','activate'])
def test_real_process_interruption_rolls_back_private_provider_decisions(authenticated,tmp_path,operation):
    import subprocess
    import sys
    c=authenticated;first,second=reviewed(c,'first'),reviewed(c,'second')
    built=setup(c,sample=first);checked=validate(c,built,first,second)
    store=c.app.state.store
    with store.connect() as db:before=[tuple(r) for r in db.execute('SELECT * FROM local_provider_records')]
    marker=tmp_path/'provider-transaction.ready'
    child=subprocess.Popen([sys.executable,str(ROOT/'tests/provider_crash_worker.py'),str(store.directory),str(marker),operation,built['layout']['id']],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        deadline=time.monotonic()+15
        while not marker.exists() and time.monotonic()<deadline and child.poll() is None:time.sleep(.02)
        assert marker.exists(),child.communicate(timeout=1) if child.poll() is not None else 'checkpoint not reached'
        child.kill();child.communicate(timeout=10)
    finally:
        if child.poll() is None:child.kill();child.communicate(timeout=10)
    with store.connect() as db:assert [tuple(r) for r in db.execute('SELECT * FROM local_provider_records')]==before
    assert check(store)['audit']=='ok'
    if operation=='activate':activate(c,built,checked)
    else:assert setup(c,sample=first,parent=built)['layout']['version']==2


def test_changed_registry_during_extraction_requires_safe_retry(authenticated,monkeypatch):
    from utilityos import pdf_extract
    c=authenticated;first,second=reviewed(c,'first'),reviewed(c,'second')
    built=setup(c,sample=first);activate(c,built,validate(c,built,first,second))
    original=pdf_extract.task
    def changed(*args,**kwargs):
        result=original(*args,**kwargs)
        post(c,f'/api/provider-layouts/{built["layout"]["id"]}/retire',{'state_id':built['layout']['state_id'],'acknowledge':True})
        return result
    monkeypatch.setattr(pdf_extract,'task',changed)
    result=c.post('/api/import',content=(CORPUS/'future.pdf').read_bytes(),headers={'content-type':'application/octet-stream','x-filename':'future.pdf','x-synthetic-data':'true'})
    assert result.status_code==422 and result.json()['error']=='LOCAL_LAYOUT_CHANGED_RETRY_IMPORT'
    assert not any(row['filename']=='future.pdf' for row in c.get('/api/staged').json())
    monkeypatch.setattr(pdf_extract,'task',original)
    retried=upload(c,'future');assert retried['intake']['extraction']['template_version'] is None


def test_unit_conflict_and_inclusive_date_conversion_are_explicit(authenticated):
    c=authenticated;first=reviewed(c,'first');built=setup(c,sample=first)
    value=deepcopy(built['definition'])
    next(rule for rule in value['rules'] if rule['field']=='services.*.consumption_unit')['expected_unit']='gal'
    preview=post(c,'/api/providers/preview',{'provider_id':built['provider']['id'],'document_id':first['document_id'],'definition':value})
    assert preview['extraction']['fields']['services.0.consumption_unit']['value'] is None
    assert 'LOCAL_UNIT_CONFLICT' in preview['extraction']['codes']
    value=deepcopy(built['definition']);value['end_date_inclusive']=True
    preview=post(c,'/api/providers/preview',{'provider_id':built['provider']['id'],'document_id':first['document_id'],'definition':value})
    assert preview['extraction']['fields']['services.0.period_end']['value']=='2026-09-02'
    assert preview['extraction']['fields']['services.0.period_end']['raw']=='09/01/2026'


def test_source_archives_exclude_local_definitions_and_unapproved_ci_paths(authenticated,tmp_path):
    from scripts.release import build,source_allowed
    c=authenticated;first=reviewed(c,'first');built=setup(c,sample=first)
    value=deepcopy(built['definition']);sentinel='PRIVATE_RULE_CONTENT_NEVER_SHARE_174519'
    value['rules'].append({'field':'service_address','label':sentinel,'required':False})
    post(c,f'/api/providers/{built["provider"]["id"]}/layouts',{'definition':value,'expected_version':1})
    archive=tmp_path/'source.zip';build(ROOT,archive,source_date_epoch=1788739200)
    with zipfile.ZipFile(archive) as z:
        assert not any(name.endswith(('.sqlite3','.db')) for name in z.namelist())
        # The test source naturally contains this synthetic sentinel literal;
        # no serialized private template or provider record may be packaged.
        private=json.dumps(value,sort_keys=True,separators=(',',':')).encode()
        assert all(private not in z.read(name) for name in z.namelist())
        assert 'SKS-UtilityOS/.github/workflows/synthetic-ci.yml' in z.namelist()
    assert source_allowed(__import__('pathlib').Path('.github/workflows/synthetic-ci.yml'))
    assert not source_allowed(__import__('pathlib').Path('.github/workflows/local-provider.yml'))


def test_onboarding_corpus_has_independent_truth_and_reproducible_digital_pdfs():
    from scripts.synthetic_onboarding import cases,pdf_bytes
    for case in cases():
        raw=(CORPUS/(case['name']+'.pdf')).read_bytes()
        assert sha256(raw).hexdigest()==CASES[case['name']]['sha256']
        if not case['scan']:
            assert pdf_bytes(case)==raw


def test_initial_onboarding_without_active_rules_is_not_layout_drift(authenticated):
    c=authenticated;first=reviewed(c,'first');built=setup(c,sample=first)
    second=upload(c,'second')
    assert 'LOCAL_LAYOUT_NOT_ACTIVE_REVIEW_REQUIRED' in second['intake']['extraction']['codes']
    layout=c.get(f'/api/provider-layouts/{built["layout"]["id"]}').json()['layout']
    assert layout['quality']['provider_drift_documents']==0
    assert not layout['quality']['investigate']


def test_single_service_bills_need_no_artificial_numbered_section(authenticated):
    c=authenticated
    first,second=reviewed(c,'single-first'),reviewed(c,'single-second')
    built=setup(c,'single-first',sample=first)
    assert built['definition']['section_prefix'] is None
    activate(c,built,validate(c,built,first,second))
    item=upload(c,'two-meters')
    assert item['intake']['extraction']['template_version'] is None
    assert 'LOCAL_LAYOUT_DRIFT' in item['intake']['extraction']['codes']
