"""Private append-only provider journal, bound to the workspace audit chain.

Definitions, status decisions, selected validation sets and extraction bindings
are separate typed records. No record is updated or deleted by the application.
The journal is in the private SQLite file and travels only in private backups.
"""
import json
import re
import uuid
from .audit import event, now
from .parsers import ValidationError, UNITS
from .provider_rules import definition, canonical, digest

KINDS = {'provider': 'CREATE_LOCAL_PROVIDER', 'layout': 'SAVE_LOCAL_LAYOUT',
         'validation': 'VALIDATE_LOCAL_LAYOUT', 'state': 'SET_LOCAL_LAYOUT_STATE',
         'link': 'BIND_LOCAL_EXTRACTION'}
TABLE = 'local_provider_records'
STATEMENTS = (
    '''CREATE TABLE local_provider_records (
       id TEXT PRIMARY KEY, kind TEXT NOT NULL CHECK(kind IN ('provider','layout','validation','state','link')),
       parent_id TEXT REFERENCES local_provider_records(id),
       document_id INTEGER UNIQUE REFERENCES documents(id), payload TEXT NOT NULL,
       payload_sha256 TEXT NOT NULL UNIQUE)''',
    'CREATE INDEX local_provider_parent ON local_provider_records(parent_id,kind)',
) + tuple(f"CREATE TRIGGER local_provider_no_{action.lower()} BEFORE {action} ON {TABLE} BEGIN SELECT RAISE(ABORT,'LOCAL_PROVIDER_HISTORY_IMMUTABLE'); END"
          for action in ('UPDATE', 'DELETE'))


def initialize(db):
    for statement in STATEMENTS:
        db.execute(statement)


def append(db, kind, data, *, parent_id=None, document_id=None):
    record = {'id': uuid.uuid4().hex, 'kind': kind, 'created_at': now(),
              'parent_id': parent_id, 'document_id': document_id, **data}
    hashed = digest(record)
    db.execute(f'INSERT INTO {TABLE} VALUES (?,?,?,?,?,?)',
               (record['id'], kind, parent_id, document_id, canonical(record), hashed))
    event(db, KINDS[kind], related_hash=hashed)
    return {**record, 'hash': hashed}


def triggers_valid(db):
    return {'local_provider_no_update', 'local_provider_no_delete'}.issubset(
        {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='trigger'")})


def read(db, row):
    try:
        record = json.loads(row['payload'])
        if (digest(record) != row['payload_sha256'] or
            any(record[key] != row[key] for key in ('id', 'kind', 'parent_id', 'document_id')) or
            not re.fullmatch('[0-9a-f]{32}', record['id']) or
            not db.execute('SELECT 1 FROM audit_events WHERE code=? AND related_hash=?',
                           (KINDS[row['kind']], row['payload_sha256'])).fetchone()):
            raise ValueError()
        if row['kind'] == 'provider':
            if (not isinstance(record['label'], str) or not 1 <= len(record['label']) <= 120 or
                    record['commodity'] not in UNITS):
                raise ValueError()
        elif row['kind'] == 'layout':
            definition(record['definition'])
            if record['provenance'] != 'staff_setup' or type(record['version']) is not int or record['version'] < 1:
                raise ValueError()
        elif row['kind'] == 'state' and record['state'] not in {'draft', 'active', 'retired'}:
            raise ValueError()
        return {**record, 'hash': row['payload_sha256']}
    except (ValueError, TypeError, KeyError):
        raise ValidationError('LOCAL_TEMPLATE_DAMAGED_MANUAL_REVIEW') from None


def records(db):
    good, damaged = [], False
    if not triggers_valid(db):
        return [], True
    cursor = db.execute(f'SELECT * FROM {TABLE} ORDER BY rowid')
    columns = [column[0] for column in cursor.description]
    rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
    for row in rows:
        try:
            good.append(read(db, row))
        except ValidationError:
            damaged = True
    # A missing record cannot be hidden by deleting its row and reinstalling a
    # trigger. The intact global audit retains every journal content hash.
    hashes = {row['hash'] for row in good}
    for row in db.execute("SELECT code,related_hash FROM audit_events"):
        if row[0] in KINDS.values() and row[1] not in hashes:
            damaged = True
    ids = {record['id'] for record in good}
    if any(record['parent_id'] and record['parent_id'] not in ids for record in good):
        damaged = True
    # A damaged decision could otherwise reactivate an earlier state. Quarantine
    # the complete local registry; ordinary manual/built-in review still works.
    return ([], True) if damaged else (good, False)


def verify(db):
    row = db.execute("SELECT value FROM settings WHERE key='schema_version'").fetchone()
    if row and int(row[0]) >= 5 and records(db)[1]:
        raise ValidationError('LOCAL_TEMPLATE_DAMAGED_MANUAL_REVIEW')


def registry(db):
    rows, damaged = records(db)
    providers = [row for row in rows if row['kind'] == 'provider']
    layouts = []
    for row in rows:
        if row['kind'] != 'layout':
            continue
        states = [r for r in rows if r['kind'] == 'state' and r['parent_id'] == row['id']]
        validations = [r for r in rows if r['kind'] == 'validation' and r['parent_id'] == row['id']]
        if not states:
            return [], [], rows, True
        layouts.append({**row, 'provider_id': row['parent_id'], 'state': states[-1]['state'],
                        'state_id': states[-1]['id'], 'states': states,
                        'validation': validations[-1] if validations else None,
                        'validations': validations})
    return providers, layouts, rows, damaged


def bind(db, document_id, provider_id, layout_id, classification, extraction):
    if provider_id is None and classification not in {'damaged', 'ambiguous'}:
        return
    layout_hash = None
    if layout_id:
        row = db.execute(f'SELECT * FROM {TABLE} WHERE id=?', (layout_id,)).fetchone()
        layout_hash = read(db, row)['hash']
    # Same financial-source/extraction transaction. No asynchronous rebinding.
    original = db.execute('SELECT payload_sha256 FROM document_extractions WHERE document_id=?', (document_id,)).fetchone()[0]
    append(db, 'link', {'provider_id': provider_id, 'layout_id': layout_id, 'template_hash': layout_hash,
                       'classification': classification, 'extraction_hash': original},
           parent_id=layout_id or provider_id, document_id=document_id)
