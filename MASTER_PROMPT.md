# Codex master prompt: develop the staff-local SKS UtilityOS ledger

Continue the working UtilityOS implementation for The Storm King School. Inspect current code and tests, choose useful work within the requested scope, and deliver complete, user-visible slices with synthetic data. Reserve questions for school decisions or unavailable capabilities.

## Instruction loading and development behavior

`AGENTS.md` is the persistent project-level instruction source and always governs repository work. This document supplies current major-milestone direction; explicit user task instructions define the detailed scope of the current slice, subject to `AGENTS.md`. Follow its scoped-loading rules: use `README.md` for current capabilities, setup and release state; this document for major milestones, development direction or ambiguous scope; and only relevant subsystem files under `docs/` for focused work. Read `.agents/skills/local-utility-engineering/SKILL.md` for accounting, bill intake/import, extraction, data semantics, support/privacy, migration or release work.

Inspect actual implementation and tests before assuming a roadmap capability is absent or choosing a rewrite. Completed milestones are context, not a checklist to rebuild or re-audit on every maintenance task, bug fix, test, documentation correction or narrow UI change. Use the full milestone context for major release planning and preserve tested accounting, privacy and operational contracts.

This workspace is exclusively for software development, testing, technical documentation and release engineering. Do not create or restore meeting briefs, presentations, procurement materials or stakeholder proposals unless explicitly requested. The removed meeting brief is intentional.

Use relevant installed skills when helpful; review additional skill instructions, dependency licenses, installation behavior, maintenance and fees before adding anything. Prefer project-local development dependencies. Do not change global Codex settings, weaken machine permissions, add accounts, purchase services or expose a server publicly.

## Current development baseline

Development has progressed beyond the trusted tagged **v0.5.0** release at commit `0d515181714e8f1f090156e43c957735e26976b7`. Preserve that baseline, earlier tags and history. The accepted development starting point was **0.6.0-rc2 / schema 6**, including:

- Building reporting; strict financial approval acknowledgement and revision enforcement.
- Account-level billing schedules, including alternate-month schedules; mapped operational usage CSV intake; provider-informed synthetic semantics; supervised update rehearsal.
- Existing ledger lifecycle, retained evidence and immutable review/audit history, backup/restore and explicit migration, privacy-safe diagnostics, Intelligent Bill Intake and Provider Studio capabilities from prior releases.

Inspect these existing capabilities before extending them. Consult `docs/VERIFICATION.md` and `docs/CHANGELOG.md` for evidence and limits, and relevant subsystem guides for focused work.

The current **0.6.0-rc3 / schema 7** candidate extends that baseline with portable artifact receipts, foreground acquisition, direct mapped XLSX intake and bounded ESPI support. Inspect current verification for the tested scope and remaining qualification gates. The candidate remains **unsigned and not school-production accepted**. Actual Central Hudson, My360 and Cornwall school-account exports, live connectors, Windows school-machine acceptance and school installation remain externally unverified. Synthetic results do not establish real-provider compatibility or general extraction accuracy. Combined municipal-service financial posting remains unsupported.

The stack remains Python/FastAPI/SQLite with browser ES modules and local extraction. Demo and staff data use separate external workspaces; mode mismatch is rejected. Schema 7 requires explicit migration from schema 6 or supported earlier schemas; startup never upgrades a workspace automatically. Preserve authentication, host/origin checks, CSRF protection and immutable storage. This remains a single-operator local pilot; named role enforcement is deferred under `docs/ACCESS_AND_CONFIGURATION.md`.

## Established staff intake workflow

Authorized staff manually downloads a utility bill from the provider portal, then imports the file locally. UtilityOS identifies a matching active local provider layout when available and extracts candidate values locally. Staff compares the source and candidates, checks mappings and warnings, completes missing values, and explicitly approves the invoice. Only approved records become authoritative for financial reporting; every financial invoice requires staff approval.

For a new provider or changed layout, staff uses Provider Studio locally to create an immutable layout version, validate it against approved local bills and explicitly activate it. Initial onboarding bills require manual review and completion; activation requires at least two distinct approved sources and the documented validation gates. Active templates are reused across future bills until a layout change or repeated correction triggers review. Drift, ambiguity and unsupported fields require investigation or manual completion; they never authorize automatic posting or silent rule changes. New versions preserve earlier definitions, source evidence and extraction history. The developer does not need the private source document or private layout text.

## 0.6.0-rc3 — Portable Deployment and Structured Acquisition

The active milestone makes UtilityOS reproducible on another authorized school computer and reduces repetitive data acquisition work while preserving local control and explicit financial review. The target operating model is:

provider-native source → local acquisition → local parsing → retained source evidence → reusable meter/building mapping → staff review → explicit financial approval where applicable → authoritative local reporting.

### 1. Portable deployment

Make installation and reproduction practical on supported school computers: reproducible dependency installation, platform-specific dependency/hash receipts, offline-friendly installation, straightforward first-run setup, separate code and private data, health/integrity checks, update and rollback, and macOS/Windows validation where practical. Report unavailable platform checks honestly.

Do not require Docker, a hosted database, Node, paid runtime services or unattended remote administration without a demonstrated requirement. A requirement does not waive school approval or the prohibition on unattended remote updaters.

### 2. Staff-controlled automatic local acquisition

The existing explicit local-folder scan may be extended into an opt-in watcher while UtilityOS is running. It may observe one explicitly configured local folder, wait for downloaded files to become stable, detect new files, fingerprint and retain them, route them through the appropriate local adapter and place resulting records into review queues. Preserve duplicate protections and visible failure status.

The watcher must not log into portals, store utility portal credentials, delete or modify staff downloads, approve financial invoices or operate as an unattended system daemon while UtilityOS is closed.

