# SKS UtilityOS

**Version 0.6.0-rc1 · local release candidate · synthetic demonstration**

A local FastAPI/SQLite application for reviewed utility invoices, stable service points, and supported electricity interval files. All supplied buildings, providers, accounts, amounts, and readings are fictional. School installation and private-data use require separate school approval.

This workspace is for software development, testing, technical documentation, and release engineering. It does not contain meeting materials or stakeholder proposals.

This candidate includes building reports and a repeatable synthetic update
rehearsal. The trusted tagged baseline remains `v0.5.0`; this candidate is not a
complete 0.6 analytics milestone, public release or school installation. See
[update rehearsal](docs/UPDATE_REHEARSAL.md) for fresh-demo validation, stopped-app
backup, schema checks, explicit migration when required, version switching and
verification of a separate rollback workspace. Every invoice still requires review.

## Run the demo on macOS

Use an approved Python 3.11+ installation. This release was verified on macOS arm64 with Python 3.13.2 and native Chrome 152.0.7977.82.

```sh
bash scripts/setup.sh
.venv/bin/python run.py demo --open
```

`Launch-Demo.command` and `Launch-Staff.command` are executable local launchers. They open the browser after startup and accept the same options as `run.py`. Stop the service with Ctrl+C in its terminal. The application listens only on IPv4 loopback. If port 8765 is occupied, use `--port 8878` and open the printed local URL.

Choose **Open synthetic demo**. Its public passphrase is `synthetic-demo-only`. Demo imports require confirmation that the file is synthetic. Staff mode uses a separately created local application passphrase. Staff cancellations and replacement approvals require that passphrase again.

For repeatable import testing, use a fresh directory outside the repository:

```sh
.venv/bin/python run.py demo --data-dir /tmp/sks-new-synthetic-demo --port 8878 --open
```

The initial demo has 45 approved invoices, eight service points, two bills awaiting review, and one day of interval readings. CSV/XML/PDF imports add to that workspace, so choose a new directory for a second complete import test.

Windows scripts are supplied, but native Windows execution and ACL behavior remain unverified. Run `scripts/setup.ps1` only through an approved PowerShell session, then `.\.venv\Scripts\python.exe run.py demo --open`. Do not weaken device execution policy.

## Working file workflows

- Import `samples/demo-import.csv`, compare it with the retained original, check its fields, acknowledge the review, and approve. September gains $579.80 in current charges.
- Import `samples/demo-invoice.pdf`. Download the source and manually enter its printed fields: Example Water, `DEMO-W03 account`, reference `SYN-PDF-W03-202608`, 6,200 gal, and $125.80. This older layout exercises manual completion; the original source is retained.
- Import `samples/demo-intervals.xml`, confirm mapping to `DEMO-E01`, and approve. Interval history grows without adding invoice charges or billed consumption.
- Save an incomplete bill draft before leaving its page. Reopen it through **Review queue**. Rejected drafts retain their source and any saved revisions.
- Open **Invoice ledger** to inspect active invoices or all retained versions. A correction creates a reviewable replacement. A supplier rebill is imported as a new document and explicitly linked to the original active invoice. Only an approved replacement takes over reporting.
- Cancel an incorrectly posted invoice with a reason and explicit confirmation. A separate financial credit remains an independent invoice with negative charges and zero quantity on charges-only lines.
- Use **Utility inventory** to correct a building label or confirmed meter mapping. Reporting uses the current mapping; original approved review values and mapping history remain available.
- Use **Privacy & support** to preview safe diagnostics, export the private active ledger, or create and download a private backup. Restoration runs with the app stopped.

## Building reports

In **Overview**, choose a **Building** and **Invoice month**, or select a building
in the spending table. Charges, the monthly trend, quantities and service-point
rows use the same selection. **Unassigned / shared** is a separate scope; these
costs are not distributed across named buildings. The selected month remains in
place when a building has no approved invoices. Empty records do not establish
zero consumption or complete coverage.

