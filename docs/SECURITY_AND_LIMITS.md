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

The diagnostic export uses an explicit allowlist: app version, schema version, mode, broad runtime version/platform, and fixed capability flags. It excludes account and building labels, invoice data, readings, amounts, filenames, paths, source text, logs, arbitrary exception messages, and secrets. Staff can preview the JSON before downloading it.

This restricted report helps diagnose version and configuration problems. Data-dependent failures may need school IT to examine the private installation and create a synthetic reproduction. Full backups, raw logs, screenshots of private invoices, and the private ledger export must stay inside school-approved channels.

A redaction promise is weaker than a bounded diagnostic schema. Future logging changes require tests that insert sentinel names, account numbers, filenames, amounts, paths, and secrets and verify that none appear in the export.

## Before real bills

School IT should approve the data location, encryption, installer, dependencies, local browser behavior, patch ownership, and backup retention. Finance and Facilities should confirm bill-date conventions, account aliases, meter mapping, current-charge treatment, and what staff may share externally. The correction/supersession workflow is implemented and tested synthetically; Finance must confirm its treatment of actual supplier credits and rebills privately.

Run a current dependency advisory scan with approved tooling and resolve relevant issues before staff deployment. A live PyPI advisory scan on 2026-09-06 found no known vulnerabilities after the documented dependency updates. Native macOS launch and isolated wheelhouse installation were tested. Windows installation remains unverified; repeat advisory and target-machine checks before staff deployment.

## Other release gaps

There is no automated retention purge, backup encryption, credential recovery/change UI, budget module, school-wide coverage inventory, expected-bill schedule, supplier CSV mapping UI, general PDF extraction, or current-carbon-factor service. Approved financial payloads remain immutable; explicit corrections, supersession, cancellation, and saved revisions preserve private audit history. Mapping changes are recorded separately and affect current reporting across invoice months. Source files no longer referenced by a restored older database may remain locally as retained artifacts; cleanup needs an explicit retention policy.

The original 0.1.0 build environment required a transport bridge. The 0.2.0 development Mac was verified through native Chrome on loopback with actual cookies, CSP, downloads, imports, desktop/mobile controls, logout, and backup recovery. No transport bridge, mocked API, staff browser profile, or weakened administration policy was used. School target-machine acceptance remains separate.


Browser backup creation and download require the local authenticated session; creation also requires CSRF, same origin, and private-content acknowledgement. Saved draft/history reasons and mapping labels are private and never enter diagnostics. Failed CLI archive/storage operations return bounded error codes rather than arbitrary exception content. Backups are published only after successful creation. The explicit schema upgrade preserves a pre-upgrade backup; no silent or remote updater is present.
