"""Schema-6 immutable operational reading evidence, separate from invoices."""
import hashlib
import json
import sqlite3
from .parsers import ValidationError

STATEMENTS = (
    '''CREATE TABLE usage_imports (
       id INTEGER PRIMARY KEY, document_id INTEGER NOT NULL REFERENCES documents(id),
       created_at TEXT NOT NULL, payload TEXT NOT NULL, payload_hash TEXT NOT NULL UNIQUE)''',
    '''CREATE TABLE usage_previews (
       import_id INTEGER NOT NULL REFERENCES usage_imports(id), revision INTEGER NOT NULL CHECK(revision>0),
       payload TEXT NOT NULL, payload_hash TEXT NOT NULL UNIQUE, PRIMARY KEY(import_id,revision))''',
    '''CREATE TABLE usage_decisions (
       import_id INTEGER PRIMARY KEY REFERENCES usage_imports(id), revision INTEGER NOT NULL,
       state TEXT NOT NULL CHECK(state IN ('approved','rejected')),
       payload TEXT NOT NULL, payload_hash TEXT NOT NULL UNIQUE)''',
    '''CREATE TABLE usage_withdrawals (
       import_id INTEGER PRIMARY KEY REFERENCES usage_decisions(import_id),
       payload TEXT NOT NULL, payload_hash TEXT NOT NULL UNIQUE)''',
    '''CREATE TABLE usage_readings (
       id INTEGER PRIMARY KEY, meter_id INTEGER NOT NULL REFERENCES meters(id),
       commodity TEXT NOT NULL, unit TEXT NOT NULL, semantics TEXT NOT NULL CHECK(semantics IN ('delta','cumulative')),
       start_utc INTEGER NOT NULL, end_utc INTEGER NOT NULL, quantity TEXT NOT NULL, quality TEXT NOT NULL,
       payload_hash TEXT NOT NULL UNIQUE,
       CHECK((semantics='delta' AND end_utc>start_utc) OR (semantics='cumulative' AND end_utc=start_utc)))''',
    '''CREATE INDEX usage_readings_meter_time ON usage_readings(meter_id,start_utc,end_utc)''',
    '''CREATE TABLE usage_evidence (
       import_id INTEGER NOT NULL REFERENCES usage_imports(id), reading_id INTEGER NOT NULL REFERENCES usage_readings(id),
       PRIMARY KEY(import_id,reading_id))''',
) + tuple(f"CREATE TRIGGER {table}_no_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'USAGE_HISTORY_IMMUTABLE'); END"
          for table in ('usage_imports','usage_previews','usage_decisions','usage_withdrawals','usage_readings','usage_evidence')
          for action in ('UPDATE','DELETE'))

READING_FIELDS = ('meter_id','commodity','unit','semantics','start_utc','end_utc','quantity','quality')
ACTIVE_READINGS = '''SELECT r.* FROM usage_readings r WHERE EXISTS (
 SELECT 1 FROM usage_evidence e JOIN usage_decisions d ON d.import_id=e.import_id
 WHERE e.reading_id=r.id AND d.state='approved'
 AND NOT EXISTS(SELECT 1 FROM usage_withdrawals w WHERE w.import_id=e.import_id))'''


def initialize(db):
    for statement in STATEMENTS:
        db.execute(statement)


def serialize(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True)


def digest(value):
    return hashlib.sha256(serialize(value).encode()).hexdigest()


def read_payload(row):
    try:
        value = json.loads(row['payload'])
        if not isinstance(value, dict) or digest(value) != row['payload_hash']:
            raise ValueError()
        return value
    except (ValueError, TypeError):
        raise ValidationError('USAGE_HISTORY_DAMAGED') from None


