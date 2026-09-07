# Security, privacy, and known limits

## Intended users and information

A designated staff operator maintains private utility records on an approved school computer. The student developer maintains synthetic fixtures and source code on a separate development computer. The school retains portal access, account authorization, source documents, the local app passphrase, backups, and private exports.

The application never asks for a utility portal password. A local app passphrase protects the browser session; it is a different credential created during staff setup. Existing authorized staff remains responsible for obtaining documents through approved channels.

## Implemented controls

The server binds to `127.0.0.1`. Host allowlisting, same-origin checks, a per-session CSRF token, HttpOnly/SameSite cookies, limited login attempts, and short sessions protect the local web interface. Passwords are stored using salted PBKDF2-SHA256. The source download endpoint requires an authenticated session and returns a download attachment with MIME-sniffing disabled.

The browser receives a restrictive content security policy and locally served assets. Uploaded content is escaped for UI display; CSV exports neutralize spreadsheet-formula prefixes. XML parsing rejects dangerous entity/DTD content. Size and record limits bound individual imports.

Runtime data is outside the source folder, and demo/staff mode mismatch is rejected. POSIX installations use restricted file and directory permissions. Staff path checks reject common cloud-synchronized locations, although these checks cannot establish an organization's complete backup or synchronization policy.

## Meaningful limits

The application is a prototype with targeted tests, not an independently audited security product. It has no application-level database or backup encryption. Staff machines require school-managed disk encryption, login controls, endpoint security, and an approved backup destination. Windows ACL behavior has not been independently tested in the build environment.

An authorized operating-system user or installed application with access to the private data directory can read its files. Installing an application release also grants that code the ability to process its stored records. A source/data directory split cannot remove this trust requirement. School IT should review changes, verify dependency provenance, approve distribution, and apply egress restrictions when needed.

The current release is unsigned. The release manifest detects changed or incomplete files after its trusted creation, while authenticity depends on a separate trusted distribution/signature process. Do not treat a manifest delivered alongside unknown executable code as proof of a trusted publisher.

The single-operator model provides no per-person role separation, multi-factor login, school SSO, tamper-proof audit trail, or remote support channel. Staff should stop the service when leaving the workstation. A shared server or public URL is outside this release's supported deployment.

## Debugging without private records

The diagnostic export uses an explicit allowlist: app version, schema version, mode, broad runtime version/platform, fixed capability flags, and bounded operational health categories. It excludes account and building labels, invoice data, readings, amounts, filenames, paths, source text, logs, arbitrary exception messages, and secrets. Staff can preview the JSON before downloading it.

This restricted report helps diagnose version and configuration problems. Data-dependent failures may need school IT to examine the private installation and create a synthetic reproduction. Full backups, raw logs, screenshots of private invoices, and the private ledger export must stay inside school-approved channels.

A redaction promise is weaker than a bounded diagnostic schema. Future logging changes require tests that insert sentinel names, account numbers, filenames, amounts, paths, and secrets and verify that none appear in the export.

## Before real bills

School IT should approve the data location, encryption, installer, dependencies, local browser behavior, patch ownership, and backup retention. Finance and Facilities should confirm bill-date conventions, account aliases, meter mapping, current-charge treatment, and what staff may share externally. The correction/supersession workflow is implemented and tested synthetically; Finance must confirm its treatment of actual supplier credits and rebills privately.

Run a current dependency advisory scan with approved tooling and resolve relevant issues before staff deployment. A live Python-package advisory scan on 2026-09-07 found no known vulnerabilities in the tested application/development/optional-OCR environment. Native libraries and OS components require separate review; see `DOCUMENT_EXTRACTION_DEPENDENCIES.md`. Native macOS launch and isolated wheelhouse installation were tested. Windows installation remains unverified; repeat advisory and target-machine checks before staff deployment.

## Other release gaps

There is no automated retention purge, backup encryption, credential recovery/change UI, budget module, authoritative school-wide coverage inventory, supplier CSV mapping UI, general-purpose PDF extraction, or current-carbon-factor service. Approved financial payloads remain immutable; explicit corrections, supersession, cancellation, and saved revisions preserve private audit history. Mapping changes are recorded separately and affect current reporting across invoice months. Source files no longer referenced by a restored older database may remain locally as retained artifacts; cleanup needs an explicit retention policy.

