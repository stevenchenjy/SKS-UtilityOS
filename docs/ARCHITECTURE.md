# Architecture and data contracts

## Deployment model

A staff member uses a browser on the same school-controlled computer that runs the application. Uvicorn binds to IPv4 loopback, and FastAPI serves both the API and static UI. SQLite and source documents live in a separate OS application-data directory. The service needs no outbound connection while processing local files.

```text
Student development computer                 Staff-controlled computer
Synthetic fixtures + source code             Authorized CSV / XML / PDF files
              |                                             |
     Reviewed source release                        Import and review
              |                                             |
              +---- School IT approves ---> Local application
                                                       |
                                    SQLite + immutable source files
                                                       |
                                   Staff-only dashboard and exports

Developer support <--- Staff previews and shares fixed diagnostic JSON
```

The application is a single-operator pilot. Two independently installed copies have separate ledgers; there is no synchronization between them. A future shared school server requires an explicit design for authentication, role separation, HTTPS, backups, and access logging that avoids document contents.

## Why this stack

FastAPI provides the local HTTP API, SQLite provides transactional storage, and defusedxml handles untrusted XML with entity defenses. The interface is separated into browser ES modules for overview, review, inventory, intervals, and support. All assets are served locally, so no CDN availability is required.

The build environment had no npm registry access. A native module frontend allowed an immediately runnable application without introducing an untested Node dependency tree. A future React conversion should have a demonstrated maintenance benefit and preserve the existing API contracts.

## Data objects

| Object | Purpose |
|---|---|
| buildings | Staff-confirmed labels for physical locations |
| providers / accounts | Supplier identity and a local account alias; no portal login |
| meters | Stable service-point identity and commodity |
| account_meters | Observed relationships connecting financial accounts to service points over time |
| documents | Original bytes, content hash, source kind, original filename, and importer release |
| staged records | Original parsed payload, current reviewed payload, saved revision, correction target, and review status |
| bills / bill_lines | Immutable reviewed versions, active/superseded/cancelled state, replacement links, current charges, periods, units, quantities, and treatment |
| bill_history / draft_history / inventory_history | Private lifecycle events, saved review revisions, and before/after mapping changes |
| interval_channels / interval_readings | Meter mapping, UTC start, duration, delta energy, and source quality |
| audit_events | Fixed events, actor context, references, and predecessor hashes |

The initial inventory is populated by reviewing a bill. A staff member can supply a local account label such as `Electric account A` rather than an entire account number. Meter codes should remain stable when accounts or suppliers change. The starter records observed association dates; a complete physical meter replacement and overlapping-service lifecycle editor remains future work.

## Financial and consumption rules

Invoice totals represent current charges in USD. Prior balances, payments, and carried-forward amounts must be excluded from those fields. Line charges reconcile exactly to the invoice current charges using integer cents. Negative current charges can represent a credit.

Each service line has a quantity treatment. `consumption` contributes to billed consumption. `charges_only` adds cost with zero consumption, such as a separate supply invoice for a meter whose delivery bill already records the kWh. `delivery` represents purchased oil or propane volume. The dashboard keeps different units separate and does not infer heat content or tank consumption.

Service periods use an inclusive start and exclusive end. Overlapping approved consumption for one meter is blocked in this version. Staff must interpret a supplier's printed end-date convention correctly. A reviewed rebill excludes only its active original while checking overlaps, then supersedes that original and inserts the replacement atomically. Reporting includes only active versions. See `INVOICE_LIFECYCLE.md`.

Costs are grouped by invoice issue month. Full service-period quantities appear with the invoices issued in the selected month. There is no pro-rata calendarization, weather normalization, completeness-adjusted comparison, savings verification, or carbon calculation in v0.5.0.

## Import flow

```text
Authorized local file
    -> size/type checks and immutable source storage
    -> parser or evidence-backed PDF candidate / manual draft
    -> field validation and possible warning flags
    -> staff review and acknowledgement
    -> transaction commits approved records
    -> dashboard reads active approved versions only
```

