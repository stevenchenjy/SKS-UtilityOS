"""Real process kill inside an authenticated synthetic provider transaction."""
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
from utilityos.app import create_app
from utilityos.config import Config
from utilityos.security import DEMO_PASSWORD
from utilityos import provider_storage

directory,marker,operation,layout_id=sys.argv[1:]
client=TestClient(create_app(Config(Path(directory),'demo',8765)),base_url='http://127.0.0.1:8765')
origin={'origin':'http://127.0.0.1:8765'}
login=client.post('/api/login',json={'password':DEMO_PASSWORD},headers=origin)
client.headers.update({**origin,'x-csrf-token':login.json()['csrf']})
layout=client.get('/api/provider-layouts/'+layout_id).json()['layout']
original=provider_storage.append
def append(db,kind,*args,**kwargs):
    result=original(db,kind,*args,**kwargs)
    if kind==('layout' if operation=='save' else 'state'):
        Path(marker).write_text('inside transaction')
        while True:time.sleep(1)
    return result
provider_storage.append=append
if operation=='save':
    result=client.post('/api/providers/'+layout['provider_id']+'/layouts',json={'definition':layout['definition'],
        'expected_version':layout['version'],'parent_layout_id':layout_id})
else:
    result=client.post('/api/provider-layouts/'+layout_id+'/activate',json={'state_id':layout['state_id'],
        'validation_id':layout['validation']['id'],'acknowledge':True})
raise SystemExit('CHECKPOINT_NOT_REACHED_'+str(result.status_code))
