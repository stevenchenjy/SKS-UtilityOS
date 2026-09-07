"""Synthetic extraction, transactional review, privacy and inbox contracts."""
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import time
import pytest
from utilityos.config import ROOT
from utilityos.extraction import parse_lines, proposed_bill
from utilityos.extraction_schema import Extraction, CRITICAL
from utilityos.intake import Intake
from utilityos.intake_storage import get_extraction, verify
from utilityos.pdf_extract import task
from utilityos.operations import backup,restore,check
from utilityos.db import Store
from utilityos.service import Ledger
from utilityos.completeness import Completeness
from utilityos.provider_templates import TEMPLATES
from scripts.benchmark_extraction import equal

CORPUS=ROOT/'samples/intake'
TRUTH=json.loads((CORPUS/'expected.json').read_text())['documents']


@pytest.mark.parametrize('case',[case for case in TRUTH if case['path']!='ocr'],ids=lambda case:case['file'])
def test_exact_digital_extraction_and_page_provenance(case):
    raw=(CORPUS/case['file']).read_bytes();assert sha256(raw).hexdigest()==case['sha256']
    result=task(raw);Extraction.model_validate(result)
    assert result['layout_state']==case['layout']
    for path,expected in case['fields'].items():
        if path.split('.')[-1] not in CRITICAL:continue
        field=result['fields'][path]
        assert equal(path,expected,field['value']),path
        if field['value'] is not None:
            page=next(p for p in result['pages'] if p['number']==field['page'])
            assert field['raw'] and field['bbox'] and field['parser_version']
            assert field['bbox'][2]<=page['width'] and field['bbox'][3]<=page['height']
            if result['layout_state']=='known':assert field['template_version']==result['template_version']
            else:assert field['method']=='native_text' and field['state']=='needs_review' and field['template_version'] is None


def test_scans_without_model_remain_manual_and_do_not_download(tmp_path,monkeypatch):
    # The production worker has no download implementation. Invalid local model
    # bytes cannot be loaded even if they occupy the expected filename.
    (tmp_path/'eng.traineddata').write_bytes(b'not a model')
    for name in ('electricity-scan.pdf','scan-rotated.pdf','scan-low-quality.pdf'):
        result=task((CORPUS/name).read_bytes(),model_dir=tmp_path)
        assert result['pdf_kind']=='scanned'
        assert 'OCR_UNAVAILABLE_MANUAL_ENTRY' in result['codes']
        assert all(field['value'] is None for field in result['fields'].values())
    assert [p.name for p in tmp_path.iterdir()]==['eng.traineddata']


def test_worker_timeout_and_bad_pdf_keep_bounded_empty_candidates():
    result=task((CORPUS/'electricity-digital.pdf').read_bytes(),timeout=.0001)
    assert result['codes']==['EXTRACTION_TIMED_OUT']
    result=task(b'%PDF-bad PRIVATE_ACCOUNT_SENTINEL')
    assert result['codes']==['PDF_UNREADABLE_MANUAL_ENTRY']
    assert 'PRIVATE_ACCOUNT_SENTINEL' not in json.dumps(result)


def test_fingerprint_excludes_account_meter_and_invoice_values():
    results=[task((CORPUS/name).read_bytes()) for name in ('electricity-digital.pdf','layout-v1.pdf')]
    assert results[0]['fields']['account_identifier']['value']!=results[1]['fields']['account_identifier']['value']
    assert results[0]['provider_fingerprint']==results[1]['provider_fingerprint']
    assert results[0]['layout_fingerprint']==results[1]['layout_fingerprint']


def test_retired_template_and_ambiguous_field_abstain():
    lines=[{'text':content,'page':1,'bbox':[40,top,500,top+10],'method':'native_text'} for content,top in (
        ('Example Valley Electric',40),('Utility statement layout 1',75),('Invoice reference: SYN-01',100),
        ('Account: SYN-A',115),('Invoice date: 2026-09-01',130),('Current charges: 12.00',145),('Current charges: 99.00',160))]
    pages=[{'number':1,'width':612,'height':792,'method':'native_text'}]
    result=parse_lines(lines,pages)
    assert result['fields']['invoice_total']['value'] is None and result['fields']['invoice_total']['state']=='conflict'
    result=parse_lines(lines,pages,templates=tuple(replace(t,active=False) for t in TEMPLATES))
    assert result['layout_state']=='known_provider_unknown_layout' and result['template_version'] is None


def imported(ledger,name='electricity-digital.pdf'):
    result=ledger.import_file(name,(CORPUS/name).read_bytes())
    return result['staged_ids'][0]


