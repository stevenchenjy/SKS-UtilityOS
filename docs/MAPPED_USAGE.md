# Generic mapped usage CSV and XLSX

The rc3 / schema-7 candidate imports staff-obtained local measurement files through **Mapped usage files**. It is tested with fictional CSVs and values-only XLSX workbooks. It is not a certified My360, Central Hudson, gas Green Button or automatic utility connector. No portal, mailbox or cloud extraction is connected. The optional foreground acquisition watcher can retain supported files for this same review queue; it cannot approve them. [Provider evidence](PROVIDER_FILE_WORKFLOWS.md) distinguishes public capabilities from unknown school-account support.

## Evidence and financial boundaries

Mapped usage is operational evidence, stored outside `bills`, `bill_lines` and the legacy electricity XML readings. It never creates invoice charges, changes billed quantities or enters Overview financial totals. An August 1 three-hour export does not establish coverage of an August 1–September 1 invoice. Operational readings and invoice quantities covering the same meter are alternative evidence, not additive use. No unit conversion, calendarization, gap filling, cumulative-counter differencing, allocation to buildings, or claim of complete campus coverage occurs.

The existing inventory supplies confirmed stable meter identity. Source commodity must match that meter; the operational source unit is retained separately from the invoice meter's billing unit. This allows, for example, an explicitly identified gas volume export for a meter billed in energy units without pretending the two are interchangeable. A shared/unassigned meter remains shared/unassigned.

A source meter identifier and commodity cannot be actively mapped to two different local meters, even for nonoverlapping exports. This conservative generic implementation has no provider-specific identifier namespace: staff must confirm source identity across imports. Correct an incorrect mapping by withdrawing its source evidence with a reason and creating a new mapping review of the unchanged retained source; do not rename source identifiers to bypass a conflict.

## Supported CSV subset

- UTF-8, optionally with a BOM, comma-separated with one unique, nonempty header row.
- One source meter per selected CSV table; staff explicitly identifies its meter column and exact source identifier. No rows are silently filtered. For CSVs, split multi-meter exports locally while retaining original evidence and documenting the conversion. XLSX allows selecting one meter’s explicit region inside the unchanged retained workbook.
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

Naive timestamps require an explicitly entered IANA timezone such as `America/New_York`. The parser checks both DST folds against a UTC round trip. Ambiguous fall-back hours and nonexistent spring-forward times are rejected; staff needs source timestamps with explicit offsets. Explicit offsets in the source take precedence over a timezone supplied for naive values. A missing local timezone database fails safely. The portable runtime includes reviewed tzdata 2026.4. Mapped usage reads that pinned package directly, independent of OS timezone paths, and records the version with new preview provenance. Missing or mismatched packaged data fails safely. Native OS acceptance remains separate.

Counter values must be nondecreasing both within an export and against adjacent active same-meter/same-unit readings from earlier exports, including interleaved single-row files. Decreases remain pending as reconciliation conflicts. Real physical counter resets/rollovers do not have a dedicated reset-event model here: retain that file and seek a reviewed extension; do not fabricate deltas or silently concatenate counters across the reset.

## Review, deduplication and correction

1. Upload the CSV or workbook. The original bytes are atomically published to the ordinary hash-addressed source store and referenced by `documents`. In demo mode, the synthetic-data checkbox is mandatory. Parse-invalid or unsafe files are refused without a document; safe workbooks with unfamiliar tables and sources with unsupported mappings remain retained and pending.
2. For XLSX, inspect the visible sheets and candidate header rows, select the exact sheet, header row, first/last column numbers and inclusive final data row, and inspect that region. Inspect the source rows and download the exact original if needed. Select the confirmed local meter, commodity, precise source unit, source identifier column/value, timestamp/value columns, quality and timezone assumptions. Save a mapping preview.
3. Review the saved preview's UTC boundaries, raw counter/delta meaning, quantities, source quality and duplicate/conflict information. Changing the mapping form disables approval until another preview is saved. Preview revisions are append-only. The optional reuse checkbox makes an approved layout available to compatible future imports; pending or withdrawn approvals never establish a reusable layout.
4. Explicitly acknowledge the source and mapping to approve operational readings. The service requires literal Boolean `true` and the current nonnegative integer revision. Approval reparses retained source bytes and rechecks live conflicts inside an immediate SQLite transaction. A stale or conflicting approval posts nothing.
5. Exact repeated source bytes reopen the latest retained attempt, including its prior decision. Differently formatted exports with identical normalized readings share one immutable reading and retain each approved source as evidence. Repeated rows inside one source are collapsed only when all normalized measurement fields, including quality, agree. Overlap, changed quality, changed quantities and conflicting units require reconciliation.

