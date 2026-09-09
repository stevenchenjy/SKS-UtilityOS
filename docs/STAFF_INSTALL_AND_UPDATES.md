# Local installation, updates, and recovery

The current working candidate is **0.6.0-rc1**, using the same schema 5 as
0.5.0. A 0.5.0 workspace needs a compatibility check and backup, not a migration.
The commands below retain the established 0.5 installation/maintenance contract;
choose the separately prepared candidate folder for a candidate rehearsal.
The reusable [synthetic update rehearsal](UPDATE_REHEARSAL.md) exercises this
sequence and a separate rollback without accepting existing staff data.

## Ownership and operating boundary

Use a school-controlled encrypted disk, approved staff-only OS account, and a named IT maintainer. The student development workspace contains synthetic data only. Private records, source files, passphrases, and backups stay with school staff. No portal credentials are used. Installing a code release grants it access to the selected local records; source/data separation does not eliminate that trust decision.

The current service supports one operator on the same computer at `127.0.0.1`. Separate installations do not synchronize. The terminal remains open while the service runs; Ctrl+C stops it. Use **Lock workspace** to revoke the current browser session. A shared server, unattended updater, remote administration, and private data in AI tools are outside this release.

Version 0.5.0 uses schema 5. macOS arm64 launch/setup, native Chrome, synthetic staff setup, backup recovery, and version switching were tested. Windows launchers and ACLs still require native target validation. School IT approval of the actual staff machine remains outstanding.

## Install into a separate code folder

1. Obtain the source ZIP through the school's approved distribution process. Verify who supplied it separately from its integrity manifest. The release is unsigned; no Apple/Windows certificate or paid distribution mechanism has been chosen.
2. Inspect the code changes, dependency decisions, release notes, and verification results. Run `python scripts/release.py verify /path/to/SKS-UtilityOS-0.5.0.zip` using a trusted copy of the verifier. A matching hash alone does not establish trusted authorship.
3. Unpack into a new code folder. Keep every private data directory and backup outside it and outside cloud-synchronized folders. Do not overwrite the previous release.
4. Use an approved Python 3.11+. Run `bash scripts/setup.sh` on macOS, or the supplied PowerShell setup through normal school policy. Setup writes only the new folder's `.venv`. It never selects or opens a staff workspace.
5. Run a fresh synthetic demo and verify the browser. Supply the same explicit `--data-dir` and `--port` when repeating maintenance or launch commands.

The source archive preserves executable mode for `.command` and `.sh` files. macOS Terminal launch was verified; Finder quarantine/Gatekeeper behavior for a school-distributed downloaded archive remains an IT acceptance check. Do not weaken operating-system security controls to open a release.

### Offline dependency installation

On a compatible approved staging machine, download reviewed wheels:

```sh
python -m pip download --only-binary=:all: -r requirements-bootstrap.txt \
  -r requirements.txt -c constraints-tested.txt --dest /approved/wheelhouse
```

Transfer the wheelhouse through the school's approved process, then run:

```sh
bash scripts/setup.sh /approved/wheelhouse
```

Windows uses `scripts/setup.ps1 -Wheelhouse C:\approved\wheelhouse`. The offline path uses `--no-index`, `--find-links`, wheel-only installation, and disables pip's version check. Obtain wheels for the target Python/OS, review their provenance, and run a current advisory scan before transfer. The developer's clean macOS installation and regression tests used an external wheelhouse. Wheels are not bundled in the source release.

## Optional local OCR preparation

Base setup provides digital PDF extraction and source previews. OCR is optional;
without its library or reviewed model, a scan remains a manual draft. Review
`DOCUMENT_EXTRACTION_DEPENDENCIES.md` before enabling the experimental scan path,
including its older bundled native engine and strictly pinned-model restriction.
The tested Apple Silicon OCR wheel requires macOS 15+ and Python 3.13; other
platforms need separate wheel/native verification. Digital rendering's tested
Mac wheel requires macOS 13+. No GPU or model server is used.

On an approved compatible staging computer, collect the optional wheels:

```sh
python -m pip download --only-binary=:all: -r requirements-ocr.txt \
  -c constraints-tested.txt --dest /approved/wheelhouse
```