**View matching invoices** opens the ledger with the same building and month.
For a split invoice, **Building charges** shows only matching service lines and
**Full invoice total** retains the whole document amount. Search and invoice
state filters work within that selection. **Back to invoice ledger** returns
from an invoice to the retained filters; **View building overview** returns to
its report. **Clear filters** resets the ledger, and **All buildings** resets
only the overview's building selection. Selections are retained while navigating
in the current session and reset on page reload or lock.

The trend shows up to eight recorded invoice months through the selection (five
on mobile), with years and an expandable exact-values table. Pending review
counts explicitly cover the whole ledger. Utility inventory's **View building
data** links use the current mapping; renames preserve building identity and
mapping changes regroup past periods. Quantities remain separate by unit and
treatment. Use **Interval data** for imported meter readings and **Bill
completeness** for separately confirmed cadence expectations.

## Intelligent Bill Intake

Open **Utility Inbox** to import files by picker or drag/drop, review a batch result, or explicitly scan a configured external local folder. The import dialog offers extractable fictional PDFs and a scanned example. Text/template extraction proposes fields beside a rendered original; optional English OCR supports the scanned corpus. Every draft still needs human review and approval.

The shipped providers and layouts are fictional. Unknown layouts, missing fields and conflicts require completion; no general real-provider compatibility is claimed. Saved corrections preserve machine evidence and prior approved values. **Bill completeness** starts with explicitly configured account/meter cadence and remains experimental. Read [the intake guide](docs/BILL_INTAKE.md), [the dependency/model decision](docs/DOCUMENT_EXTRACTION_DEPENDENCIES.md), and [offline OCR setup](docs/STAFF_INSTALL_AND_UPDATES.md).

## Private Provider Onboarding and Local Template Studio

Open **Provider Management** or **Set up or inspect provider layout** beside a
PDF review. Create a private local provider, select source candidates, assign
bounded field rules, and preview an immutable draft layout. Validate it against
at least two locally approved bills before explicitly activating it for future
candidate extraction. All invoices still require ordinary review and approval.

Local definitions, selected validation sets, correction counts and retained
versions live in the external workspace database and its private backups. Changed
layouts receive new versions; historical extraction is unchanged. The dedicated
support bundle downloads exactly its value-free preview. Start with the new
provider example PDFs in the import dialog. Read [the provider studio guide](docs/PROVIDER_STUDIO.md)
for the initial manual review, activation gate, supported rule vocabulary and
privacy/recovery boundaries. No real-provider compatibility is claimed from the
fictional onboarding corpus.

## Data and accounting boundaries

Amounts use integer cents and quantities use decimal arithmetic. Supply-only invoices add charges with zero repeated consumption. Oil/propane deliveries are purchased volume. Shared meters remain unallocated. Charts group active charges by invoice month, preserve negative credits, and do not claim complete campus coverage or calendarized consumption.

Green Button support is limited to a tested file subset: forward, delta electricity energy in Wh, with explicit multipliers and resolvable ReadingType links. Unsupported semantics, revised/conflicting readings, and duplicate stream mappings are rejected. There is no utility certification, universal format compatibility, portal login, CMD/OAuth, or live feed.

Code and data are separate. No Node build, hosted database, Docker, online account, utility API, or cloud extraction service is required. Setup downloads Python wheels, or accepts a local wheelhouse:

```sh
bash scripts/setup.sh /approved/local/wheelhouse
```

`requirements-bootstrap.txt` pins the installer; `requirements.txt` and `constraints-tested.txt` pin the tested runtime. See [dependency decisions](docs/DEPENDENCY_DECISIONS.md).

This remains a single-operator local pilot. [Role enforcement is explicitly deferred](docs/ACCESS_AND_CONFIGURATION.md); audit actors identify operator context, not individual people. SQLite and backups have no application-level encryption. Staff need an approved encrypted disk, OS account, retention policy, and maintenance owner. Multi-user access and school deployment require additional decisions.

