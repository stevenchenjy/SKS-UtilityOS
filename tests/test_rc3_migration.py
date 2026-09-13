"""Schema 7 is a compatibility barrier; old rows/sources are not rewritten."""
from contextlib import closing
import sqlite3
import json
import zipfile
from hashlib import sha256
import pytest
from utilityos.config import ROOT
from utilityos.db import Store
from utilityos.migrations import to_v6
from utilityos.operations import migrate, check, restore
from utilityos.service import Ledger


def test_schema_six_explicit_migration_and_preserved_rollback_backup(tmp_path,raw_csv):
    directory=tmp_path/'rc2';directory.mkdir();(directory/'sources').mkdir()
    with closing(sqlite3.connect(directory/'utilityos.sqlite3')) as db, db:
        db.executescript((ROOT/'tests/fixtures/schema_v5.sql').read_text())
        to_v6(db)
        db.execute("UPDATE settings SET value='6' WHERE key='schema_version'")
    old=Store(directory,'demo',expected_schema=6)
    ledger=Ledger(old)
    stage=ledger.import_file('synthetic.csv',raw_csv)['staged_ids'][0]
    ledger.approve_bill(stage,ledger.stage(stage)['payload'],True,revision=0)
    original=ledger.export_csv()
    before=old.path.read_bytes()
    with pytest.raises(ValueError,match='SCHEMA_VERSION_UNSUPPORTED'):
        Store(directory,'demo')
    assert old.path.read_bytes()==before
    saved=migrate(directory,'demo')
    upgraded=Store(directory,'demo')
    assert check(upgraded)['schema_version']==7
    assert Ledger(upgraded).export_csv()==original
    with pytest.raises(ValueError,match='SCHEMA_VERSION_UNSUPPORTED'):
        Store(directory,'demo',expected_schema=6)
    # New code refuses the older backup; real rollback must use old code.
    recovered=Store(tmp_path/'rollback','demo')
    with pytest.raises(ValueError,match='BACKUP_SCHEMA_OR_MODE_MISMATCH'):
        restore(recovered,saved,'demo')
    # Inspect the preserved synthetic backup independently without changing it.
    inspected=tmp_path/'inspection';inspected.mkdir()
    with zipfile.ZipFile(saved) as archive:
        manifest=json.loads(archive.read('MANIFEST.json'))
        assert manifest['schema_version']==6
        for name,digest in manifest['files'].items():
            raw=archive.read(name);assert sha256(raw).hexdigest()==digest
            target=inspected/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    snapshot=Store(inspected,'demo',initialize=False,expected_schema=6)
    assert Ledger(snapshot).export_csv()==original
    assert Ledger(upgraded).export_csv()==original