def verify(db):
    version = db.execute("SELECT value FROM settings WHERE key='schema_version'").fetchone()
    if not version or int(version[0]) < 6:
        return
    # Backup verification uses tuple rows as well as the application's Row factory.
    previous_factory = db.row_factory
    db.row_factory = sqlite3.Row
    try:
        triggers = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
        expected = {f'{table}_no_{action}' for table in ('usage_imports','usage_previews','usage_decisions','usage_withdrawals','usage_readings','usage_evidence') for action in ('update','delete')}
        if not expected.issubset(triggers):
            raise ValueError()
        expected_events = set()
        imports = {}
        previews = {}
        decisions = {}
        for table in ('usage_imports','usage_previews','usage_decisions','usage_withdrawals'):
            for row in db.execute(f'SELECT * FROM {table}'):
                data = read_payload(row)
                identifier = row['id'] if table == 'usage_imports' else row['import_id']
                if data.get('import_id') != identifier:
                    raise ValueError()
                code = {'usage_imports':'IMPORT_USAGE_CSV','usage_previews':'PREVIEW_USAGE',
                        'usage_decisions':'APPROVE_USAGE' if data.get('state') == 'approved' else 'REJECT_USAGE',
                        'usage_withdrawals':'WITHDRAW_USAGE'}[table]
                expected_events.add((code,row['payload_hash']))
                if db.execute('SELECT COUNT(*) FROM audit_events WHERE code=? AND related_hash=?', (code,row['payload_hash'])).fetchone()[0] != 1:
                    raise ValueError()
                if table == 'usage_imports':
                    document = db.execute('SELECT sha256 FROM documents WHERE id=?', (row['document_id'],)).fetchone()
                    if not document or data['source_sha256'] != document[0] or data['document_id'] != row['document_id'] or data['at'] != row['created_at']:
                        raise ValueError()
                    imports[identifier] = data
                elif table == 'usage_previews':
                    if data['revision'] != row['revision'] or data['source_sha256'] != imports[identifier]['source_sha256']:
                        raise ValueError()
                    previews[(identifier,row['revision'])] = data
                elif table == 'usage_decisions':
                    if data['revision'] != row['revision'] or data['state'] != row['state']:
                        raise ValueError()
                    if data['state'] == 'approved' and data['preview_hash'] != digest(previews[(identifier,row['revision'])]):
                        raise ValueError()
                    decisions[identifier] = data
                elif identifier not in decisions or decisions[identifier]['state'] != 'approved':
                    raise ValueError()
        for identifier, data in imports.items():
            parent = data.get('reattempt_of')
            if parent is not None:
                if (type(parent) is not int or parent >= identifier or parent not in imports
                    or data['document_id'] != imports[parent]['document_id']
                    or not isinstance(data.get('reason'),str) or not 3 <= len(data['reason']) <= 500
                    or parent not in decisions or (decisions[parent]['state'] != 'rejected'
                    and not db.execute('SELECT 1 FROM usage_withdrawals WHERE import_id=?',(parent,)).fetchone())):
                    raise ValueError()
        actual_events = {(r[0],r[1]) for r in db.execute("SELECT code,related_hash FROM audit_events WHERE code IN ('IMPORT_USAGE_CSV','PREVIEW_USAGE','APPROVE_USAGE','REJECT_USAGE','WITHDRAW_USAGE')")}
        if expected_events != actual_events:
            raise ValueError()
        for identifier, data in decisions.items():
            actual = {r[0] for r in db.execute('SELECT r.payload_hash FROM usage_evidence e JOIN usage_readings r ON r.id=e.reading_id WHERE e.import_id=?', (identifier,))}
            wanted = {digest(r) for r in previews[(identifier,data['revision'])]['readings']} if data['state'] == 'approved' else set()
            if actual != wanted:
                raise ValueError()
        if db.execute('SELECT 1 FROM usage_evidence e LEFT JOIN usage_decisions d ON d.import_id=e.import_id WHERE d.import_id IS NULL').fetchone():
            raise ValueError()
        if db.execute('SELECT 1 FROM usage_readings r WHERE NOT EXISTS(SELECT 1 FROM usage_evidence e WHERE e.reading_id=r.id)').fetchone():
            raise ValueError()
        for row in db.execute('SELECT * FROM usage_readings'):
            if digest({key:row[key] for key in READING_FIELDS}) != row['payload_hash']:
                raise ValueError()
    except (ValueError,KeyError,TypeError,sqlite3.DatabaseError):
        raise ValidationError('USAGE_HISTORY_DAMAGED') from None
    finally:
        db.row_factory = previous_factory