def test_pdf_is_pending_until_review_and_missing_total_never_uses_balance(ledger):
    identifier=imported(ledger)
    assert ledger.overview()['total_cents']==0
    bill=ledger.stage(identifier)['payload']
    with pytest.raises(ValueError,match='ACKNOWLEDGE'):ledger.approve_bill(identifier,bill,False)
    ledger.approve_bill(identifier,bill,True,revision=0)
    assert ledger.overview()['total_cents']==10000
    missing=imported(ledger,'missing-total.pdf');payload=ledger.stage(missing)['payload']
    assert payload['current_total']==''
    with pytest.raises(ValueError):ledger.approve_bill(missing,payload,True)
    assert ledger.stage(missing)['status']=='pending'


def test_saved_corrections_preserve_machine_evidence_and_ancillary_values(ledger,tmp_path):
    identifier=imported(ledger,'demand-charge.pdf');item=ledger.stage(identifier)
    original=deepcopy(item['intake']['extraction']);bill=item['payload'];bill['current_total']='120.00';bill['lines'][0]['current_charge']='120.00'
    details={'services.0.demand_quantity':'13.5','due_date':'2026-09-22'}
    ledger.save_draft(identifier,bill,0,intake_details=details)
    with pytest.raises(ValueError,match='DRAFT_CHANGED'):ledger.approve_bill(identifier,bill,True,revision=0)
    ledger.approve_bill(identifier,bill,True,revision=1)
    final=ledger.stage(identifier)
    assert final['intake']['extraction']==original
    assert final['intake']['reviewed_values']['services.0.demand_quantity']=='13.5'
    assert {d['field'] for d in final['intake']['differences']} >= {'invoice_total','services.0.demand_quantity','due_date'}
    correction=ledger.create_correction(final['bill']['id'],'Synthetic correction')['staged_id']
    assert ledger.stage(correction)['intake']['reviewed_values']['due_date']=='2026-09-22'
    saved=backup(ledger.store);restored=Store(tmp_path/'recovered','demo');restore(restored,saved,'demo')
    recovered=Ledger(restored).stage(identifier)
    assert recovered['intake']==final['intake']
    assert check(restored)['sources']=='ok'
    with ledger.store.connect() as db:
        with pytest.raises(sqlite3.IntegrityError):db.execute("UPDATE document_extractions SET payload='{}'")
        with pytest.raises(sqlite3.IntegrityError):db.execute('DELETE FROM intake_reviews')
        verify(db)


def test_extraction_hash_and_audit_reference_are_verified(ledger):
    identifier=imported(ledger)
    with ledger.store.connect() as db:
        db.execute('DROP TRIGGER document_extractions_no_update')
        db.execute("UPDATE document_extractions SET payload=replace(payload,'100.00','999.00')")
    with pytest.raises(ValueError,match='EXTRACTION_HISTORY_DAMAGED'):ledger.stage(identifier)
    with pytest.raises(ValueError,match='EXTRACTION_HISTORY_DAMAGED'):backup(ledger.store)


@pytest.mark.parametrize('name',['supply-only.pdf','heating-oil.pdf','propane.pdf','credit.pdf','multiple-meters.pdf'])
def test_extracted_financial_and_quantity_semantics(ledger,name):
    identifier=imported(ledger,name);item=ledger.stage(identifier);bill=item['payload']
    if name=='supply-only.pdf':
        assert bill['lines'][0]['usage']=='0'
        assert item['intake']['extraction']['fields']['services.0.consumption_quantity']['value']=='100.25'
        bad=deepcopy(bill);bad['lines'][0].update(usage_role='consumption',usage='100.25')
        with pytest.raises(ValueError,match='SUPPLIER_ONLY'):ledger.approve_bill(identifier,bad,True)
    if name in {'heating-oil.pdf','propane.pdf'}:assert bill['lines'][0]['usage_role']=='delivery'
    ledger.approve_bill(identifier,bill,True)
    assert ledger.overview()['total_cents']==int(Decimal(bill['current_total'])*100)


def test_validation_conflicts_distinct_from_extraction_failure(ledger):
    identifier=imported(ledger,'reading-conflict.pdf');item=ledger.stage(identifier)
    assert not item['intake']['extraction']['codes']
    assert any(flag['code']=='READING_DIFFERENCE_REQUIRES_REVIEW' and not flag['blocking'] for flag in item['flags'])
    for name in ('negative-quantity.pdf','wrong-unit.pdf','supporting-document.pdf'):
        identifier=imported(ledger,name)
        with pytest.raises(ValueError):ledger.approve_bill(identifier,ledger.stage(identifier)['payload'],True)
        assert ledger.stage(identifier)['status']=='pending'


