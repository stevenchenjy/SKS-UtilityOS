# 0.6.0-rc3: portable deployment and structured acquisition

Verification date: **2026-09-13**. Starting accepted repository commit:
`23a2b659575a74442f8ec6fc15c0345a9544e97d`, rc2/schema 6. The candidate is
**0.6.0-rc3 / schema 7**, prepared locally with synthetic data only. It remains
unsigned, untagged and unpublished. The trusted `v0.5.0` and earlier history are
unchanged. Windows/current-runtime CI and school/provider acceptance are still
open; this is not a completed production or cross-platform qualification.

## Implemented and synthetically exercised

- **Portable installation:** source release + approved CPython 3.13 GIL runtime
  + exact target wheelhouse. Each new code directory gets its own environment;
  an existing environment is refused. Original-data directories are never opened
  by setup. Every artifact is verified before installation, with offline,
  wheel-only, hash-required pip and inherited pip configuration disabled.
  Guided staff launch chooses an external directory, establishes local credentials
  and prints health before opening the loopback browser.
- **Health:** fixed categories cover app/schema/runtime, dependency receipt,
  database and migration state, disk, source integrity, directory permissions,
  backup, optional OCR and acquisition availability. Tests exclude private paths,
  labels, values, source snippets and credential sentinels. Windows ACL checks
  are bounded and never change execution policy.
- **Acquisition:** disabled at every launch/restore, explicit acknowledged
  configuration and enablement, pause/resume/disable, five-second foreground
  polling, at least two seconds of file stability, no recursion, at most 1,000
  inspected entries and one parser per tick. Temporary downloads and symlinks are
  ignored, unstable files defer, original downloads remain untouched, repeated
  sources deduplicate and failures remain visible. No watcher daemon survives
  application stop. Financial approval remains an independent staff action.
- **Adapters and spreadsheets:** PDF and canonical invoice CSV stage financial
  candidates; Green Button XML, mapped CSV and bounded `.xlsx` stage operational
  candidates. Workbook bytes, sheet/region/cell/raw/normalized/unit/mapping
  provenance are retained. Approved layout and confirmed meter relationships
  can be reused explicitly; new/conflicting identifiers need review. Formula
  caches, macros, external refresh, encrypted/active workbooks, hidden-sheet
  ambiguity and selected merged/hidden cells are rejected. `.xls` is unsupported.
  Naive mapped-usage timestamps use pinned tzdata 2026.4 independently of host
  timezone files; explicit source offsets remain authoritative, and ambiguous
  date/time inputs fail review.
- **Water accounting:** optional service days, payments and balance adjustments
  remain separate from service periods, cumulative readings, billed consumption,
  current charges and total due. Reading differences are advisory checks;
  provider-established units and explicit review remain required.
- **Green Button:** resolved ESPI resource links and source identities, UTC starts,
  duration, integer raw values, explicit multipliers and retained quality. Accepted
  forward deltas are electricity Wh→kWh, natural-gas therms and drinkable-water
  m3/US_gal. Unsupported flow, aggregation, qualifiers, units, cumulative streams
  and precision fail before staging. Existing electricity and historical pending
  draft semantics are preserved; conflicts never overwrite approved readings.
- **Portfolio Manager:** production configuration/sync stays disabled and accepts
  no credentials. Local in-memory fixtures exercise explicit selections, original
  evidence, pagination, high-water observations, repeated pulls, revisions,
  partial failures and disconnect. No API service was contacted and no fixture
  writes financial records or enables production ingestion.

See [portable deployment](PORTABLE_DEPLOYMENT.md), [acquisition](ACQUISITION.md),
[mapped usage](MAPPED_USAGE.md), [Green Button](GREEN_BUTTON.md) and
[Portfolio Manager](PORTFOLIO_MANAGER.md) for contracts and primary-source notes.

## Actual platform and artifact evidence

