# Development verification — 0.5.0

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