def test_intake_batch_isolated_duplicate_and_restart_recovery(ledger):
    intake=Intake(ledger,'demo');raw=(CORPUS/'electricity-digital.pdf').read_bytes()
    first=intake.import_file('synthetic.pdf',raw);assert first['state']=='needs_mapping'
    duplicate=intake.import_file('renamed.pdf',raw);assert duplicate['state']=='duplicate'
    assert duplicate['staged_ids']==first['staged_ids']
    assert intake.import_file('unsupported.exe',b'fictional')['state']=='unsupported'
    assert intake.import_file('broken.xml',b'<bad>')['state']=='failed_safely'
    with ledger.store.connect() as db:
        db.execute("UPDATE intake_attempts SET state='processing' WHERE id=?",(first['id'],))
        db.execute("INSERT INTO intake_attempts(filename,sha256,origin,started_at,state) VALUES ('synthetic-unfinished','missing','picker','2026-09-06','processing')")
    intake.recover_interrupted()
    assert intake.history()[0]['state']=='failed_safely'
    assert intake.item(first['id'])['staged_ids']==first['staged_ids']
    ledger.reject(first['staged_ids'][0]);assert intake.item(first['id'])['state']=='rejected'


def test_inbox_stability_symlinks_location_and_repeat_scan(ledger,tmp_path):
    intake=Intake(ledger,'demo');directory=tmp_path/'UtilityOS Inbox';directory.mkdir()
    target=directory/'synthetic.pdf';target.write_bytes((CORPUS/'electricity-digital.pdf').read_bytes())
    with pytest.raises(ValueError):intake.configure(str(ROOT),True)
    with pytest.raises(ValueError):intake.configure(str(ledger.store.sources),True)
    with pytest.raises(ValueError,match='CONFIRM'):intake.configure(str(directory),False)
    intake.configure(str(directory),True)
    result=intake.scan(str(directory),True);assert result['results'][0]['code']=='INBOX_FILE_STILL_CHANGING_RESCAN'
    old=time.time()-5;os.utime(target,(old,old))
    (directory/'unsafe.pdf').symlink_to(target)
    result=intake.scan(str(directory),True)
    assert [item['state'] for item in result['results']]==['needs_mapping','failed_safely']
    assert intake.scan(str(directory),True)['results'][0]['state']=='duplicate'
    assert target.read_bytes()==(CORPUS/'electricity-digital.pdf').read_bytes()
    with pytest.raises(ValueError,match='CHANGED'):intake.scan(str(tmp_path),True)


def test_private_extraction_corrections_and_settings_absent_from_diagnostics(ledger):
    identifier=imported(ledger);item=ledger.stage(identifier);bill=item['payload'];bill['account_alias']='PRIVATE_ACCOUNT_SENTINEL'
    ledger.save_draft(identifier,bill,0,intake_details={'service_address':'PRIVATE_SOURCE_REGION_SENTINEL'})
    with ledger.store.connect() as db:db.execute("INSERT INTO settings VALUES ('inbox_directory','/PRIVATE_PATH_SENTINEL')")
    report=json.dumps(ledger.diagnostics('demo'))
    for word in ('PRIVATE_ACCOUNT_SENTINEL','PRIVATE_SOURCE_REGION_SENTINEL','PRIVATE_PATH_SENTINEL','SYN-ACCOUNT','Imaginary Lane','bbox','pdfplumber'):
        assert word not in report


def test_expected_cadence_requires_mapping_and_handles_review_approval_cancel(ledger,raw_csv):
    coverage=Completeness(ledger.store)
    assert coverage.report('2026-09')['counts']['expected']==0
    identifier=ledger.import_file('base.csv',raw_csv)['staged_ids'][0];bill=ledger.stage(identifier)['payload']
    approved=ledger.approve_bill(identifier,bill,True)['id'];inventory=ledger.inventory()
    data={'account_id':inventory['accounts'][0]['id'],'meter_id':inventory['meters'][0]['id'],'revision':0,'cadence':'monthly',
          'first_month':'2026-09','last_month':None,'enabled':True,'reason':'Synthetic monthly schedule','acknowledge':True}
    coverage.configure(data)
    assert coverage.report('2026-09')['counts']=={'expected':1,'received':1,'under_review':0,'approved':1,'missing':0}
    assert coverage.report('2026-10')['counts']['missing']==1
    with pytest.raises(ValueError,match='CHANGED'):coverage.configure(data)
    data.update(revision=1,cadence='delivery');coverage.configure(data)
    assert coverage.report('2026-10')['counts']['missing']==0
    data.update(revision=2,cadence='monthly');coverage.configure(data)
    correction=ledger.create_correction(approved,'Synthetic replacement')['staged_id']
    ledger.cancel_bill(approved,'Synthetic cancellation',True)
    assert coverage.report('2026-09')['counts']['under_review']==1
    ledger.reject(correction)
    assert coverage.report('2026-09')['counts']['missing']==1


