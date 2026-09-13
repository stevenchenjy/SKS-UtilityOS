"""Synthetic foreground lifecycle, copy stability and review-only dispatch."""
import json
import os
import time
from pathlib import Path
import pytest
from utilityos.acquisition import Acquisition
from utilityos.config import ROOT
from utilityos.intake import Intake
from utilityos.operations import backup, restore, check
from utilityos.db import Store


def watcher(ledger, tmp_path):
    folder = tmp_path / 'synthetic-incoming'
    folder.mkdir()
    intake = Intake(ledger, 'demo')
    worker = Acquisition(intake)
    worker.configure(str(folder), True)
    return worker, folder


def enable(worker, folder, action='enable'):
    return worker.control({'action':action,'directory':str(folder),'acknowledge':True,'synthetic':True})


def aged(path, raw):
    path.write_bytes(raw)
    before = time.time() - 10
    os.utime(path, (before, before))


def test_foreground_defaults_strict_consent_pause_restart_and_stop(ledger,tmp_path,raw_csv):
    worker, folder = watcher(ledger,tmp_path)
    aged(folder/'bill.csv',raw_csv)
    worker.tick(0);worker.tick(5)
    assert worker.status()['state']=='disabled' and ledger.stages()==[]
    for change in ({'acknowledge':'true'},{'synthetic':False},{'directory':str(tmp_path)}):
        with pytest.raises(ValueError):
            worker.control(dict(action='enable',directory=str(folder),acknowledge=True,synthetic=True,**{})|change)
    enable(worker,folder)
    worker.tick(10)
    worker.control({'action':'pause'})
    worker.tick(20)
    assert ledger.stages()==[]
    with pytest.raises(ValueError,match='DISABLE_ACQUISITION'):
        worker.configure('',True)
    enable(worker,folder,'resume');worker.tick(30);worker.tick(35)
    assert len(ledger.stages())==1 and ledger.overview()['total_cents']==0
    replacement=Acquisition(Intake(ledger,'demo'))
    assert replacement.status()['state']=='disabled'
    assert replacement.status()['directory']==str(folder)
    worker.start();worker.stop()
    assert not worker.worker.is_alive()
    assert (folder/'bill.csv').read_bytes()==raw_csv


def test_copy_write_rename_duplicate_and_unchanged_failures_are_bounded(ledger,tmp_path,raw_csv):
    worker, folder = watcher(ledger,tmp_path);enable(worker,folder)
    temporary=folder/'bill.csv.crdownload'
    aged(temporary,raw_csv[:100]);worker.tick(0);worker.tick(5)
    assert worker.intake.history()==[]
    partial=folder/'bill.csv'
    aged(partial,raw_csv[:100]);worker.tick(10)
    aged(partial,raw_csv);worker.tick(15)
    assert worker.intake.history()==[]
    worker.tick(20)
    assert len(ledger.stages())==1,worker.intake.history()
    worker.tick(25)
    assert len(worker.intake.history())==1
    # Completion rename is discovered on a subsequent snapshot. Same bytes
    # link to the original draft and never repeat financial or usage postings.
    aged(temporary,raw_csv);temporary.rename(folder/'another.csv')
    worker.tick(30);worker.tick(35)
    assert len(ledger.stages())==1
    assert worker.intake.history()[0]['state']=='duplicate'
    aged(folder/'unsupported.exe',b'fictional unsupported source')
    worker.tick(40);worker.tick(45);worker.tick(50)
    assert worker.intake.history()[0]['state']=='unsupported'
    assert len(worker.intake.history())==3
    aged(folder/'broken.xml',b'<bad>');worker.tick(55);worker.tick(60);worker.tick(65)
    assert len(worker.intake.history())==4
    assert worker.intake.history()[0]['state']=='failed_safely'
    assert worker.status()['sources'][1]['pending_review']==1


def test_symlinks_subfolders_and_changed_read_fail_closed(ledger,tmp_path,raw_csv,monkeypatch):
    worker,folder=watcher(ledger,tmp_path);enable(worker,folder)
    (folder/'subfolder').mkdir();aged(folder/'subfolder'/'not-read.csv',raw_csv)
    (folder/'link.csv').symlink_to(folder/'subfolder'/'not-read.csv')
    worker.tick(0);worker.tick(5)
    assert ledger.stages()==[]
    assert worker.intake.history()[0]['code']=='INBOX_FILE_UNSAFE_OR_TOO_LARGE'
    target=folder/'moving.csv';aged(target,raw_csv)
    original=Path.lstat
    calls=0
    def changing(path,*args,**kwargs):
        nonlocal calls
        if path==target:
            calls+=1
            if calls==2:
                aged(path,raw_csv+b'\n')
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'lstat',changing)
    with pytest.raises(ValueError,match='CHANGED_DURING_READ'):
        worker.intake.read_stable(target)
    assert ledger.stages()==[]


