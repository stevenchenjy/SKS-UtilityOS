-- Frozen from the verified, immutable 0.3.0 installation, schema 3.
CREATE TABLE account_meters (
 id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL REFERENCES accounts(id),
 meter_id INTEGER NOT NULL REFERENCES meters(id), valid_from TEXT NOT NULL, valid_to TEXT,
 UNIQUE(account_id,meter_id,valid_from));
CREATE TABLE accounts (
 id INTEGER PRIMARY KEY, provider_id INTEGER NOT NULL REFERENCES providers(id),
 alias TEXT NOT NULL, UNIQUE(provider_id,alias));
CREATE TABLE audit_events (
 id INTEGER PRIMARY KEY, at TEXT NOT NULL, code TEXT NOT NULL, staged_id INTEGER,
 actor TEXT NOT NULL, subject_kind TEXT NOT NULL, subject_id INTEGER,
 operation_id TEXT NOT NULL DEFAULT '', related_hash TEXT NOT NULL DEFAULT '',
 previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL UNIQUE);
CREATE TABLE bill_history (
 id INTEGER PRIMARY KEY, bill_id INTEGER NOT NULL REFERENCES bills(id),
 at TEXT NOT NULL, action TEXT NOT NULL CHECK(action IN ('approved','superseded','cancelled')),
 related_bill_id INTEGER REFERENCES bills(id), reason TEXT NOT NULL DEFAULT '');
CREATE TABLE bill_lines (
 id INTEGER PRIMARY KEY, bill_id INTEGER NOT NULL REFERENCES bills(id),
 meter_id INTEGER NOT NULL REFERENCES meters(id), period_start TEXT NOT NULL, period_end TEXT NOT NULL,
 usage TEXT NOT NULL, unit TEXT NOT NULL, charge_cents INTEGER NOT NULL,
 usage_role TEXT NOT NULL CHECK(usage_role IN ('consumption','charges_only','delivery')),
 read_type TEXT NOT NULL CHECK(read_type IN ('actual','estimated','unknown')),
 CHECK(period_end>period_start));
CREATE TABLE bills (
 id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL REFERENCES accounts(id),
 invoice_number TEXT NOT NULL, bill_date TEXT NOT NULL, current_total_cents INTEGER NOT NULL,
 document_id INTEGER REFERENCES documents(id), staged_id INTEGER UNIQUE REFERENCES staged(id),
 approved_at TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','superseded','cancelled')),
 supersedes_id INTEGER UNIQUE REFERENCES bills(id));
CREATE TABLE buildings (
 id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, area_sqft TEXT,
 CHECK(area_sqft IS NULL OR CAST(area_sqft AS REAL)>0));
CREATE TABLE documents (
 id INTEGER PRIMARY KEY, sha256 TEXT UNIQUE NOT NULL, filename TEXT NOT NULL,
 extension TEXT NOT NULL, size INTEGER NOT NULL, created_at TEXT NOT NULL,
 importer_version TEXT NOT NULL DEFAULT 'legacy-unrecorded');
CREATE TABLE draft_history (
 id INTEGER PRIMARY KEY, staged_id INTEGER NOT NULL REFERENCES staged(id), at TEXT NOT NULL,
 revision INTEGER NOT NULL, payload TEXT NOT NULL, correction_of INTEGER REFERENCES bills(id),
 reason TEXT NOT NULL, UNIQUE(staged_id,revision));
CREATE TABLE interval_channels (
 id INTEGER PRIMARY KEY, meter_id INTEGER NOT NULL REFERENCES meters(id),
 source_channel TEXT NOT NULL, metadata TEXT NOT NULL,
 UNIQUE(meter_id,source_channel));
CREATE TABLE interval_readings (
 channel_id INTEGER NOT NULL REFERENCES interval_channels(id), start_utc INTEGER NOT NULL,
 duration_s INTEGER NOT NULL CHECK(duration_s>0), quantity TEXT NOT NULL, quality TEXT NOT NULL,
 document_id INTEGER REFERENCES documents(id), PRIMARY KEY(channel_id,start_utc));
CREATE TABLE inventory_history (
 id INTEGER PRIMARY KEY, at TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('building','meter')),
 entity_id INTEGER NOT NULL, before_value TEXT NOT NULL, after_value TEXT NOT NULL, reason TEXT NOT NULL);
CREATE TABLE meters (
 id INTEGER PRIMARY KEY, code TEXT UNIQUE NOT NULL, building_id INTEGER REFERENCES buildings(id),
 commodity TEXT NOT NULL, unit TEXT NOT NULL);
CREATE TABLE providers (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL);
CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE staged (
 id INTEGER PRIMARY KEY, document_id INTEGER NOT NULL REFERENCES documents(id),
 kind TEXT NOT NULL CHECK(kind IN ('bill','intervals')), status TEXT NOT NULL DEFAULT 'pending'
 CHECK(status IN ('pending','approved','rejected')),
 payload TEXT NOT NULL, review_payload TEXT, created_at TEXT NOT NULL, reviewed_at TEXT,
 correction_of INTEGER REFERENCES bills(id), correction_reason TEXT NOT NULL DEFAULT '',
 revision INTEGER NOT NULL DEFAULT 0);
CREATE UNIQUE INDEX active_invoice_identity ON bills(account_id,invoice_number) WHERE status='active';
CREATE INDEX bill_lines_meter_period ON bill_lines(meter_id,period_start,period_end);
CREATE TRIGGER audit_no_delete BEFORE DELETE ON audit_events
BEGIN SELECT RAISE(ABORT,'AUDIT_APPEND_ONLY'); END;
CREATE TRIGGER audit_no_update BEFORE UPDATE ON audit_events
BEGIN SELECT RAISE(ABORT,'AUDIT_APPEND_ONLY'); END;
