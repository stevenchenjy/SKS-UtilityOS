# Development verification — 0.2.0

Date: 2026-09-06. Platform: macOS arm64 (Darwin 25.6.0), Python 3.13.2, native Chrome 152.0.7977.82, Playwright 1.57.0. All workspaces used known synthetic fixtures and were created outside the source folder. No private school installation, browser profile, bill, password, or backup was inspected.

## Automated outcomes

- Initial suite: **66 passed**, one upstream deprecation warning. The first attempted run could not start until the already-declared development dependencies were installed.
- Final suite: **100 passed**, two upstream test-client deprecation warnings. Repeated against an independently installed source release with its own virtual environment, also **100 passed**.
- `pip check`: no dependency conflicts in both development and clean-install environments.
- Live PyPI advisory scan with pip-audit 2.10.1: initial findings in Starlette, pytest, and pip; **no known vulnerabilities** after the documented updates. No ignored advisory identifiers. See `DEPENDENCY_DECISIONS.md`.
- Source archive verification checks its complete manifest, source-only membership, required bootstrap/schema fixture, and executable launcher attributes. No runtime databases, backups, environments, screenshots, or non-development documents are packaged.

The remaining warnings are the upstream Starlette/httpx test-client deprecation and AnyIO's deprecated BlockingPortal alias. They do not fail tests; dependencies were not added solely to suppress warnings. Advisory results are dated rather than a security certification.

Coverage includes invoice accounting, CSV/XML validation, negative credits, supply-only treatment, duplicate files/invoices, same-reference replacement chains, new-source rebills, multiple meters, unrelated overlaps, atomic failed approval, cancellation, rejected corrections, saved partial entry, stale revisions/mappings, source retention, interval conflicts and duplicate stream mapping, tiny decimal round trips, authentication/origin/CSRF, diagnostic exclusions, backup integrity, failed writes, migration failure, and recovery.

## Native browser evidence

The flow under test is: local launch → login → import/review → approve or reject → active ledger/history → downloads/backup → logout, including recovery into another workspace.

The Browser plugin was unavailable. The existing Playwright dependency controlled an isolated native Chrome profile through real loopback HTTP. There was **no HTTP transport bridge, mocked API, private browser profile, remote tunnel, or change to browser administration policy**. Headed Chrome and the native macOS launchers were also exercised.

| Check | Outcome |
|---|---|
| Page identity and nonblank content | Correct local URL, `Overview | SKS UtilityOS`, and functional screens |
| Runtime/console | Zero unexpected console warnings/errors or uncaught page errors; the explicit duplicate-file check returns the expected HTTP 422 |
| Desktop / mobile | 1440×1000 and 390×844; six navigation screens, dialogs, forms, tables, and exports exercised; no document-wide horizontal overflow |
| Login/logout | Native HttpOnly/SameSite cookie, authenticated navigation, cookie removal and session revocation |
| CSV | Upload, unchanged source download, validation, acknowledgement, approval, and duplicate rejection |
| PDF-assisted entry | Original bytes downloaded unchanged; the supplied synthetic water invoice's actual printed values manually entered, saved, reopened, and approved |
| XML | Supported file imported, mapping confirmed to `DEMO-E01`, approved; interval and bill draft rejection exercised |
| Corrections | Transcription correction saved and approved; active charge changes from $579.80 to $500; original retained as superseded |
| Supplier rebill | Separate source imported and explicitly linked; same invoice reference replaces the $500 version with $499.80 |
| Rejection/cancellation | Mobile correction rejection leaves the active original intact; mobile PDF invoice cancellation retains history and excludes its charges/quantity |
| Credit/report precision | Independent October credit is −$50 with zero consumption; chart labels remain separated; decimal strings retain precision |
| Mapping | Mobile meter reassignment and building rename update grouping with before/after history |
| Downloads | Original CSV/PDF/XML source links, private ledger CSV, safe diagnostic JSON, private backup ZIP; mobile exports |
| Backup/restore | Browser-generated ZIP restored into a separate workspace; matching dashboard/active totals, source integrity, login, exports, and native browser smoke checks |

The final synthetic ledger export verifies September's active current charges at **$499.80** after replacement and cancellation, and October's independent credit at **−$50.00**. Superseded originals and the cancelled PDF are excluded. Screenshots were inspected for desktop history, PDF review, mobile cancellation/mapping, corrected reports, support, and negative-credit charts. Screenshot/log evidence is retained outside the repository.

## Operational checks actually run

- Native executable `Launch-Demo.command`, argument forwarding, browser opening after startup, and Ctrl+C shutdown on this Mac. Port 8765 was occupied; verification used disposable loopback ports. A second service on an occupied test port received a fixed `LOCAL_PORT_UNAVAILABLE_CHOOSE_ANOTHER_PORT` error.
- Native `Launch-Staff.command` first-time passphrase setup in a newly created **synthetic staff-mode** directory, followed by browser login, sample CSV approval, ledger export, and logout. No default private staff directory was opened.
- Source archive unpacked to a separate folder; `scripts/setup.sh` installed from a prepared local wheelhouse using `--no-index` and wheels only. The clean environment ran the complete regression suite. Database/source hashes before and after code installation matched.
- Deliberate same-schema switch: stop the original app, back up, run `check` with the second code folder, and launch that folder against the same known synthetic workspace. Native browser checks and exports passed. The prior code folder remains usable for rollback.
- Explicit schema 1 → 2 upgrade of a full synthetic demo, including database/foreign-key/source checks and pre-upgrade backup. Automated tests also validate original IDs, reviewed payloads, source bytes, password hash, and new corrections after migration.
- Rollback rehearsal with the retained 0.1.0 code and pre-upgrade schema-1 backup restored into a new recovery directory. Old-version integrity and mode checks passed. This does not assert that old code can read schema 2.
- Damaged paths, hashes, mode/schema, foreign keys, malformed archives, failed backup writes, failed final migration replacement, and stopped-workspace locks tested. Failed migration preserves the original database; failed restore does not replace it. Orphaned source reimports require identical bytes.

## Remaining external validation

Windows launch/ACLs, other browsers, the actual staff workstation, Finder quarantine/Gatekeeper treatment of a distributed archive, code signing/trusted distribution, school ownership/retention/encryption decisions, and Finance/Facilities validation against private source records remain unverified. No public publishing, school installation, portal access, paid integration, cloud extraction, or live data occurred. This completes the development milestone, not school pilot acceptance.

## Reproduction

Use a fresh external synthetic directory and the commands in `README.md`. `scripts/native_browser_smoke.py --exercise-imports --milestone` performs the extended browser path and intentionally mutates only an explicitly checked demo installation. Omit `--exercise-imports` for a smoke check after restoration or a code-folder switch. Retain native screenshots/downloads outside source with `--evidence-dir`. Separate staff setup and cross-version rollback checks were executed against disposable developer-created directories as described above.
