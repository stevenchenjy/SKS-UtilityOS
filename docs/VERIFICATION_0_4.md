# Development verification — 0.4.0

Date: 2026-09-06, development Mac (macOS arm64 / Darwin 25.6.0), Python 3.13.2,
Chrome 152.0.7977.82 and Playwright 1.57.0. All documents, credentials, source data,
workspaces and browser evidence used in these checks are synthetic and external.

## Baseline and implementation regression

Before behavior changed, the clean Git tree, immutable `v0.3.0` tag at
`e61facf6c07079add53be46bf6e2f319b085f6df` and all 83 source manifest entries matched.
The trusted archive hash is recorded in `INTAKE_DESIGN.md`. Its 144 tests passed
in development and a fresh offline installation. Native desktop/mobile imports,
manual PDF entry, XML mapping, approvals/rejections, lifecycle, exports, browser
backup/recovery, logout and a prior-schema migration all passed. No new baseline
issue was found; the two existing upstream test-client deprecations remain.

The 0.4.0 development suite passes **201 tests**, including the full prior suite.
Added coverage includes exact digital extraction/evidence, unavailable model,
parser deadline/failure isolation, unknown/retired/ambiguous templates and drift,
charge/quantity semantics, immutable extraction and review revisions, stale edits,
corrections, tamper detection, private diagnostics, stable folder reads/symlinks,
batch duplicate/recovery and multi-page scan continuation, cadence/history,
authenticated page previews, safe sample downloads and model preparation.
The deterministic generator recreates all 28 fixture PDFs and truth metadata
byte for byte with the pinned development toolchain.

Real subprocess termination additionally exercises extraction completed before
source/storage, extraction insertion before commit, and schema-3 → 4 migration
before switch. Retry preserves original sources and posts once. Existing actual
kill tests for approval, backup, restore and earlier migration boundaries remain.
No production fault hooks, simulated claim of hardware power loss or real bills
were introduced. Model-copy tests also verify failure leaves published bytes
unchanged; release tests check byte-identical fixed-timestamp rebuilds.

## Extraction benchmark actually run

`scripts/benchmark_extraction.py` checks source fixture hashes and compares exact
text/date values and Decimal numeric values. Results below are from a run with
**all network access denied** to the benchmark and child processes by a temporary
macOS sandbox-exec profile. This does not alter machine permissions or claim the
normal worker itself is an OS sandbox. All local methods still passed.

| Path | Documents | Exact scored fields | Missing | Incorrect | False extraction | Wrong units | Total seconds |
|---|---:|---:|---:|---:|---:|---:|---:|
| Known digital templates | 21 | 215 / 215 | 0 | 0 | 0 | 0 | 3.104 |
| Generic native text / unknown layout | 4 | 39 / 39 | 0 | 0 | 0 | 0 | 0.511 |
| Local English OCR | 3 | 30 / 30 | 0 | 0 | 0 | 0 | 2.490 |

The 284 scored nonmissing observations cover provider/reference/account/meter,
invoice and period dates, usage/unit, demand/delivery quantity and current total.
Unsupported-unit and renamed/missing-label cases intentionally abstain; they are
not counted as successful fabricated values. False extraction checks fields
whose truth is absent. Detailed by-field/outcome JSON stays with external evidence.
Timings are single-run development observations, not guaranteed throughput.

The corpus includes water, gas, oil, propane, supply-only, demand, estimated,
credit/correction/rebill, unusual period, multiple pages/meters, missing total,
rotated/low-quality scans, two layouts and three drift variants. Its labels and
truth data are authored independently from the template registry. It is a small
known fictional corpus, not a held-out real-world accuracy estimate. No actual
utility layout, handwriting, language other than English or general table parser
has been validated. Docling/Granite were evaluated but not run for inference.

An initial rotation heuristic selected gibberish and scored only 20/30 OCR fields;
using recognizable fixed labels/provider anchors fixed it. Native testing found
a late preview callback after navigation and unsaved supplementary values reset
by line-list rendering; both were fixed and their affected workflow rerun. No
machine-generated candidate can auto-approve an invoice.

## Native browser verification

The Browser plugin was unavailable, so the existing Playwright dependency used
isolated native Chrome with real loopback HTTP/cookies/downloads. No private
browser session, transport bridge, mocked application API, remote tunnel or
weakened administration setting was used.

