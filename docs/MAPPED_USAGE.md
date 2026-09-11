# Generic mapped usage CSV

This schema-6 development slice imports staff-obtained local measurement files through **Mapped usage files**. It is tested with fictional CSVs. It is not a certified My360, Central Hudson, gas Green Button or automatic utility connector. No portal, mailbox, cloud extraction or scheduled acquisition is connected. [Provider evidence](PROVIDER_FILE_WORKFLOWS.md) distinguishes public capabilities from unknown school-account support.

## Evidence and financial boundaries

Mapped usage is operational evidence, stored outside `bills`, `bill_lines` and the legacy electricity XML readings. It never creates invoice charges, changes billed quantities or enters Overview financial totals. An August 1 three-hour export does not establish coverage of an August 1–September 1 invoice. Operational readings and invoice quantities covering the same meter are alternative evidence, not additive use. No unit conversion, calendarization, gap filling, cumulative-counter differencing, allocation to buildings, or claim of complete campus coverage occurs.

The existing inventory supplies confirmed stable meter identity. Source commodity must match that meter; the operational source unit is retained separately from the invoice meter's billing unit. This allows, for example, an explicitly identified gas volume export for a meter billed in energy units without pretending the two are interchangeable. A shared/unassigned meter remains shared/unassigned.

A source meter identifier and commodity cannot be actively mapped to two different local meters, even for nonoverlapping exports. This conservative generic implementation has no provider-specific identifier namespace: staff must confirm source identity across imports. Correct an incorrect mapping by withdrawing its source evidence with a reason and creating a new mapping review of the unchanged retained source; do not rename source identifiers to bypass a conflict.

## Supported CSV subset

- UTF-8, optionally with a BOM, comma-separated with one unique, nonempty header row.
- One source meter per file; staff explicitly identifies its meter column and exact source identifier. No rows are silently filtered. Split multi-meter exports locally while retaining original evidence and documenting the conversion.
- Up to 8 MB, 5,000 data rows, 30 columns and 250 characters per cell. The parser stops materializing rows at the row cap. Blank rows, inconsistent widths, control characters and duplicate headers fail validation.
- Explicit value, timestamp, commodity, unit and delta/counter meaning. Quality and source-unit columns are optional. Missing or blank quality is retained as `unknown`; supplied quality is retained verbatim.
- Nonnegative decimal values with at most 16 integer and nine fractional digits. No locale separators, exponent notation, negative/net/export readings or demand quantities.
- Cells whose trimmed beginning is `=`, `+`, `-` or `@` are rejected as formula-like, including unmapped cells. No CSV expression is executed.

| Commodity | Exact supported operational units |
| --- | --- |
| `water` | `US_gal`, `m3`, `L` |
| `natural_gas` | `ft3`, `CCF`, `Mcf`, `m3`, `therm`, `kWh` |
| `electricity` | `Wh`, `kWh` |

`US_gal` specifically means US gallons. `CCF` means hundred cubic feet and `Mcf` means thousand cubic feet. Generic `gal`, unspecified gas units, electricity demand `kW`, and unrecognized labels require clarification. If a unit column is mapped, every cell must exactly equal the declared source unit. If the provider uses another spelling, staff must first establish its precise meaning; the application does not guess aliases, convert volume to energy, or infer gas heating value.

The checked-in [fictional water example](../samples/generic-water-usage.csv) uses source identifier `SYN-WATER-01`, `US_gal`, interval deltas and explicit UTC offsets. Map the `source_meter`, `start`, `end`, `value`, `unit` and `quality` columns. Choose an already-confirmed fictional water meter when demonstrating it. The example is original synthetic data and does not claim a provider export schema.

## Time and counter semantics

Delta rows describe a nonnegative quantity over `[start, end)`, with an explicitly mapped exclusive end after the start. Intervals need not be hourly, daily, monthly or exactly 60 days. Their actual UTC boundaries are retained. Cumulative rows record a raw counter at one timestamp; the end-column mapping must be empty. They are never summed or converted to delta consumption.

Timestamps use ISO date-time strings such as `2026-08-01T00:00:00-04:00` or `2026-08-01T04:00:00Z`; minute precision is also accepted. Date-only, subsecond, locale-formatted and numeric epoch timestamps are outside this subset. Original strings remain in the retained CSV. Normalized whole-second UTC boundaries, explicit mapping, and the declared timezone assumption remain in immutable preview evidence.

Naive timestamps require an explicitly entered IANA timezone such as `America/New_York`. The parser checks both DST folds against a UTC round trip. Ambiguous fall-back hours and nonexistent spring-forward times are rejected; staff needs source timestamps with explicit offsets. Explicit offsets in the source take precedence over a timezone supplied for naive values. A missing local timezone database fails safely; no timezone dependency is added by this slice.

Counter values must be nondecreasing both within an export and against adjacent active same-meter/same-unit readings from earlier exports, including interleaved single-row files. Decreases remain pending as reconciliation conflicts. Real physical counter resets/rollovers do not have a dedicated reset-event model here: retain that file and seek a reviewed extension; do not fabricate deltas or silently concatenate counters across the reset.

## Review, deduplication and correction