## Upgrade and recovery

Version 0.6.0-rc1 uses **schema 5**, unchanged from 0.5.0. Starting the app never upgrades an existing schema-1, schema-2, schema-3 or schema-4 workspace. Stage the new code separately, review it, stop the old app, and follow [the installation and update guide](docs/STAFF_INSTALL_AND_UPDATES.md). The explicit `migrate --confirm-migrate` command validates a copy and creates a backup in the original schema before switching the database. Older code cannot read schema 5; rollback uses the preserved older release and pre-upgrade backup in a separate recovery directory.

Useful maintenance commands, with the selected mode and external data directory supplied consistently:

```sh
.venv/bin/python run.py check --mode demo --data-dir /tmp/sks-new-synthetic-demo
.venv/bin/python run.py backup --mode demo --data-dir /tmp/sks-new-synthetic-demo
.venv/bin/python run.py diagnostics --mode demo --data-dir /tmp/sks-new-synthetic-demo
```

Private backups and ledger exports remain with staff. Only reviewed allowlisted diagnostics and synthetic reproductions are suitable for developer support. Releases are unsigned; hashes establish integrity, while trusted provenance requires the school's separate distribution decision.

## Larger synthetic campus

For a deterministic 24-month development fixture, create a new external directory:

```sh
.venv/bin/python scripts/synthetic_campus.py --data-dir /tmp/sks-new-campus
.venv/bin/python run.py demo --data-dir /tmp/sks-new-campus --port 8884 --open
```

It contains 20 fictional buildings, 60 service points, 1,923 active invoices,
1,927 retained versions and 288 interval readings, with seasonal usage,
corrections, a supplier rebill, credits and deliberate anomalies. The generator
refuses an existing directory; failed disposable generation can be repeated in
a new directory. It uses the normal import/review services and no live data.

## Development verification

```sh
.venv/bin/python -m pip install -r requirements-dev.txt -c constraints-tested.txt
.venv/bin/python -m pytest -q
.venv/bin/python scripts/native_browser_smoke.py \
  --url http://127.0.0.1:8878 \
  --browser-executable '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
  --exercise-imports --milestone --evidence-dir /tmp/sks-browser-evidence
```

The extended browser test requires a **fresh synthetic demo**. It uses a separate browser profile, native HTTP/cookies/downloads, and desktop/mobile viewports; there is no transport bridge or mocked application API. Playwright is a development dependency only. An existing approved Chrome executable avoids an additional browser download.

Read [verification results](docs/VERIFICATION.md), [release notes](docs/CHANGELOG.md), [architecture](docs/ARCHITECTURE.md), [invoice lifecycle](docs/INVOICE_LIFECYCLE.md), [security and limits](docs/SECURITY_AND_LIMITS.md), and [the roadmap](docs/ROADMAP.md). Continue development using `AGENTS.md`, `MASTER_PROMPT.md`, and the project-local engineering skill.

Additional native recovery, audit, large-campus search/pagination and synthetic
staff passphrase-confirmation checks create their own new external workspaces:

```sh
.venv/bin/python scripts/native_readiness_smoke.py \
  --work-dir /tmp/sks-new-readiness-check \
  --browser-executable '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
```

Read the [operational contracts](docs/OPERATIONS.md), [access/configuration decision](docs/ACCESS_AND_CONFIGURATION.md),
[release/signing notes](docs/RELEASE_AND_SIGNING.md) and [development/Git guide](docs/DEVELOPMENT.md).

The intake benchmark and native evidence/batch/OCR/recovery checks use only the
checked-in fictional PDF corpus and a reviewed external model directory:

```sh
.venv/bin/python scripts/benchmark_extraction.py --ocr-model-dir /approved/local/models \
  --output /tmp/sks-extraction-benchmark.json
.venv/bin/python scripts/native_intake_smoke.py --work-dir /tmp/sks-new-intake-check \
  --ocr-model-dir /approved/local/models \
  --browser-executable '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
```
