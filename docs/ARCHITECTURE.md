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
| documents | Original bytes, content hash, source kind, and original filename |
| staged records | Original parsed payload, current reviewed payload, saved revision, correction target, and review status |
| bills / bill_lines | Immutable reviewed versions, active/superseded/cancelled state, replacement links, current charges, periods, units, quantities, and treatment |
| bill_history / draft_history / inventory_history | Private lifecycle events, saved review revisions, and before/after mapping changes |
| interval_channels / interval_readings | Meter mapping, UTC start, duration, delta energy, and source quality |
| audit_events | Fixed event codes for the single local operator |

The initial inventory is populated by reviewing a bill. A staff member can supply a local account label such as `Electric account A` rather than an entire account number. Meter codes should remain stable when accounts or suppliers change. The starter records observed association dates; a complete physical meter replacement and overlapping-service lifecycle editor remains future work.

## Financial and consumption rules

Invoice totals represent current charges in USD. Prior balances, payments, and carried-forward amounts must be excluded from those fields. Line charges reconcile exactly to the invoice current charges using integer cents. Negative current charges can represent a credit.

Each service line has a quantity treatment. `consumption` contributes to billed consumption. `charges_only` adds cost with zero consumption, such as a separate supply invoice for a meter whose delivery bill already records the kWh. `delivery` represents purchased oil or propane volume. The dashboard keeps different units separate and does not infer heat content or tank consumption.

Service periods use an inclusive start and exclusive end. Overlapping approved consumption for one meter is blocked in this version. Staff must interpret a supplier's printed end-date convention correctly. A reviewed rebill excludes only its active original while checking overlaps, then supersedes that original and inserts the replacement atomically. Reporting includes only active versions. See `INVOICE_LIFECYCLE.md`.

Costs are grouped by invoice issue month. Full service-period quantities appear with the invoices issued in the selected month. There is no pro-rata calendarization, weather normalization, completeness-adjusted comparison, savings verification, or carbon calculation in v0.2.0.

## Import flow

```text
Authorized local file
    -> size/type checks and immutable source storage
    -> parser or blank PDF-entry draft
    -> field validation and possible warning flags
    -> staff review and acknowledgement
    -> transaction commits approved records
    -> dashboard reads active approved versions only
```

Canonical CSV rows can describe multiple service lines. The parser enforces invoice identity consistency, supported units, quantity treatment, dates, and charge reconciliation. Exact source duplicates, repeated invoice identity, and duplicate consumption are checked separately.

PDF handling preserves the source and creates a blank entry form. The application contains no PDF text extractor, OCR model, or external inference API. The synthetic PDF is a test fixture for this workflow.

The Green Button reader accepts a narrow DMD XML contract: electricity, Wh units, forward flow, delta energy, an explicit power-of-ten multiplier, and correctly linked ReadingType/MeterReading/IntervalBlock resources. Readings are normalized to kWh and stored separately from monthly bill consumption. Unsupported water, gas, net/export, cumulative, demand, or ambiguous readings fail validation. Source links are resolved within the document and are never fetched over the network.

## Size and deployment boundaries

Uploads are limited to 8 MiB. The starter additionally limits CSV rows/invoices and XML readings to bound import work. Limits are explicit engineering defaults; they can be raised after resource tests. The UI is intended for a small local utility ledger, and no enterprise throughput claim has been measured.

SQLite transactions keep approvals consistent. The launcher uses an OS-level workspace lock. Backup uses SQLite's backup API and verifies source-file hashes. Restore checks archive paths, hashes, database integrity, schema, mode, and referenced sources before replacing the workspace database.

## Maintenance and module boundaries in 0.2.0

`service.py` retains import, approval, interval, and reporting contracts. `lifecycle.py` owns saved draft revisions, correction targets, cancellation, and version history. `inventory.py` owns explicit mapping edits; `audit.py` holds fixed-code audit helpers. Frontend `bills.js` and `lifecycle.js` extend the existing ES module structure. No component framework or build system was added.

Schema 2 replaces the unconditional invoice-number uniqueness constraint with active-identity uniqueness and explicit replacement lineage. A schema-1 snapshot is retained as a test fixture. The explicit migration in `operations.py` builds a validated copy after backup; ordinary startup never migrates. The launcher holds the workspace lock for startup and maintenance. Browser backups use SQLite snapshots while the service owns that lock; restoration and migration require a stopped app.

Installing into a separate code folder changes no staff data. Hash manifests protect release integrity; trusted provenance remains an external school decision. Rollback across the schema boundary requires the old code and pre-upgrade backup in a separate recovery directory. Private source retention and backup paths are not included in diagnostics.