For a corrected export, inspect each conflicting active import. **Withdraw approved usage source** requires an explicit acknowledgement and a private reason. It withdraws that source's contribution to active evidence without deleting readings, prior previews, decisions or original bytes. A reading supported by another active duplicate source remains active; withdraw all conflicting sources before re-previewing and approving a correction. The conflicting file stays pending until resolved or explicitly rejected with a reason.

For a mapping-only mistake, use **Review this retained source again** after withdrawal or rejection. An explicit reason and acknowledgement create a new import attempt pointing to the same document bytes and the earlier attempt. Only one pending/active attempt per original source is allowed. The earlier decision is preserved. No artificial file editing or hash change is necessary.

Generic electricity deltas overlapping approved legacy XML evidence are blocked. The XML approval path reciprocally blocks active generic deltas. Legacy XML lacks a withdrawal workflow; keep its evidence and reject a conflicting generic file. Do not route water/gas XML through the electricity parser by relabeling it.

## Direct local XLSX subset

The original `.xlsx` ZIP bytes are atomically retained in the same hash-addressed
source store as PDFs, XML and CSV; the application never saves or rewrites that
workbook. `.xls`, `.xlsm`, encrypted Office files and arbitrary renamed archives
are unsupported. Direct generic XLSX intake is implemented and tested with
synthetic files. An authorized school installation still needs to establish
whether its My360 export is `.xlsx`, verify its real schema, units and time
meaning, and validate Cornwall-on-Hudson meter/building relationships. If the
actual export is `.xls`, that is an external compatibility gap.

Each approved workbook keeps its immutable mapping version, source SHA-256,
sheet, selected region, workbook date system and every mapped row/column/cell.
Field evidence includes the raw value, XML numeric lexeme or shared-string
reference, cell type, number format, normalized value and declared unit. Native
numeric values use their original XML decimal strings, avoiding float rounding
of meter quantities. The UI shows the first eight evidence rows; private
backups retain all rows. No workbook metadata enters developer diagnostics.

The reader accepts plain visible worksheets with literal values. The chosen
region has 2–30 unique header columns and 1–5,000 data rows. Empty data rows,
merged cells in the region, hidden rows/columns in the region, missing required
fields and multiple source meter identifiers in that region fail review.
Other regions remain in the original source and are explicitly excluded from
this operational import. Candidate header rows are inspection hints only;
they do not select a table or declare its meaning.

Text timestamps use the CSV ISO rules. Native Excel datetime cells must have an
explicit time-bearing format and whole-second precision; staff declares an IANA
timezone. Date-only formats, durations, times without dates, early invalid 1900
serials, ambiguous DST times and subsecond datetimes fail validation. The 1900
and 1904 workbook epochs are retained. Strings with explicit UTC offsets remain
the least ambiguous supported representation. Numeric columns with no date/time
semantics do not become timestamps automatically.

All workbook parts are inspected before the reader opens them. Formulas and
cached formula results, external relationships, connections/query tables,
macros/VBA/ActiveX, embedded objects, pivot content, hidden sheets and unsupported
binary parts are refused. No formula evaluation, macros, external refresh,
Excel/LibreOffice automation or network conversion is performed. Text cells with
formula-like prefixes are also rejected. A workbook containing one of these
features needs a provider-supplied supported values-only export; the application
does not strip features or silently substitute cached values.

The archive is limited to 8 MB compressed, 32 MB expanded, 200 members, 8 MB per
member and a bounded compression ratio. Duplicate/unsafe member names,
encryption, unsupported compression, dangerous XML DTD/entities, more than
650,000 XML nodes, more than 150,030 explicit cells, more than ten sheets and
cell positions beyond row 6,000 / column 50 fail validation. These are documented
format/resource limits, not a general-purpose spreadsheet sandbox.

## Reusable layout and meter relationships

Select **After approval, reuse this layout and confirmed source meter
relationship** when saving the preview. The approval’s immutable preview is the
saved version; its identity is the import ID and revision. No separate mutable
mapping file can overwrite that history. A compatible future file prepopulates
the approved fields and previously confirmed source-meter-to-local-meter
relationship. Staff still reviews each source, saves its preview and explicitly
approves operational readings. No financial approval follows from reuse.

A compatible layout has the same format, header labels and column order and,
for XLSX, the same sheet/header/column region. If a confirmed region ended at
the worksheet’s final populated row, future previews extend to the new final
row so longer exports are included. A fixed subregion is reused only when the
sheet row count is unchanged; changed shapes require region review. Unit,
timestamp and known meter conflicts prevent applying a saved suggestion.
A new identifier can reuse the layout but leaves the local meter blank for
explicit confirmation. Later compatible exports reuse that approved relationship
without monthly remapping. Separate building meters remain separate inventory
identities. Withdraw/reject and reattempt are still required to correct a
previously approved conflicting meter relationship.

