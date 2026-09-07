# Local operation and recovery contracts

Version 0.4.0 remains a single-operator, loopback-only application. Use explicit
external data directories for every command. See `STAFF_INSTALL_AND_UPDATES.md`
for installation, backups, and the stopped-app migration procedure.

## Imports and provenance

| Situation | Deliberate behavior |
|---|---|
| Identical bytes, even under another filename | Legacy import rejects as `DUPLICATE_SOURCE_DOCUMENT`; batch/inbox reports duplicate and links the existing review/source |
| Different bytes, same provider/account/invoice reference | Stage for review; block independent approval; staff may explicitly link a replacement with a reason |
| Overlapping consumption on the same stable meter | Block approval; a replacement excludes only the selected active original from overlap checks |
| Separate supply charges | Require zero quantity on charges-only lines; do not repeat delivery consumption |
| Same reference in a replacement chain | Retain every source/version; only the latest approved active version counts |
| Same XML intervals in a differently encoded document | Skip identical readings; retain the new document and its review; no duplicate consumption |
| Changed interval values, duration, quality, metadata, overlapping starts, or stream mapping | Reject the complete approval transaction; no partial channel posting |
| Malformed CSV/XML or unsupported XML semantics | Reject before creating document or draft rows |
| Interrupted import | Incomplete bytes have a `.pending` name; complete unreferenced bytes can be reused on retry; SQLite rolls back uncommitted drafts |

Invoice identity matching is exact after the parser's whitespace normalization;
there is no fuzzy provider/account/reference matching. Changed aliases and
supplier references still require source review. Service dates and consumption
checks provide a separate line of protection; they do not establish campus
coverage or identify every possible supplier duplicate.

Original source bytes are addressed by SHA-256. New documents record the
importer release. Upgraded documents say `legacy-unrecorded`; the application
does not invent historical parser versions. Each review links to its original;
corrections retain saved revisions and supplier rebills retain separate sources.
XML approval checks its cached parse against the retained source. Original
source downloads validate the reference and hash before serving bytes.

## Interrupted operations

| Checkpoint | State after restart and operator action |
|---|---|
| Source write or draft insertion | No committed invoice. Retry the original file; a successful earlier commit instead produces the explicit duplicate error |
| Approval before commit | Original invoice stays active and draft stays pending; review and retry |
| Approval committed but response lost | Draft is approved; reopening shows the posted invoice; retry cannot post it twice |
| Migration before final database switch | Original schema and source files remain usable; a pre-upgrade backup exists; rerun the explicit migration after checking storage |
| Restore before final database switch | Current financial rows and retained sources remain usable; some complete orphan sources may be present; validate and retry the selected archive |
| Backup interrupted | No unfinished archive is published in `backups`; audit shows a started attempt without completion; make a new backup |
| Filesystem error after a final atomic switch | Reopen and run `check` to determine whether the complete old or new state is present before retrying; do not infer failure from a missing response |

Temporary files from a killed process can remain in the selected workspace.
They are excluded from backups and financial reporting. Diagnostics reports a
boolean for interrupted source files. Do not delete retained hash-named sources
or entire workspaces to resolve an error. Local IT can inspect abandoned
`.pending` files and temporary operation directories while the app is stopped;
retention and cleanup remain staff decisions.

A conflicting existing source is never overwritten, including a damaged orphan
left by an older release. Preserve it and use an authorized IT recovery or a
verified backup in a new workspace. Process-kill tests cover the documented
transaction boundaries; they are not hardware power-loss certification.

## Damaged review data

A damaged draft is isolated in the review list. Opening it offers the original
source, recovery for a pending bill, or rejection. Recovery appends a new draft
revision from the most recent structurally readable saved revision or original
draft. It requires acknowledgement and leaves the result pending for source
comparison; it never approves automatically. If no readable candidate exists,
preserve the installation and recover through local IT or a backup. Approved
financial versions are not rewritten by this control. Rejection also retains
the source. A damaged interval cache has no automated repair UI; preserve/reject
it and let authorized IT recover from a known-good snapshot.

## Audit and diagnostics

The private audit view in **Privacy & support** shows UTC time, a fixed action,
actor context, and a local review/history reference. It paginates 100 events at
a time. Audit rows cannot be updated or deleted through normal SQL while their
schema rules are intact; each row hashes its predecessor and fixed fields.
Startup, backup, restore, migration validation and `check` validate the chain.
The current head is also checked. This detects corruption and ordinary changes;
an OS owner who can rewrite the whole database and code can replace the chain.
There is no independently signed external audit anchor or per-person identity.

Financial actions and their audit events commit together. Backup events use an
opaque operation ID shared with the backup manifest: `BACKUP_STARTED` precedes
the snapshot; `BACKUP_CREATED` follows completed archive publication. An abrupt
exit between publication and the final event can leave a valid archive and only
a started event; local IT can verify the archive and its operation ID. Restore
continues the snapshot's chain, adds `RESTORE_SNAPSHOT` linked to the prior
workspace's safety-snapshot audit head, and preserves the replaced timeline in its safety
backup. Restoring a snapshot therefore does not pretend that later work never
existed. Legacy events keep their original IDs/times with unknown actors.

Diagnostics reports version/schema, runtime compatibility, database access,
coarse free-space thresholds, the type of backup location, permission status,
loopback port status, source-temp presence, audit status and unsigned-manifest
integrity. It emits no paths, record IDs, names, financial values, filenames,
source excerpts, environment values or exception text. CLI diagnostics also
works on an incompatible or damaged database without modifying it. Review the
report before sharing; it does not replace the full stopped-app `check`.

## Intake operation in schema 4

Read `BILL_INTAKE.md` for explicit scanning, cursor continuation, source evidence,
manual fallback, extraction bounds and model preparation. Each intake attempt
commits new/processing status before parsing; on restart unfinished attempts
become a safe retry or resolve to their already committed source. Extraction
hash, draft and extraction audit event commit together. Approval and supplementary
review values append together under the existing revision guard. A malformed
extraction snapshot is rejected by integrity checks, not silently re-extracted.

Private backups include extraction and review history, cadence/history and the
saved inbox location. They exclude public model assets and temporary page images
(which exist only in worker memory). Restore does not scan any directory or load
a model automatically. Reconfirm the visible location and use the installed
release's explicit `--ocr-model-dir` when launching. Source hash/audit checks
cover retained extraction snapshots as well as original bytes. Legacy schema-3
PDFs retain their original manual workflow after migration.
