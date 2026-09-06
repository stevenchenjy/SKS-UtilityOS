-- Frozen 0.1.0 schema for migration regression tests. Synthetic databases only.

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
 extension TEXT NOT NULL, size INTEGER NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS staged (
 id INTEGER PRIMARY KEY, document_id INTEGER NOT NULL REFERENCES documents(id),
 kind TEXT NOT NULL CHECK(kind IN ('bill','intervals')), status TEXT NOT NULL DEFAULT 'pending'
 CHECK(status IN ('pending','approved','rejected')),
 payload TEXT NOT NULL, review_payload TEXT, created_at TEXT NOT NULL, reviewed_at TEXT);
CREATE TABLE IF NOT EXISTS bills (
 id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL REFERENCES accounts(id),
 invoice_number TEXT NOT NULL, bill_date TEXT NOT NULL, current_total_cents INTEGER NOT NULL,
 document_id INTEGER REFERENCES documents(id), staged_id INTEGER UNIQUE REFERENCES staged(id),
 approved_at TEXT NOT NULL, UNIQUE(account_id,invoice_number));
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
CREATE TABLE IF NOT EXISTS audit_events (
 id INTEGER PRIMARY KEY, at TEXT NOT NULL, code TEXT NOT NULL, staged_id INTEGER);
