"""Local-only HTTP application. Start through run.py to enforce loopback binding."""
from pathlib import Path
import hmac
import json
import time
import sqlite3
import re
from .operations import backup
from .audit import acting_as
from .storage import read_source
from urllib.parse import unquote
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from . import __version__
from .config import Config, ROOT, MAX_UPLOAD
from .db import Store
from .service import Ledger
from .security import Sessions, verify_password
from .parsers import ValidationError


def create_app(config: Config):
    config.validate()
    store=Store(config.data_dir,config.mode)
    ledger=Ledger(store)
    sessions=Sessions()
    app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
    app.state.ledger=ledger
    app.state.sessions=sessions
    app.state.store=store

    @app.middleware('http')
    async def boundary(request: Request, call_next):
        host=request.headers.get('host','')
        allowed_hosts={f'127.0.0.1:{config.port}',f'localhost:{config.port}'}
        if host not in allowed_hosts:
            response=JSONResponse({'error':'HOST_NOT_ALLOWED'},status_code=400)
        elif request.method not in {'GET','HEAD','POST'}:
            response=JSONResponse({'error':'METHOD_NOT_ALLOWED'},status_code=405)
        elif request.method=='POST' and request.headers.get('origin') not in config.origins:
            response=JSONResponse({'error':'SAME_ORIGIN_REQUIRED'},status_code=403)
        else:
            if request.url.path.startswith('/api/') and request.url.path not in {'/api/login','/api/meta'}:
                session=sessions.get(request.cookies.get('utilityos_session'))
                if not session:
                    response=JSONResponse({'error':'LOGIN_REQUIRED'},status_code=401)
                elif request.method=='POST' and not hmac.compare_digest(request.headers.get('x-csrf-token',''),session['csrf']):
                    response=JSONResponse({'error':'CSRF_TOKEN_REQUIRED'},status_code=403)
                else:
                    request.state.session=session
                    response=await call_next(request)
            else:
                response=await call_next(request)
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['Cache-Control']='no-store'
        response.headers['Permissions-Policy']='camera=(), microphone=(), geolocation=()'
        return response

    @app.exception_handler(ValidationError)
    async def invalid(request, exc):
        return JSONResponse({'error':exc.code},status_code=422)

    @app.exception_handler(sqlite3.IntegrityError)
    async def integrity(request, exc):
        return JSONResponse({'error':'DATABASE_CONFLICT_REVIEW_IMPORT'},status_code=409)

    @app.exception_handler(Exception)
    async def unexpected(request, exc):
        # Explicitly avoid echoing exception data or paths into the response.
        return JSONResponse({'error':'INTERNAL_ERROR_USE_SYNTHETIC_REPRODUCTION'},status_code=500)

    async def body(request,limit=256*1024):
        try:
            size=int(request.headers.get('content-length','0'))
        except ValueError:
            raise ValidationError('CONTENT_LENGTH_INVALID')
        if size>limit:
            raise ValidationError('REQUEST_TOO_LARGE')
        raw=bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw)>limit:
                raise ValidationError('REQUEST_TOO_LARGE')
        return bytes(raw)

    async def json_body(request):
        if request.headers.get('content-type','').split(';')[0]!='application/json':
            raise ValidationError('APPLICATION_JSON_REQUIRED')
        raw=await body(request)
        try:
            data=json.loads(raw)
        except (json.JSONDecodeError,UnicodeError):
            raise ValidationError('JSON_INVALID')
        if not isinstance(data,dict):
            raise ValidationError('JSON_OBJECT_REQUIRED')
        return data

    def reauthenticate(data):
        if config.mode == 'demo':
            return 'local_operator'
        if sessions.rate_limited():
            raise ValidationError('TOO_MANY_ATTEMPTS_WAIT_ONE_MINUTE')
        password = data.get('current_passphrase')
        if not isinstance(password, str) or not verify_password(store, password):
            sessions.failures.append(time.monotonic())
            raise ValidationError('CURRENT_PASSPHRASE_REQUIRED_FOR_SENSITIVE_ACTION')
        return 'reauthenticated_operator'

    @app.get('/api/meta')
    def meta(request: Request):
        return {'authenticated':sessions.get(request.cookies.get('utilityos_session')) is not None,'app':'SKS UtilityOS','version':__version__,'mode':config.mode,'local_only':True,'synthetic':config.mode=='demo'}

    @app.post('/api/login')
    async def login(request: Request):
        if sessions.rate_limited():
            return JSONResponse({'error':'TOO_MANY_ATTEMPTS_WAIT_ONE_MINUTE'},status_code=429)
        data=await json_body(request)
        password=data.get('password','')
        if not isinstance(password,str) or not verify_password(store,password):
            sessions.failures.append(time.monotonic())
            return JSONResponse({'error':'PASSPHRASE_INCORRECT'},status_code=401)
        token,csrf=sessions.create()
        response=JSONResponse({'csrf':csrf})
        response.set_cookie('utilityos_session',token,httponly=True,samesite='strict',max_age=1800,path='/')
        return response

    @app.get('/api/session')
    def session(request: Request):
        return {'csrf':request.state.session['csrf'],'mode':config.mode}

    @app.post('/api/logout')
    def logout(request: Request):
        sessions.remove(request.cookies.get('utilityos_session'))
        response=JSONResponse({'ok':True})
        response.delete_cookie('utilityos_session',path='/')
        return response

    @app.get('/api/overview')
    def overview(month: str|None=None):
        return ledger.overview(month)

    @app.get('/api/inventory')
    def inventory():
        return ledger.inventory()

    @app.get('/api/staged')
    def stages():
        return ledger.stages()

    @app.get('/api/staged/{item_id}')
    def stage(item_id:int):
        return ledger.stage(item_id)

    @app.post('/api/validate-bill')
    async def validate(request:Request):
        data=await json_body(request)
        return ledger.validate_draft(data.get('payload'),data.get('staged_id'))

    @app.get('/api/bills')
    def bills():
        return ledger.bills()

    @app.post('/api/staged/{item_id}/draft')
    async def save_draft(item_id:int,request:Request):
        data=await json_body(request)
        return ledger.save_draft(item_id,data.get('payload'),data.get('revision'),data.get('correction_of'),data.get('reason',''))

    @app.post('/api/staged/{item_id}/recover')
    async def recover_draft(item_id:int,request:Request):
        data=await json_body(request)
        return ledger.recover_draft(item_id,data.get('revision'),data.get('acknowledge') is True)

    @app.get('/api/audit')
    def audit_history(before:int|None=None):
        return ledger.audit_history(before)

    @app.post('/api/bills/{bill_id}/correct')
    async def correct(bill_id:int,request:Request):
        return ledger.create_correction(bill_id,(await json_body(request)).get('reason',''))

    @app.post('/api/bills/{bill_id}/cancel')
    async def cancel(bill_id:int,request:Request):
        data=await json_body(request)
        with acting_as(reauthenticate(data)):
            return ledger.cancel_bill(bill_id,data.get('reason',''),data.get('acknowledge') is True)

    @app.post('/api/inventory/{kind}/{entity_id}')
    async def edit_inventory(kind:str,entity_id:int,request:Request):
        data=await json_body(request)
        return ledger.edit_inventory(kind,entity_id,data.get('before'),data.get('value'),data.get('reason',''),data.get('acknowledge') is True)

    @app.post('/api/backups')
    async def create_backup(request:Request):
        data=await json_body(request)
        if data.get('acknowledge') is not True:
            raise ValidationError('CONFIRM_PRIVATE_BACKUP_CONTENTS')
        saved=backup(store)
        return {'download_url':'/api/backups/'+saved.name}

    @app.get('/api/backups/{filename}')
    def download_backup(filename:str):
        if not re.fullmatch(r'utilityos-private-[0-9T_+\-]+-[0-9a-f]{6}\.zip',filename):
            raise ValidationError('BACKUP_NOT_FOUND')
        path=store.directory/'backups'/filename
        if not path.is_file() or path.is_symlink():
            raise ValidationError('BACKUP_NOT_FOUND')
        return FileResponse(path,media_type='application/zip',filename='utilityos-private-backup.zip')

    @app.post('/api/staged/{item_id}/approve')
    async def approve(item_id:int,request:Request):
        data=await json_body(request)
        item=ledger.stage(item_id)
        if item['kind']=='bill':
            with acting_as(reauthenticate(data) if item.get('correction_of') is not None else 'local_operator'):
                return ledger.approve_bill(item_id,data.get('payload'),data.get('acknowledge') is True,revision=data.get('revision',0))
        if data.get('acknowledge') is not True:
            raise ValidationError('CONFIRM_INTERVAL_MAPPING_AND_SOURCE_REVIEW')
        return ledger.approve_intervals(item_id,data.get('meter_code',''))

    @app.post('/api/staged/{item_id}/reject')
    async def reject(item_id:int,request:Request):
        await json_body(request)
        ledger.reject(item_id)
        return {'ok':True}

    @app.post('/api/import')
    async def upload(request:Request):
        if request.headers.get('content-type','').split(';')[0]!='application/octet-stream':
            raise ValidationError('OCTET_STREAM_REQUIRED')
        if config.mode=='demo' and request.headers.get('x-synthetic-data')!='true':
            raise ValidationError('DEMO_REQUIRES_SYNTHETIC_DATA_CONFIRMATION')
        filename=unquote(request.headers.get('x-filename',''))
        return ledger.import_file(filename,await body(request,MAX_UPLOAD))

    @app.get('/api/sources/{document_id}')
    def source(document_id:int):
        with store.connect() as db:
            row=db.execute('SELECT * FROM documents WHERE id=?',(document_id,)).fetchone()
        if not row:
            return JSONResponse({'error':'SOURCE_NOT_FOUND'},status_code=404)
        read_source(store,row)
        path=store.sources/f"{row['sha256']}{row['extension']}"
        return FileResponse(path,media_type='application/octet-stream',filename=f"local-source-{document_id}{row['extension']}",content_disposition_type='attachment')

    @app.get('/api/intervals')
    def intervals(meter:str|None=None):
        return ledger.intervals(meter)

    @app.get('/api/diagnostics')
    def diagnostics():
        return ledger.diagnostics(config.mode,config.port,running=True)

    @app.get('/api/diagnostics/export')
    def diagnostics_export():
        return Response(json.dumps(ledger.diagnostics(config.mode,config.port,running=True),indent=2),media_type='application/json',
                        headers={'Content-Disposition':'attachment; filename="utilityos-safe-diagnostics.json"'})

    @app.get('/api/ledger/export')
    def export():
        return Response(ledger.export_csv(),media_type='text/csv',
                        headers={'Content-Disposition':'attachment; filename="staff-private-utility-ledger.csv"'})

    @app.get('/api/samples/{filename}')
    def sample(filename:str):
        allowed={'demo-import.csv','demo-intervals.xml','blank-bill-template.csv','demo-invoice.pdf'}
        if filename not in allowed:
            return JSONResponse({'error':'SAMPLE_NOT_FOUND'},status_code=404)
        return FileResponse(ROOT/'samples'/filename,media_type='application/octet-stream',filename=filename)

    app.mount('/',StaticFiles(directory=ROOT/'web',html=True),name='web')
    return app
