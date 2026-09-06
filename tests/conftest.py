from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest
from fastapi.testclient import TestClient
from utilityos.config import Config,ROOT
from utilityos.db import Store
from utilityos.service import Ledger
from utilityos.security import set_password,DEMO_PASSWORD
from utilityos.app import create_app
from utilityos.parsers import parse_csv

@pytest.fixture
def store(tmp_path):
    return Store(tmp_path/'local-data','demo')

@pytest.fixture
def ledger(store):
    return Ledger(store)

@pytest.fixture
def bill():
    return parse_csv((ROOT/'samples/demo-import.csv').read_bytes())[0]

@pytest.fixture
def raw_csv():
    return (ROOT/'samples/demo-import.csv').read_bytes()

@pytest.fixture
def raw_xml():
    return (ROOT/'samples/demo-intervals.xml').read_bytes()

@pytest.fixture
def client(tmp_path):
    config=Config(tmp_path/'http-data','demo',8765)
    app=create_app(config)
    set_password(app.state.store,DEMO_PASSWORD)
    with TestClient(app,base_url='http://127.0.0.1:8765',raise_server_exceptions=False) as c:
        yield c

@pytest.fixture
def authenticated(client):
    origin={'origin':'http://127.0.0.1:8765'}
    result=client.post('/api/login',json={'password':DEMO_PASSWORD},headers=origin)
    assert result.status_code==200
    client.headers.update({**origin,'x-csrf-token':result.json()['csrf']})
    return client