| Target | Artifact verification | Execution actually performed |
|---|---|---|
| macOS Apple Silicon | 26 base wheels, 25,099,219 bytes; 28 optional OCR wheels, 28,935,517 bytes; exact official Python installer receipt | macOS 26.6.2 arm64, Python 3.13.2, Chrome 152.0.7977.84; fresh install, HTTP handoff, native desktop/mobile and upgrade/rollback |
| Windows x64 | 26 Windows wheels, 27,748,570 bytes, active target dependency closure and official Python installer hashes checked | No Windows host available; launch, ACL, installer, browser and shutdown acceptance unverified |
| Linux x64 | 26 Linux wheels, 28,306,558 bytes and target dependency closure checked | No local Linux execution; regression CI configured |
| macOS Intel | No supported wheel receipt | Deferred because the current required cryptography dependency has no macOS x64 wheel; no downgrade or private native build introduced |

Both official **Python 3.13.15** installer artifacts were downloaded and hashed,
but neither was executed. CI is configured for that patch on macOS 15 arm64,
Windows Server 2025 x64 and Ubuntu 24.04. Hosted CI was not pushed or dispatched;
no passing CI receipt is claimed. Local Python 3.13.2 is an older development
runtime, not a recommendation for school installation. Windows Server CI will
not replace actual Windows 11 staff-device acceptance. Optional OCR currently
has a reviewed artifact receipt only for Apple Silicon/macOS 15+.

The base installed Mac environment used 76,736,453 regular-file bytes excluding
its linked interpreter. Wheel counts include pip and the full active runtime
closure. Added packages are openpyxl 3.1.5, et-xmlfile 2.0.0 and tzdata 2026.4.
Receipts retain filenames, sizes, SHA-256, platform/runtime, public origins and
license references. On September 13, public PyPI release advisory metadata was
checked for all **40 installed development/optional packages**: no unavailable
responses or reported advisories. `pip check` passed. This was a metadata query,
not a new pip-audit run or a complete native-library/OS audit.

## Automated and native outcomes

The accepted baseline passed **414 tests**. After implementation and corrections,
the working environment passed **545 tests**; a separately extracted source ZIP
installed through its actual setup script into a fresh external environment also
passed **545 tests**, both exit zero. Two existing Starlette/httpx and AnyIO
deprecation warnings remain. Targeted tests cover malicious wheel/configuration
changes, tampered kits, hostile spreadsheets/XML, source-retention races, mapping
conflicts, watcher lifecycle, accounting preservation and old/new schema refusal.
Platform-only skips are disclosed in [synthetic CI](SYNTHETIC_CI.md).

Native checks used existing Python Playwright and an isolated installed Chrome
because the Browser plugin was unavailable. They used real loopback HTTP,
cookies, CSRF, local files and downloads, with desktop **1440×1000** and mobile
**390×844** viewports. No staff browser profile or mock API response was used.
Successful checks cover core CSV/PDF/XML review, explicit approval, duplicate
refusal, corrections/rebills/credits/cancellation, inventory, ledger/support
exports, source viewing, backups and logout; Provider Studio activation/drift/
retirement; batch/drop/folder intake and OCR evidence; billing schedules;
damaged-draft recovery, synthetic staff confirmation and the 1,923-invoice campus.

New native runs additionally cover watcher enable/pause/resume, PDF/XLSX/XML
arrival, distinct financial/operational approvals, exact workbook downloads,
water XML US_gal display, source region/provenance, approved spreadsheet mapping
reuse, stale-preview refusal, acquisition health, restart-disabled behavior and
backup/restore. Final successful runs have no unexpected browser/runtime/HTTP
errors. Expected duplicate and reauthentication refusals remain negative tests.
Desktop/mobile screenshots were inspected. Owned browsers and servers stopped.

The retained 28-PDF benchmark matched **284/284 fields**: 215 template, 39 generic
native-text and 30 optional OCR, with zero missing/incorrect/false fields or
incorrect units. The separate 25-document digital benchmark also passed. OCR used
the previously reviewed English model, whose bytes and license were staged and
hash-verified externally; there is no runtime model download. These are exact
fictional-corpus results, not estimates of real-provider accuracy.

