"""Mapped usage routes behind the application's authentication and CSRF boundary."""
from urllib.parse import unquote
from fastapi import Request
from starlette.concurrency import run_in_threadpool
from .config import MAX_UPLOAD
from .parsers import ValidationError
from .usage import UsageImport


def mount(app, ledger, json_body, body, config):
    usage = UsageImport(ledger)
    app.state.usage = usage

    @app.get('/api/usage')
    def listing():
        return usage.listing()

    @app.post('/api/usage/import')
    async def upload(request: Request):
        if request.headers.get('content-type','').split(';')[0] != 'application/octet-stream':
            raise ValidationError('OCTET_STREAM_REQUIRED')
        if config.mode == 'demo' and request.headers.get('x-synthetic-data') != 'true':
            raise ValidationError('DEMO_REQUIRES_SYNTHETIC_DATA_CONFIRMATION')
        raw = await body(request, MAX_UPLOAD)
        return await run_in_threadpool(usage.import_file,unquote(request.headers.get('x-filename','')),raw)

    @app.get('/api/usage/{identifier}')
    def detail(identifier: int):
        return usage.detail(identifier)

    @app.post('/api/usage/{identifier}/preview')
    async def preview(identifier: int, request: Request):
        return await run_in_threadpool(usage.preview,identifier,await json_body(request))

    @app.post('/api/usage/{identifier}/approve')
    async def approve(identifier: int, request: Request):
        return await run_in_threadpool(usage.approve,identifier,await json_body(request))

    @app.post('/api/usage/{identifier}/reject')
    async def reject(identifier: int, request: Request):
        return await run_in_threadpool(usage.close,identifier,await json_body(request))

    @app.post('/api/usage/{identifier}/withdraw')
    async def withdraw(identifier: int, request: Request):
        return await run_in_threadpool(usage.close,identifier,await json_body(request),withdraw=True)

    @app.post('/api/usage/{identifier}/reattempt')
    async def reattempt(identifier: int, request: Request):
        return await run_in_threadpool(usage.reattempt,identifier,await json_body(request))
