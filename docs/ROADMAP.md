# Development status and next milestones

## Current implementation

The existing local service now includes reviewed CSV/evidence-backed PDF/limited electricity XML entry, saved drafts, full-invoice correction and rebill history, cancellation, independent credits, current mapping edits, active-only reporting/exports, fixed diagnostics, browser backup download, stopped-app restore, explicit schema-1/2/3/4 upgrades, and source-only release verification. Native desktop/mobile browser verification runs directly on the development Mac.

The 0.3.0 readiness milestone adds interruption-safe source publication, an
append-oriented audit view, schema-3 provenance and migration coverage,
diagnostics for local IT, staff passphrase confirmation and deterministic
20-building campus tests. Named role enforcement remains deferred under the
single-operator boundary; the exact proposed role contract is documented.

## Milestone A: actual-computer verification — complete on the development Mac

Verified native launch, local authentication/cookies, CSV/XML/PDF review, approval and rejection, source/sample downloads, exports, logout, desktop and mobile layout, console/runtime health, and synthetic staff setup. Regressions found during verification were fixed. All runtime data and screenshots were kept outside source. This is a runnable software demonstration; no meeting or presentation materials were created.

## Milestone B: correction and maintenance engineering — implemented and tested

Completed and tested corrections/supersession, same-number supplier rebills, negative credits, multi-meter invoices, supply/delivery separation, mapping corrections with retained history, saved review revisions, backup/restore, explicit schema migration, and deliberate code-folder switching. Native macOS operation and an isolated wheelhouse install were exercised. See `VERIFICATION.md` for exact evidence and limitations.

**School pilot acceptance remains a school decision.** The school must approve trusted distribution, target-machine validation, dependencies/advisories, encryption, private storage and retention, access rules, and maintenance ownership. Finance must confirm current-charge/credit/rebill semantics; Facilities must confirm stable service points and physical coverage. Private records may be evaluated only by authorized staff in the school's installation. No school deployment or live records were used in this milestone.

## Milestone C: Intelligent Bill Intake — implemented and tested in 0.4.0

The 0.4.0 slice includes picker/drop/batch and explicit folder scanning, digital PDF extraction, two versioned layouts for each of five fictional providers, optional local English OCR, field evidence, drift handling and retained correction differences. A deterministic 28-document corpus and exact benchmark exercise those paths. Explicit monthly/delivery/irregular cadence powers a labelled experimental completeness view. Manual entry remains usable without OCR.

Private provider onboarding is implemented in 0.5.0 below. Richer table layouts, multilingual OCR and CSV mappings need a demonstrated use case and new independent synthetic cases. Measure saved time and real correction rates privately with school authorization before claiming broad automation. See `BILL_INTAKE.md` and `VERIFICATION.md`.

No utility connector, portal automation, paid service, CMD/OAuth, email integration, or cloud extraction is enabled. A future external integration requires school authorization and confirmed coverage, security, fees, and maintenance. File-only operation remains supported.

## Milestone D: Private Provider Onboarding — implemented in 0.5.0

Local staff can author bounded layouts from retained source candidates, validate
multiple approved PDFs, activate or retire immutable versions, and inspect drift
and correction counts. The dedicated support export previews exactly the
value-free JSON downloaded. Private journals survive backup/restore and checked
code-folder updates; corrupt templates fail closed while manual entry remains.
The independent 18-document fictional corpus and native desktop/mobile checks
are described in `VERIFICATION.md`. No real provider has been privately validated
by the developer, and these results are not general extraction accuracy.

Further local extraction work should start from a demonstrated independent
synthetic failure or a school-side summary under `PROVIDER_STUDIO.md`. Do not
repeat completed roadmaps as a presumed missing-feature checklist.

## Milestone E: shared access and reporting — conditional

Only pursue concurrent users after a school request and a design for identity, roles, HTTPS, concurrency, backups, and person-attributed audits. Current installations are independent and local.

The experimental completeness view requires confirmed cadence; it does not establish real coverage or an authoritative missing-bill claim. Fiscal budgets, normalization, calendarized consumption, carbon factors, and public aggregate reports remain future work with explicit assumptions and source provenance.

## Unverified external matters

Native Windows launch/ACLs, the actual staff workstation and browser, Finder quarantine/signing/distribution, school retention and maintenance policy, provider-specific PDF/XML compatibility, utility availability and fees, and private-record accounting validation remain unverified. Runtime advisory results are dated and must be repeated before installation.
