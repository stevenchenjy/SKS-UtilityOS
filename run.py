#!/usr/bin/env python3
"""Local operator entry point. Never binds to a LAN or public interface."""
import argparse
import getpass
import json
import os
import re
import socket
import threading
import webbrowser
import sqlite3
import zipfile
from pathlib import Path
import sys
from utilityos.config import Config,ROOT,default_data_dir
from utilityos.db import Store
from utilityos.security import set_password,has_password,DEMO_PASSWORD
from utilityos.service import Ledger
from utilityos.operations import instance_lock,backup,restore,check,migrate
from utilityos import __version__, SCHEMA_VERSION
from utilityos.audit import acting_as


@acting_as('synthetic_generator')
def seed_demo(ledger):
    with ledger.store.connect() as db:
        if db.execute("SELECT 1 FROM settings WHERE key='demo_seed_complete'").fetchone():return
    source=ROOT/'samples'/'demo-seed.csv'
    result=ledger.import_file(source.name,source.read_bytes())
    for item_id in result['staged_ids']:
        ledger.approve_bill(item_id,ledger.stage(item_id)['payload'],True)
    intervals=ROOT/'samples'/'demo-intervals-seed.xml'
    staged=ledger.import_file(intervals.name,intervals.read_bytes())
    for item_id in staged['staged_ids']:
        ledger.approve_intervals(item_id,'DEMO-E01')
    pending=ROOT/'samples'/'demo-review.csv'
    ledger.import_file(pending.name,pending.read_bytes())
    with ledger.store.connect() as db:
        db.execute("INSERT INTO settings VALUES ('demo_seed_complete','yes')")


def main():
    parser=argparse.ArgumentParser(description='SKS UtilityOS local pilot. Staff records stay outside source code.')
    parser.add_argument('command',choices=['demo','staff','backup','restore','diagnostics','check','migrate','version'])
    parser.add_argument('--mode',choices=['demo','staff'],default='staff',help='Workspace for maintenance commands')
    parser.add_argument('--data-dir',type=Path)
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--archive',type=Path,help='Private backup ZIP for restore')
    parser.add_argument('--confirm-restore',action='store_true')
    parser.add_argument('--confirm-migrate',action='store_true')
    parser.add_argument('--restore-to-new-workspace',action='store_true',help='Recover into a new explicit data directory; preserve an existing damaged workspace')
    parser.add_argument('--open',action='store_true',help='Open the local browser after the server starts')
    args=parser.parse_args()
    if args.command=='version':print(__version__);return
    mode=args.command if args.command in {'demo','staff'} else args.mode
    config=Config((args.data_dir or default_data_dir(mode)).expanduser(),mode,args.port)
    config.validate()
    if os.name!='nt':os.umask(0o077)
    if args.command not in {'demo','staff'} and not config.data_dir.is_dir() and not args.restore_to_new_workspace:
        raise ValueError('EXISTING_WORKSPACE_REQUIRED')
    if args.restore_to_new_workspace and (args.command!='restore' or not args.data_dir or config.data_dir.exists()):
        raise ValueError('RESTORE_RECOVERY_REQUIRES_NEW_EXPLICIT_DIRECTORY')
    if args.command=='migrate' and not args.confirm_migrate:
        raise ValueError('MIGRATION_REQUIRES_CONFIRM_MIGRATE')
    if args.command=='restore' and (not args.archive or not args.confirm_restore):
        raise ValueError('RESTORE_REQUIRES_ARCHIVE_AND_CONFIRM_RESTORE')
    if args.command=='diagnostics':
        from utilityos.diagnostics import report
        print(json.dumps(report(config.data_dir,mode,args.port),indent=2))
        return
    with instance_lock(config.data_dir), acting_as('local_operator' if args.command in {'demo','staff'} else 'local_maintainer'):
        if args.command=='migrate':
            saved=migrate(config.data_dir,mode)
            print(f'Workspace upgraded to schema {SCHEMA_VERSION}. Pre-upgrade private backup:',saved)
            return
        store=Store(config.data_dir,mode,initialize=args.command in {'demo','staff'} or args.restore_to_new_workspace)
        ledger=Ledger(store)
        if args.command=='backup':
            saved=backup(store)
            print('PRIVATE BACKUP CREATED. Contains records, source files, and password hash.')
            print(saved)
            return
        if args.command=='check':
            print(json.dumps(check(store),indent=2))
            return
        if args.command=='restore':
            saved=restore(store,args.archive,mode)
            print('Local backup restored. Previous state preserved at:',saved)
            return
        # Reserve loopback before announcing success or requesting a passphrase.
        listen_socket=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        try:
            listen_socket.bind(('127.0.0.1',args.port))
        except OSError:
            listen_socket.close()
            raise ValueError('LOCAL_PORT_UNAVAILABLE_CHOOSE_ANOTHER_PORT') from None
        if mode=='demo':
            if not has_password(store):set_password(store,DEMO_PASSWORD)
            seed_demo(ledger)
        elif not has_password(store):
            print('Staff setup: choose a LOCAL APP passphrase. Never enter a utility portal password.')
            password=getpass.getpass('New local app passphrase (12+ characters): ')
            if password!=getpass.getpass('Repeat local app passphrase: '):raise ValueError('PASSPHRASES_DO_NOT_MATCH')
            set_password(store,password)
        import uvicorn
        from utilityos.app import create_app
        print(f'SKS UtilityOS {__version__} | {mode.upper()} | single-operator local pilot')
        print(f'Open http://127.0.0.1:{args.port} in this computer\'s browser.')
        print('Press Ctrl+C to stop. The data directory remains outside application code.')
        # Access logs and traceback logging are intentionally disabled to avoid
        # accidentally logging filenames, query strings, and uploaded content.
        server=uvicorn.Server(uvicorn.Config(create_app(config),host='127.0.0.1',port=args.port,access_log=False,log_config=None,log_level='critical'))
        finished=threading.Event()
        if args.open:
            def open_when_ready():
                for _ in range(300):
                    if finished.wait(0.1):return
                    if server.started:
                        webbrowser.open(f'http://127.0.0.1:{args.port}')
                        return
            threading.Thread(target=open_when_ready,daemon=True).start()
        try:
            server.run(sockets=[listen_socket])
        finally:
            finished.set()
            listen_socket.close()

if __name__=='__main__':
    try:main()
    except (ValueError,OSError,sqlite3.Error,zipfile.BadZipFile) as exc:
        if isinstance(exc,ValueError) and re.fullmatch(r'[A-Z][A-Z0-9_]{1,100}',str(exc)):print(f'Action stopped: {exc}',file=sys.stderr)
        else:print('Action stopped: LOCAL_ACTION_FAILED_CHECK_STORAGE_AND_ARCHIVE',file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:pass