Canonical CSV rows can describe multiple service lines. The parser enforces invoice identity consistency, supported units, quantity treatment, dates, and charge reconciliation. Exact source duplicates, repeated invoice identity, and duplicate consumption are checked separately.

PDF handling preserves the source and immutable field evidence from a bounded local worker. Digital text uses pdfplumber; PDFium supplies the preview. Optional hash-pinned English Tesseract OCR proposes scan fields. Versioned fictional templates abstain on unknown layouts, and missing/unsupported fields remain for staff completion. There is no external inference API. See `BILL_INTAKE.md`.

The Green Button reader accepts a narrow DMD XML contract: electricity, Wh units, forward flow, delta energy, an explicit power-of-ten multiplier, and correctly linked ReadingType/MeterReading/IntervalBlock resources. Readings are normalized to kWh and stored separately from monthly bill consumption. Unsupported water, gas, net/export, cumulative, demand, or ambiguous readings fail validation. Source links are resolved within the document and are never fetched over the network.

## Size and deployment boundaries

Uploads are limited to 8 MiB. The starter additionally limits CSV rows/invoices and XML readings to bound import work. Limits are explicit engineering defaults; they can be raised after resource tests. The UI is intended for a small local utility ledger, and 20-building/60-service-point synthetic fixture covers 24 months. This is a measured development case, not an enterprise throughput claim.

SQLite transactions keep approvals consistent. The launcher uses an OS-level workspace lock. Backup uses SQLite's backup API and verifies source-file hashes. Restore checks archive paths, hashes, database integrity, schema, mode, and referenced sources before replacing the workspace database.

## Maintenance and module boundaries in 0.2.0

`service.py` retains import, approval, interval, and reporting contracts. `lifecycle.py` owns saved draft revisions, correction targets, cancellation, and version history. `inventory.py` owns explicit mapping edits; `audit.py` holds fixed-code audit helpers. Frontend `bills.js` and `lifecycle.js` extend the existing ES module structure. No component framework or build system was added.

Schema 2 replaces the unconditional invoice-number uniqueness constraint with active-identity uniqueness and explicit replacement lineage. A schema-1 snapshot is retained as a test fixture. The explicit migration in `operations.py` builds a validated copy after backup; ordinary startup never migrates. The launcher holds the workspace lock for startup and maintenance. Browser backups use SQLite snapshots while the service owns that lock; restoration and migration require a stopped app.

Installing into a separate code folder changes no staff data. Hash manifests protect release integrity; trusted provenance remains an external school decision. Rollback across the schema boundary requires the old code and pre-upgrade backup in a separate recovery directory. Private source retention and backup paths are not included in diagnostics.

## 0.3.0 maintenance boundaries

`storage.py` publishes fsynced source bytes through a same-directory temporary
file and a non-overwriting atomic link. Migration/restore switches use flushed
files and atomic replacement. SQLite commits financial rows, statuses, saved
revisions and their audit events together. Temporary or complete orphan source
files never represent approved records.

`review_data.py` validates persisted payload structure and compares saved bill
entry against its revision. A damaged item is isolated; recovery appends a new
pending revision. `migrations.py` keeps frozen transitions separate from the
current schema and validates the complete path on a copy. Schema 3 adds document
importer provenance and the audit table's fixed actor/subject/reference/hash
fields with update/delete rejection rules. Maintenance validates the chain;
restoration records an explicit snapshot boundary and retains a safety backup.

`diagnostics.py` has a fixed operational schema, coarse categories and no data
serialization. Browser ledger rendering uses search and 100-row pages; review
includes every pending draft plus 500 recent closed imports. Audit history uses
a server cursor with 100-event pages. The deterministic campus generator uses
existing ledger APIs and standard-library code. Dependencies remain unchanged.

Single-operator authentication remains intentional. See
`ACCESS_AND_CONFIGURATION.md` for the proposed future role matrix and current
passphrase-confirmation/OS-maintenance boundary, and `OPERATIONS.md` for exact
idempotency, recovery and audit limitations.

## 0.4.0 intake boundaries

