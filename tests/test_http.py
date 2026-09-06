from utilityos.security import DEMO_PASSWORD


def test_api_rejects_unauthenticated_reads(client):
    for path in ['/api/overview','/api/inventory','/api/staged','/api/ledger/export','/api/diagnostics','/api/sources/1']:
        assert client.get(path).status_code==401

def test_auth_cookie_is_httponly_samesite(client):
    result=client.post('/api/login',json={'password':DEMO_PASSWORD},headers={'origin':'http://127.0.0.1:8765'})
    cookie=result.headers['set-cookie'].lower()
    assert 'httponly' in cookie and 'samesite=strict' in cookie

def test_cross_origin_login_is_rejected(client):
    result=client.post('/api/login',json={'password':DEMO_PASSWORD},headers={'origin':'https://attacker.invalid'})
    assert result.status_code==403

def test_dns_rebinding_host_is_rejected(client):
    assert client.get('/api/meta',headers={'host':'attacker.invalid'}).status_code==400

def test_mutations_require_csrf_token(authenticated):
    authenticated.headers['x-csrf-token']='wrong'
    assert authenticated.post('/api/logout',json={}).status_code==403

def test_logout_revokes_session(authenticated):
    assert authenticated.post('/api/logout',json={}).status_code==200
    assert authenticated.get('/api/overview').status_code==401

def test_csp_disallows_cloud_and_inline_execution(client):
    csp=client.get('/').headers['content-security-policy']
    assert "connect-src 'self'" in csp and "frame-ancestors 'none'" in csp
    assert "'unsafe-inline'" not in csp

def test_import_approve_export_http_flow(authenticated,raw_csv):
    result=authenticated.post('/api/import',content=raw_csv,headers={'content-type':'application/octet-stream','x-filename':'example.csv','x-synthetic-data':'true'})
    assert result.status_code==200,result.text
    identifier=result.json()['staged_ids'][0]
    draft=authenticated.get(f'/api/staged/{identifier}').json()
    assert authenticated.get('/api/overview').json()['total_cents']==0
    approved=authenticated.post(f'/api/staged/{identifier}/approve',json={'payload':draft['payload'],'acknowledge':True})
    assert approved.status_code==200,approved.text
    assert authenticated.get('/api/overview').json()['total_cents']==57980
    assert 'attachment' in authenticated.get('/api/ledger/export').headers['content-disposition']
    source=authenticated.get(f"/api/sources/{draft['document_id']}")
    assert source.content==raw_csv
    assert source.headers['x-content-type-options']=='nosniff'

def test_demo_requires_synthetic_confirmation(authenticated,raw_csv):
    result=authenticated.post('/api/import',content=raw_csv,headers={'content-type':'application/octet-stream','x-filename':'example.csv'})
    assert result.status_code==422

def test_login_rate_limit(client):
    for _ in range(5):
        result=client.post('/api/login',json={'password':'wrong'},headers={'origin':'http://127.0.0.1:8765'})
        assert result.status_code==401
    result=client.post('/api/login',json={'password':DEMO_PASSWORD},headers={'origin':'http://127.0.0.1:8765'})
    assert result.status_code==429

def test_private_responses_are_no_store(authenticated):
    assert authenticated.get('/api/overview').headers['cache-control']=='no-store'

def test_unsupported_upload_extension(authenticated):
    result=authenticated.post('/api/import',content=b'hello',headers={'content-type':'application/octet-stream','x-filename':'test.html','x-synthetic-data':'true'})
    assert result.status_code==422


def test_correction_and_saved_draft_http(authenticated,raw_csv):
    item=authenticated.post('/api/import',content=raw_csv,headers={'content-type':'application/octet-stream','x-filename':'synthetic.csv','x-synthetic-data':'true'}).json()['staged_ids'][0]
    payload=authenticated.get(f'/api/staged/{item}').json()['payload']
    bill=authenticated.post(f'/api/staged/{item}/approve',json={'payload':payload,'acknowledge':True}).json()['id']
    correction=authenticated.post(f'/api/bills/{bill}/correct',json={'reason':'Synthetic corrected amount'}).json()['staged_id']
    payload['current_total']=payload['lines'][0]['current_charge']='50.00'
    save=authenticated.post(f'/api/staged/{correction}/draft',json={'payload':payload,'revision':0,'correction_of':bill,'reason':'Synthetic corrected amount'})
    assert save.status_code==200,save.text
    assert authenticated.post(f'/api/staged/{correction}/approve',json={'payload':payload,'acknowledge':True,'revision':0}).status_code==422
    approved=authenticated.post(f'/api/staged/{correction}/approve',json={'payload':payload,'acknowledge':True,'revision':1})
    assert approved.status_code==200,approved.text
    assert authenticated.get('/api/overview').json()['total_cents']==5000
    assert len(authenticated.get('/api/bills').json())==2
    cancelled=authenticated.post(f"/api/bills/{approved.json()['id']}/cancel",json={'reason':'Synthetic cancellation','acknowledge':True})
    assert cancelled.status_code==200,cancelled.text
    assert authenticated.get('/api/overview').json()['total_cents']==0


