# Codex master prompt: complete the staff-local SKS UtilityOS pilot

You are continuing an existing working starter for The Storm King School. Act as the lead engineer and product builder. Inspect what is already implemented, plan the most useful next work, then execute it through tests and a usable local demonstration. Proceed on tasks that can be completed with synthetic data; reserve questions for genuine school decisions or unavailable capabilities.

## Workspace scope and current engineering status

This workspace is exclusively for SKS UtilityOS software development, testing, technical documentation, and release engineering. Do not create or restore meeting briefs, presentations, procurement materials, or stakeholder proposals unless explicitly requested. The removed meeting brief is intentional.

Version 0.2.0 continues the original implementation. Milestone A and the development portion of milestone B have been implemented and verified on the development Mac: native browser flows, invoice corrections/rebills/cancellation, saved draft history, mapping edits, backup recovery, explicit schema migration, and operator-controlled code-folder switching. Read `docs/VERIFICATION.md`, `docs/CHANGELOG.md`, and the actual tests before deciding more work is needed. School acceptance and real-data validation are still separate external decisions. The next optional entry-effort milestone needs a demonstrated synthetic-format use case; do not infer a missing feature from the historical priority list below.

## Situation and desired result

The school has multiple buildings with separate electricity, water, heating, and other utility services. Finance and Facilities want one place to see reviewed invoices, costs, and consumption. The student developer will have no utility portal access and should receive no school passwords or private bill database.

The product must work on a school-controlled local computer. Staff supplies authorized files and confirms their interpretation. The student develops with synthetic examples, publishes reviewable code releases, and receives a deliberately restricted diagnostic report when staff requests help. The school chooses whether to install each update.

Complete a reliable local pilot before chasing automatic feeds. Aim for a workflow that a staff member can demonstrate and maintain: start the app, import a document, reconcile its fields, review warnings, approve it, inspect the updated ledger, export a private report, make a backup, and restore a test workspace.

## Read first

Read `AGENTS.md`, `README.md`, `.agents/skills/local-utility-engineering/SKILL.md`, and `docs/ROADMAP.md`. Inspect the actual code, tests, and dependency files. Read the architecture, private-support, and free-data documentation when working in those areas. Existing documentation describes the build environment's limitations honestly; validate those claims against the running app.

You may use relevant installed engineering, testing, frontend, database, and security skills. Review additional skill instructions and open-source licenses before installing anything. Prefer project-local development dependencies. Do not change global Codex settings, weaken machine permissions, add accounts, purchase services, or expose a server publicly.

## What currently exists

Version 0.2.0 uses FastAPI, SQLite, defusedxml, and native browser ES modules. There is no Node build or cloud service. Demo and staff databases live outside the project folder, and mode mismatch is rejected. Authentication, host/origin checks, CSRF checks, immutable source storage, local diagnostics, backup/restore, and source-release verification have initial tests.

The app supports canonical CSV bills, PDF attachment with manual field entry, and a limited Green Button Download My Data XML importer for forward delta electricity energy. Staff review precedes approval. Invoice charges and measured usage stay separate. Synthetic fixtures include separate supplier charges, estimated readings, delivered heating fuel, and an abnormal water bill.

Use this implementation as the starting point. Choose a different component when there is a clear benefit and preserve the working contracts through tests. A full rewrite, a large EMS fork, a cloud deployment, and a commercial aggregator are unnecessary prerequisites.

## First execution pass

Run the existing test suite and start a fresh disposable demo on the user's actual computer. Verify native browser navigation, cookies, logout, original-file downloads, exports, and the main UI at desktop and mobile widths. The original build environment used a local HTTP bridge; native Chrome verification was subsequently completed on the development Mac for 0.2.0. Repeat affected flows against the current code and intended staff machine.

Review any concrete failures, fix them, and continue implementation. Produce a short plan organized by user-visible outcomes. Prefer one complete useful release over disconnected backend stubs or a static dashboard.

## Highest-priority improvements

### 1. Make local installation and maintenance practical

Confirm the user's actual operating system and available Python. Make launch, stop, first staff setup, backup, and a version update straightforward for a school IT member. Test the supplied launch scripts; improve them or create an offline-friendly packaged app where this reduces maintenance without introducing license fees. Explain any Apple/Windows signing or distribution requirement and its cost before choosing it.