`extraction_schema.py` defines the strict candidate contract; `extraction.py`
normalizes exact values and separates invoice totals from balances. Literal-label
`provider_templates.py` is independent from ledger/storage. `pdf_worker.py` runs
bounded parsing/rendering/OCR in a disposable process; `pdf_extract.py` limits
concurrency, private IPC and deadlines. `intake.py` owns durable attempts and
explicit stable-file scans. Neither worker nor inbox can approve records.

Schema 4 adds immutable extraction/audit bindings, revision-linked intake review
snapshots and structured differences, durable intake attempts, and explicit
cadence/history tables. `intake_storage.py` joins these with the existing draft
and approval transactions. `extraction_quality.py` aggregates fixed-key counts;
`completeness.py` reports only explicitly configured invoice-month expectations.
New evidence, inbox and completeness browser modules extend the existing shell.
The ledger payload and active-only accounting contracts are unchanged.

Migration 3 → 4 adds these tables and rules without reparsing historical PDFs,
changing old payloads or fabricating extraction evidence. Backup/restore carries
the private extraction/review snapshots and verifies their source/audit integrity.
Model weights remain separately installed software assets outside both code and
private backups. No OCR cache, trained model or document log is generated.


## 0.5.0 private provider boundaries

Schema 5 adds an append-only `local_provider_records` journal for private
providers, immutable layout definitions, validations, state decisions and
original extraction links. Each record has canonical JSON, a SHA-256 digest and
an audit binding committed in the same transaction. Database guards reject
ordinary updates and deletes. The journal is private workspace data; no local
registry is written into the source tree.

`provider_rules.py` validates a small declarative grammar and compiles observations
into the existing Extraction v1 contract. Locators use literal labels, bounded
page/region/distance constraints and typed parsers. Single-service documents and
numbered repeated sections are explicit alternatives. There is no executable
plugin or operator-supplied regex. `pdf_worker.py` supplies bounded Observations
v1 through the existing isolated worker; PDF/OCR library details remain behind
this adapter. Historical extraction JSON is never recompiled by template edits.

`provider_storage.py` owns the journal and integrity checks;
`provider_studio.py` owns private validation, activation, retirement, quality and
preview; `provider_routes.py` exposes authenticated operations; and
`provider_support.py` constructs a separate positive-schema support export.
`web/modules/providers.js` reuses the existing evidence viewer for setup.
Validation compares selected retained PDFs with their final approved revisions.
Activation rechecks that corpus snapshot and requires a deliberate operator
acknowledgement. Active layouts still stage candidates for ordinary approval.

Import captures the registry before extraction and checks it again in the
publication transaction. A concurrent state change requests a retry without
publishing a stale candidate. Damaged registry state quarantines local parsers;
manual intake remains available. Backup, restore, migration and `check` require
journal integrity and fail closed. These hashes detect corruption, not an OS
owner rewriting the complete database, audit chain and application.

See `PROVIDER_STUDIO.md` for the full grammar, gates, privacy contract and future
school-side extraction-engine A/B evaluation boundary.


## Building reporting (unreleased)

`reporting.py` validates the common `building` (`all`, `unassigned`, or a current
building ID) and `month` (`YYYY-MM`) scope used by `/api/overview` and `/api/bills`.
Invalid selections fail explicitly. An explicit valid month with no matching
invoices stays selected instead of silently switching to another period.
Overview month choices come from active campus invoices plus any explicit month;
zero-count scoped months mean no approved records, not established zero use.

Both endpoints join service lines to current meter mappings. Dashboard sums use
active line charges, counting a split invoice once within each matching scope.
The bill list retains every version and returns `matched_total_cents` alongside
`current_total_cents`; the UI defaults to active versions. Building subtotals
reconcile to the all-building total without allocating unassigned lines. Building
IDs keep a physical label that happens to equal "Unassigned / shared" separate
from the unassigned bucket. `stats` retains whole-ledger counts; `scope_stats`
reports mapped service points and accounts/invoices with active bills across all
months. Selected-month service points explicitly show missing bills.

No migration, writes, new dependencies, interval summation, estimated allocation,
or calendarization is part of this reporting change. Source and review payloads
retain their original labels after an inventory mapping edit. Report selections
live only in the browser session's in-memory navigation context.
