# Reproducible local update rehearsal

This developer tool runs the release-switch workflow on newly created synthetic
data. It is not a staff installer, background updater, or authorization to open
school records. It accepts two separately installed, trusted source releases
and a **new** external working directory. Existing work directories are refused.
It never searches for or stops an existing application. All processes it stops
were created by that invocation, and all demo servers are stopped on completion.

## Prepare the two releases

Retain the old source package, manifest and environment. Build a new source ZIP
with `scripts/release.py` outside the repository. Verify its origin through the
approved distribution process and its content with the trusted verifier.
Extract into a different code folder, preserving executable modes. Install each
folder's dependencies using its own `scripts/setup.sh` or `scripts/setup.ps1`.
An approved target-specific wheelhouse permits offline installation. The source
package does not contain Python, dependency wheels, OCR models or staff data.

Run the candidate's full tests and existing native synthetic checks before
accepting a release. A copied `.venv` is not a fresh-install test. Do not replace
the running code folder or fetch a moving Git branch on an employee's machine.

On a Mac development installation with native Chrome and the existing Playwright
development dependency, invoke the new release's interpreter:

```sh
/approved/new-code/.venv/bin/python /approved/new-code/scripts/rehearse_update.py \
  --old-code /approved/old-code \
  --new-code /approved/new-code \
  --work-dir /private/tmp/utilityos-new-update-rehearsal \
  --browser-executable '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
```

Use real approved code paths. Every run needs a different work directory.
Symbolic links in the work path are refused; on macOS use `/private/tmp` rather
than its `/tmp` symlink. Windows uses each folder's `.venv\Scripts\python.exe`
and its approved browser executable. Windows execution remains unverified until
an actual Windows host completes the native checks; a Python test on macOS is
not evidence of Windows acceptance.

## What the script verifies

1. Both source folders match their manifests and have their own installed Python.
2. The candidate starts a fresh demo. Desktop/mobile UI, source PDF rendering,
   original download, ledger download and logout work before old data is opened.
3. The old release creates its own separate demo. A synthetic PDF is imported
   through the UI and retained pending review. Seeded approved invoices populate
   the ledger. A stopped-app maintenance command is refused while it is running.
4. The script stops that old process, runs the old `check`, and creates a backup
   with the old version. It preserves the backup and records its hash.
5. Equal schemas require no migration. Different schemas first exercise the new
   code's incompatible-schema refusal without changing the database, then invoke
   `migrate --confirm-migrate` explicitly on this synthetic workspace only.
6. The new `check` verifies integrity, sources, extraction/provider history and
   audit chain. The rehearsal compares all previously present non-audit tables,
   stable settings and source hashes. Audit events legitimately advance during
   backup/migration; their correctness is checked by the application.
7. The candidate opens the same workspace. Browser downloads of the ledger CSV
   and original PDF match the old version exactly. Desktop/mobile navigation,
   source rendering and logout are checked again.
8. The old version restores the pre-switch backup into a **different** rollback
   directory. The old schema, retained rows, settings, originals and browser
   downloads are verified. The upgraded workspace and its later history remain.

`result.json` records completed application checks and their status. It is
written before the browser driver finishes shutting down; inspect the command
exit status as well. The final Mac acceptance runs completed those checks but
required cleanup of their own idle Playwright drivers and exited 1. Unattended
runner shutdown remains unverified; see `VERIFICATION.md`. Screenshots,
synthetic ledger/source downloads and synthetic server logs remain beside it.
On a failure, inspect this disposable local evidence; the script does not retry
by overwriting data, automatically roll back, or delete the failed workspace.
The result is development evidence, not the application's support-bundle schema.
Do not adapt this script to receive private data through a developer/AI session.

Source manifests verify integrity, not trusted authorship or installed dependency
provenance. Tests use installed native Chrome, isolated browser contexts and real
loopback HTTP/cookies/downloads. They do not use staff browser sessions. They do
not establish cold target-machine readiness, downloaded-app signing acceptance,
real-provider accuracy or shared multi-user deployment.

## Future supplier acquisition

Plan each supplier route from its actual documented capability:

| Available supplier route | Preparation now | Information needed from supplier/IT |
|---|---|---|
| Original PDF or structured billing API | Keep original bytes, revision identities and pending review boundary | Public API specification, institutional-account coverage, sandbox, authorized scopes, invoice/PDF endpoints, history, limits and fees |
| Green Button CMD | Preserve the separate meter-reading import contract | Actual function blocks/scopes, utility registration, authorization/revocation and whether billing totals are supplied |
| Scheduled CSV/PDF/EDI delivery | Exercise local folder scan and synthetic duplicates/rebills | Format specification, delivery method and cadence, sample fictional exports and correction identifiers; each new format needs an adapter |
| Portal download only | Keep manual file download plus picker/drop usable | Written automation permission, supported login/MFA flow, session lifetime and change notification; unattended operation is not assured |

Do not ask a student/developer to obtain school passwords or real bills. Staff
can validate authorized records locally; developers use supplier documentation,
public/synthetic examples or an approved synthetic sandbox. Credential storage,
retry scheduling, revocation and connector support ownership require a concrete
school-approved design once the route is known. None is enabled by this release.

Source note (checked 2026-09-08): the [US Department of Energy](https://www.energy.gov/data/green-button)
distinguishes manual Download My Data from consent-based automatic Connect My
Data. The [Green Button Alliance function blocks](https://www.greenbuttonalliance.org/cmd-function-blocks)
describe usage and billing capabilities separately. Supplier support for one
capability does not establish support for the other.

Once suppliers are known, staff/IT should record supported account classes,
official billing/PDF APIs, Green Button CMD scopes, scheduled file delivery,
consent, authentication, history, publication lag, corrections, fees and support.
The existing admission requirements in `FREE_DATA_AND_SOURCES.md` still apply.

Prefer approved original-file or structured-data delivery that can feed the
retained-source/review boundary. PDF files and canonical CSV already use that
boundary. Supplier CSV mappings, API/EDI adapters, credentials, scheduling and
automatic folder intake are future work. Green Button usage coverage does not
establish complete financial-invoice coverage. Browser download automation is
supplier-specific and needs explicit permission and a reauthentication strategy.

No connector is enabled by the update rehearsal. Until a supplier-specific
decision, keep picker/drop and explicit local-folder scanning available. Future
retrieval must stage drafts, preserve original bytes and revisions, detect
duplicates/rebills and leave financial approval with staff. Use synthetic source
simulators for connection failures; production validation stays on school systems.

## Distribution and everyday use

The dashboard is the browser interface to a local service. For an initial
single-operator school installation, IT obtains an approved immutable source
release, installs into its own versioned code folder and prepares Python and
dependencies. The operator launches the local application and opens its
loopback dashboard. Staff records and backups stay in a separate school-owned
data folder, retained across software versions. Daily use requires no Git.

GitHub can distribute reviewed source releases after publishing is authorized;
`git pull` on a moving branch is not the staff update procedure. Current launchers
still need Python and dependencies and are not standalone `.app`/`.exe`
installers. A future native installer must preserve the same data separation,
explicit migration, backup and rollback procedure and pass target-OS checks.

Separate computers currently have separate ledgers and do not synchronize. If
several people must work on one ledger, choose a school-managed shared service
only after designing identity, roles, TLS, concurrency, backup and audit
attribution. Exposing the current loopback server is not a completed multi-user
deployment. See `STAFF_INSTALL_AND_UPDATES.md` for the current installation path.
