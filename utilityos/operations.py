"""Staff-controlled local backup/restore. Backups contain sensitive records."""
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
import json
import os
import re
import shutil
import secrets
import sqlite3
import zipfile
from . import __version__, SCHEMA_VERSION
from .audit import now
from .db import Store, SCHEMA
from .parsers import ValidationError


@contextmanager
def instance_lock(directory: Path):
    directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    handle=(directory/'instance.lock').open('a+b')
    try:
        if os.name=='nt':
            import msvcrt
            handle.seek(0)
            handle.write(b'0')
            handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except (OSError,BlockingIOError):
        handle.close()
        raise ValidationError('WORKSPACE_ALREADY_RUNNING_STOP_APP_FIRST')
    try:
        yield
    finally:
        if os.name=='nt':
            handle.seek(0)
            msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
        else:
            fcntl.flock(handle,fcntl.LOCK_UN)
        handle.close()


def check(store: Store):
    """Read-only integrity and source-retention check with bounded output."""
    with store.connect() as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValidationError('WORKSPACE_DATABASE_INVALID')
        if db.execute('PRAGMA foreign_key_check').fetchone():
            raise ValidationError('WORKSPACE_FOREIGN_KEYS_INVALID')
        settings = dict(db.execute('SELECT key,value FROM settings'))
        documents = db.execute('SELECT sha256,extension FROM documents').fetchall()
    for sha, extension in documents:
        if not re.fullmatch(r'[0-9a-f]{64}',sha) or extension not in {'.csv','.xml','.pdf'}:
            raise ValidationError('SOURCE_REFERENCE_INVALID')
        path = store.sources / (sha + extension)
        if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            raise ValidationError('SOURCE_INTEGRITY_CHECK_FAILED_BACKUP_ABORTED')
    return {'database':'ok','foreign_keys':'ok','sources':'ok',
            'schema_version':int(settings['schema_version']),'mode':settings['mode']}


def backup(store: Store) -> Path:
    destination = store.directory / 'backups'
    destination.mkdir(exist_ok=True,mode=0o700)
    stamp = now().replace(':','').replace('+','_')
    target = destination / f'utilityos-private-{stamp}-{secrets.token_hex(3)}.zip'
    with TemporaryDirectory(dir=store.directory) as temporary:
        snapshot = Path(temporary) / 'utilityos.sqlite3'
        with store.connect() as source, sqlite3.connect(snapshot) as copied:
            source.backup(copied)
        copied.close()
        with sqlite3.connect(snapshot) as db:
            if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or db.execute('PRAGMA foreign_key_check').fetchone():
                raise ValidationError('BACKUP_DATABASE_INVALID')
            docs = db.execute('SELECT sha256,extension FROM documents').fetchall()
            settings = dict(db.execute('SELECT key,value FROM settings'))
        db.close()
        files = {'utilityos.sqlite3':snapshot}
        for sha, extension in docs:
            if not re.fullmatch(r'[0-9a-f]{64}',sha) or extension not in {'.csv','.xml','.pdf'}:
                raise ValidationError('SOURCE_REFERENCE_INVALID')
            path = store.sources / f'{sha}{extension}'
            if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != sha:
                raise ValidationError('SOURCE_INTEGRITY_CHECK_FAILED_BACKUP_ABORTED')
            files[f'sources/{sha}{extension}'] = path
        manifest = {'format':'utilityos-private-backup-v1','app_version':__version__,
                    'schema_version':int(settings['schema_version']),'mode':settings['mode'],
                    'files':{name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in files.items()}}
        if len(files)+1>5000 or sum(path.stat().st_size for path in files.values())+len(json.dumps(manifest).encode())>1024**3:
            raise ValidationError('BACKUP_LIMIT_OR_DUPLICATE_MEMBER')
        completed = Path(temporary) / 'completed.zip'
        with zipfile.ZipFile(completed,'x',zipfile.ZIP_DEFLATED) as archive:
            for name,path in files.items():
                archive.write(path,name)
            archive.writestr('MANIFEST.json',json.dumps(manifest,indent=2))
        if os.name != 'nt':
            completed.chmod(0o600)
        # A failed archive write never leaves a file presented as a usable backup.
        os.replace(completed,target)
    return target