def test_adapter_usage_review_and_retained_sources_survive_backup(ledger,tmp_path):
    worker,folder=watcher(ledger,tmp_path);enable(worker,folder)
    raw=(ROOT/'samples/generic-water-usage.csv').read_bytes()
    aged(folder/'water.csv',raw);worker.tick(0);worker.tick(5)
    item=worker.intake.history()[0]
    assert item['adapter']=='usage_csv' and item['usage_ids'] and not item['staged_ids']
    assert ledger.stages()==[] and ledger.overview()['total_cents']==0
    saved=backup(ledger.store)
    recovered=Store(tmp_path/'restored','demo');restore(recovered,saved,'demo')
    assert check(recovered)['sources']=='ok'
    assert (folder/'water.csv').read_bytes()==raw
    report=json.dumps(ledger.diagnostics('demo'))
    assert str(folder) not in report and 'water.csv' not in report


def test_authenticated_controls_no_silent_activation_or_secret_fields(authenticated,tmp_path):
    client=authenticated;folder=tmp_path/'downloads';folder.mkdir()
    assert client.get('/api/acquisition').json()['state']=='disabled'
    assert client.post('/api/intake/configuration',json={'directory':str(folder),'acknowledge':True}).status_code==200
    assert client.post('/api/acquisition/control',json={'action':'enable','directory':str(folder),'acknowledge':True}).status_code==422
    assert client.post('/api/acquisition/control',json={'action':'enable','directory':str(folder),'acknowledge':True,'synthetic':True}).status_code==200
    assert client.get('/api/acquisition').json()['state']=='watching'
    client.post('/api/acquisition/control',json={'action':'disable'})
    assert client.get('/api/acquisition').json()['connector']['network_enabled'] is False
    client.post('/api/logout',json={})
    assert client.get('/api/acquisition').status_code==401
    assert client.post('/api/acquisition/control',json={'action':'enable'}).status_code==401


def test_status_includes_direct_operational_uploads(authenticated):
    client=authenticated
    raw=(ROOT/'samples/generic-water-usage.csv').read_bytes()
    result=client.post('/api/usage/import',content=raw,headers={
        'content-type':'application/octet-stream','x-filename':'direct-water.csv','x-synthetic-data':'true'})
    assert result.status_code==200
    status=client.get('/api/acquisition').json()
    source=next(row for row in status['sources'] if row['id']=='usage_csv')
    assert source['pending_review']==1 and source['last_file']=='direct-water.csv'
    assert source['last_success']


def test_future_mtime_or_transient_copy_does_not_starve_stable_files(ledger,tmp_path,raw_csv):
    worker,folder=watcher(ledger,tmp_path);enable(worker,folder)
    future=folder/'a-future.csv';future.write_bytes(raw_csv)
    os.utime(future,(time.time()+86400,)*2)
    aged(folder/'b-stable.csv',raw_csv+b'\n')
    aged(folder/'c-stable.csv',raw_csv+b'\n\n')
    worker.tick(0);worker.tick(5)
    assert len(worker.intake.history())==1
    assert worker.intake.history()[0]['filename']=='b-stable.csv'
    assert len(ledger.stages())==1
    # Each tick still attempts at most one supported parser/import.
    worker.tick(10)
    assert len(worker.intake.history())==2
    assert worker.intake.history()[0]['filename']=='c-stable.csv'
    assert future.read_bytes()==raw_csv


@pytest.mark.skipif(not hasattr(os,'mkfifo') or not hasattr(os,'O_NONBLOCK'), reason='POSIX FIFO replacement defense; Windows descriptor identity covered separately')
def test_replaced_fifo_is_opened_nonblocking_and_never_read(ledger,tmp_path,raw_csv,monkeypatch):
    worker,folder=watcher(ledger,tmp_path)
    target=folder/'replaced.csv';aged(target,raw_csv)
    original=os.open
    def replacing(path,flags,*args,**kwargs):
        if Path(path)==target:
            # Assert before creating the FIFO so a regression fails without
            # hanging the test runner on a blocking os.open.
            assert flags & os.O_NONBLOCK
            target.unlink();os.mkfifo(target)
        return original(path,flags,*args,**kwargs)
    monkeypatch.setattr(os,'open',replacing)
    with pytest.raises(ValueError,match='CHANGED_DURING_READ'):
        worker.intake.read_stable(target)
    assert ledger.stages()==[]


