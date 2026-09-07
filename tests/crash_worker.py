"""Test-only process checkpoints. Parent kills this child; no product fault hooks."""
from contextlib import contextmanager
from pathlib import Path
import os
import sys
import time
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from utilityos.config import ROOT
from utilityos.db import Store
from utilityos.service import Ledger
from utilityos.operations import instance_lock, backup, restore, migrate
from utilityos.migrations import read_version
from utilityos import storage, migrations

operation, checkpoint, directory, marker, *rest = sys.argv[1:]
directory, marker = Path(directory), Path(marker)


def pause():
    marker.touch()
    while True:
        time.sleep(.05)


if checkpoint == 'partial_source':
    original_fdopen = os.fdopen
    class PartialWriter:
        def __init__(self, stream): self.stream=stream
        def __enter__(self): return self
        def __exit__(self,*args): self.stream.close()
        def write(self, data):
            self.stream.write(data[:20]);self.stream.flush();os.fsync(self.stream.fileno());pause()
    def fdopen(fd,*args,**kwargs):
        stream=original_fdopen(fd,*args,**kwargs)
        return PartialWriter(stream) if args and args[0]=='wb' else stream
    storage.os.fdopen=fdopen
elif checkpoint == 'published_source':
    original_link=os.link
    def link(*args,**kwargs): original_link(*args,**kwargs);pause()
    storage.os.link=link
elif checkpoint == 'approval_transaction':
    original_connect=Store.connect
    @contextmanager
    def connect(self):
        with original_connect(self) as db:
            def trace(statement):
                if statement.startswith('INSERT INTO bill_lines'): pause()
            db.set_trace_callback(trace)
            yield db
    Store.connect=connect
elif checkpoint == 'migration_transaction':
    original_step=migrations.STEPS[2]
    def step(db): original_step(db);pause()
    migrations.STEPS[2]=step
elif checkpoint == 'database_switch':
    original_replace=os.replace
    def replace(source,target):
        if Path(target)==directory/'utilityos.sqlite3':pause()
        return original_replace(source,target)
    storage.os.replace=replace
elif checkpoint == 'incomplete_backup':
    original_write=zipfile.ZipFile.write
    def write(*args,**kwargs): original_write(*args,**kwargs);pause()
    zipfile.ZipFile.write=write
elif checkpoint == 'extraction_finished':
    from utilityos import pdf_extract
    original_task=pdf_extract.task
    def task(*args,**kwargs):
        result=original_task(*args,**kwargs);pause();return result
    pdf_extract.task=task
elif checkpoint == 'extraction_transaction':
    original_connect=Store.connect
    @contextmanager
    def connect(self):
        with original_connect(self) as db:
            def trace(statement):
                if statement.startswith('INSERT INTO document_extractions'):pause()
            db.set_trace_callback(trace);yield db
    Store.connect=connect
elif checkpoint == 'intake_migration':
    original_step=migrations.STEPS[3]
    def step(db):original_step(db);pause()
    migrations.STEPS[3]=step

with instance_lock(directory):
    if operation=='migration':migrate(directory,'demo')
    else:
        store=Store(directory,'demo',initialize=False,expected_schema=read_version(directory/'utilityos.sqlite3'))
        ledger=Ledger(store)
        if operation=='import':ledger.import_file('synthetic.csv',(ROOT/'samples/demo-import.csv').read_bytes())
        elif operation=='intake':
            from utilityos.intake import Intake
            Intake(ledger,'demo').import_file('synthetic.pdf',(ROOT/'samples/intake/electricity-digital.pdf').read_bytes())
        elif operation=='approval':
            ledger.approve_bill(int(rest[0]),ledger.stage(int(rest[0]))['payload'],True)
            if checkpoint=='lost_response':pause()
        elif operation=='restore':restore(store,Path(rest[0]),'demo')
        elif operation=='backup':backup(store)