Verification found and corrected mobile health overflow, stale CSV-invalid test
expectations, a native locator mismatch, watcher starvation by unstable files,
regular-file replacement by a FIFO, unsupported XML precision reaching review,
host-dependent timezone data and inherited pip configuration. The final native
intake fixture now tests incomplete invoice-shaped CSV; an unfamiliar generic
CSV legitimately enters mapped usage review. Failed attempts are retained as
development evidence and are not counted as successful runs.

## Fresh installation, migration, rollback and integrity

The portable rehearsal built two identical archives, extracted into a fresh
external code folder and installed its own environment from the exact offline
Mac wheelhouse. Real HTTP exercised new workspace/login, watcher PDF/XML/XLSX,
exact original downloads, explicit invoice and separate usage approval, restart,
approved mapping reuse, backup, disposable restore, integrity, logout and clean
shutdown. It used no source-tree virtual environment. Native browser checks were
performed separately on the same application implementation.

The actual rc2→rc3 rehearsal independently installed the accepted old source and
the candidate. It refused maintenance while running, backed up with old code,
refused incompatible startup, migrated **schema 6→7** only with explicit
confirmation, and preserved **27 pre-existing data tables and four originals**.
Ledger CSV and original PDF download hashes matched exactly after the switch.
Schema 7 is a compatibility boundary for new source/provenance/audit semantics;
migration does not reparse or rewrite historical rows. Old code cannot open it.

The old release restored its pre-upgrade backup into a separate rollback
workspace, verified historical records and sources, and passed native desktop/
mobile downloads and logout. The receipt records `status: passed`,
`runner_exit_code: 0`, all rehearsal servers stopped and all browser checkpoints
closed. Later schema-7 activity stays in the upgraded workspace; rolling back
does not transfer that later history into the old schema.

Final source packaging uses fixed epoch **1789257600**. The source allowlist,
two-build byte equality, manifest verification and exact source comparison with
the tested extracted environments are checked before local commit. The final
source manifest excludes itself; the exact commit and final ZIP/kit hashes are
recorded in the external development artifact receipt to avoid a self-referential
archive. Final source changes after installed verification are release notes and
the focused native-intake fixture correction, not application code. Target kits
contain the source ZIP, reviewed base wheels, official runtime installer and
receipts. Optional OCR models, databases, backups, logs and private configuration
are excluded. Hashes verify integrity; trusted provenance still requires a
separately approved distribution/signing process.

Local synthetic receipts, screenshots and artifact hashes are retained outside
Git under the development release directory `0.6.0-rc3-20260913`. These are
developer evidence, not the application's privacy-safe staff support bundle.

## Remaining acceptance decisions

1. Run the prepared macOS/Windows/Linux CI and qualify the reviewed current
   Python patch. Complete native Windows install/launch/ACL/browser/stop and
   actual school-machine acceptance, including antivirus, Gatekeeper/quarantine,
   runtime signatures, encryption, backup/retention and maintenance ownership.
2. Authorize source publication and select trusted distribution/signing before
   deployment. No final or candidate tag is justified by the unavailable checks.
3. Have authorized staff validate actual My360 exports locally: `.xlsx` versus
   `.xls`, table/date/unit/quality meanings, selected date range, separate meter/
   building identities and mapping reuse. Cornwall-on-Hudson compatibility is
   externally unverified; a genuine `.xls` export remains a parser gap.
4. Validate actual Central Hudson Green Button files and supported ESPI semantics
   on the school installation. There is no certified connector or portal scraper.
5. Before EPA TEST or LIVE, obtain school approval, confirm account eligibility,
   individual versus whole-building meter coverage, recurrence, resolution,
   historical revisions, fees, consent and support owner. Then implement and
   verify transport, approved credential storage/removal and staff-local atomic
   persistence through the documented acceptance procedure. Neither service was
   contacted here. Manual sync comes before any separately approved schedule.
6. Keep My360 remote automation disabled unless a documented school-scoped
   read-only feed or scheduled export is offered and separately approved. Public
   local export documentation does not establish an API or permission to scrape.