### 3. Provider-native structured files

PDF remains a supported evidence source, but is not the universal input format. Prefer provider-native structured data when available. Support distinct acquisition adapters for PDF invoices, Green Button XML, CSV usage, spreadsheet usage exports and future explicitly approved remote connectors. Keep financial invoice data and operational usage evidence separate; overlapping evidence must not double-count usage.

### 4. My360 spreadsheet workflow

Public My360 documentation supports consumption exports to Excel or PDF, as recorded in `docs/PROVIDER_FILE_WORKFLOWS.md`. Direct local spreadsheet intake is a justified development target; the exact Cornwall-on-Hudson tenant workbook schema remains unverified.

Develop a safe generic architecture using synthetic files, reusable mappings, retained original workbooks, explicit units/timestamps and staff review. Do not advertise certified My360 compatibility before authorized school-side validation. Do not use cloud spreadsheet conversion, execute workbook macros or external links, or treat formulas or cached formula values as trusted meter data.

### 5. Green Button

Move parsing toward official ESPI semantics while preserving safe rejection of unsupported ReadingType, commodity, unit, multiplier, direction, accumulation, aggregation, duration or quality semantics. Preserve ReadingType link resolution, UTC interval starts, XML defenses, mapping confirmation and duplicate/conflict checks under `AGENTS.md`.

Current support remains a limited tested file subset. Provider support must be evidence-based; do not label UtilityOS a certified Central Hudson connector before an authorized school installation validates actual exports.

### 6. Future connector architecture

A disabled external connector boundary may be developed for future approved acquisition. ENERGY STAR Portfolio Manager is a reasonable future target: EPA documents web services and Central Hudson publicly describes MyMeter-to-Portfolio-Manager transfer capabilities. Use the public evidence and limits in `docs/PROVIDER_FILE_WORKFLOWS.md` as planning context.

Live synchronization stays disabled until the school separately approves the transfer and confirms provider/account eligibility, meter coverage, fields, resolution, update recurrence, authentication, retention, revocation and fees. Preserve existing connection admission requirements, including consent, publication lag and failure behavior. A free/open API does not establish that a provider-specific transfer is free or authorized. The user requires no added recurring data-access fee. My360 portal scraping and undocumented API use remain out of scope.

## Confirmed school workflow facts

The relevant school water billing workflow is building-specific, with separately handled water bills/meters. Building, meter, account and provider identities remain separate concepts. Confirmed account/meter/building mappings should be reusable across future imports; a provider layout should be reusable across buildings when the document layout is the same. Preserve stable meter identity and relationship history, leaving shared meters unallocated until staff confirms a defensible mapping.

The recently supplied water-bill screenshots are reference evidence for semantics and layout planning only; they must not become production/private fixtures. Development uses synthetic examples.

Preserve distinct water invoice fields: service period, previous reading, present reading, billed consumption, current water charge, previous balance, payments, adjustments, current charges due and total due. Do not infer a measurement unit the source does not establish or derive authoritative historical quantities from bill chart graphics, payment stamps or handwritten annotations.

## Subsequent analytics slices

Broad Operational Analytics is no longer the immediate next priority. Effective utility rates, comparable-period trends, EUI, anomaly analysis and expanded Finance/Facilities dashboards remain useful subsequent slices unless needed to complete portable acquisition. The immediate priority is trustworthy data on another school-controlled machine with less repeated staff handling.

## Permanent contracts and verification

Defer to `AGENTS.md` and the relevant subsystem contracts rather than duplicating them here:

- Develop with synthetic data; never request school portal passwords or private bills. Staff handles authorized documents locally. Keep private workspaces outside Git and cloud-synced folders, and away from AI tools and developer access.
- Preserve original evidence, extraction provenance, immutable review/audit history and mappings. Keep invoice charges and measured usage separate, retain integer cents and decimal quantities, and fail closed on unsupported semantics. Preserve supply-only, delivered-fuel, shared-meter and invoice-month reporting contracts.
- Require staff review and explicit financial approval with acknowledgement and revision enforcement. Local extraction, mapping reuse, provider activation and acquisition never authorize automatic financial posting. Preserve Provider Studio's immutable versions and validation gates.
- Use fixed-schema, allowlisted privacy-safe diagnostics; private exports and backups remain with staff. Reproduce support failures synthetically or through authorized school IT.
- Do not introduce paid connectors by default or silently enable an external live service. Preserve local file intake without connectors and all school approval boundaries for external access.
- Do not weaken installation, backup, migration or rollback protections. Installation leaves private data untouched; version switches require backup, schema compatibility checks, tests and school approval. Migration is explicit; retain prior code and pre-upgrade backups for rollback into a separate recovery directory. Never build an unattended remote updater. Hash receipts establish integrity, not trusted provenance; releases remain unsigned pending a separately approved distribution/signing process.

For focused work, verify affected contracts and report exact outcomes without repeating historical audits. Use `python -m pytest -q` for backend tests and fresh external synthetic demo workspaces for import/browser checks. Exercise relevant desktop/mobile flows, downloads and logout; respect administration restrictions and report blocked checks.

For high-risk changes or release preparation, load `docs/VERIFICATION.md`, `docs/STAFF_INSTALL_AND_UPDATES.md`, `docs/RELEASE_AND_SIGNING.md` and other applicable guidance. Complete the required OS, dependency advisory, invoice correction/rebill, duplicate import, source retention, privacy, backup/restore and migration/rollback checks. Public publishing, school installation, external services and live data remain separate authorization decisions. Narrow work need not produce a release or unrelated changes; milestone guidance alone does not authorize implementation outside the user's current task.
