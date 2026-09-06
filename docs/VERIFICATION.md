# Development verification — 0.3.0

Date: 2026-09-06. macOS arm64 (Darwin 25.6.0), Python 3.13.2,
native Chrome 152.0.7977.82, Playwright 1.57.0. Every workspace, source, credential
and screenshot used here was synthetic and created outside the repository.

## Baseline before changes

The original 0.2.0 working source matched all 66 entries in the verified archive.
Its full suite passed **100 tests** in both the existing environment and a fresh
wheelhouse installation. Native headed Chrome repeated login/logout, CSV,
PDF-assisted entry, XML, approval/rejection, corrections/rebills/cancellation,
exports, backup and desktop/mobile navigation. Browser-generated backup recovery,
stopped-app schema-1 → 2 migration and release integrity passed.

Before modifying application code, real child-process interruption probes
reproduced truncated final source files during import and overwritten sources
during restore. A corrupted review payload also broke the whole review list.
Those observations were recorded in Git before the fixes. Ordinary 0.2.0 paths
passed; roadmap wording was not treated as evidence of a missing implementation.

## Regression and failure recovery

The final suite passed **144 tests** in both the development environment and the
independently installed source package. Execution evidence remains external. Two upstream deprecation
warnings remain: Starlette's httpx test client and AnyIO's BlockingPortal alias.
They do not fail the suite. `pip check` reports no conflicts. The existing pinned
environment's pip-audit 2.10.1 scan on this date found **no known vulnerabilities**
and ignored no advisory IDs. No dependency was added for 0.3.0.

Tests retain the previous accounting, lifecycle, imports, security and release
coverage, and add these recovery checks:

| Scenario actually executed | Verified result |
|---|---|
| Kill during partial source write or after source publication | No partial document/invoice rows; retry succeeds or explicitly identifies an already committed source |
| Kill within approval transaction | Original financial state and pending review remain; retry posts once |
| Kill after approval commit before caller response | Approved state remains; retry cannot duplicate it |
| Kill within migration transaction or before database switch | Original bytes/schema remain usable; backup exists; explicit retry succeeds |
| Kill restore during source publication or before database switch | Current financial rows and original source hashes remain valid; retry restores the selected snapshot |
| Kill incomplete backup / simulate full-disk write failure | No unfinished backup is published; failed import creates no financial rows |
| Corrupt JSON, wrong payload structure or changed saved revision | Other reviews remain accessible; approval is blocked; acknowledged recovery stays pending |
| No readable draft history | Bounded recovery failure, with source retention and rejection still available |
| Changed cached XML readings | Approval refuses data that does not match its retained original |
| Tampered audit / update-delete attempt | Append rules reject mutation; startup/check/backup detect invalid history |
| Restore audit boundary | Boundary hash matches the exact head actually retained in the safety backup |
| Future synthetic upgrade from each supported schema | Registered steps commit together; failed step rolls back; unknown path creates no replacement |
| Old pending draft beyond 500 closed imports | Pending review stays visible; closed history stays bounded |

The interruption tests terminate separate Python processes executing production
storage/ledger/maintenance operations at test-controlled checkpoints. They do
not add runtime fault hooks or claim physical power-loss/drive-failure testing.
Fixed error/diagnostic schemas are tested with synthetic path, filename, account,
amount, configuration, environment and credential sentinels.

## Native browser outcomes

The Browser plugin was unavailable; the existing Playwright dependency controlled
isolated native Chrome profiles through real loopback HTTP. No transport bridge,
mocked API, private browser session, remote tunnel or device-policy change was used.
The full workflow and readiness checks passed in the workspace and independently
installed source package, with **zero unexpected console/runtime errors**.