def test_authenticated_intake_preview_and_extra_review_routes(authenticated):
    client=authenticated
    sample=client.get('/api/intake-samples/electricity-digital.pdf')
    assert sample.content==(CORPUS/'electricity-digital.pdf').read_bytes()
    assert 'attachment' in sample.headers['content-disposition']
    assert client.get('/api/intake-samples/expected.json').status_code==404
    denied_location=client.post('/api/intake/configuration',json={'directory':str(ROOT),'acknowledge':True})
    assert denied_location.status_code==422 and str(ROOT) not in denied_location.text
    result=client.post('/api/intake',content=(CORPUS/'electricity-digital.pdf').read_bytes(),
              headers={'content-type':'application/octet-stream','x-filename':'synthetic.pdf','x-synthetic-data':'true'})
    assert result.status_code==200 and result.json()['state']=='needs_mapping'
    identifier=result.json()['staged_ids'][0];item=client.get(f'/api/staged/{identifier}').json()
    page=client.get(f'/api/sources/{item["document_id"]}/pages/1')
    assert page.content.startswith(b'\x89PNG') and page.headers['cache-control']=='no-store'
    invalid=client.get(f'/api/sources/{item["document_id"]}/pages/999');assert invalid.status_code==422
    denied=client.post(f'/api/staged/{identifier}/draft',json={'payload':item['payload'],'revision':0,'intake_details':{'secret':'private'}})
    assert denied.status_code==422 and 'private' not in denied.text
    approved=client.post(f'/api/staged/{identifier}/approve',json={'payload':item['payload'],'revision':0,'acknowledge':True})
    assert approved.status_code==200
    assert client.get('/api/intake').json()['items'][0]['state']=='approved'
    assert client.get('/api/intake/quality/export').headers['content-disposition'].startswith('attachment')
    client.post('/api/logout',json={});assert client.get(f'/api/sources/{item["document_id"]}/pages/1').status_code==401


def test_model_preparation_checks_hash_and_publishes_atomically(tmp_path,monkeypatch):
    from scripts import prepare_ocr
    raw=b'synthetic-model-for-public-file-install-contract'
    source=tmp_path/'reviewed.model';source.write_bytes(raw)
    monkeypatch.setattr(prepare_ocr,'MODEL_BYTES',len(raw))
    monkeypatch.setattr(prepare_ocr,'MODEL_SHA256',sha256(raw).hexdigest())
    destination=tmp_path/'models'
    prepare_ocr.prepare(source,destination);prepare_ocr.prepare(source,destination)
    assert [p.name for p in destination.iterdir()]==['eng.traineddata']
    assert (destination/'eng.traineddata').read_bytes()==raw
    source.write_bytes(b'x'*len(raw))
    with pytest.raises(ValueError,match='HASH'):prepare_ocr.prepare(source,destination)
    assert (destination/'eng.traineddata').read_bytes()==raw
    link=tmp_path/'link';link.symlink_to(destination,target_is_directory=True)
    with pytest.raises(ValueError,match='SYMLINKS'):prepare_ocr.prepare(source,link)
    with pytest.raises(ValueError,match='EXTERNAL'):prepare_ocr.prepare(source,ROOT/'models')


def test_fictional_corpus_regenerates_exactly(tmp_path):
    from scripts.synthetic_documents import generate
    generate(tmp_path)
    assert {p.name for p in tmp_path.iterdir()}=={p.name for p in CORPUS.iterdir()}
    assert all(p.read_bytes()==(CORPUS/p.name).read_bytes() for p in tmp_path.iterdir())


def test_mixed_closed_csv_intake_does_not_claim_every_invoice_approved(ledger):
    intake=Intake(ledger,'demo')
    result=intake.import_file('synthetic-batch.csv',(ROOT/'samples/demo-review.csv').read_bytes())
    first,second=result['staged_ids']
    ledger.approve_bill(first,ledger.stage(first)['payload'],True)
    ledger.reject(second)
    assert intake.item(result['id'])['state']=='partially_approved'


