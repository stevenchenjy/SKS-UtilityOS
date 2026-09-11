# Development verification — 0.6.0-rc2

## Provider-informed file slice — 2026-09-10

Execution started from clean commit `f61656d6d406fcf62e8cf7712297d81c289198de`,
version 0.6.0-rc1/schema 5. This candidate is **0.6.0-rc2/schema 6**, unsigned,
untagged and unpublished. The trusted `v0.5.0` commit remains
`0d515181714e8f1f090156e43c957735e26976b7`. Existing tags and historical receipts
are preserved. This completes the bounded provider-informed development slice;
it does not complete the planned 0.6 analytics milestone or authorize school use.

### Delivered scope

- **Approval controls:** every financial approval requires literal Boolean
  acknowledgement at the authoritative service boundary. HTTP approval requires
  an explicit nonnegative integer revision. Missing, null, Boolean, string,
  negative and stale revision requests fail without changing saved review or
  financial state. Existing correction, warning, reconciliation and passphrase
  controls remain in force. Native approval checks observe the submitted revision
  and acknowledgement.
- **Rehearsal completion:** each browser checkpoint owns a short-lived driver.
  The supervisor publishes success only after completed checks, runner exit zero,
  shutdown confirmation and, on POSIX, no remaining owned process-group members.
  Timeout/nonzero-exit tests retain unsuccessful status.
- **Account schedules:** every-two-month anchors, issue day, inclusive grace and
  effective dates, skip/reschedule exceptions, immutable review versions and
  account-level statement counting. Existing monthly/delivery/irregular choices
  remain. Quiet/unconfigured periods establish neither missing bills nor zero
  usage. Manual retrieval intent, expected invoices and measurement sampling
  remain distinct. See [billing schedules](BILLING_SCHEDULES.md).
- **Mapped operational CSV:** retained originals, transparent revisioned mapping,
  source units, meter identity, UTC boundaries/timezone assumptions, delta/raw
  counter semantics and quality. Explicit approval, deduplication, conflicting
  source withdrawal and same-original reattempt preserve all prior evidence.
  Operational imports do not change invoice charges or quantities. See
  [mapped usage](MAPPED_USAGE.md).
- **Provider semantics:** seven original fictional PDFs, deterministic generation,
  Provider Studio validation and twelve tests cover balances versus current
  charges, water-only/combined statements, supplier-only charges, kW versus kWh,
  gas ambiguity, shared meters and variable service periods. Public source
  evidence and its unknowns are recorded in
  [provider file workflows](PROVIDER_FILE_WORKFLOWS.md).

### Regression, native workflows and extraction

The working-tree full suite passed **414 tests in 73.38 seconds**, with two
existing Starlette/httpx and AnyIO test-client deprecation warnings. The starting
baseline passed 286 tests. After the packaging-test correction described below,
a new source archive was extracted and installed with a fresh environment through
the actual setup script. Its full suite passed **414 tests in 70.31 seconds**,
with the same two warnings and command exit **0**; `pip check` passed too.

Native Chrome **152.0.7977.83** on macOS arm64/Python 3.13.2 used fresh external
synthetic workspaces, real loopback HTTP/cookies/downloads, desktop 1440×1000 and
mobile 390×844. The Browser plugin was unavailable; the existing Python Playwright
development dependency was used with isolated contexts. No staff browser profile
or transport bridge was used. Successful checks covered:

- Core CSV/PDF/XML intake, saved review/approval, source downloads, duplicate
  refusal, correction/rebill/credit/cancellation, inventory, ledger/support
  downloads, backup and logout.
- Provider Studio source selection, independent two-source validation, explicit
  activation, future pending drafts, layout drift/retirement, exact support
  preview/download and restored provider history.
- Batch isolation, picker/drop, rotated local OCR/evidence, stable-folder explicit
  scan, delivered fuel, account completeness and restored source evidence.
- New schedules on desktop/mobile, issue/grace dates, quiet months, mobile
  exception saves, unchanged charges, logout and backup/restore.