Manually obtain the pinned public English model and its Apache-2.0 license from
`DOCUMENT_EXTRACTION_DEPENDENCIES.md` through the approved software-distribution
process. It is 4,113,088 bytes; model revision and SHA-256 are documented there.
UtilityOS has no automatic model downloader. Transfer the model, licenses and
reviewed wheelhouse for offline installation, then run from the new code folder:

```sh
.venv/bin/python -m pip install --no-index --find-links /approved/wheelhouse \
  --only-binary=:all: --disable-pip-version-check \
  -r requirements-ocr.txt -c constraints-tested.txt
.venv/bin/python scripts/prepare_ocr.py \
  --model-file /approved/staging/eng.traineddata \
  --destination /approved/local/utilityos-models
.venv/bin/python run.py demo --data-dir /approved/local/new-synthetic-demo \
  --ocr-model-dir /approved/local/utilityos-models --open
```

Preparation verifies size/hash and atomically copies the public model. It never
opens a utility workspace or changes installed code. Keep the external model
folder under IT control; do not replace it with arbitrary/custom traineddata.
The app performs no fine tuning and stores no page-image/model cache. Supply the
model argument again on each launch (the `.command` launcher forwards it). Model
assets are not in private backups; retain their reviewed software distribution
separately. Base digital dependencies add about 48.4 MB, optional OCR about 9.8 MB
plus the 4.1 MB model, excluding interpreter, documents, backups and staging.
A source-only release contains no weights or wheels; keep dependency licenses and
corresponding LGPL source availability with a redistributed optional wheelhouse.

## First staff setup

Run `Launch-Staff.command` or `.venv/bin/python run.py staff --open`. The first run requests a local application passphrase of at least 12 characters, entered twice. This must be distinct from portal passwords. Do not send it to the developer. The browser opens only after server startup; a busy port reports a fixed error and can be changed with `--port 8878`.

Default data locations:

| OS | Staff data directory |
|---|---|
| macOS | `~/Library/Application Support/SKS-UtilityOS/staff` |
| Windows | `%LOCALAPPDATA%/SKS-UtilityOS/staff` |
| Linux | `~/.local/share/SKS-UtilityOS/staff` |

Use `--data-dir /approved/local/workspace` to choose another approved location. The limited cloud-folder name checks cannot establish the school's complete synchronization policy. Demo and staff directories are separate and a mode mismatch is rejected.

## Same-schema update

1. Review and prepare the new code folder without opening private records. Its declared schema must match the existing workspace.
2. Lock the browser and stop the old application. Using the current release, create a backup:

   ```sh
   .venv/bin/python run.py backup --mode staff --data-dir /approved/local/workspace
   ```

3. Using the new release, run `python run.py check --mode staff --data-dir /approved/local/workspace`. This verifies database integrity, foreign keys, and retained source hashes. It does not modify records or create a missing workspace.
4. Deliberately launch the new release against that directory. Verify login, an existing original download, ledger export, diagnostics, and backup. Confirm active invoice versions and totals before accepting the switch.
5. Retain the old code and backup through the acceptance period. A same-schema rollback may run the retained old code against compatible current data after stopping the new app; if rolling data back too, restore the pre-update backup deliberately. Later entries need recovery or re-entry.

Maintenance commands require the workspace to be stopped. The browser can create a consistent backup while its app is running. No scheduled download, silent migration, or unattended switch is implemented.

## Upgrade schema 1, 2, 3 or 4 to schema 5

0.5.0 implements ordered migrations from schemas 1, 2, 3 and 4 through schema 5. Startup never migrates.
After source/dependency review, synthetic rehearsal and school approval:

1. Stop the old app. Back it up with its own version and retain the old code and
   environment. Older code cannot open schema 5.
2. From the separately prepared 0.5.0 folder, run:

   ```sh
   .venv/bin/python run.py migrate --mode staff \
     --data-dir /approved/local/workspace --confirm-migrate
   ```

3. The command locks the stopped workspace, checks integrity and retained sources,
   and creates another backup in the original schema. It applies every registered
   step in one transaction on a copy, checks integrity/foreign keys/audit history,
   then atomically switches the database. Original source bytes are unchanged.
4. Run `check`, launch 0.5.0 and verify totals, versions, original downloads, audit,
   exports and backup before accepting the switch. Historical importer versions
   and actor identities are explicitly marked unrecorded/unknown.