def test_browser_backup_requires_ack_and_protects_download(authenticated):
    assert authenticated.post('/api/backups',json={}).status_code==422
    result=authenticated.post('/api/backups',json={'acknowledge':True})
    assert result.status_code==200,result.text
    url=result.json()['download_url']
    response=authenticated.get(url)
    assert response.status_code==200,response.text
    assert response.content.startswith(b'PK')
    assert response.headers['content-disposition'].startswith('attachment')
    assert authenticated.get('/api/backups/utilityos.sqlite3').status_code==422
    authenticated.post('/api/logout',json={})
    assert authenticated.get(url).status_code==401


def test_new_mutations_require_same_origin_and_csrf(authenticated):
    for path in ['/api/backups','/api/staged/1/draft','/api/bills/1/correct','/api/bills/1/cancel','/api/inventory/meter/1']:
        assert authenticated.post(path,json={},headers={'origin':'https://synthetic.invalid'}).status_code==403
        assert authenticated.post(path,json={},headers={'x-csrf-token':'bad'}).status_code==403


def test_backup_storage_errors_are_bounded(authenticated,monkeypatch):
    import utilityos.app
    def fail(store):raise OSError('/SYNTHETIC_PRIVATE_PATH/account-9988')
    monkeypatch.setattr(utilityos.app,'backup',fail)
    response=authenticated.post('/api/backups',json={'acknowledge':True})
    assert response.status_code==500
    assert '9988' not in response.text
    assert 'SYNTHETIC_PRIVATE_PATH' not in response.text


def test_audit_and_corrupt_draft_recovery_http(authenticated,raw_csv):
    item=authenticated.post('/api/import',content=raw_csv,headers={'content-type':'application/octet-stream','x-filename':'synthetic.csv','x-synthetic-data':'true'}).json()['staged_ids'][0]
    ledger=authenticated.app.state.ledger
    payload=ledger.stage(item)['payload']
    ledger.save_draft(item,payload,0)
    with ledger.store.connect() as db:db.execute('UPDATE staged SET review_payload=? WHERE id=?',('{broken',item))
    assert authenticated.get('/api/staged').status_code==200
    assert authenticated.get(f'/api/staged/{item}').json()['data_error']
    failed=authenticated.post(f'/api/staged/{item}/approve',json={'payload':payload,'acknowledge':True,'revision':1})
    assert failed.status_code==422
    result=authenticated.post(f'/api/staged/{item}/recover',json={'revision':1,'acknowledge':True})
    assert result.status_code==200 and result.json()['status']=='pending'
    codes=[r['code'] for r in authenticated.get('/api/audit').json()['events']]
    assert 'RECOVER_DRAFT' in codes
    authenticated.post('/api/logout',json={})
    assert authenticated.get('/api/audit').status_code==401


def test_staff_sensitive_actions_require_current_passphrase(tmp_path,raw_csv):
    from fastapi.testclient import TestClient
    from utilityos.config import Config
    from utilityos.app import create_app
    from utilityos.security import set_password
    app=create_app(Config(tmp_path/'synthetic-staff','staff'))
    password='synthetic-staff-password-only';set_password(app.state.store,password)
    ledger=app.state.ledger
    item=ledger.import_file('synthetic.csv',raw_csv)['staged_ids'][0]
    bill=ledger.approve_bill(item,ledger.stage(item)['payload'],True)['id']
    correction=ledger.create_correction(bill,'Synthetic correction')['staged_id']
    with TestClient(app,base_url='http://127.0.0.1:8765') as client:
        client.headers['origin']='http://127.0.0.1:8765'
        login=client.post('/api/login',json={'password':password})
        client.headers['x-csrf-token']=login.json()['csrf']
        args={'payload':ledger.stage(correction)['payload'],'acknowledge':True,'revision':0}
        assert client.post(f'/api/staged/{correction}/approve',json=args).status_code==422
        assert ledger.overview()['stats']['approved_bills']==1
        result=client.post(f'/api/staged/{correction}/approve',json={**args,'current_passphrase':password})
        assert result.status_code==200
        new=result.json()['id'];args={'reason':'Synthetic cancellation','acknowledge':True}
        assert client.post(f'/api/bills/{new}/cancel',json=args).status_code==422
        assert client.post(f'/api/bills/{new}/cancel',json={**args,'current_passphrase':'wrong'}).status_code==422
        assert ledger.overview()['total_cents']==57980
        assert client.post(f'/api/bills/{new}/cancel',json={**args,'current_passphrase':password}).status_code==200
        events=client.get('/api/audit').json()['events']
        assert events[0]['actor']=='reauthenticated_operator'
        assert password not in str(events)+client.get('/api/diagnostics').text+client.get('/api/ledger/export').text