- New mapped usage upload/preview/approval, exact source download, duplicate
  evidence, withdrawal, same-byte reattempt, correction reconciliation, unchanged
  invoice totals and logout. Its receipt also confirms driver shutdown and
  demo-server exit zero.
- Backup recovery, a 1,923-active-invoice fictional campus, and synthetic staff
  confirmation. This is local development evidence, not a school installation.

Final native runs reported **zero unexpected console/runtime errors**. Deliberate
duplicate and staff reauthentication refusals were expected. Desktop/mobile
screenshots were visually inspected. The 28-document synthetic extraction
benchmark matched **284/284 fields**: 215 template, 39 generic digital and 30 OCR,
with zero missing/incorrect fields, false extractions or incorrect units. The
seven new provider PDFs were separately rendered and inspected. These are bounded
fixture results, not real-provider accuracy estimates.

### Fresh installation, migration and rollback

Old `v0.5.0` and the candidate were extracted into separate external code folders
and each installed using its actual `scripts/setup.sh` with a target-specific
offline wheelhouse. No virtual environment was copied. Runtime/development/OCR
dependency pins are unchanged; no new dependency was introduced. `pip check`
passed. September 10 checks of PyPI release advisory metadata covered all
**37 installed packages**, with no reported advisories and no skipped packages.
This was a direct PyPI metadata check, not a new pip-audit run, and does not audit
all bundled native libraries or the operating system. The optional English OCR
model and license were explicitly staged and hash-verified outside the source;
there is no runtime model download.

The complete native `v0.5.0` → rc2 rehearsal **exited 0**. Its final receipt says
`status: passed`, `runner_exit_code: 0`, `all_rehearsal_servers_stopped: true` and
`all_browser_checkpoints_closed: true`. It exercised incompatible-start refusal,
backup, explicit schema **5 → 6** migration, preserved 20 prior non-audit tables
and four source originals, and matched pre/post-switch ledger and PDF downloads.
The old release separately restored the original backup into a different
rollback directory and passed the same browser checks. The upgraded data was
retained. No private workspace was migrated.

The rehearsal archive was retained as a snapshot. Later corrections were limited
to current documentation and the package test's assumption about Git metadata;
application files, fixtures, dependency pins and native verification scripts
remained byte-identical. The final package is compared to the independently
tested source and recorded separately with its hash; only this verification
report differs from that source snapshot. Two fixed-timestamp builds contain
**204 verified source files** and are byte-identical. The refreshed local release
manifest matches the final source. The package contains source and synthetic
fixtures only, with no environments, databases, logs, wheels or models.

### Failures retained and limitations

An initial account-schedule native check raced a pending save; the form now
disables submission/filtering while saving and the harness waits for the saved
state. A later harness check treated its deliberately unauthorized post-logout
fetch as an unexpected console failure; that assertion now uses the native
request context. Subsequent schedule runs passed. Neither failed run was
rewritten as successful.

The first independent full source-installation suite reported **413 passed and
one failed** in 74.16 seconds: its new packaging test assumed a `.git` directory,
which a source-only release correctly excludes. The test now checks the shipped
ignore rules in an isolated temporary repository and keeps exact archive-byte
assertions. Its focused tests passed both in the checkout and a Git-free archive.
The subsequent independent full run is the acceptance result. Historical rc1
rehearsals below that required cleanup and exited nonzero remain unsuccessful.

Combined municipal water/sewer/garbage statements remain unposted until a reviewed
accounting extension supports every charge and full reconciliation. This slice
does not certify provider exports, directly parse Excel, turn raw counters into
consumption, model physical counter resets, reconstruct historic schedule versions
automatically, or provide operational usage analytics. The explicit folder scan
remains; automatic polling was evaluated and deferred. Portal/email/API/EPA
connections remain disabled. Actual school meters/exports, provider eligibility
and fees, native Windows behavior, downloaded-app signing/Gatekeeper acceptance
and school installation remain externally unverified.

---

# Development verification — 0.6.0-rc1

## Local candidate acceptance — 2026-09-08