The existing extended native regression passed CSV, legacy manual PDF, XML,
review/approval/rejection, correction/rebill/cancellation, mapping, downloads,
exports, backup and logout on desktop/mobile. New headed intake checks passed
picker and batch success/duplicate/failure, drag/drop, v2/drift, rotated OCR,
source-region selection, original-byte download, supplementary edits retained
through line changes, saved approval, closed-version evidence, correction history,
folder configuration/scan, delivered-fuel approval, cadence/missing view, quality
export, private backup and restored source evidence on mobile. There were **zero
unexpected console/runtime errors**. Desktop 1440×1000 and mobile 390×844 showed
no page-wide overflow. Source highlight and mobile OCR screenshots were inspected.

## Actual 0.3 migration and rollback

Actual trusted 0.3 code generated a new 20-building/60-service-point campus with
1,923 active invoices and retained history, plus a saved legacy PDF draft. The
current migration preserved documents, staged records, saved draft history,
bills, bill lines and original source hashes exactly. Active CSV exports were
byte-identical. The old code refused schema 4 without changing the database
bytes. Its pre-upgrade backup restored into a new workspace with the old release;
checks and native browser flows passed after both upgrade and rollback. Frozen
schemas 1, 2 and 3 plus simulated future paths are covered separately by tests.

## Dependencies and release checks

`pip check` passes. pip-audit 2.10.1 against the development runtime, installer,
development packages and optional OCR found **no known Python-package
vulnerabilities**, with no ignored IDs. This does not audit every native engine
or OS library. `DOCUMENT_EXTRACTION_DEPENDENCIES.md` records the current wrapper's
older bundled Tesseract, upstream model-deserialization fixes, pinned trusted
model restriction, system zlib linkage and OS patch responsibility. The initial
probe environment's older pip was upgraded before final checks. No AGPL parser,
cloud inference or automatic model download was added.

A separately unpacked source archive received a fresh `.venv` through the
wheel-only `--no-index` setup. Hashes of the selected existing synthetic
workspace, including its database, sources and backups, stayed unchanged during
installation. Base source plus environment occupied **75,173,101 bytes**, excluding
the shared Python interpreter; the full development/OCR environment occupied
243,873,460 bytes before final documentation-only edits. Optional model assets
are measured separately. The base install had no tesserocr: a native mobile
scan download, manual completion, approval and logout passed there.

Optional OCR wheels were then installed offline and the real reviewed English
model copied/verified using `prepare_ocr.py`. **All 201 tests passed** both in
development (25.17 s) and in the independently installed environment (25.16 s).
There are still only the two upstream deprecation warnings. `pip check` and a
separate installed-environment pip-audit scan passed, with no known Python-package
advisories and no ignored IDs. Final reviewed source is checked against the
installed copy after packaging; runtime/model files remain outside the manifest.

The installed package passed the complete original native import/lifecycle/export/
backup workflow, browser-generated backup recovery, damaged-draft recovery,
1,923-invoice campus paging/search, synthetic staff passphrase confirmation, and
the new evidence/batch/folder/OCR/cadence workflow. The final intake rerun also
checked corrected supplementary-field labels and restored evidence. All had zero
unexpected console/runtime errors. The duplicate-source and missing staff
passphrase responses are deliberate negative checks. The campus navigation
maximum in this run was 0.112 s; it is not a deployment performance guarantee.

The installed benchmark ran again with network access denied and reproduced
215/215 template, 39/39 native-text and 30/30 OCR exact fields, with no false,
missing, incorrect or wrongly normalized unit values. Path times were 2.808 s,
0.526 s and 2.157 s respectively. Reviewed raster samples included layout v2, the
second meter page, and the low-quality scan; fictional markings and text were
visible without overlapping or clipped content.

Source packaging uses fixed epoch `1788652800` with deterministic ZIP metadata.
The final release contains **135 manifested source files**, plus its manifest.
Two independent builds are compared byte for byte, indexed/tagged blobs are
verified against the manifest, and normal Git-archive membership is verified.
The local annotated `v0.4.0` release is created only after these checks. The
immutable `v0.3.0` commit and archive are retained. No remote was contacted or
pushed; no non-development artifact or private runtime data is packaged.

## Continuing limits

