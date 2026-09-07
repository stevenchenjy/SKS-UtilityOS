"""Ordered, explicit schema transitions. Tests can supply future synthetic steps."""
from pathlib import Path
import sqlite3
from . import SCHEMA_VERSION
from .audit import migrate_v2, event, verify
from .parsers import ValidationError


def to_v2(db):
    # Frozen 1 -> 2 contract; never derive an old transition from the current schema.
    db.execute('''CREATE TABLE bills_new (
        id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL REFERENCES accounts(id),
        invoice_number TEXT NOT NULL, bill_date TEXT NOT NULL, current_total_cents INTEGER NOT NULL,
        document_id INTEGER REFERENCES documents(id), staged_id INTEGER UNIQUE REFERENCES staged(id),
        approved_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active'
        CHECK(status IN ('active','superseded','cancelled')), supersedes_id INTEGER UNIQUE REFERENCES bills(id))''')
    db.execute('''INSERT INTO bills_new(id,account_id,invoice_number,bill_date,current_total_cents,document_id,staged_id,approved_at)
        SELECT id,account_id,invoice_number,bill_date,current_total_cents,document_id,staged_id,approved_at FROM bills''')
    db.execute('DROP TABLE bills')
    db.execute('ALTER TABLE bills_new RENAME TO bills')
    db.execute('ALTER TABLE staged ADD COLUMN correction_of INTEGER REFERENCES bills(id)')
    db.execute("ALTER TABLE staged ADD COLUMN correction_reason TEXT NOT NULL DEFAULT ''")
    db.execute('ALTER TABLE staged ADD COLUMN revision INTEGER NOT NULL DEFAULT 0')
    for statement in V2_ADDITIONS.split(';'):
        if statement.strip():
            db.execute(statement)
    db.execute("INSERT INTO bill_history(bill_id,at,action) SELECT id,approved_at,'approved' FROM bills")


V2_ADDITIONS = """
CREATE UNIQUE INDEX active_invoice_identity ON bills(account_id,invoice_number) WHERE status='active';
CREATE TABLE bill_history (
 id INTEGER PRIMARY KEY, bill_id INTEGER NOT NULL REFERENCES bills(id),
 at TEXT NOT NULL, action TEXT NOT NULL CHECK(action IN ('approved','superseded','cancelled')),
 related_bill_id INTEGER REFERENCES bills(id), reason TEXT NOT NULL DEFAULT '');
CREATE TABLE draft_history (
 id INTEGER PRIMARY KEY, staged_id INTEGER NOT NULL REFERENCES staged(id), at TEXT NOT NULL,
 revision INTEGER NOT NULL, payload TEXT NOT NULL, correction_of INTEGER REFERENCES bills(id),
 reason TEXT NOT NULL, UNIQUE(staged_id,revision));
CREATE TABLE inventory_history (
 id INTEGER PRIMARY KEY, at TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('building','meter')),
 entity_id INTEGER NOT NULL, before_value TEXT NOT NULL, after_value TEXT NOT NULL, reason TEXT NOT NULL);
"""


def to_v3(db):
    db.execute("ALTER TABLE documents ADD COLUMN importer_version TEXT NOT NULL DEFAULT 'legacy-unrecorded'")
    migrate_v2(db)
    event(db, 'MIGRATE_SCHEMA')


def to_v4(db):
    from .intake_storage import initialize
    initialize(db)
    event(db, 'MIGRATE_SCHEMA')


def to_v5(db):
    from .provider_storage import initialize
    initialize(db)
    event(db, 'MIGRATE_SCHEMA')


STEPS = {1: to_v2, 2: to_v3, 3: to_v4, 4: to_v5}


def plan(start, target=SCHEMA_VERSION, steps=None):
    steps = STEPS if steps is None else steps
    if type(start) is not int or type(target) is not int or start < 1 or start >= target:
        raise ValidationError('MIGRATION_SOURCE_OR_TARGET_UNSUPPORTED')
    if any(version not in steps for version in range(start, target)):
        raise ValidationError('MIGRATION_PATH_UNSUPPORTED')
    return [steps[version] for version in range(start, target)]


def read_version(path: Path):
    if not path.is_file() or path.is_symlink():
        raise ValidationError('EXISTING_WORKSPACE_REQUIRED')
    with sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True) as db:
        row = db.execute("SELECT value FROM settings WHERE key='schema_version'").fetchone()
    db.close()
    try:
        return int(row[0])
    except (TypeError, ValueError):
        raise ValidationError('WORKSPACE_SCHEMA_INVALID') from None


def upgrade_copy(store, target: Path, target_version=SCHEMA_VERSION, steps=None):
    """Never switches the live file. One transaction across the complete path."""
    start = read_version(store.path)
    transitions = plan(start, target_version, steps)
    with store.connect() as source, sqlite3.connect(target) as db:
        source.backup(db)
    db.close()
    db = sqlite3.connect(target)
    try:
        db.execute('PRAGMA foreign_keys=OFF')
        db.execute('BEGIN IMMEDIATE')
        for version, transition in enumerate(transitions, start + 1):
            transition(db)
            db.execute("UPDATE settings SET value=? WHERE key='schema_version'", (str(version),))
            if db.execute('PRAGMA foreign_key_check').fetchone() or db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValidationError('MIGRATION_VALIDATION_FAILED')
            if version >= 3:
                verify(db)
            if version >= 4:
                from .intake_storage import verify as verify_extraction
                verify_extraction(db)
            if version >= 5:
                from .provider_storage import verify as verify_providers
                verify_providers(db)
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()