This is an unsigned, untagged, unpublished local candidate. The trusted tagged
baseline remains `v0.5.0` (`0d515181714e8f1f090156e43c957735e26976b7`).
Existing building-reporting changes below are included and preserved. Schema
remains 5 and dependency pins are unchanged. This is not completion of the full
planned 0.6 analytics milestone or permission to install on a school machine.

### Independent installation and regression

The source candidate was extracted into a separate external directory and given
a fresh virtual environment using the actual setup script and a target-specific
offline wheelhouse. Both retained old releases were separately installed too;
no virtual environment was copied. The candidate's final full suite passed
**286 tests in 195.97 seconds**, with two existing test-client deprecation
warnings. `pip check` passed. An isolated `pip-audit 2.10.1` scan on September 8
checked all 37 installed runtime, development and optional OCR packages: **zero
known advisories and zero skipped packages**. This does not audit every bundled
native library or the operating system. No runtime dependency was introduced.

Native Chrome 152.0.7977.82 checks used fresh external synthetic workspaces,
desktop 1440×1000 and mobile 390×844, isolated contexts and actual loopback
HTTP, cookies and downloads. The Browser plugin was unavailable; the existing
Python Playwright development dependency was used. No staff browser profile,
transport bridge or mocked application data was used. Passed workflows:

- Core imports, review, CSV/PDF/XML originals, duplicate rejection, correction,
  rebill, credit, cancellation, mapping, ledger/support exports, backup and logout.
- Provider setup, two-source validation, explicit activation, future pending
  candidates, layout drift, retirement, exact support preview/download and restore.
- Intake batches, saved revisions, drag/drop, OCR rotation/evidence on mobile,
  explicit folder scan, delivered fuel, cadence and restored original evidence.
- Recovery, a 1,923-active-invoice synthetic campus, and synthetic staff-mode
  confirmation. These are fictional records, not a school staff installation.

There were zero unexpected browser/runtime failures. Intentional duplicate and
passphrase refusals were expected. The 28-document synthetic benchmark matched
284/284 expected fields: 215 template, 39 generic digital and 30 OCR, with no
incorrect/missing fields, false extractions or incorrect units. These fixtures
do not establish real-supplier accuracy or target-machine performance.

### Findings fixed during acceptance

Candidate versions originally failed the provider support schema. A strictly
bounded `-rcN` suffix is now accepted without permitting free-form labels.
Schema-4 diagnostics now correctly offer explicit migration to schema 5.

Native intake uncovered an actual preview/extraction contention bug: a preview
holding the sole worker for over one second could leave the next PDF as an
empty draft. One extraction may now wait within the existing total deadline;
excess queue capacity returns a retryable import failure without retaining an
empty document. Three regression tests cover waiting, the total time budget,
capacity refusal, absence of retained files and a successful same-file retry.
The complete suite and native intake were rerun after this correction.

The new rehearsal initially used an exact accessible name for a navigation
button containing a pending count; its locator was corrected. PDF evidence
checks now wait for actual local rendering before recording screenshots.
Initial dependency-file loading on this development computer was unusually
slow. Public installed software files were warmed in the filesystem cache;
no product deadline or test assertion was relaxed to accommodate that behavior.
Cold school-machine launch and install acceptance remain outstanding.

### Stopped-app update and rollback evidence

The final application code completed both native rehearsals:

| Old release | Schema route | Result |
|---|---|---|
| 0.5.0 | 5 → 5, no migration | 20 existing non-audit tables and four originals retained |
| 0.4.0 | 4 → 5, explicit migration | 19 existing non-audit tables and four originals retained |

Each rehearsal first verified a separate fresh candidate demo, created its own
old demo, refused maintenance while it was running, stopped only its own old
process, checked and backed it up with the old release, and checked compatibility.
The schema-4 route first verified refusal without changing database bytes, then
ran `migrate --confirm-migrate`. Both routes verified the switched ledger and
original downloads, desktop/mobile behavior and logout. They restored the old
backup with the old release into a separate rollback directory and repeated the
checks. Stable settings, pre-existing non-audit rows and original hashes matched;
audit correctness was checked separately because backup/migration advances it.

