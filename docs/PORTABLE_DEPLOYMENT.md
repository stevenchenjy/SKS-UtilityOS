# Portable deployment decision and handoff — 2026-09-13

The rc3 installation is a separately extracted source release, an approved
CPython 3.13 GIL runtime, and a reviewed platform-specific offline wheelhouse.
Application setup creates only the new code folder's `.venv`; it never opens,
migrates, moves or selects an existing private workspace. No Node, Docker,
database server, cloud service, paid installer or remote support agent is needed.
The source release remains unsigned. School approval and native acceptance are
still required before access to private records.

## Packaging options evaluated

| Approach | Licensing and size | Reproduction, offline behavior and maintenance | OS/security and decision |
|---|---|---|---|
| Source + approved Python + exact wheels | UtilityOS MIT; CPython PSF-2.0 and bundled notices; individual dependency licenses in receipts. Base wheels are about 25 MB on Apple Silicon and 27 MB on Windows, excluding Python and expanded files. | Inspectable source and explicit artifacts; no compilation on staff machines; source and environment rebuilt in a new folder. Same private workspace is selected only after backup/schema checks. Old code/runtime/backup remain available for rollback. Ordinary Python tracebacks can be reproduced using synthetic data. | Selected: smallest change to the working application. Python installation belongs to school IT; Windows supports per-user installation. Existing approved Python avoids administrator access for app setup. macOS's official package may require IT-managed installation. No execution-policy or Gatekeeper bypass. |
| Bundle/embedded Python | CPython license and every bundled library's notices still apply. Python 3.13.15 Windows embedded archive is about 10.5 MB before dependencies; official Mac installer is about 68.7 MiB. | Reduces initial runtime selection but makes the application distributor own interpreter layout, patching, native libraries and all runtime provenance. Windows embedded Python omits pip and does not support ordinary pip-managed dependencies. A cross-platform embedded layout is extra work. | Not selected: no demonstrated advantage justifies a second runtime layout now. A later bundled runtime needs its own review, Windows runtime prerequisites and complete signing strategy. |
| Standalone PyInstaller app | PyInstaller GPL-2.0 with bundling exception, with some Apache-2.0 files; bundled dependencies retain their own licenses. Still carries interpreter and native PDF libraries; a one-file executable unpacks runtime assets. No precise UtilityOS size claim without a build. | Native builds for each OS/architecture, hook maintenance, bundled data-path handling, antivirus acceptance and debugging of frozen processes. Reproducibility requires a separate native build chain. | Not selected. Apple Silicon binaries need code signing at least ad hoc; trusted distribution/notarization is a separate school-owned process. Packing does not remove Gatekeeper or antivirus acceptance. |

