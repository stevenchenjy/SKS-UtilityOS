# SKS UtilityOS

**Version 0.2.0 · staff-local utility ledger · synthetic demonstration**

A local FastAPI/SQLite application for reviewed utility invoices, stable service points, and supported electricity interval files. All supplied buildings, providers, accounts, amounts, and readings are fictional. School installation and private-data use require separate school approval.

This workspace is for software development, testing, technical documentation, and release engineering. It does not contain meeting materials or stakeholder proposals.

## Run the demo on macOS

Use an approved Python 3.11+ installation. This release was verified on macOS arm64 with Python 3.13.2 and native Chrome 152.0.7977.82.

```sh
bash scripts/setup.sh
.venv/bin/python run.py demo --open
```

`Launch-Demo.command` and `Launch-Staff.command` are executable local launchers. They open the browser after startup and accept the same options as `run.py`. Stop the service with Ctrl+C in its terminal. The application listens only on IPv4 loopback. If port 8765 is occupied, use `--port 8878` and open the printed local URL.

Choose **Open synthetic demo**. Its public passphrase is `synthetic-demo-only`. Demo imports require confirmation that the file is synthetic. Staff mode uses a separately created local application passphrase.

For repeatable import testing, use a fresh directory outside the repository:

```sh
.venv/bin/python run.py demo --data-dir /tmp/sks-new-synthetic-demo --port 8878 --open
```

The initial demo has 45 approved invoices, eight service points, two bills awaiting review, and one day of interval readings. CSV/XML/PDF imports add to that workspace, so choose a new directory for a second complete import test.

Windows scripts are supplied, but native Windows execution and ACL behavior remain unverified. Run `scripts/setup.ps1` only through an approved PowerShell session, then `.\.venv\Scripts\python.exe run.py demo --open`. Do not weaken device execution policy.

## Working file workflows

- Import `samples/demo-import.csv`, compare it with the retained original, check its fields, acknowledge the review, and approve. September gains $579.80 in current charges.
- Import `samples/demo-invoice.pdf`. Download the source and manually enter its printed fields: Example Water, `DEMO-W03 account`, reference `SYN-PDF-W03-202608`, 6,200 gal, and $125.80. The PDF remains an attachment; there is no PDF extraction or OCR in the application.
- Import `samples/demo-intervals.xml`, confirm mapping to `DEMO-E01`, and approve. Interval history grows without adding invoice charges or billed consumption.
- Save an incomplete bill draft before leaving its page. Reopen it through **Review queue**. Rejected drafts retain their source and any saved revisions.
- Open **Invoice ledger** to inspect active invoices or all retained versions. A correction creates a reviewable replacement. A supplier rebill is imported as a new document and explicitly linked to the original active invoice. Only an approved replacement takes over reporting.
- Cancel an incorrectly posted invoice with a reason and explicit confirmation. A separate financial credit remains an independent invoice with negative charges and zero quantity on charges-only lines.
- Use **Utility inventory** to correct a building label or confirmed meter mapping. Reporting uses the current mapping; original approved review values and mapping history remain available.
- Use **Privacy & support** to preview safe diagnostics, export the private active ledger, or create and download a private backup. Restoration runs with the app stopped.

## Data and accounting boundaries

Amounts use integer cents and quantities use decimal arithmetic. Supply-only invoices add charges with zero repeated consumption. Oil/propane deliveries are purchased volume. Shared meters remain unallocated. Charts group active charges by invoice month, preserve negative credits, and do not claim complete campus coverage or calendarized consumption.

Green Button support is limited to a tested file subset: forward, delta electricity energy in Wh, with explicit multipliers and resolvable ReadingType links. Unsupported semantics, revised/conflicting readings, and duplicate stream mappings are rejected. There is no utility certification, universal format compatibility, portal login, CMD/OAuth, or live feed.

Code and data are separate. No Node build, hosted database, Docker, online account, utility API, or cloud extraction service is required. Setup downloads Python wheels, or accepts a local wheelhouse:

```sh
bash scripts/setup.sh /approved/local/wheelhouse
```

`requirements-bootstrap.txt` pins the installer; `requirements.txt` and `constraints-tested.txt` pin the tested runtime. See [dependency decisions](docs/DEPENDENCY_DECISIONS.md).

This remains a single-operator local pilot. SQLite and backups have no application-level encryption. Staff need an approved encrypted disk, OS account, retention policy, and maintenance owner. Multi-user access and school deployment require additional decisions.

## Upgrade and recovery

Version 0.2.0 uses **schema 2**. Starting the app never upgrades an existing schema-1 workspace. Stage the new code separately, review it, stop the old app, and follow [the installation and update guide](docs/STAFF_INSTALL_AND_UPDATES.md). The explicit `migrate --confirm-migrate` command validates a copy and creates a schema-1 backup before switching the database. Older code cannot read schema 2; rollback uses the preserved older release and pre-upgrade backup in a separate recovery directory.

Useful maintenance commands, with the selected mode and external data directory supplied consistently:

```sh
.venv/bin/python run.py check --mode demo --data-dir /tmp/sks-new-synthetic-demo
.venv/bin/python run.py backup --mode demo --data-dir /tmp/sks-new-synthetic-demo
.venv/bin/python run.py diagnostics --mode demo --data-dir /tmp/sks-new-synthetic-demo
```

Private backups and ledger exports remain with staff. Only reviewed allowlisted diagnostics and synthetic reproductions are suitable for developer support. Releases are unsigned; hashes establish integrity, while trusted provenance requires the school's separate distribution decision.

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