Ledger CSV SHA-256 before switch, after switch and after rollback:
`97e110700830296f1589973b70303d04aaa55ef0655b4ff005d0afb9baf8f83f`.
Original PDF SHA-256 at all three checkpoints:
`f93816bec9019355cf411d1bc4471ebde862a3923cf837de3fdf07e17ade53cd`.
Both reports confirm all rehearsal application processes were stopped.

The two final rehearsal **application checks passed**, but their CLI runners
did not exit cleanly: Playwright's auxiliary driver remained idle during browser
shutdown after the reports had been written. Only those two owned test drivers
were terminated, after which each runner exited 1. No application server or
data check was interrupted. This is a remaining test-harness shutdown limitation
on this Mac, not an unqualified unattended rehearsal pass. The retained receipt
records the CLI failure separately from the completed data/browser checks;
native intake and the other native runners exited successfully.

Final source packaging is reproducible at a fixed source timestamp, excludes
private workspaces and dependencies, and is verified against its manifest.
The final package receipt, old source archives, synthetic backups, test logs,
native screenshots and rehearsal reports are retained outside the repository
under `~/Library/Application Support/SKS-UtilityOS-Development-Releases/`.
Hash integrity does not provide trusted signing or distribution provenance.

Native Windows execution/ACLs, Finder quarantine/Gatekeeper acceptance, signing,
real supplier adapters, portal/API authorization, unattended acquisition,
shared-server identity/concurrency and school deployment remain unverified.
No existing user-run application, private workspace or external utility portal
was opened or stopped. Earlier verification sections below are historical.

---

## Working-tree building reporting review — 2026-09-08 (unreleased)

This focused review adds building reporting to the existing local pilot; it is
not a tagged release or a new school-deployment acceptance. The 0.5.0 release
verification below is historical. Schema, dependencies and approval semantics
remain unchanged. Existing unrelated edits in `MASTER_PROMPT.md` were preserved.

### Findings and disposition

- Overview had only a month filter and static building totals. Building IDs now
  scope charges, quantities, trends, service points and invoice drill-down.
  Split-invoice matching charges are distinct from full invoice totals.
- The chart highlighted the latest month regardless of the selected report and
  omitted years. It now ends at the selection, labels years, retains negative
  credits, and exposes an exact monthly values table. Cards show exact cents.
- An empty selected month could silently fall back to a different period. Valid
  requested months now remain selected; missing bills do not imply zero use.
- Inventory labels were grouped as text, allowing a physical building named
  "Unassigned / shared" to merge with the special bucket. ID-based grouping
  separates them. Shared meters remain unallocated.
- Invoice detail always returned to Review queue. Ledger-origin details now
  return to the filtered ledger; inventory labels link to building data.
- Native interaction testing caught ambiguous accessible names on the new
  selectors. Explicit Building/Invoice month names now support label-based
  interactions. Browser report filters reset on lock or full page reload.

### Checks and current workflow assessment

The full working-tree suite passes **266 tests** (110.21 s), including 18 new
building tests. A targeted 52-test run also covered ledger corrections and the
1,923-active-invoice campus. Tests reconcile scoped charges with the campus total,
retain exact decimal quantities, distinguish supplier credits and fuel purchases,
exercise empty/invalid scopes and months, authenticate the HTTP filters, and
verify cancellation, replacement and current-mapping behavior.

The first 248-test invocation encountered four failures in PDF extraction, PDF
preview and two provider-worker startup checkpoints while installed dependency
files were loading unusually slowly. All four passed in the complete repeat with
`PYTHONPYCACHEPREFIX=/tmp/sks-python-cache`; no product timeout, extraction rule or
assertion was weakened. Two pre-existing test-client deprecation warnings remain.
This identifies a local test/startup reliability observation, not a proven
application fix or a freshly verified cold-install experience.

The existing native Chrome core smoke passed on a fresh external synthetic demo
at `http://127.0.0.1:8878`, desktop 1440×1000 and mobile 390×844, with imports and
`--milestone`. CSV/PDF/XML, source/sample downloads, review, duplicate rejection,
saved drafts, corrections/rebills, cancellation, mapping changes, support/ledger
exports, browser backup download and logout passed. It reported zero unexpected
console/runtime errors; the duplicate-source 422 was expected.