Reuse is a suggestion based on the newest compatible approved opt-in version,
never a parser assertion of provider identity or complete coverage. Exact
repeated source bytes reopen their existing history. No saved layout alters
original source bytes, past approved values or building history.

## Reader dependency review — 2026-09-13

The selected reader is [openpyxl 3.1.5](https://pypi.org/project/openpyxl/3.1.5/)
(MIT/Expat), with [et-xmlfile 2.0.0](https://pypi.org/project/et-xmlfile/2.0.0/)
(MIT) as its pure-Python dependency. The wheels are approximately 250 kB and
18 kB. It needs neither a spreadsheet application nor a paid service. The
existing defusedxml dependency is retained because the maintainers warn that
openpyxl alone does not defend XML entity expansion. The application first
parses every XML member with DTD/entities/external references prohibited and
performs its own bounded archive and content checks.

The [reader API](https://openpyxl.readthedocs.io/en/3.1.2/api/openpyxl.reader.excel.html)
is invoked with `read_only=True`, `data_only=False`, `keep_links=False` and
`keep_vba=False`; the application rejects formulas before invoking it. Those
options alone are not the application’s safety boundary. The
[optimized-mode documentation](https://openpyxl.readthedocs.io/en/stable/optimized.html)
explains lazy worksheet loading and explicit workbook closing. Package metadata
(shared strings/styles) still consumes memory, so archive/node/cell limits apply
before parsing, and actual cell coordinates are checked instead of trusting a
workbook’s dimension declaration. The reader is closed on success and failure.

The [date/time documentation](https://openpyxl.readthedocs.io/en/stable/datetime.html)
explains numeric and ISO representations, missing timezone information, two
epochs and the 1900 calendar defect. UtilityOS retains those semantics and
rejects ambiguous subsets instead of interpreting display formatting as
measurement authority. xlrd targets the unsupported legacy format; pandas adds
a broad analysis stack while still requiring an Excel reader. A project-owned
OOXML implementation would duplicate shared-string/style/date semantics, so the
small reviewed reader plus fail-closed preflight is the selected approach.
Package versions and hashes belong in the portable platform receipts. Native
school/provider validation remains separate from generic synthetic acceptance.

## Integrity, backup and UI scope

The schema-6 baseline introduced immutable import attempts, mapping previews, decisions, withdrawals, readings and source-evidence links. JSON payload hashes bind to fixed audit codes; verification checks both journal-to-audit and audit-to-journal completeness, approved reading/evidence correspondence, source hashes, reattempt parent links and immutable triggers. Audit codes contain no source values, filenames, meter labels, units, quantities or private reasons. Full backups remain private and include source files and all usage history. Source download requires the existing authenticated session.

The UI shows the latest 200 import attempts, up to eight source rows, twenty preview readings and the latest 100 active readings. Displayed totals state the complete reading count; the bounded tables are not a complete export. Historic mapping previews are preserved in the database/backups, while the detail page shows the latest preview and original decision. There is no new public service or usage analytics aggregate. The optional foreground acquisition watcher routes CSV/XLSX sources through the same retained review workflow.

Schemas 1–6 require the ordinary explicit backup-first migration. Startup never migrates silently. See [installation and updates](STAFF_INSTALL_AND_UPDATES.md).

## Synthetic verification

`tests/test_spreadsheet.py` covers XLSX region selection, native/literal values, exact cell provenance, reusable building/meter relationships, unsafe content rejection, date semantics, original retention, API approval and backup restore. `tests/test_usage.py` covers explicit mapping and strict acknowledgement/revision, source bytes, single-meter scope, commodity/unit rejection, formulas, row caps, offset/DST handling, raw gas counters and cross-export counter discontinuities, concurrency/deduplication, partial overlaps, mapping changes, correction withdrawal and same-source reattempt, reciprocal XML conflict rejection, backup/restore and integrity tampering. It also verifies that a partial operational export overlapping the same water meter's monthly invoice leaves invoice amounts and quantities unchanged.

```sh
.venv/bin/python -m pytest -q tests/test_usage.py tests/test_spreadsheet.py
.venv/bin/python scripts/native_usage_smoke.py \
  --work-dir /tmp/sks-new-usage-check \
  --browser-executable '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
```

The native check requires a new external synthetic directory. It exercises real upload, mapping preview, approval, download, duplicate source handling, withdrawal, same-original reattempt, conflict reconciliation and logout at desktop/mobile viewports. It also imports XLSX on desktop, inspects a region, approves separate operational readings, downloads the exact original and reuses a saved layout/meter on mobile. Its success receipt is emitted only after owned browser/driver shutdown and a zero-exit demo server. Actual school exports, Windows timezone availability/native browser operation, meters and provider acceptance remain externally unverified.