def test_replaced_regular_descriptor_is_rejected_before_any_read(ledger,tmp_path,raw_csv,monkeypatch):
    worker,folder=watcher(ledger,tmp_path)
    target=folder/'replaced.csv';aged(target,raw_csv)
    other=folder/'replacement.csv';aged(other,b'synthetic replacement which must not be read')
    original=os.open
    descriptor_read=False
    def replacing(path,flags,*args,**kwargs):
        if Path(path)==target:
            other.replace(target)
        return original(path,flags,*args,**kwargs)
    original_fdopen=os.fdopen
    class ObservedStream:
        def __init__(self,descriptor,*args):self.stream=original_fdopen(descriptor,*args)
        def __enter__(self):return self
        def __exit__(self,*args):return self.stream.__exit__(*args)
        def fileno(self):return self.stream.fileno()
        def read(self,*args):
            nonlocal descriptor_read
            descriptor_read=True
            return self.stream.read(*args)
    monkeypatch.setattr(os,'open',replacing)
    monkeypatch.setattr(os,'fdopen',ObservedStream)
    with pytest.raises(ValueError,match='CHANGED_DURING_READ'):
        worker.intake.read_stable(target)
    assert not descriptor_read


@pytest.mark.parametrize('metadata_changes_during_read',[False,True])
def test_windows_creation_time_matches_across_stat_apis_without_losing_change_detection(
        ledger,tmp_path,raw_csv,monkeypatch,metadata_changes_during_read):
    from types import SimpleNamespace
    from utilityos import intake as intake_module
    worker,folder=watcher(ledger,tmp_path)
    target=folder/'windows-timestamps.csv';aged(target,raw_csv)
    lstat,fstat=Path.lstat,os.fstat
    creation=1_700_000_000_000_000_000
    change=creation+5_000_000_000
    calls=0
    def windows_stat(item,ctime):
        fields={name:getattr(item,name) for name in
                ('st_mode','st_dev','st_ino','st_size','st_mtime_ns')}
        return SimpleNamespace(**fields,st_birthtime_ns=creation,st_ctime_ns=ctime)
    def path_stat(path,*args,**kwargs):
        result=lstat(path,*args,**kwargs)
        return windows_stat(result,creation) if path==target else result
    def descriptor_stat(descriptor):
        nonlocal calls
        calls+=1
        # Windows fstat reports change time, not lstat's legacy creation time.
        # A change after the first descriptor check must still fail closed,
        # even when device, inode, size, mtime and creation time are unchanged.
        stamp=change+int(metadata_changes_during_read and calls>1)
        return windows_stat(fstat(descriptor),stamp)
    with monkeypatch.context() as patch:
        patch.setattr(intake_module,'platform','win32')
        patch.setattr(Path,'lstat',path_stat)
        patch.setattr(os,'fstat',descriptor_stat)
        if metadata_changes_during_read:
            with pytest.raises(ValueError,match='CHANGED_DURING_READ'):
                worker.intake.read_stable(target)
        else:
            assert worker.intake.read_stable(target)==raw_csv
    assert calls==2


def test_stable_source_read_preserves_binary_bytes_with_windows_text_default(ledger,tmp_path):
    worker,folder=watcher(ledger,tmp_path)
    raw=b'fictional binary source\r\nline two\x1aafter DOS EOF\x00\xff\r\n'
    target=folder/'binary.pdf';aged(target,raw)
    # Explicit O_BINARY must win even if the hosting Windows CRT defaults to
    # text mode. Restore that process setting before any other test runs.
    runtime=None
    if os.name=='nt':
        import ctypes
        runtime=ctypes.CDLL('ucrtbase')
        previous=ctypes.c_int()
        assert runtime._get_fmode(ctypes.byref(previous))==0
        assert runtime._set_fmode(os.O_TEXT)==0
    try:
        assert worker.intake.read_stable(target)==raw
    finally:
        if runtime is not None:
            assert runtime._set_fmode(previous.value)==0
    assert target.read_bytes()==raw