The additional building flow passed against the unchanged synthetic demo at
`http://127.0.0.1:8765` on both viewports: table-to-building selection, exact
$2,780.16 August total for Demo Academic, per-point quantities, the exact-values
table, June selection/highlight without future months, scoped invoice columns,
search and filter retention after opening a source, original CSV download byte
comparison, inventory-to-building navigation, unassigned/empty results, explicit
January 2000 preservation while changing buildings, clear filters and lock/relogin
reset. There were **zero console/runtime errors and zero HTTP failures**. Rendered
desktop, mobile, empty and invoice screenshots were inspected with no page
overflow. Evidence is retained outside source at `/tmp/sks-building-evidence` and
`/tmp/sks-building-core-evidence`; the focused browser script is
`/tmp/sks-building-visual.py`. No new browser test dependency was introduced.

Browser plugin was not available. Native verification used the existing Python
Playwright dependency, installed Chrome 152.0.7977.82, isolated browser contexts
and real loopback HTTP/cookies/downloads. No staff browser profile, transport
bridge or mocked application API was used. Installed Playwright JavaScript files
were read into the local filesystem cache to complete the unusually slow first
driver launch. Test code and screenshots remain outside the repository.

The current operator workflow is coherent for a single local ledger: import in
Utility Inbox, review evidence and approve, inspect a building/month, open its
invoices, and make an explicit correction when needed. Utility inventory handles
confirmed mapping changes; Bill completeness requires separately configured
expectations. Provider setup is an optional extraction aid and does not bypass
review. Interval data remains a separate historical meter-reading view.

Remaining acceptance boundaries: no calendarized building usage, floor-area or
weather normalization, inferred shared-meter allocation, authoritative campus
coverage, real-provider validation or live data. Native Windows, cold installation,
new release packaging/signing, fresh dependency advisory review and school
deployment were not rerun for this scoped reporting change.

---

Verified on 2026-09-07 with synthetic records on macOS 26.6.2 arm64,
Python 3.13.2 and native Google Chrome 152.0.7977.82. This is development release
acceptance, not school deployment, real-provider validation or a security audit.
Prior reports are preserved verbatim in [VERIFICATION_0_4.md](VERIFICATION_0_4.md).

## Trusted baseline and scope

The clean starting release was `57a293b2c33f1bbd667c995f3885b2ec9778b0ee`.
The annotated `v0.4.0` object was verified locally and on the expected
`stevenchenjy/SKS-UtilityOS` origin. Only that previously absent tag was pushed,
without force, under the explicit user instruction. Its 135 source manifest
entries matched the trusted Git blobs; the original manifest and reproducible
ZIP remain preserved. Exact baseline/tag/archive details are in
[PROVIDER_STUDIO_PLAN.md](PROVIDER_STUDIO_PLAN.md).

The baseline passed 201 tests before application edits. Its native intake,
source, correction, OCR, export, backup/recovery and logout paths also passed.
The existing Python/FastAPI/SQLite and browser-module structure was retained.
No non-development artifact, school record, portal credential or external
extraction service was used.

## Regression and independent onboarding corpus

The complete 0.5 suite passes **248 tests**, preserving all prior tests. The
working checkout run took 50.43 seconds; the separately installed candidate
passed the same 248 tests in 51.71 seconds. These timings are observations on
this computer, not service guarantees. Two existing test-client deprecation
warnings remain (httpx and the AnyIO BlockingPortal alias).

The new `samples/onboarding` corpus contains **18 independently generated
fictional PDFs**. `scripts/synthetic_onboarding.py` does not import application
rule definitions. Expected values are separate from the operator-created rules.
API helpers create providers, map observations, save drafts, approve sources,
validate and change state through authenticated application routes; no provider
or layout is injected directly into a fixture database.