| Flow | Evidence |
|---|---|
| Application launch and sessions | Native macOS demo/staff launch, first-time synthetic staff passphrase setup; local login, HttpOnly/SameSite cookie, logout/revocation |
| CSV / PDF-assisted / XML | Uploads, original/sample downloads, retained bytes, manual PDF values, validation, mapping, approval and rejection |
| Invoice lifecycle | Correction, new-source supplier rebill, same reference, independent negative credit, mobile rejection/cancellation and mapping history |
| Damaged bill draft | Isolated recovery screen, acknowledged recovery of saved values, fresh review acknowledgement and approval |
| Staff sensitive operations | Missing passphrase blocks replacement approval; correct passphrase approves; mobile cancellation confirms passphrase; actor context appears in audit |
| Audit | Current/older event pages, private review links, bounded fields and truthful shared-operator attribution |
| Large ledger | 100-row paging, lookup of an old invoice, all 24 months, current totals and complete CSV export |
| Responsive behavior | 1440×1000 and 390×844; six screens, dialogs, input controls and downloads; no page-wide horizontal overflow |
| Restore | Native browser recovery of a browser-generated backup, matching ledger/source integrity and fresh login |

The expected negative HTTP responses are the explicit duplicate-source rejection
and missing staff passphrase in their respective tests. Screenshots of recovered
entry, source provenance, mobile passphrase confirmation, audit history and campus
overview were inspected. Screenshots/downloads remain outside Git.

## Larger campus and version switching

The deterministic fixture includes **20 buildings, 60 service points, 80 accounts,
six synthetic vendors, 24 service months, 1,923 active invoices, 1,927 retained
versions and 288 interval readings**. It uses electricity, water, gas, oil and
propane, separate supply charges, seasonal profiles, three corrections, a supplier
rebill, three credits and two deliberate anomalies. Generated monthly charges
reconcile independently with the active export; supply quantities stay zero and
fuel quantities stay purchases. Fixture generation on this Mac took about 2.7 s.
The dedicated campus browser run observed navigation below 0.2 s; this is a dated
small-campus development measurement, not a deployment throughput guarantee.

The fixture was also created using the **actual retained 0.2.0 code**, then
migrated with 0.3.0. Source hashes and the full active CSV export matched byte for
byte across the upgrade. Old code rejected schema 3 without changing its bytes.
The pre-upgrade backup was restored with 0.2.0 into a new workspace; integrity
and native browser checks passed. Automated tests separately cover frozen schema
1 and schema 2 and simulated future transitions beyond schema 3.

## Installation, Git and release integrity

Fresh macOS virtual environments were installed from reviewed local wheels with
`--no-index` and wheel-only setup. Installing code left the selected existing
synthetic workspace's database, sources and backups byte-identical. Source-only
archives were unpacked independently; regression, native import/recovery,
large-campus and synthetic staff checks passed there.

The existing Git initial commit is retained. An object-level release review found
four CSV blobs normalized by the old Git attribute. Baseline commit `38d20e6`
preserves exact archive bytes and executable modes and disables checkout
normalization. All 66 baseline manifest entries now match the `v0.2.0` Git objects.
The local `v0.3.0` release includes only code, tests, technical documentation and
synthetic fixtures. Its complete source manifest, indexed blobs and source-only
membership are checked. Standard Git ZIP directory entries are accepted only
when they contain listed source files; unexpected files/directories remain rejected. No remote was created, contacted or pushed.

## Remaining limits

Named users/role enforcement are explicitly deferred with a proposed exact matrix
in `ACCESS_AND_CONFIGURATION.md`. Audit actor contexts do not identify people;
an OS owner can rewrite the full database/code and replace the chain. Private
backup encryption, hardware power-loss behavior, native Windows/ACLs, other
browsers, Finder quarantine/Gatekeeper treatment, signing/trusted distribution,
the actual school workstation, maintenance/retention ownership and private-data
accounting acceptance remain outside the tested boundary. Signing research is
documented; no credentials, signing service, payment or production deployment
was configured. No portals, school records, paid APIs or cloud extraction were used.

## Reproduction

Use `README.md` for the full suite and extended native import test. Run
`scripts/native_readiness_smoke.py` with a **new external** work directory for
its self-created recovery, campus and synthetic-staff cases. Run
`scripts/synthetic_campus.py` only with a new demo directory. See `OPERATIONS.md`
for exact retry, provenance, diagnostic and audit semantics and
`STAFF_INSTALL_AND_UPDATES.md` for stopped-app upgrade and rollback.