def test_published_extraction_schema_matches_runtime_contract():
    assert json.loads((ROOT/'docs/extraction-schema.json').read_text())==Extraction.model_json_schema()


@pytest.mark.parametrize('checkpoint',['extraction_finished','extraction_transaction'])
def test_killed_pdf_intake_keeps_evidence_and_financial_state_atomic(ledger,tmp_path,checkpoint):
    from test_readiness import kill_at
    kill_at(tmp_path,'intake',checkpoint,ledger.store.directory)
    intake=Intake(ledger,'demo');intake.recover_interrupted()
    assert intake.history()[0]['state']=='failed_safely'
    assert ledger.stages()==[] and ledger.overview()['total_cents']==0
    result=intake.import_file('retry.pdf',(CORPUS/'electricity-digital.pdf').read_bytes())
    assert result['count']==1
    with ledger.store.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM document_extractions').fetchone()[0]==1
        verify(db)
    assert check(ledger.store)['sources']=='ok'


def test_killed_schema_three_to_four_preserves_original_and_retries(tmp_path,raw_csv):
    from test_readiness import previous_store,kill_at
    from utilityos.operations import migrate
    old=previous_store(tmp_path,raw_csv,3);before=old.path.read_bytes()
    kill_at(tmp_path,'migration','intake_migration',old.directory)
    # Backup audit events are intentionally durable before migration starts.
    assert Ledger(old).export_csv()
    with old.connect() as db:
        assert db.execute("SELECT value FROM settings WHERE key='schema_version'").fetchone()[0]=='3'
        assert not db.execute("SELECT 1 FROM sqlite_master WHERE name='document_extractions'").fetchone()
    migrate(old.directory,'demo')
    assert check(Store(old.directory,'demo'))['schema_version']==4


def test_scan_continuation_reaches_files_beyond_first_batch(ledger,tmp_path):
    intake=Intake(ledger,'demo');directory=tmp_path/'many-files';directory.mkdir();old=time.time()-10
    # Invalid files are inexpensive and still occupy their deliberate scan page.
    for index in range(27):
        path=directory/f'{index:02}.csv';path.write_bytes(b'invalid,synthetic\n');os.utime(path,(old,old))
    intake.configure(str(directory),True)
    first=intake.scan(str(directory),True);assert len(first['results'])==25 and first['remaining']==2
    second=intake.scan(str(directory),True,first['next_cursor']);assert len(second['results'])==2 and second['next_cursor'] is None
    assert len(intake.history())==27


def test_template_quality_uses_final_approved_corrections_and_fixed_fields(ledger):
    from utilityos.extraction_quality import report
    for name in ('electricity-digital.pdf','layout-v1.pdf'):
        identifier=imported(ledger,name);bill=ledger.stage(identifier)['payload'];bill['current_total']=bill['lines'][0]['current_charge']='109.00'
        ledger.save_draft(identifier,bill,0,intake_details={'service_address':'PRIVATE_CORRECTION_SENTINEL'})
        ledger.save_draft(identifier,bill,1)
        ledger.approve_bill(identifier,bill,True,revision=2)
    result=report(ledger.store)
    row=next(row for row in result['rows'] if row['field']=='invoice_total')
    assert row['count']==2 and row['candidate_improvement']
    assert 'PRIVATE_CORRECTION_SENTINEL' not in json.dumps(result) and '109.00' not in json.dumps(result)
    assert result['automatic_template_changes'] is False


def test_pdf_resource_limit_and_footer_over_scan(tmp_path):
    import io
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    from utilityos.pdf_worker import render
    output=io.BytesIO();pdf=canvas.Canvas(output,invariant=1)
    for _ in range(21):pdf.drawString(40,700,'FICTIONAL PAGE LIMIT TEST');pdf.showPage()
    pdf.save();assert task(output.getvalue())['codes']==['PDF_PAGE_LIMIT']
    output=io.BytesIO();pdf=canvas.Canvas(output,pagesize=(612,792),invariant=1)
    image=render((CORPUS/'electricity-digital.pdf').read_bytes(),1)
    pdf.drawImage(ImageReader(image),0,0,612,792);image.close()
    pdf.drawString(40,15,'FICTIONAL digital footer on an image-only test bill; no real account or provider data.')
    pdf.save();result=task(output.getvalue())
    assert result['pdf_kind']=='scanned' and 'OCR_UNAVAILABLE_MANUAL_ENTRY' in result['codes']