Sources: [pip secure installs](https://pip.pypa.io/en/stable/topics/secure-installs/),
[repeatable installs](https://pip.pypa.io/en/stable/topics/repeatable-installs/),
[official Windows runtime guidance](https://docs.python.org/3.13/using/windows.html),
[official macOS runtime guidance](https://docs.python.org/3.13/using/mac.html),
[Python 3.13.15 artifacts](https://www.python.org/downloads/release/python-31315/),
[PyInstaller license](https://pyinstaller.org/en/stable/license.html),
[PyInstaller signing behavior](https://pyinstaller.org/en/stable/feature-notes.html#macos-binary-code-signing).
The support-burden comparisons are engineering judgments for this application.

## Targets and exact artifacts

| Target | Reviewed artifact closure | Runtime/native acceptance |
|---|---|---|
| macOS Apple Silicon, macOS 13+ for base PDF wheels | `dependency-receipts/macos-arm64-cp313-base.json`: 26 exact wheels, 25,099,219 bytes | Initial 3.13.2 rehearsal followed by fresh native 3.13.15 qualification on macOS 26.6.2 arm64. The current-runtime run uses the disclosed external development launcher; normal system-installer and school-device acceptance remain separate. |
| Windows x64, school-supported Windows 11 | `dependency-receipts/windows-x64-cp313-base.json`: 26 exact wheels, 27,748,570 bytes | Windows-specific wheels downloaded and hashed; target-marker dependency closure checked. Windows Server 2025 CI has executed the portable handoff and synthetic tests; exact results and fixes are in the acceptance report. Windows desktop/ACL/launch acceptance remains outstanding. |
| Linux x64, glibc 2.28+ | `dependency-receipts/linux-x64-cp313-base.json`: 26 exact wheels, 28,306,558 bytes | Regression target; wheels verified and Ubuntu 24.04 hosted tests executed. Native desktop execution was not performed locally. |
| macOS Intel | No install receipt; setup refuses | Evaluated and deferred. `cryptography==50.0.1`, required by the existing PDF dependency, has no macOS x64 wheel. Upstream removed that platform in 49.0.0. Forking an older security dependency or privately maintaining Rust/native builds would add unreasonable patch burden for this slice. |
| Optional OCR, Apple Silicon/macOS 15+ only | `dependency-receipts/macos-arm64-cp313-ocr.json`: full base plus tesserocr/cysignals, 28 wheels, 28,935,517 bytes | Existing synthetic Mac OCR capability; optional native engine/model restrictions remain in the extraction dependency guide. No Windows OCR compatibility claim. |

The Intel limit is based on an actual failed wheel-only target resolution and
the [upstream removal notice](https://cryptography.io/en/49.0.0/changelog/).
No source compilation or downgrade was used to conceal it.

Each wheel receipt records exact package/version, wheel filename, SHA-256, byte
size, public origin URL, license/reference, bundled license paths and all active
dependencies evaluated for the target platform. Base receipt includes pip and
the complete runtime closure, including openpyxl 3.1.5, et-xmlfile 2.0.0 and
tzdata 2026.4. Windows needs this explicit IANA timezone database for zoneinfo.
The Python-maintained tzdata package is Apache-2.0 with public-domain IANA data;
see [Python zoneinfo portability](https://docs.python.org/3.13/library/zoneinfo.html)
and [tzdata 2026.4](https://pypi.org/project/tzdata/2026.4/).
The normal installer accepts only these artifacts. Extra, missing, symlinked or
modified wheel files are rejected. CPython minor/ABI/architecture must match;
free-threaded Python and arbitrary Python 3.11+ environments are not claimed as
portable receipt targets.

`dependency-receipts/python-runtime.json` separately records official CPython
3.13.15 macOS and Windows installer filenames, sizes, SHA-256 hashes, origins and
signature references. Downloaded installer bytes were checked against the
official release page; neither installer was executed through its normal install
flow. The unchanged signed Mac framework payload was extracted externally and
qualified on 3.13.15 with an explicit development-only launcher, including actual
isolated PDF workers. Qualifying CI pins 3.13.15. Actual interpreter version is
recorded in every new environment and health report. A different patch needs
review/requalification; neither the old 3.13.2 run nor the external launcher
establishes normal school-machine installer acceptance. See
[current acceptance](RC3_ACCEPTANCE.md) for the method and retained failures.
Python installer hashes verify bytes, not the publisher; school IT verifies the
upstream signature and approves the runtime under its software policy.

## Staging and installation

Obtain the reviewed source release/verifier through the approved distribution
channel, run `python scripts/release.py verify /approved/release.zip`, and extract
to a new code folder. Keep the prior release/environment for recovery. Obtain a
school-approved CPython 3.13.15 GIL build, including venv and pip. Windows's
per-user standard installer avoids an all-users install; macOS IT should supply
its approved Python. UtilityOS setup never attempts to install Python globally.

On an approved online staging machine, collect exact public artifacts for each
target. These commands fetch software only and never execute the Python installer:

```sh
python scripts/runtime_artifacts.py fetch --target windows-x64 --directory /approved/python
python scripts/runtime_artifacts.py verify --target windows-x64 --directory /approved/python
python scripts/dependency_artifacts.py fetch --target windows-x64 --directory /approved/windows-wheels
python scripts/dependency_artifacts.py verify --target windows-x64 --directory /approved/windows-wheels
```

Use `macos-arm64` for a Mac kit. The staging machine can download another target's
artifacts; this does not prove the target executes them. Transfer the source ZIP,
Python installer and its signature evidence, wheelhouse and associated receipts
through the approved process. Preserve notices already inside wheels, including
bundled PDFium/native library notices. Wheel fetches never replace expected
hashes with the downloaded hash. A completed wheelhouse is published only when
all expected artifacts match.

`scripts/deployment_kit.py` packages an already verified source ZIP, the matching
base wheelhouse, and the reviewed official Python installer into one reproducible
offline ZIP. It verifies those inputs first and rejects a source archive whose
dependency receipts differ from the selected artifact set. Example staging:

```sh
python scripts/deployment_kit.py build --target windows-x64 --source /approved/source.zip --wheelhouse /approved/windows-wheels --runtime-directory /approved/python --output /approved/new-windows-kit.zip
python scripts/deployment_kit.py verify --output /approved/new-windows-kit.zip
```

The kit retains the exact source ZIP, wheels, installer and receipts, with a
manifest covering each file. Its verifier also compares artifacts with the
reviewed receipts, so changing a wheel and recomputing the kit manifest fails.
No installer is executed while packaging or verifying. Obtain the verifier
through a separately trusted channel; a ZIP and its own hashes do not establish
publisher authenticity. Optional OCR is distributed separately under its
additional source/license obligations, not silently included in base kits.

On the target, verify the source archive and runtime installer before running
school-approved installer/setup. From the fresh extracted source directory:

```sh
# macOS, existing approved Python 3.13 selected as python3
bash scripts/setup.sh /approved/macos-wheels
.venv/bin/python run.py staff --choose-data-dir --open
```

```powershell
# Windows, approved PowerShell session and Python 3.13 launcher
.\scripts\setup.ps1 -Wheelhouse C:\approved\windows-wheels
.\scripts\launch-staff.ps1
```

Neither launcher changes device execution policy. With no wheelhouse argument,
setup explicitly downloads the same exact public artifacts, verifies hashes and
then installs offline; this is software setup, not an application update service.
Offline setup never accesses an index or fetches anything. Pip runs isolated,
wheel-only, with `--require-hashes`, `--no-index`, `--no-deps` and no cache.
Every pip subprocess clears inherited pip variables and sets `PIP_CONFIG_FILE`
to the platform null device, disabling global/site/user configuration that could
otherwise redirect an installation or inject remote `find-links`. The complete
closure is explicit and `pip check` validates it after installation. It verifies the
bootstrap pip artifact too. A pre-existing `.venv` is refused: prepare a new code
folder rather than modifying an accepted environment. An interrupted install
has no completed installation receipt; discard that new failed environment and
start again. Private data is untouched.

Staff launch asks for the external private workspace directory (Enter uses the
platform-local default), then asks twice for a local app passphrase when one is
absent. `--data-dir` overrides the prompt. Use the same selected directory on
later launches. No Python, JSON, SQLite or environment-variable editing is
required. The server reserves loopback, checks retained source integrity, prints
health categories and opens the browser only after startup. Keep the terminal
open; Ctrl+C stops the foreground watcher and server. `Lock workspace` revokes
the browser session. `scripts/launch-demo.ps1` and `Launch-Demo.command` provide
the synthetic path. A busy port can be selected explicitly with `--port` (or
PowerShell `-Port`).

## Optional OCR and dependency changes

For a new Mac OCR environment use `dependency_artifacts.py fetch/install` with
`--profile ocr`, and the reviewed macOS 15+ target. This full receipt includes
the base closure and avoids a later unhashed pip modification. The model is
prepared separately by `scripts/prepare_ocr.py`; it never downloads a model.
The exact English model is 4,113,088 bytes, SHA-256
`7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2`, revision
`87416418657359cb625c412a48b6e1d6d41c29bd`, Apache-2.0. See
[extraction dependencies](DOCUMENT_EXTRACTION_DEPENDENCIES.md) for native engine
limitations and the fixed-model requirement. Optional cysignals is LGPL-3.0;
retain its license, replacement ability and corresponding upstream source
availability when distributing that optional wheelhouse. No weights are in the
source archive. Windows/Linux optional OCR has no reviewed install receipt.

Maintainers changing dependencies use the explicit `review` command on a NEW
external staging directory, then inspect the diff and run platform tests:

```sh
python scripts/dependency_artifacts.py review --target macos-arm64 --directory /new/staging/mac-wheels
python scripts/dependency_artifacts.py review --target windows-x64 --directory /new/staging/windows-wheels
python scripts/dependency_artifacts.py review --target linux-x64 --directory /new/staging/linux-wheels
```

Review is the only action that resolves pins and writes wheel receipts. It
compares downloaded hashes with current PyPI metadata and checks active target
dependencies, not the host's marker environment. Normal fetch/verify/install
commands never update reviewed hashes. Wheel licenses, native components and
current advisories still need review; a matching hash establishes neither safety
nor a vulnerability scan. No new recurring fee is introduced.

## Health and verification

`run.py health --mode staff --data-dir <selected-private-directory>` and the
authenticated acquisition page show version/schema, database access/migration,
Python/runtime patch, source manifest, retained source hashes, coarse free space,
data-directory permissions, backup-directory access, optional OCR, dependency
installation status and acquisition-folder availability. The JSON contains fixed
categories, version/platform identifiers and no private paths, account labels,
amounts, filenames, source text or credentials. It can read incompatible schema
state without migrating it. OCR health establishes model/library presence,
not successful inference; the synthetic OCR benchmark is separate.

POSIX permissions check mode restrictions. On Windows, a read-only, bounded
PowerShell ACL check looks for broad Everyone/Authenticated Users/Builtin Users
allow grants and reparse points on the workspace/database/source/backup roots.
An execution-policy block reports `acl_check_unavailable`; it never bypasses
policy. A result without broad grants is a limited check, not complete Windows
access-policy certification. School IT reviews owner/group/effective ACLs and
encryption on the actual workstation. Installed dependency health compares
versions and the recorded installation receipt; it does not re-attest every
mutable file in site-packages or the interpreter binary.

`scripts/portable_rehearsal.py` creates two byte-identical source archives,
verifies/extracts one, installs a separate fresh environment from the exact
offline wheelhouse, and runs real loopback HTTP with synthetic data. It exercises
login, explicit invoice approval, watcher PDF/XML/XLSX intake, unchanged original
downloads, separate operational approval, restart with watcher disabled,
spreadsheet relationship reuse, backup/download, restore into a disposable
workspace, integrity checks, logout and graceful process stop. Run it with a
new external `--work-dir` and the selected `--wheelhouse`. It is a handoff
rehearsal, never an updater or a replacement for native browser/OS acceptance.

CI executes these checks on Windows Server 2025 x64, macOS 15 arm64 and Ubuntu
24.04 with Python 3.13.15 following the authorized candidate-branch publication.
See [synthetic CI](SYNTHETIC_CI.md) for the matrix and explicit platform skips, and
[current acceptance](RC3_ACCEPTANCE.md) for actual run results, including the
preserved initial Windows failures. School
runtime installation, Windows desktop/ACL behavior, Finder quarantine/Gatekeeper,
current dependency/native advisories and real-provider acceptance remain distinct
release gates. No production-ready claim or final tag follows from local tests.