1. Upload the CSV. The original bytes are atomically published to the ordinary hash-addressed source store and referenced by `documents`. In demo mode, the synthetic-data checkbox is mandatory. Parse-invalid files are refused without a document; valid files with unsupported mappings remain retained and pending.
2. Inspect the source rows and download the exact original if needed. Select the confirmed local meter, commodity, precise source unit, source identifier column/value, timestamp/value columns, quality and timezone assumptions. Save a mapping preview.
3. Review the saved preview's UTC boundaries, raw counter/delta meaning, quantities, source quality and duplicate/conflict information. Changing the mapping form disables approval until another preview is saved. Preview revisions are append-only.
4. Explicitly acknowledge the source and mapping to approve operational readings. The service requires literal Boolean `true` and the current nonnegative integer revision. Approval reparses retained source bytes and rechecks live conflicts inside an immediate SQLite transaction. A stale or conflicting approval posts nothing.
5. Exact repeated source bytes reopen the latest retained attempt, including its prior decision. Differently formatted exports with identical normalized readings share one immutable reading and retain each approved source as evidence. Repeated rows inside one source are collapsed only when all normalized measurement fields, including quality, agree. Overlap, changed quality, changed quantities and conflicting units require reconciliation.

For a corrected export, inspect each conflicting active import. **Withdraw approved usage source** requires an explicit acknowledgement and a private reason. It withdraws that source's contribution to active evidence without deleting readings, prior previews, decisions or original bytes. A reading supported by another active duplicate source remains active; withdraw all conflicting sources before re-previewing and approving a correction. The conflicting file stays pending until resolved or explicitly rejected with a reason.

For a mapping-only mistake, use **Review this retained source again** after withdrawal or rejection. An explicit reason and acknowledgement create a new import attempt pointing to the same document bytes and the earlier attempt. Only one pending/active attempt per original source is allowed. The earlier decision is preserved. No artificial file editing or hash change is necessary.

Generic electricity deltas overlapping approved legacy XML evidence are blocked. The XML approval path reciprocally blocks active generic deltas. Legacy XML lacks a withdrawal workflow; keep its evidence and reject a conflicting generic file. Do not route water/gas XML through the electricity parser by relabeling it.

## Spreadsheet conversion boundary

Direct `.xlsx`/`.xls` intake is intentionally unavailable: no exact provider export extension/schema has been verified, and this slice introduces no spreadsheet dependency. Authorized staff may use a school-approved offline spreadsheet tool to inspect an export without enabling macros, external links, formulas or automatic recalculation. Preserve the original workbook in school-controlled storage, verify that the measurement cells are literal provider values, and export those values with their meter, unit, timestamp and quality information as UTF-8 comma-separated CSV. Record conversion provenance in a quality column or in the school's retained local evidence notes.

Do not treat cached formula results as qualified measured data. If a file requires evaluating formulas or following external workbook links to establish values, stop that conversion and request a provider-supplied values-only export/schema. Do not use an online converter or send private files to developer/AI tools. UtilityOS retains the imported CSV; the unimported original workbook stays in the school's separately controlled storage.

## Integrity, backup and UI scope

Schema 6 adds immutable import attempts, mapping previews, decisions, withdrawals, readings and source-evidence links. JSON payload hashes bind to fixed audit codes; verification checks both journal-to-audit and audit-to-journal completeness, approved reading/evidence correspondence, source hashes, reattempt parent links and immutable triggers. Audit codes contain no source values, filenames, meter labels, units, quantities or private reasons. Full backups remain private and include source files and all usage history. Source download requires the existing authenticated session.

The UI shows the latest 200 import attempts, up to eight source rows, twenty preview readings and the latest 100 active readings. Displayed totals state the complete reading count; the bounded tables are not a complete export. Historic mapping previews are preserved in the database/backups, while the detail page shows the latest preview and original decision. There is no new public service, automatic folder poller, native Excel parser or usage analytics aggregate.

Schema-5 workspaces require the ordinary explicit backup-first migration. Startup never migrates silently. See [installation and updates](STAFF_INSTALL_AND_UPDATES.md).

## Synthetic verification

`tests/test_usage.py` covers explicit mapping and strict acknowledgement/revision, source bytes, single-meter scope, commodity/unit rejection, formulas, row caps, offset/DST handling, raw gas counters and cross-export counter discontinuities, concurrency/deduplication, partial overlaps, mapping changes, correction withdrawal and same-source reattempt, reciprocal XML conflict rejection, backup/restore and integrity tampering. It also verifies that a partial operational export overlapping the same water meter's monthly invoice leaves invoice amounts and quantities unchanged.

```sh
.venv/bin/python -m pytest -q tests/test_usage.py
.venv/bin/python scripts/native_usage_smoke.py \
  --work-dir /tmp/sks-new-usage-check \
  --browser-executable '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
```

The native check requires a new external synthetic directory. It exercises real upload, mapping preview, approval, download, duplicate source handling, withdrawal, same-original reattempt, conflict reconciliation and logout at desktop/mobile viewports. Its success receipt is emitted only after owned browser/driver shutdown and a zero-exit demo server. Actual school exports, Windows timezone availability/native browser operation, meters and provider acceptance remain externally unverified.