def migrate(directory: Path, mode: str):
    """Caller holds the workspace lock and has explicitly confirmed migration.

    Only schema 1 -> 2. Build and verify a copy, preserve a schema-1 backup,
    then replace the database atomically. Application start never migrates.
    """
    store = Store(directory,mode,initialize=False,expected_schema=1)
    check(store)
    saved = backup(store)
    with TemporaryDirectory(dir=store.directory) as temporary:
        target = Path(temporary) / 'utilityos.sqlite3'
        with store.connect() as source, sqlite3.connect(target) as db:
            source.backup(db)
        db.close()
        db = sqlite3.connect(target)
        try:
            db.execute('PRAGMA foreign_keys=OFF')
            db.execute('BEGIN IMMEDIATE')
            bill_schema = next(statement for statement in SCHEMA.split(';') if 'CREATE TABLE IF NOT EXISTS bills (' in statement)
            db.execute(bill_schema.replace('IF NOT EXISTS bills (','bills_new ('))
            db.execute("INSERT INTO bills_new(id,account_id,invoice_number,bill_date,current_total_cents,document_id,staged_id,approved_at) SELECT id,account_id,invoice_number,bill_date,current_total_cents,document_id,staged_id,approved_at FROM bills")
            db.execute('DROP TABLE bills')
            db.execute('ALTER TABLE bills_new RENAME TO bills')
            db.execute('ALTER TABLE staged ADD COLUMN correction_of INTEGER REFERENCES bills(id)')
            db.execute("ALTER TABLE staged ADD COLUMN correction_reason TEXT NOT NULL DEFAULT ''")
            db.execute('ALTER TABLE staged ADD COLUMN revision INTEGER NOT NULL DEFAULT 0')
            for statement in SCHEMA.split(';'):
                if statement.strip():
                    db.execute(statement)
            db.execute("INSERT INTO bill_history(bill_id,at,action) SELECT id,approved_at,'approved' FROM bills")
            db.execute("UPDATE settings SET value=? WHERE key='schema_version'", (str(SCHEMA_VERSION),))
            if db.execute('PRAGMA foreign_key_check').fetchone() or db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                raise ValidationError('MIGRATION_VALIDATION_FAILED')
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
        if os.name!='nt':target.chmod(0o600)
        os.replace(target,store.path)
    return saved


def restore(store: Store, archive_path: Path, mode: str):
    """Caller holds the instance lock. Validate all paths and bytes before replace."""
    with zipfile.ZipFile(archive_path) as archive:
        infos=archive.infolist()
        names=[entry.filename for entry in infos]
        if len(names)!=len(set(names)) or len(names)>5000 or sum(i.file_size for i in infos)>1024**3:
            raise ValidationError('BACKUP_LIMIT_OR_DUPLICATE_MEMBER')
        if 'MANIFEST.json' not in names or archive.getinfo('MANIFEST.json').file_size>1024*1024:
            raise ValidationError('BACKUP_MANIFEST_INVALID')
        manifest=json.loads(archive.read('MANIFEST.json'))
        if not isinstance(manifest,dict):
            raise ValidationError('BACKUP_MANIFEST_INVALID')
        if manifest.get('format')!='utilityos-private-backup-v1' or manifest.get('schema_version')!=SCHEMA_VERSION or manifest.get('mode')!=mode:
            raise ValidationError('BACKUP_SCHEMA_OR_MODE_MISMATCH')
        expected=manifest.get('files',{})
        if not isinstance(expected,dict) or not all(isinstance(k,str) and isinstance(v,str) and re.fullmatch(r'[0-9a-f]{64}',v) for k,v in expected.items()):
            raise ValidationError('BACKUP_MANIFEST_INVALID')
        if set(names)!=set(expected)|{'MANIFEST.json'} or 'utilityos.sqlite3' not in expected:
            raise ValidationError('BACKUP_CONTENTS_MISMATCH')
        for name in expected:
            if name!='utilityos.sqlite3' and not re.fullmatch(r'sources/[0-9a-f]{64}\.(csv|xml|pdf)',name):
                raise ValidationError('BACKUP_PATH_NOT_ALLOWED')
            info=archive.getinfo(name)
            if (info.external_attr>>16)&0o170000==0o120000:
                raise ValidationError('BACKUP_SYMLINK_NOT_ALLOWED')
        with TemporaryDirectory(dir=store.directory) as temporary:
            root=Path(temporary)
            for name,sha in expected.items():
                data=archive.read(name)
                if hashlib.sha256(data).hexdigest()!=sha:
                    raise ValidationError('BACKUP_HASH_MISMATCH')
                target=root/name
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(data)
                if os.name!='nt':target.chmod(0o600)
            restored=sqlite3.connect(root/'utilityos.sqlite3')
            try:
                if restored.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                    raise ValidationError('BACKUP_DATABASE_INVALID')
                restored_mode=restored.execute("SELECT value FROM settings WHERE key='mode'").fetchone()[0]
                restored_schema=restored.execute("SELECT value FROM settings WHERE key='schema_version'").fetchone()[0]
                if restored_mode!=mode or int(restored_schema)!=SCHEMA_VERSION:
                    raise ValidationError('BACKUP_DATABASE_MODE_OR_SCHEMA_MISMATCH')
                if restored.execute('PRAGMA foreign_key_check').fetchone():
                    raise ValidationError('BACKUP_FOREIGN_KEYS_INVALID')
                for sha,extension in restored.execute('SELECT sha256,extension FROM documents'):
                    name=f'sources/{sha}{extension}'
                    if expected.get(name)!=sha:
                        raise ValidationError('BACKUP_SOURCE_REFERENCE_INVALID')
            finally:
                restored.close()
            safety=backup(store)
            # Sources are content-addressed and immutable. Restore adds the
            # snapshot's files, then atomically replaces the DB while stopped.
            for path in (root/'sources').glob('*') if (root/'sources').exists() else []:
                shutil.copy2(path,store.sources/path.name)
            os.replace(root/'utilityos.sqlite3',store.path)
            return safety