| Case or failure | Verified behavior |
|---|---|
| Unknown provider; two bills in one layout | Private setup; immutable draft; exact selected-source comparison; explicit activation only after two distinct approved sources |
| Single service without a section marker | Explicit single-service mode locates fields without requiring artificial numbering |
| Page-two services and two meters | Correct page/section scope and independent service values |
| Changed layout; relocated account; renamed usage | Known-provider drift/manual path; separately validated new version; previous version retained and retired |
| Repeated labels or overlapping active layouts | Ambiguity abstains instead of choosing an account or amount arbitrarily |
| Optional missing field; incorrect operator rule | Exact absence is distinguished from missing/corrected extraction; required failures block activation |
| Scan with and without optional OCR | Local observations with the reviewed model; retained source and manual approval when OCR is unavailable |
| Supply-only and delivered fuel | Charges do not duplicate consumption; fuel quantity remains purchased volume |
| Unit conflict and inclusive printed end | Unit failure is explicit; configured inclusive end becomes the next exclusive day with original evidence retained |
| Stale validation, state, draft version or changed approved target | Request fails; revalidation/reload required; no overwritten decision |
| Repeated approved corrections | Scoped counts flag investigation; rules and original extraction stay immutable |
| Registry change during extraction | Safe retry before document staging; no stale parser decision is published |
| Process killed inside layout save or activation | Journal and audit transaction roll back together; explicit retry succeeds |
| Corrupt JSON/hash/state, missing record or removed journal guard | Registry quarantined; manual entry/approval remain usable; maintenance rejects damaged templates |
| Private backup/restore and a populated future migration probe | Every journal row and extraction binding preserved; unregistered or incompatible paths fail closed |
| Support/privacy sentinels and source packaging | Exact positive-schema support excludes private values; source archives contain no runtime definitions, databases, backups or model weights |

The future migration probe registers a test-only schema-5 → 6 step. It proves
journal preservation in the migration framework; schema 6 is not released.
Hashes detect corruption and ordinary changes, not a privileged owner rewriting
all data, audit bindings and code together.

## Native browser outcomes

Native Chrome used isolated temporary profiles and real loopback HTTP with
actual cookies, CSP, source responses and downloads. The Browser plugin was not
available; tests used the existing Playwright development dependency and the
installed Chrome executable. No transport bridge, staff profile, mocked API
payload, portal or remote-debug tunnel was used.

The fresh installation's provider workflow passed entirely through the UI:
source candidate selection, provider creation, 13 field rules, preview/save,
two ordinary approved reviews, selected validation, explicit activation,
future pending candidates, desktop/mobile source evidence, layout replacement,
retirement and a third single-service version. The support download matched the
preview byte for byte. Browser-created private backup restoration retained all
three layout versions and states; the restored mobile management view passed.
Desktop was 1440×1000 and mobile review was 390×844. There were **zero unexpected
console/runtime errors and zero HTTP failures** in this provider run.

The installed core workflow also passed CSV, manual/PDF-assisted entry, Green
Button XML mapping/approval, rejection, duplicate protection, saved review,
correction/rebill history, cancellation, mapping changes, source/sample downloads,
ledger/diagnostic exports, browser backup download and logout. Mobile navigation
and financial views had no page overflow. The intentional duplicate-source 422
was the sole expected HTTP rejection; no unexpected console/runtime error occurred.

The existing intake and readiness scripts separately exercise batch/drop/folder
imports, digital/OCR/drift evidence, supplementary details, cadence, restored
source viewing, damaged-draft recovery, synthetic staff passphrase confirmation,
and the 1,923-invoice campus. All passed with no unexpected runtime errors.
The measured campus navigation maximum in the installed readiness run was 0.410 s.
The missing staff confirmation 422 is an intentional negative check.

Native testing found and fixed two asynchronous UI problems: changing source
while the old provider editor was still interactive, and a delayed audit response
after logout accessing removed controls. Provider navigation now invalidates
stale views; audit/backup callbacks retain and check their original controls.
The readiness regression deliberately delays delivery of an otherwise unchanged
real audit fetch response by 350 ms, logs out, then verifies safe completion.
It does not mock server data or authentication.