The release is unsigned, single-operator and tested on this development Mac.
Native Windows/ACLs, Finder quarantine, signed distribution, school workstation,
real utility layouts/records, language/table generalization, role-separated
approval, backup encryption and authoritative coverage are not validated.
Expected cadence is explicitly configured and labelled experimental. School IT
and authorized Finance/Facilities staff retain their installation, retention,
security and private accounting acceptance decisions. Nothing was publicly
published or connected to school portals or data services.

The historical 0.3.0 verification follows for continuity; it describes that
release, not the current dependency/schema choices.

## Development verification — 0.3.0

Date: 2026-09-06. macOS arm64 (Darwin 25.6.0), Python 3.13.2,
native Chrome 152.0.7977.82, Playwright 1.57.0. Every workspace, source, credential
and screenshot used here was synthetic and created outside the repository.

### Baseline before changes

The original 0.2.0 working source matched all 66 entries in the verified archive.
Its full suite passed **100 tests** in both the existing environment and a fresh
wheelhouse installation. Native headed Chrome repeated login/logout, CSV,
PDF-assisted entry, XML, approval/rejection, corrections/rebills/cancellation,
exports, backup and desktop/mobile navigation. Browser-generated backup recovery,
stopped-app schema-1 → 2 migration and release integrity passed.

Before modifying application code, real child-process interruption probes
reproduced truncated final source files during import and overwritten sources
during restore. A corrupted review payload also broke the whole review list.
Those observations were recorded in Git before the fixes. Ordinary 0.2.0 paths
passed; roadmap wording was not treated as evidence of a missing implementation.

### Regression and failure recovery

The final suite passed **144 tests** in both the development environment and the
independently installed source package. Execution evidence remains external. Two upstream deprecation
warnings remain: Starlette's httpx test client and AnyIO's BlockingPortal alias.
They do not fail the suite. `pip check` reports no conflicts. The existing pinned
environment's pip-audit 2.10.1 scan on this date found **no known vulnerabilities**
and ignored no advisory IDs. No dependency was added for 0.3.0.

Tests retain the previous accounting, lifecycle, imports, security and release
coverage, and add these recovery checks:

| Scenario actually executed | Verified result |
|---|---|
| Kill during partial source write or after source publication | No partial document/invoice rows; retry succeeds or explicitly identifies an already committed source |
| Kill within approval transaction | Original financial state and pending review remain; retry posts once |
| Kill after approval commit before caller response | Approved state remains; retry cannot duplicate it |
| Kill within migration transaction or before database switch | Original bytes/schema remain usable; backup exists; explicit retry succeeds |
| Kill restore during source publication or before database switch | Current financial rows and original source hashes remain valid; retry restores the selected snapshot |
| Kill incomplete backup / simulate full-disk write failure | No unfinished backup is published; failed import creates no financial rows |
| Corrupt JSON, wrong payload structure or changed saved revision | Other reviews remain accessible; approval is blocked; acknowledged recovery stays pending |
| No readable draft history | Bounded recovery failure, with source retention and rejection still available |
| Changed cached XML readings | Approval refuses data that does not match its retained original |
| Tampered audit / update-delete attempt | Append rules reject mutation; startup/check/backup detect invalid history |
| Restore audit boundary | Boundary hash matches the exact head actually retained in the safety backup |
| Future synthetic upgrade from each supported schema | Registered steps commit together; failed step rolls back; unknown path creates no replacement |
| Old pending draft beyond 500 closed imports | Pending review stays visible; closed history stays bounded |

The interruption tests terminate separate Python processes executing production
storage/ledger/maintenance operations at test-controlled checkpoints. They do
not add runtime fault hooks or claim physical power-loss/drive-failure testing.
Fixed error/diagnostic schemas are tested with synthetic path, filename, account,
amount, configuration, environment and credential sentinels.

### Native browser outcomes

The Browser plugin was unavailable; the existing Playwright dependency controlled
isolated native Chrome profiles through real loopback HTTP. No transport bridge,
mocked API, private browser session, remote tunnel or device-policy change was used.
The full workflow and readiness checks passed in the workspace and independently
installed source package, with **zero unexpected console/runtime errors**.