The original 0.1.0 build environment required a transport bridge. The 0.2.0 development Mac was verified through native Chrome on loopback with actual cookies, CSP, downloads, imports, desktop/mobile controls, logout, and backup recovery. No transport bridge, mocked API, staff browser profile, or weakened administration policy was used. School target-machine acceptance remains separate.


Browser backup creation and download require the local authenticated session; creation also requires CSRF, same origin, and private-content acknowledgement. Saved draft/history reasons and mapping labels are private and never enter diagnostics. Failed CLI archive/storage operations return bounded error codes rather than arbitrary exception content. Backups are published only after successful creation. The explicit schema upgrade preserves a pre-upgrade backup; no silent or remote updater is present.

## 0.3.0 hardening

Audit events now use a verified hash chain and database rules rejecting ordinary
updates/deletes. This is append-oriented history, not proof against an OS owner
rewriting the full installation. Actor context does not provide per-person
attribution. Named roles are explicitly deferred with a proposed permission
matrix in `ACCESS_AND_CONFIGURATION.md`; sensitive staff corrections/cancellation
require the current passphrase again, and maintenance stays behind stopped-app
OS access. No user-management or portal-secret system was added.

Atomic non-overwriting source publication prevents killed imports/restores from
truncating retained originals. Damaged drafts are isolated and require explicit
recovery/review. Diagnostics includes coarse disk, permission, backup-location,
port, audit and unsigned-manifest checks; tests exclude synthetic secret/config
sentinels from those reports and operational exports. Release and Git index
checks reject known runtime/credential paths. Private backups intentionally
retain the app's password hash and records; future integration credentials must
remain in an OS-managed store, subject to separate authorization.

Read `OPERATIONS.md` for actual failure semantics and `RELEASE_AND_SIGNING.md`
for researched signing options and the limits of the unsigned source release.

## 0.4.0 document boundary

Source text, raw/normalized extraction, coordinates and human differences are
private workspace data. Diagnostics never serializes them. The separate local
quality export selects fixed provider/template/field keys and counts only; it
requires an authenticated deliberate download. Inbox paths remain private settings.
Rendered page responses require authentication and use no-store caching.

The PDF worker has bounded bytes/pages/pixels/text, one-worker concurrency and a
parent deadline. It suppresses exception text and closes in-memory page images.
This is process isolation for reliability, not a complete OS security sandbox.
The reviewed OCR model is hash/size checked, never downloaded automatically, and
not included in utility backups. The optional native engine has dependencies
beyond what pip-audit inspects; review the documented version/model restrictions
and OS patch status before use with private files. No document URLs, PDF scripts,
Tesseract network image inputs or external extraction endpoints are invoked.


## 0.5.0 private provider setup and support

Provider definitions contain private labels and locators and stay in the private
workspace journal. They are included in private backups, excluded from source
releases and never serialized into ordinary diagnostics. All setup, source
observation, validation and lifecycle routes use the existing authentication,
same-origin, CSRF and resource limits. Definitions admit bounded typed rules,
not code, SQL, shell or unrestricted regular expressions. Ambiguous matches
abstain; active layouts produce candidates without financial approval authority.

The dedicated Provider Extraction Support Bundle is constructed through the
positive schema in `provider-support-schema.json`. It admits anonymous IDs and
hashes, fixed field/rule/evidence/error categories and counts. It excludes names,
source text, coordinates, filenames, paths, invoice dates, account/meter IDs,
quantities, demand, charges, balances and credentials. The exact downloaded JSON
must first be previewed and acknowledged. There is no optional label-text export
in this release: local label strings cannot reliably be classified as public.
Synthetic sentinel tests cover both stored private values and all export fields.
Hashes and anonymous local identifiers can correlate reports; this is a bounded
technical report, not a guarantee of anonymity against every outside dataset.

Registry integrity failures disable local templates while preserving manual
entry. Maintenance refuses corrupt definitions. The journal and audit chain
protect ordinary history and detect corruption; they do not establish authenticity
against an OS owner who rewrites all records and code. No automatic rule tuning,
private-data upload, remote support endpoint or model service is installed.
