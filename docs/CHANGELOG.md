# Release notes

## 0.3.0 — 2026-09-06

Local production-readiness development milestone, preserving the 0.2.0 ledger.

- Fixed killed imports leaving truncated final sources and interrupted restore
  overwriting retained originals. Source publication now flushes temporary bytes
  and atomically publishes without overwriting existing files.
- Isolated damaged drafts, added acknowledged recovery to a new pending review
  revision, and blocked approval of corrupt stored review/interval data.
- Added a fixed-field, hash-linked audit chain with update/delete rejection,
  integrity checks and a paginated private browser view. Financial changes and
  audit events commit together. Backup attempts/completion, restore snapshot
  boundaries, migration and local passphrase setup are recorded. Legacy actors
  remain unknown; there is no person-attribution claim.
- Added source importer-version provenance. Existing documents are explicitly
  unrecorded; source bytes and original review histories remain unchanged.
- Added schema 3 and ordered migrations from schemas 1 and 2. Frozen prior-schema
  fixtures, synthetic future-step tests and real process termination test
  all-or-nothing recovery. No automatic migration or unattended update was added.
- Required the current app passphrase for staff cancellation and replacement
  approval. Named roles remain explicitly deferred under the single-operator
  model; a future role matrix and configuration/credential boundary are documented.
- Expanded allowlisted diagnostics with bounded runtime, database, disk,
  backup-location, permissions, port, migration, audit and unsigned-source
  integrity checks. Damaged/incompatible workspaces can be diagnosed read-only.
- Added a deterministic campus with 20 buildings, 60 meters/service points,
  24 months, 1,923 active invoices and 288 interval readings. Added invoice
  search/100-row pages and preserved old pending drafts beyond recent-history
  limits. Existing invoice-month accounting and unit semantics remain intact.
- Established a byte-preserving trusted Git baseline/tag, strengthened ignores
  and source-release membership checks, accepted normal Git ZIP directory entries
  without admitting unlisted files, and researched future macOS signing.
  Dependencies remain unchanged; the dated advisory scan found no known issues.

Schema compatibility: 0.3.0 reads/writes schema 3. Explicit migration preserves a
backup in the original schema. Rollback uses the corresponding old code and
pre-upgrade backup in a new workspace. Read `VERIFICATION.md` for actual checks.
This unsigned source release remains a development-tested single-operator pilot;
it is not school acceptance, role-separated access or production deployment.

## 0.2.0 — 2026-09-06

Development milestone B: audited bill corrections and practical local maintenance, built on the existing implementation.

- Added full-invoice corrections, same-reference rebills with separate sources, cancellation, and retained version history. Active-only reports and exports prevent double counting. Independent credits remain negative charges with zero repeated consumption.
- Added saved partial drafts, append-only saved review revisions, stale-review detection, service-line removal, invoice history navigation, building-label editing, and confirmed meter mapping changes with before/after history.
- Prevented chart-axis label collisions when small negative credits appear beside larger positive months.
- Fixed review lists showing the original empty PDF payload after staff entry. Tiny decimal quantities now round-trip in plain decimal notation and display without rounding away recorded precision.
- Prevented one imported electricity stream from being approved under multiple meters. Restore-orphan reimports reuse verified identical source bytes and refuse conflicting content.
- Added acknowledged browser backup creation/download and stopped-app recovery instructions. Backup archives appear only after successful completion and use the same size/member limits as restoration.
- Added explicit schema 1 → 2 migration: validate a copy, preserve a schema-1 backup, and atomically replace the database. Normal launch rejects incompatible schema without changing it. No unattended update service or arbitrary migration runner was added.
- Made macOS launchers executable, forwarded workspace/port arguments, opened the browser after startup, and added a clear occupied-port error. Fixed the staff guide link. Added wheel-only/offline setup and preserved launcher permissions in release ZIPs.
- Updated advisory-affected dependencies; added native browser and recovery tests. Removed obsolete references to non-development materials from technical documentation.

Schema compatibility: 0.2.0 reads/writes schema 2. Migration from schema 1 requires an explicit operator command and backup. Schema-1 code cannot open schema 2. Rollback uses the retained old release and pre-upgrade backup in a separate recovery workspace; post-backup work requires deliberate recovery.

This release is unsigned and is a development-tested local pilot. School installation, private records, multi-user access, Windows validation, signing/distribution, retention, and maintenance ownership remain separate decisions. See `VERIFICATION.md` for tests actually run.

## 0.1.0

Initial staff-local ledger, synthetic fixtures, CSV/manual PDF/limited XML review, local sessions, fixed diagnostics, backup/restore, and source release tooling. Native browser checks in the original build environment were blocked and used an explicit test transport bridge. No school installation or portal access was performed.