| Flow | Evidence |
|---|---|
| Application launch and sessions | Native macOS demo/staff launch, first-time synthetic staff passphrase setup; local login, HttpOnly/SameSite cookie, logout/revocation |
| CSV / PDF-assisted / XML | Uploads, original/sample downloads, retained bytes, manual PDF values, validation, mapping, approval and rejection |
| Invoice lifecycle | Correction, new-source supplier rebill, same reference, independent negative credit, mobile rejection/cancellation and mapping history |
| Damaged bill draft | Isolated recovery screen, acknowledged recovery of saved values, fresh review acknowledgement and approval |
| Staff sensitive operations | Missing passphrase blocks replacement approval; correct passphrase approves; mobile cancellation confirms passphrase; actor context appears in audit |
| Audit | Current/older event pages, private review links, bounded fields and truthful shared-operator attribution |
| Large ledger | 100-row paging, lookup of an old invoice, all 24 months, current totals and complete CSV export |
| Responsive behavior | 1440×1000 and 390×844; six screens, dialogs, input controls and downloads; no page-wide horizontal overflow |
| Restore | Native browser recovery of a browser-generated backup, matching ledger/source integrity and fresh login |

The expected negative HTTP responses are the explicit duplicate-source rejection
and missing staff passphrase in their respective tests. Screenshots of recovered
entry, source provenance, mobile passphrase confirmation, audit history and campus
overview were inspected. Screenshots/downloads remain outside Git.

### Larger campus and version switching

The deterministic fixture includes **20 buildings, 60 service points, 80 accounts,
six synthetic vendors, 24 service months, 1,923 active invoices, 1,927 retained
versions and 288 interval readings**. It uses electricity, water, gas, oil and
propane, separate supply charges, seasonal profiles, three corrections, a supplier
rebill, three credits and two deliberate anomalies. Generated monthly charges
reconcile independently with the active export; supply quantities stay zero and
fuel quantities stay purchases. Fixture generation on this Mac took about 2.7 s.
The dedicated campus browser run observed navigation below 0.2 s; this is a dated
small-campus development measurement, not a deployment throughput guarantee.

The fixture was also created using the **actual retained 0.2.0 code**, then
migrated with 0.3.0. Source hashes and the full active CSV export matched byte for
byte across the upgrade. Old code rejected schema 3 without changing its bytes.
The pre-upgrade backup was restored with 0.2.0 into a new workspace; integrity
and native browser checks passed. Automated tests separately cover frozen schema
1 and schema 2 and simulated future transitions beyond schema 3.

### Installation, Git and release integrity

Fresh macOS virtual environments were installed from reviewed local wheels with
`--no-index` and wheel-only setup. Installing code left the selected existing
synthetic workspace's database, sources and backups byte-identical. Source-only
archives were unpacked independently; regression, native import/recovery,
large-campus and synthetic staff checks passed there.

The existing Git initial commit is retained. An object-level release review found
four CSV blobs normalized by the old Git attribute. Baseline commit `38d20e6`
preserves exact archive bytes and executable modes and disables checkout
normalization. All 66 baseline manifest entries now match the `v0.2.0` Git objects.
The local `v0.3.0` release includes only code, tests, technical documentation and
synthetic fixtures. Its complete source manifest, indexed blobs and source-only
membership are checked. Standard Git ZIP directory entries are accepted only
when they contain listed source files; unexpected files/directories remain rejected. No remote was created, contacted or pushed.

### Remaining limits

Named users/role enforcement are explicitly deferred with a proposed exact matrix
in `ACCESS_AND_CONFIGURATION.md`. Audit actor contexts do not identify people;
an OS owner can rewrite the full database/code and replace the chain. Private
backup encryption, hardware power-loss behavior, native Windows/ACLs, other
browsers, Finder quarantine/Gatekeeper treatment, signing/trusted distribution,
the actual school workstation, maintenance/retention ownership and private-data
accounting acceptance remain outside the tested boundary. Signing research is
documented; no credentials, signing service, payment or production deployment
was configured. No portals, school records, paid APIs or cloud extraction were used.

### Reproduction

Use `README.md` for the full suite and extended native import test. Run
`scripts/native_readiness_smoke.py` with a **new external** work directory for
its self-created recovery, campus and synthetic-staff cases. Run
`scripts/synthetic_campus.py` only with a new demo directory. See `OPERATIONS.md`
for exact retry, provenance, diagnostic and audit semantics and
`STAFF_INSTALL_AND_UPDATES.md` for stopped-app upgrade and rollback.
