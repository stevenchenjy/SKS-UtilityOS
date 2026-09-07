"""Provider APIs share the existing session, origin, CSRF and body boundary."""
from fastapi import Request
from starlette.concurrency import run_in_threadpool
from .provider_studio import ProviderStudio


def mount(app, ledger, json_body):
    studio = ProviderStudio(ledger)
    app.state.provider_studio = studio

    @app.get('/api/providers')
    def providers():
        return studio.listing()

    @app.get('/api/providers/documents')
    def documents():
        return studio.documents()

    @app.get('/api/providers/documents/{document_id}/observations')
    def observations(document_id: int):
        return studio.observe(document_id)

    @app.post('/api/providers')
    async def create(request: Request):
        return studio.create_provider(await json_body(request))

    @app.post('/api/providers/{provider_id}/layouts')
    async def create_layout(provider_id: str, request: Request):
        return studio.save_layout(provider_id, await json_body(request))

    @app.post('/api/providers/preview')
    async def preview(request: Request):
        data = await json_body(request)
        return await run_in_threadpool(studio.preview, data.get('provider_id'), data.get('document_id'), data.get('definition'))

    @app.get('/api/provider-layouts/{layout_id}')
    def inspect(layout_id: str):
        return studio.inspect(layout_id)

    @app.post('/api/provider-layouts/{layout_id}/preview')
    async def preview_saved(layout_id: str, request: Request):
        data = await json_body(request)
        layout = studio.inspect(layout_id)['layout']
        return await run_in_threadpool(studio.preview, layout['provider_id'], data.get('document_id'), layout['definition'], layout_id)

    @app.post('/api/provider-layouts/{layout_id}/validate')
    async def validate(layout_id: str, request: Request):
        data = await json_body(request)
        return await run_in_threadpool(studio.validate, layout_id, data.get('document_ids'))

    @app.post('/api/provider-layouts/{layout_id}/activate')
    async def activate(layout_id: str, request: Request):
        return studio.change_state(layout_id, 'active', await json_body(request))

    @app.post('/api/provider-layouts/{layout_id}/retire')
    async def retire(layout_id: str, request: Request):
        return studio.change_state(layout_id, 'retired', await json_body(request))

    @app.get('/api/provider-layouts/{layout_id}/support')
    def support(layout_id: str):
        return studio.support(layout_id)