Schema 3 adds the append-oriented audit chain and document importer version; it
was not introduced just to test migrations. Schema 4 adds immutable extraction/review snapshots, intake attempts and expected cadence/history without reparsing old PDFs. Schema 5 adds the private provider journal without changing historical extractions. Frozen schema-1/schema-2/schema-3/schema-4 fixtures
and synthetic future-step tests exercise the migration runner. Unregistered
paths fail before switching any data.

Rollback requires the retained old release and its compatible pre-upgrade backup
in a **new recovery directory**. Stop the new app, restore using the old version's
commands, and verify that recovered installation before switching to it. Preserve
the upgraded workspace for recovery of later entries. There is no schema downgrade
or automatic merging of post-backup work. See `OPERATIONS.md` for interruption
states and audit continuity across restore.

## Backup and restoration

**Privacy & support** previews diagnostics separately from the private ledger and backup controls. A backup requires acknowledgement and includes the SQLite database, local password hash, original source files, saved drafts, invoice history, mapping history, extraction evidence, reviewed differences, intake status, cadence settings, and all private provider/layout/validation/status history. It is retained in the workspace's `backups` folder; **Download private backup ZIP** downloads an additional copy through the native browser. Treat both as confidential and keep browser downloads under approved retention rules.

Backups use a consistent SQLite snapshot and content hashes. A failed write does not expose an incomplete archive as a completed backup. Backup and restore share limits of 5,000 members and 1 GiB expanded size; larger workspaces need an explicitly reviewed extension. Archives have no application-level encryption.

To restore an existing healthy compatible workspace, lock its browser, stop the app, and run:

```sh
.venv/bin/python run.py restore --mode staff \
  --data-dir /approved/local/workspace \
  --archive /approved/backups/private-backup.zip --confirm-restore
```

The command validates mode/schema, paths, duplicate members, hashes, database integrity, foreign keys, and referenced sources before replacing anything. It creates a safety backup of the existing healthy workspace, adds immutable source files, then replaces the database. The backup's passphrase hash is restored, so use the passphrase in effect when the backup was made.

If the existing workspace is damaged, preserve it and recover into an explicitly new directory:

```sh
.venv/bin/python run.py restore --mode staff \
  --data-dir /approved/local/new-recovery-workspace \
  --archive /approved/backups/private-backup.zip \
  --confirm-restore --restore-to-new-workspace
```

The recovery option refuses an existing destination. Select that new directory when checking and launching the recovered app. Reopen the browser and log in; previous browser sessions are not restored. Verify invoice versions, totals, quantities, and original downloads. Never restore over a running app.

Restoring an older snapshot can leave immutable source files that are no longer referenced by the database. Reimport reuses such a file only when its bytes match its content hash; conflicting bytes are rejected. Retention and deletion remain staff policy decisions, not an automatic purge.

## Privacy-safe support and acceptance

Preview the allowlisted diagnostic JSON before sharing. It excludes record labels, quantities, charges, filenames, paths, source text, histories/reasons, and credentials. Give data-specific problems to authorized school IT for private inspection and a synthetic reproduction. Do not send the developer private invoices, backups, database files, or a staff browser session.

Before real-data use, the school must approve the installation and trusted distribution, target OS/browser, dependencies/advisories, local data and encryption policies, access/retention, backup destinations, named maintainer, and patch cadence. Finance must confirm current charges, credit/rebill treatment, and service-date semantics; Facilities must confirm physical meter mappings and coverage. No real records, school installation or portal integration was used. The user-authorized trusted v0.4.0 tag was published; 0.5.0 publication remains a separate release step.

## Operational diagnostics and authorization

The browser support page previews fixed diagnostic categories and the private
audit view separately. `diagnostics` can inspect an incompatible or damaged
stopped database without opening records or changing its bytes. `check` additionally
validates every retained source and the audit chain. A low-space warning is a
coarse threshold, not a guarantee that a particular backup will fit.

Staff cancellation and replacement approval require the local app passphrase
again. Restore/migration require stopped-app OS access and explicit confirmation.
Named roles remain deferred; see `ACCESS_AND_CONFIGURATION.md`. For unsigned
source distribution and the future macOS signing decision, see
`RELEASE_AND_SIGNING.md`. No update runs unattended.
