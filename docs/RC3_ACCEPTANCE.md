# rc3 portability and release-candidate acceptance — 2026-09-13

This acceptance work starts from feature-frozen **0.6.0-rc3 / schema 7** at
`ad39a4a8f3f1eaf579207c13968536e7c6a8fe37`. It introduces only demonstrated
portability fixes, their regressions and release-evidence corrections. The
candidate branch is published; no main merge, release tag, historical-tag change
or school installation is authorized by these synthetic checks.

## Git reconciliation and publication

| Reference at initial reconciliation | Commit |
|---|---|
| rc3 HEAD | `ad39a4a8f3f1eaf579207c13968536e7c6a8fe37` |
| Local main | `23a2b659575a74442f8ec6fc15c0345a9544e97d` |
| Freshly fetched origin/main | `23a2b659575a74442f8ec6fc15c0345a9544e97d` |
| Merge base | `23a2b659575a74442f8ec6fc15c0345a9544e97d` |

The single rc3 implementation commit was unique to the candidate; no commit was
unique to origin/main. The accessibility/responsive work was already included,
so no integration or conflict resolution was needed. Ordinary non-force pushes
publish only `codex/portable-acquisition-rc3` to the expected
[GitHub repository](https://github.com/stevenchenjy/SKS-UtilityOS).

## Observed failures and bounded changes

1. The [first hosted run](https://github.com/stevenchenjy/SKS-UtilityOS/actions/runs/34783220560)
   passed Mac and Linux suites (545 passed; 544 passed/one skipped respectively),
   but Windows stopped at portable-rehearsal shutdown. Its first workflow body
   completed; the server then exited nonzero. Uvicorn handles Windows SIGBREAK,
   cleans up, restores the original handler and replays the signal. The default
   Windows handler does not take the CLI's normal KeyboardInterrupt path.
   `run.py` now installs that interrupt handler for SIGBREAK around the server
   run and restores the prior handler afterwards. The strict zero-exit gate is
   retained. A real subprocess regression checks stop and subsequent maintenance
   access. See [Python signal semantics](https://docs.python.org/3.13/library/signal.html).
2. The [second hosted run](https://github.com/stevenchenjy/SKS-UtilityOS/actions/runs/34783580315)
   passed Windows shutdown/restart but reached HTTP 500 at backup creation.
   `replace_file` opened a completed file read-only before fsync; Windows needs
   write access for the flush. It now uses `r+b`, preserving bytes, flush-before-
   replace, close-before-rename and failure propagation. New regressions prove
   backup/restore byte retention and refusal to publish after a sync failure.
   The prior helper failed the actual-descriptor writability regression locally;
   116 focused tests passed after the fix. See
   [Windows FlushFileBuffers requirements](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-flushfilebuffers).
3. The [third hosted run](https://github.com/stevenchenjy/SKS-UtilityOS/actions/runs/34783911857)
   passed the complete portable rehearsal on all three platforms. Windows then
   reported 22 suite failures: 19 database replacement errors, two inbox
   assertions and one Git ignore assertion. The database errors came from frozen
   schema fixtures that exited SQLite transaction contexts without closing their
   connections. Explicit fixture cleanup retains commit/rollback behavior and
   releases the file before replacement; the production migration path is
   unchanged. A regression retains real connection references to expose the leak
   even on Mac; it failed before the correction. All 78 focused migration/recovery
   tests passed afterwards. The Git assertion now uses binary NUL framing to avoid
   Windows text-mode newline conversion and pathname quoting; every original
   ignored path is still checked exactly.
   The inbox failures revealed incompatible Windows timestamps between path and
   descriptor metadata in CPython 3.13.15. Cross-API identity now uses explicit
   birth time on Windows while retaining device, inode, size and modification
   time. Change time is also compared before/after reading the same descriptor.
   The descriptor is explicitly opened in binary mode to preserve CRLF, DOS EOF
   and arbitrary source bytes regardless of the Windows CRT default. Regressions
   cover both stable files with differing API timestamps and changes during the
   read, plus binary-byte retention. Existing copy, duplicate, symlink and FIFO
   defenses remain asserted. All 68 focused acquisition/intake tests passed on
   qualified Mac Python 3.13.15; actual Windows confirmation requires hosted
   execution. The timestamp regression models the documented API difference;
   it is not described as native Windows execution. See CPython 3.13.15's
   [path metadata implementation](https://github.com/python/cpython/blob/v3.13.15/Modules/posixmodule.c#L2066-L2076),
   [descriptor metadata implementation](https://github.com/python/cpython/blob/v3.13.15/Python/fileutils.c#L1022-L1041)
   and [binary-open contract](https://docs.python.org/3.13/library/os.html#os.open).
4. Original kits reproduced correctly but contained five historical development
   locations in verification prose. Those location strings were removed while
   retaining the historical outcomes. No private school data or credentials were
   found. Generic command examples, normal OS default locations, public URLs and
   pip's public certificate-authority bundle are distinct from actual private
   paths or credentials.

The first two code fixes are commits `9a61a4e505c4075a9e3031f00ab5e051f6a52dc8`
and `9c365313be2dd75e25b75626c2864241daa3ec0b`; their three regressions raised
the suite from 545 to 548 tests before the subsequent Windows follow-up. CI uses
`-ra` to retain actual skipped-test identities. The fixture lifetime regression
and three intake cases bring the final collected suite to 552 cases; executed
pass/fail/skip counts belong to the completed runtime receipts.
No schema, accounting, source format, approval, authentication, connector or
analytics feature was added.

## Local Python runtime qualification

The reviewed official Python 3.13.15 installer hash and PSF Developer ID Installer
signature were verified. Installing it at the standard system location would
replace the existing Python 3.13.2, so its unchanged signed framework was
extracted into a separate external development directory instead. Original
interpreter/library hashes remain unchanged.

Direct process-local relocation initially failed: the deliberately restricted
PDF-worker environment omitted the loader paths, causing a worker to load the
old system framework alongside newer modules. That attempt's 83 failed/463
passed tests and failed PDF/native evidence remain preserved. They do not qualify
Python 3.13.15 and were not hidden as successful checks.

An external qualification-only launcher supplies the fixed reviewed framework
and library paths and macOS venv-launcher identity on each invocation. The
application's worker environment restrictions are unchanged. Parent and actual
isolated PDF-worker probes verify Python 3.13.15, OpenSSL 3.0.21, the correct
stdlib/library paths and successful PDF extraction. The signed binaries are
unchanged. This launcher is neither a product feature nor part of the source or
offline kits; it is a disclosed development harness. Actual standard-installer,
Finder quarantine and school-device acceptance remain separate.

Fresh base and optional-OCR installations use their exact 26/28 reviewed wheels.
The separate development overlay uses 12 pinned wheels with recorded hashes and
licenses. No prior virtual environment is copied. The final qualification uses
the corrected source and the same retained synthetic workflows as rc3.

## Acceptance results

The Mac environment for `9c36531` passed **548 tests, zero skipped and zero failed**
in 87.96 seconds, with two existing test-client deprecation warnings. Base,
OCR/development and separate old-rc2 environments passed dependency consistency.
The new base handoff performed its own offline installation and passed real HTTP
PDF/XLSX/XML intake, exact source downloads, distinct financial/operational
approval, mapping reuse, restart, backup/restore, logout and clean shutdown.

Native Chrome **152.0.7977.84**, desktop **1440×1000** and mobile **390×844**,
passed seven retained browser groups: core financial milestones, acquisition,
mapped usage, recovery/campus/staff readiness, schedules, Provider Studio and
intake. The eighth group, the full extraction benchmark, passed separately through
its CLI. The Browser plugin was unavailable; existing Python
Playwright used isolated Chrome contexts and real loopback HTTP/cookies/downloads.
The corpus matched **284/284 fields across 28 documents**, with zero missing,
incorrect, extra or incorrect-unit fields. Screenshots were inspected, including
loaded acquisition controls, reusable XLSX mapping and OCR evidence. A transient
refresh screenshot remains preserved alongside its fully loaded recapture.

Both the old schema-6 release and corrected schema-7 release ran under verified
3.13.15 launchers for the actual migration rehearsal. Pre-upgrade backup,
incompatible-start refusal, explicit migration, **27 pre-existing tables and four
source originals**, configuration and exact ledger/source downloads all passed.
The old code restored its pre-upgrade backup into a separate rollback workspace
and passed native verification. The supervised runner exited zero and confirmed
all browser drivers and servers closed. All 25 observed native server addresses
and 16 native process groups were checked stopped; migration independently
verified its owned shutdown.

Hosted job counts and skips are recorded from completed logs, not inferred from
the configured matrix. The external acceptance receipt binds the final commit,
completed hosted runs and final source/kit hashes without creating a
self-referential source archive. Source comparisons identify which native checks
remain applicable and which workflows require another run after a correction.

The unsuccessful hosted runs are retained as evidence; they are not final gate
passes. All used Python **3.13.15**:

| Run | macOS 15 arm64 | Ubuntu 24.04 x64 | Windows Server 2025 x64 |
|---|---|---|---|
| [34783220560](https://github.com/stevenchenjy/SKS-UtilityOS/actions/runs/34783220560) | 545 passed; exit 0 | 544 passed, 1 skipped; exit 0 | Portable shutdown failed; pytest not reached; exit 1 |
| [34783580315](https://github.com/stevenchenjy/SKS-UtilityOS/actions/runs/34783580315) | 546 passed; exit 0 | 545 passed, 1 skipped; exit 0 | Portable backup failed; pytest not reached; exit 1 |
| [34783911857](https://github.com/stevenchenjy/SKS-UtilityOS/actions/runs/34783911857) | 548 passed; exit 0 | 547 passed, 1 skipped; exit 0 | Portable rehearsal passed; 523 passed, 22 failed, 3 skipped; exit 1 |

Linux skips the Mac scan-byte reproduction test. Windows also skips the POSIX
FIFO replacement test and the artifact symlink case requiring device privilege.
These cases are executed on the native Mac; their Windows skips remain explicit.
The final candidate must pass all configured hosted jobs, including dependency
consistency, portable handoff, complete tests, source integrity/reproducibility
and digital extraction. Use the completed run for the exact candidate commit in
the [ordinary workflow history](https://github.com/stevenchenjy/SKS-UtilityOS/actions/workflows/synthetic-ci.yml)
and its acceptance receipt; a queued/running job is not a pass.

## Continuing external gates

There is no local Windows desktop/VM execution target. Hosted Windows Server
testing must not be represented as Windows 11 staff-device or browser acceptance.
macOS Intel remains deferred; no new compatible dependency closure was introduced.
Actual school hardware, approved runtime installation, effective ACLs, encryption,
backup/retention ownership and maintenance remain school-side decisions.

My360 workbook format/unit/date/meter semantics and actual Central Hudson ESPI
exports still require authorized school-side validation. No real provider file,
school credential or EPA TEST/LIVE service was accessed. Portfolio Manager,
My360 remote automation and scheduled external synchronization remain disabled.
Any later connector needs approved coverage, recurrence, resolution, fees,
consent, credential ownership/removal and maintenance. Signing and trusted
distribution are separate from the authorized branch publication.
