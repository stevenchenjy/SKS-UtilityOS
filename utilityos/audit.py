"""Fixed-code, append-oriented audit chain. No names, source text or secrets."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import re
from .parsers import ValidationError

ZERO = '0' * 64
ACTORS = {'local_operator', 'reauthenticated_operator', 'local_maintainer', 'synthetic_generator', 'legacy_unknown'}
CODES = {'IMPORT_CSV', 'IMPORT_XML', 'IMPORT_PDF', 'CREATE_DRAFT', 'SAVE_DRAFT',
         'APPROVE_BILL', 'SUPERSEDE_BILL', 'APPROVE_REBILL', 'APPROVE_INTERVALS',
         'REJECT_DRAFT', 'CREATE_CORRECTION', 'CANCEL_BILL', 'EDIT_BUILDING_LABEL',
         'EDIT_METER_MAPPING', 'OBSERVE_ACCOUNT_MAPPING', 'RECOVER_DRAFT',
         'BACKUP_STARTED', 'BACKUP_CREATED', 'RESTORE_SNAPSHOT', 'MIGRATE_SCHEMA', 'SET_LOCAL_PASSPHRASE',
         'CREATE_LOCAL_PROVIDER', 'SAVE_LOCAL_LAYOUT', 'VALIDATE_LOCAL_LAYOUT', 'SET_LOCAL_LAYOUT_STATE', 'BIND_LOCAL_EXTRACTION',
         'EXTRACT_DOCUMENT', 'CONFIGURE_INBOX', 'SCAN_INBOX', 'INTAKE_ATTEMPT', 'CONFIGURE_EXPECTATION'}
ACTOR = ContextVar('audit_actor', default='local_operator')
TABLE = """CREATE TABLE audit_events (
 id INTEGER PRIMARY KEY, at TEXT NOT NULL, code TEXT NOT NULL, staged_id INTEGER,
 actor TEXT NOT NULL, subject_kind TEXT NOT NULL, subject_id INTEGER,
 operation_id TEXT NOT NULL DEFAULT '', related_hash TEXT NOT NULL DEFAULT '',
 previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL UNIQUE);
"""
TRIGGERS = """
CREATE TRIGGER audit_no_update BEFORE UPDATE ON audit_events
BEGIN SELECT RAISE(ABORT,'AUDIT_APPEND_ONLY'); END;
CREATE TRIGGER audit_no_delete BEFORE DELETE ON audit_events
BEGIN SELECT RAISE(ABORT,'AUDIT_APPEND_ONLY'); END;
"""
FIELDS = ('id','at','code','staged_id','actor','subject_kind','subject_id','operation_id','related_hash','previous_hash')


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def money(value):
    return f'{Decimal(value)/100:.2f}'


@contextmanager
def acting_as(actor):
    if actor not in ACTORS:
        raise ValueError('AUDIT_ACTOR_INVALID')
    token = ACTOR.set(actor)
    try:
        yield
    finally:
        ACTOR.reset(token)


def enabled(db):
    return 'event_hash' in {row[1] for row in db.execute('PRAGMA table_info(audit_events)')}


def digest(row):
    return hashlib.sha256(json.dumps([row[key] for key in FIELDS], separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


def head(db):
    row = db.execute("SELECT value FROM settings WHERE key='audit_head'").fetchone()
    return row[0] if row else ZERO


def event(db, code, staged_id=None, *, subject_kind=None, subject_id=None, operation_id='', related_hash='', at=None, event_id=None):
    if code not in CODES or ACTOR.get() not in ACTORS:
        raise ValidationError('AUDIT_FIXED_VALUES_REQUIRED')
    kind = subject_kind or ('draft' if staged_id is not None else 'workspace')
    subject_id = staged_id if kind == 'draft' else subject_id
    if kind not in {'draft', 'inventory_change', 'workspace'} or (subject_id is not None and (type(subject_id) is not int or subject_id < 1)):
        raise ValidationError('AUDIT_SUBJECT_INVALID')
    if (operation_id and not re.fullmatch(r'[0-9a-f]{32}', operation_id)) or (related_hash and not re.fullmatch(r'[0-9a-f]{64}', related_hash)):
        raise ValidationError('AUDIT_REFERENCE_INVALID')
    if not db.in_transaction:
        db.execute('BEGIN IMMEDIATE')
    previous = db.execute('SELECT id,event_hash FROM audit_events ORDER BY id DESC LIMIT 1').fetchone()
    previous_hash = previous[1] if previous else ZERO
    if head(db) != previous_hash:
        raise ValidationError('AUDIT_INTEGRITY_FAILED')
    identifier = event_id if event_id is not None else (previous[0] + 1 if previous else 1)
    if type(identifier) is not int or identifier <= (previous[0] if previous else 0):
        raise ValidationError('AUDIT_SEQUENCE_INVALID')
    row = dict(zip(FIELDS, (identifier, at or now(), code, staged_id, ACTOR.get(), kind, subject_id, operation_id, related_hash, previous_hash)))
    value = digest(row)
    db.execute('INSERT INTO audit_events VALUES (?,?,?,?,?,?,?,?,?,?,?)', tuple(row[key] for key in FIELDS) + (value,))
    db.execute("INSERT OR REPLACE INTO settings VALUES ('audit_head',?)", (value,))


def verify(db):
    if not enabled(db):
        row=db.execute("SELECT value FROM settings WHERE key='schema_version'").fetchone()
        if row and int(row[0])>=3:
            raise ValidationError('AUDIT_INTEGRITY_FAILED')
        return 'legacy_unprotected'
    previous = ZERO
    last_id = 0
    names = [col[1] for col in db.execute('PRAGMA table_info(audit_events)')]
    for values in db.execute('SELECT * FROM audit_events ORDER BY id'):
        row = dict(zip(names, values))
        if (row['previous_hash'] != previous or row['event_hash'] != digest(row)
            or row['id'] <= last_id or row['code'] not in CODES or row['actor'] not in ACTORS):
            raise ValidationError('AUDIT_INTEGRITY_FAILED')
        previous, last_id = row['event_hash'], row['id']
    triggers = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
    if head(db) != previous or not {'audit_no_update', 'audit_no_delete'}.issubset(triggers):
        raise ValidationError('AUDIT_INTEGRITY_FAILED')
    return 'ok'


def migrate_v2(db):
    rows = db.execute('SELECT id,at,code,staged_id FROM audit_events ORDER BY id').fetchall()
    db.execute('ALTER TABLE audit_events RENAME TO audit_events_legacy')
    db.execute(TABLE)
    db.execute("INSERT OR REPLACE INTO settings VALUES ('audit_head',?)", (ZERO,))
    with acting_as('legacy_unknown'):
        for identifier, at, code, staged_id in rows:
            event(db, code, staged_id, at=at, event_id=identifier)
    db.execute('DROP TABLE audit_events_legacy')
    for name, action in [('audit_no_update', 'UPDATE'), ('audit_no_delete', 'DELETE')]:
        db.execute(f"CREATE TRIGGER {name} BEFORE {action} ON audit_events BEGIN SELECT RAISE(ABORT,'AUDIT_APPEND_ONLY'); END")
