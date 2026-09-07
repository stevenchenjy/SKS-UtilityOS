# SKS UtilityOS development instructions

`AGENTS.md` is the persistent project-level instruction source and always governs work in this repository. The primary outcome is a maintainable staff-local utility ledger with a truthful demonstration.

## Instruction loading

- Read `README.md` when current product capabilities, setup, or release state are relevant.
- Read `MASTER_PROMPT.md` when starting a new milestone, choosing the next major development direction, or resolving ambiguous scope.
- Read only the relevant files under `docs/` for the subsystem being changed, rather than every project document on every task.
- Read `.agents/skills/local-utility-engineering/SKILL.md` for utility accounting, bill intake/import, extraction, data semantics, support/privacy, migration, or release work.
- Inspect current code and tests before assuming a roadmap item remains unimplemented. Treat completed historical milestones as context, not a checklist to re-audit on every small task.
- For focused maintenance, bug fixes, tests, documentation corrections, or narrow UI changes, load only the instructions and documentation needed for that work.

Scoped loading does not waive verification requirements. Perform full baseline and release verification when preparing a tagged release, migration, recovery change, accounting-semantic change, security-sensitive change, or other high-risk milestone; load the applicable verification and release guidance explicitly.

## Data and permissions

Develop with synthetic fixtures only. The student developer has no authorization to access utility portals, private school bills, portal passwords, staff browser sessions, staff database files, or confidential backups. Keep private workspaces outside the repository and cloud-synced folders. Never request those materials through an AI tool or commit them to Git.

Only staff may review and import their own authorized documents inside a school-controlled installation. Do not connect email, web portals, cloud extraction services, remote-debug tunnels, automated update services, or external APIs without a specific school-approved decision. No paid connector or metered service may be introduced by default.

## Engineering scope

Preserve existing functionality and inspect actual behavior before deciding a rewrite is necessary. The current stack is Python/FastAPI/SQLite with browser ES modules; project size and offline operation make this a reasonable initial implementation. Choose additional libraries or skills when they solve a demonstrated need, after reviewing their licenses, install behavior, maintenance, and fees.

Implement complete useful slices with tests. A feature's UI status must match backend behavior. Maintain an explicit distinction between implemented, experimentally tested, and externally unverified work. Avoid endless audit cycles when the next practical step is known.

## Accounting and energy semantics

Keep invoices and their current charges separate from consumption and interval readings. Use integer cents and decimal quantities. Maintain stable meter identity across supplier/account changes. Preserve original source bytes, extraction provenance, draft review history, units, service dates, and measurement semantics.

Supply-only bills add charges without adding repeated consumption. Delivered oil/propane volume represents purchases. Shared meters remain unallocated until staff provides a defensible mapping. Current charts use invoice months; any future calendarization must retain the original billing periods and label estimates.

Resolve Green Button ReadingType links and multipliers. Reject unsupported units, direction, aggregation, or missing semantics. Store interval starts in UTC and retain duration and quality information. Add XML defenses, duplication/conflict checks, and mapping confirmation to every extension.

## Support and release boundaries

Use fixed diagnostic schemas with allowlisted keys. Account labels, quantities, charges, filenames, paths, source snippets, free-form exceptions, and secrets do not belong in a developer support bundle. Reproduce failures with synthetic fixtures or use a school IT member who can inspect the private installation under school policy.

A new release must leave the private data directory untouched during installation. Require backup, a schema compatibility check, tests, and school approval before switching versions. Hash manifests verify integrity; trusted provenance requires a separately approved distribution or signing process. The current release is unsigned.

## Commands and verification

Use `python -m pytest -q` for backend tests. Start `python run.py demo` with a fresh external demo data directory when testing imports. Verify the core browser path on desktop and a mobile-sized viewport, including download behavior and logout. Respect browser administration restrictions and report blocked checks accurately.

Before presenting a staff deployment, verify supported OS launch behavior, dependency advisories, corrected/rebilled invoices, duplicate imports, backup restore, source retention, and privacy-safe support. Public GitHub publishing, school installation, external services, and live data are separate authorization decisions.