One first fresh provider attempt timed out at setup while the regression suite
was running. A direct retry and the complete fresh run passed without raising
the timeout or changing parser behavior. That failed run was retained externally;
the harness now captures the last rendered state and console/HTTP failures on
any failed run. This isolated timeout is not represented as a fixed product bug.

## Installation, upgrade and recovery actually run

The candidate source ZIP was extracted into a new external code folder with its
executable modes preserved. The actual `scripts/setup.sh` installed base wheels
from the reviewed external wheelhouse using `--no-index` and wheel-only mode.
Development and optional OCR wheels were installed the same way. Its own Python
ran the full regression and native checks. The real `Launch-Demo.command` started
a fresh external demo; installation did not open an existing data workspace.
The final source files and manifest are verified against that installed folder.

An actual backup made by the preserved 0.4 installation was restored with that
release, then explicitly migrated by 0.5. All **19 pre-existing data tables**
(excluding mutable settings/audit), three original extraction records, source
hashes and ledger export bytes were preserved. Schema 5 begins with an empty
provider journal; historical bills were not reparsed. Old code refused the new
schema without writing to it.

The old release restored its pre-upgrade backup into a separate rollback
workspace. Native Chrome opened both the upgraded 0.5 and rollback 0.4 workspaces,
verified original PDF download hashes, exact ledger export parity, diagnostics,
mobile ledger layout and logout, with zero unexpected errors. New private layouts
cannot be carried back into schema 4; retain the schema-5 workspace for later-work
recovery. Populated schema-5 templates were separately retained across the new
code-folder switch and browser backup/restore.

## Dependencies, benchmark and CI

No application/development/OCR dependency or model runtime was added or repinned.
Both working and fresh environments passed `pip check`. A current pip-audit
2.10.1 scan of the fresh installed distributions on 2026-09-07 returned **no known
vulnerabilities**, with no ignored advisory IDs. Only public package metadata
was queried. This does not assess every bundled native library or the OS.
The older optional Tesseract 5.5.1 engine and pinned-model restriction remain
explicit in [DOCUMENT_EXTRACTION_DEPENDENCIES.md](DOCUMENT_EXTRACTION_DEPENDENCIES.md).

The preserved 28-document benchmark ran with OS network access denied for the
benchmark and child workers. It matched 215/215 fields on 21 template documents,
39/39 on four generic native-text documents, and 30/30 on three OCR documents.
There were no missing, incorrect, false or wrongly normalized unit values on
that corpus. Measured path times were 2.631 s, 0.484 s and 1.978 s respectively.
These are exact fictional-corpus results, not general or real-provider accuracy.
The normal application worker is not claimed to have a complete OS sandbox.

The minimal synthetic CI workflow uses reviewed, full-SHA-pinned first-party MIT
actions, read-only repository permissions and no private data, custom secrets,
OCR models, deployment or artifact upload. Its source-integrity, reproducible
archive and 25-document digital benchmark commands pass locally. **Hosted GitHub
Actions was not pushed or dispatched** during this milestone. Native acceptance
remains outside CI. See [SYNTHETIC_CI.md](SYNTHETIC_CI.md) for pins and provenance.

## Release gate and continuing limits

Source packaging uses fixed epoch `1788739200`. The final archive contains 174
manifested source files plus `RELEASE-MANIFEST.json`. Two independent builds are
compared byte for byte, every installed and committed source blob is checked
against the manifest, and the Git source allowlist is checked. The annotated
local `v0.5.0` tag is created only after verification and a clean committed tree.
No 0.5 branch, tag or archive is pushed. The original 0.4 tag/archive remain intact.

The release is unsigned. Native Windows launch/ACLs, downloaded-archive Finder
quarantine/Gatekeeper behavior, actual staff hardware and browser, school
retention/maintenance ownership, private accounting semantics and representative
real-provider layouts remain external acceptance work. The existing bounded
English OCR and simple service-section grammar are experimental. Initial local
onboarding sources still require manual review; private validation is scoped to
the chosen provider/version/sample set. No portal, public deployment, real school
record, paid API, fine tuning or unattended administration was introduced.