Keep application code and staff records physically separate. An update should stage a new code release, verify a trusted source and file integrity, create a consistent backup, check schema compatibility, run smoke tests, and allow a deliberate switch or rollback. Do not build an unattended remote updater. Test restoration using a disposable workspace and preserve any existing data.

### 2. Preserve and extend trustworthy bill corrections

The staff-visible correction and supersession workflow is implemented in 0.2.0. Inspect and preserve its contracts before extending it. Preserve the original source and prior reviewed version. Clearly define cancellation, replacement, credits, rebills, and which version contributes to reporting. Avoid silently editing history or counting both an original invoice and its replacement.

Extend tests to cover the same invoice number being rebilled, a credit-only document, overlapping corrected periods, multiple meters on an invoice, and separate supply/delivery accounts. Show useful explanations in the UI. Add metadata-editing and mapping correction where needed so staff can fix a building label or confirmed service relationship without modifying database files.

### 3. Reduce entry effort while keeping records local

Improve the canonical CSV workflow with preview and reusable column mappings when a real synthetic-format use case supports it. Add an optional local import folder only after designing file completeness checks, duplicate protection, clear failure status, and explicit staff review. A folder watcher does not download invoices by itself.

PDF entry currently requires staff transcription. Explore a local, permissively licensed text parser for text-based PDFs and provider-template adapters. Keep extraction reviewable and preserve source-to-field evidence. Reject unsupported formats cleanly. Use synthetic examples now; ask school IT to validate templates privately against actual files later.

Treat scanned PDFs as a separate future capability. Evaluate local OCR accuracy, installation burden, license, and resource use before adding it. No cloud OCR or metered model API may receive school bills. Do not advertise general automatic bill extraction until varied representative test cases support the claim.

### 4. Improve useful reporting and support

Keep invoice-month charges understandable. Add the basic filters, original-source links, exports, and selected building/meter history that Finance and Facilities need. Preserve full precision and correct negative-credit charts. Label delivered fuel as purchased volume and keep units separate.

Define source coverage before adding missing-bill or campus-total claims. A missing expected invoice needs a staff-confirmed active account and expected cadence. A percentage change requires comparable coverage and periods. Any future normalization, carbon calculation, or calendarization must expose assumptions and source factors.

Enhance debugging through bounded, fixed error codes and schema-validated diagnostics. Test that identifiers, source names, quantities, charges, paths, account numbers, and secrets cannot enter a shared report. Staff should preview the diagnostic JSON and explicitly export it. When private data is needed to investigate a problem, keep the inspection with authorized school IT and reproduce the issue with synthetic data.

## Green Button and connection policy

Green Button is an open, royalty-free implementation standard. Individual utility access and third-party services can have their own onboarding, availability, security requirements, or charges. The current guaranteed application-fee-free path is a file obtained by authorized staff and parsed locally.

Keep Connect My Data/OAuth, utility portal automation, commercial aggregators, email integrations, live metering, and ENERGY STAR cloud synchronization disabled. Implement one only after the school confirms the actual provider and account class, authorizes the transfer, and confirms fees in writing. The user requires no added recurring data-access fee.

For XML extensions, resolve the correct ReadingType for each MeterReading. Validate commodity, unit, power multiplier, direction, accumulation behavior, duration, and quality. Retain UTC timestamps and interval semantics, protect the XML parser, and test duplicates, revised records, overlaps, daylight-saving boundaries, and unsupported data. No certification or universal utility-compatibility claim is permitted without corresponding evidence.

## Data boundary

Use fictitious building and account labels until staff works inside its own installation. Never request portal passwords, full staff backups, production database copies, or confidential invoices in this conversation or the development repository. Do not attach AI coding tools to the staff data directory under the current authorization.

The application process necessarily accesses its own stored records. School IT must review the source/dependencies and trust each release. Data/code separation and an allowlisted support report reduce accidental disclosure; they do not remove the trust involved in installing executable code. Document this plainly and support the school's egress and endpoint controls.

## Testing and finish

Test the financial calculations, record lifecycle, imports, authorization, privacy, and operational procedures. Use actual browser evidence for the interface. Keep temporary screenshots, logs, and private runtime data outside the repository. Run a current dependency vulnerability check when network access is available and state any unverified advisory status.

Finish with a runnable demonstration, a concise changelog, exact test outcomes, an updated staff guide, a source-only release, and a clear list of remaining school decisions. Distinguish tests run from tests merely provided. Keep every development demonstration fully synthetic. Continue until the chosen pre-portal milestone is complete or a genuine external blocker is reached.
