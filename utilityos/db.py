"""SQLite schema and local-only persistence. Original files remain outside source."""
from contextlib import contextmanager
from pathlib import Path
import sqlite3
import os
from . import SCHEMA_VERSION
from .audit import TABLE as AUDIT_TABLE, TRIGGERS as AUDIT_TRIGGERS, verify as verify_audit

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS buildings (
 id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, area_sqft TEXT,
 CHECK(area_sqft IS NULL OR CAST(area_sqft AS REAL)>0));
CREATE TABLE IF NOT EXISTS providers (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS accounts (
 id INTEGER PRIMARY KEY, provider_id INTEGER NOT NULL REFERENCES providers(id),
 alias TEXT NOT NULL, UNIQUE(provider_id,alias));
CREATE TABLE IF NOT EXISTS meters (
 id INTEGER PRIMARY KEY, code TEXT UNIQUE NOT NULL, building_id INTEGER REFERENCES buildings(id),
 commodity TEXT NOT NULL, unit TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS account_meters (
 id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL REFERENCES accounts(id),
 meter_id INTEGER NOT NULL REFERENCES meters(id), valid_from TEXT NOT NULL, valid_to TEXT,
 UNIQUE(account_id,meter_id,valid_from));
CREATE TABLE IF NOT EXISTS documents (
 id INTEGER PRIMARY KEY, sha256 TEXT UNIQUE NOT NULL, filename TEXT NOT NULL,
 extension TEXT NOT NULL, size INTEGER NOT NULL, created_at TEXT NOT NULL,
 importer_version TEXT NOT NULL DEFAULT 'legacy-unrecorded');
CREATE TABLE IF NOT EXISTS staged (
 id INTEGER PRIMARY KEY, document_id INTEGER NOT NULL REFERENCES documents(id),
 kind TEXT NOT NULL CHECK(kind IN ('bill','intervals')), status TEXT NOT NULL DEFAULT 'pending'
 CHECK(status IN ('pending','approved','rejected')),
 payload TEXT NOT NULL, review_payload TEXT, created_at TEXT NOT NULL, reviewed_at TEXT,
 correction_of INTEGER REFERENCES bills(id), correction_reason TEXT NOT NULL DEFAULT '',
 revision INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS bills (
 id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL REFERENCES accounts(id),
 invoice_number TEXT NOT NULL, bill_date TEXT NOT NULL, current_total_cents INTEGER NOT NULL,
 document_id INTEGER REFERENCES documents(id), staged_id INTEGER UNIQUE REFERENCES staged(id),
 approved_at TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','superseded','cancelled')),
 supersedes_id INTEGER UNIQUE REFERENCES bills(id));
CREATE UNIQUE INDEX IF NOT EXISTS active_invoice_identity ON bills(account_id,invoice_number) WHERE status='active';
CREATE TABLE IF NOT EXISTS bill_lines (
 id INTEGER PRIMARY KEY, bill_id INTEGER NOT NULL REFERENCES bills(id),
 meter_id INTEGER NOT NULL REFERENCES meters(id), period_start TEXT NOT NULL, period_end TEXT NOT NULL,
 usage TEXT NOT NULL, unit TEXT NOT NULL, charge_cents INTEGER NOT NULL,
 usage_role TEXT NOT NULL CHECK(usage_role IN ('consumption','charges_only','delivery')),
 read_type TEXT NOT NULL CHECK(read_type IN ('actual','estimated','unknown')),
 CHECK(period_end>period_start));
CREATE INDEX IF NOT EXISTS bill_lines_meter_period ON bill_lines(meter_id,period_start,period_end);
CREATE TABLE IF NOT EXISTS interval_channels (
 id INTEGER PRIMARY KEY, meter_id INTEGER NOT NULL REFERENCES meters(id),
 source_channel TEXT NOT NULL, metadata TEXT NOT NULL,
 UNIQUE(meter_id,source_channel));
CREATE TABLE IF NOT EXISTS interval_readings (
 channel_id INTEGER NOT NULL REFERENCES interval_channels(id), start_utc INTEGER NOT NULL,
 duration_s INTEGER NOT NULL CHECK(duration_s>0), quantity TEXT NOT NULL, quality TEXT NOT NULL,
 document_id INTEGER REFERENCES documents(id), PRIMARY KEY(channel_id,start_utc));
CREATE TABLE IF NOT EXISTS bill_history (
 id INTEGER PRIMARY KEY, bill_id INTEGER NOT NULL REFERENCES bills(id),
 at TEXT NOT NULL, action TEXT NOT NULL CHECK(action IN ('approved','superseded','cancelled')),
 related_bill_id INTEGER REFERENCES bills(id), reason TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS draft_history (
 id INTEGER PRIMARY KEY, staged_id INTEGER NOT NULL REFERENCES staged(id), at TEXT NOT NULL,
 revision INTEGER NOT NULL, payload TEXT NOT NULL, correction_of INTEGER REFERENCES bills(id),
 reason TEXT NOT NULL, UNIQUE(staged_id,revision));
CREATE TABLE IF NOT EXISTS inventory_history (
 id INTEGER PRIMARY KEY, at TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('building','meter')),
 entity_id INTEGER NOT NULL, before_value TEXT NOT NULL, after_value TEXT NOT NULL, reason TEXT NOT NULL);
"""


class Store:
    def __init__(self, directory: Path, mode: str, *, initialize=True, expected_schema=SCHEMA_VERSION):
        self.directory = directory.resolve()
        self.sources = self.directory / "sources"
        self.path = self.directory / "utilityos.sqlite3"
        if not initialize and not self.path.is_file():
            raise ValueError("EXISTING_WORKSPACE_REQUIRED")
        if initialize:
            self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        existing = self.path.is_file()
        with self.connect() as db:
            if existing:
                try:
                    settings = dict(db.execute("SELECT key,value FROM settings"))
                except sqlite3.DatabaseError:
                    raise ValueError("WORKSPACE_DATABASE_INVALID") from None
                if settings.get('mode') != mode:
                    raise ValueError("MODE_DATA_MISMATCH_USE_A_SEPARATE_DIRECTORY")
                if settings.get('schema_version') != str(expected_schema):
                    raise ValueError("SCHEMA_VERSION_UNSUPPORTED_REQUIRES_REVIEWED_MIGRATION")
                if expected_schema >= 3 and verify_audit(db) != 'ok':
                    raise ValueError("AUDIT_INTEGRITY_FAILED")
                if expected_schema >= 4:
                    from .intake_storage import verify
                    verify(db)
                if expected_schema >= 6:
                    from .billing_schedules import verify as verify_schedules
                    from .usage_storage import verify as verify_usage
                    verify_schedules(db)
                    verify_usage(db)
            elif initialize and expected_schema == SCHEMA_VERSION:
                db.executescript(SCHEMA + AUDIT_TABLE + AUDIT_TRIGGERS)
                from .intake_storage import initialize
                initialize(db)
                from .provider_storage import initialize as initialize_providers
                initialize_providers(db)
                from .billing_schedules import initialize as initialize_schedules
                from .usage_storage import initialize as initialize_usage
                initialize_schedules(db)
                initialize_usage(db)
                db.executemany("INSERT INTO settings VALUES (?,?)", [('schema_version',str(SCHEMA_VERSION)),('mode',mode)])
            else:
                raise ValueError("EXISTING_WORKSPACE_REQUIRED")
        if initialize:
            self.sources.mkdir(exist_ok=True, mode=0o700)
            if os.name != 'nt':
                self.directory.chmod(0o700)
                self.sources.chmod(0o700)
                self.path.chmod(0o600)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=20)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
