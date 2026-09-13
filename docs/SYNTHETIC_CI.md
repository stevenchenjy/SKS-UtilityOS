# Public synthetic CI and dependency decision — 2026-09-07

`.github/workflows/synthetic-ci.yml` now has a matrix of Ubuntu 24.04 x64,
macOS 15 arm64 and Windows Server 2025 x64 for source and fictional fixtures.
It selects CPython 3.13.15, fetches exact target wheel artifacts using checked-in
SHA-256 receipts, verifies and installs a fresh runtime offline, then runs the
portable code-folder handoff rehearsal. It separately installs the pinned
development test packages, runs `pip check` and `python -m pytest -q`, checks the Git source allowlist,
builds/verifies two identical source archives, and runs the 25-document digital
extraction benchmark. A changed working-tree manifest is not assumed to be a
release: CI builds and verifies its own source-only candidate archive.

No staff workspace, production configuration, portal credential, OCR model,
school browser profile or application deployment is involved. There are no
custom secrets, background schedules, artifact uploads or deployment jobs.
The token has `contents: read`, checkout does not persist credentials, and the
workflow uses `pull_request`, not privileged `pull_request_target` execution.
Only this exact workflow path is added to the release allowlist; arbitrary YAML
or private configuration directories remain excluded.

Two maintained first-party GitHub actions were reviewed using their release,
package, action metadata and MIT license files on 2026-09-07:

| Component | Immutable pin | Decision |
|---|---|---|
| checkout 7.0.1, released 2026-07-20 | `3d3c42e5aac5ba805825da76410c181273ba90b1` | Source checkout on disposable CI runner; MIT; Node 24 runner action |
| setup-python 7.0.0, released 2026-07-20 | `5fda3b95a4ea91299a34e894583c3862153e4b97` | Exact Python runtime on disposable CI runner; MIT; Node 24 runner action |

These actions execute upstream bundled code on CI, with dependency/provenance
trust that must be reviewed when updating pins. They are not dependencies of a
school installation; no new local Python package or model was added. Sources:
[checkout release](https://github.com/actions/checkout/releases/tag/v7.0.1),
[checkout license](https://github.com/actions/checkout/blob/3d3c42e5aac5ba805825da76410c181273ba90b1/LICENSE),
[setup-python release](https://github.com/actions/setup-python/releases/tag/v7.0.0),
[setup-python license](https://github.com/actions/setup-python/blob/5fda3b95a4ea91299a34e894583c3862153e4b97/LICENSE),
[GitHub secure-use guidance](https://docs.github.com/en/actions/reference/security/secure-use).

Hosted runner execution is separate from local reproduction of the CI commands.
The workflow is prepared for the public synthetic repository and has not been
pushed or dispatched as part of the 0.5.0 release work. Only the explicitly
authorized, previously absent `v0.4.0` tag was published. Running/publishing new
source on GitHub remains a separate deliberate release step.

Native Mac Chrome workflows, optional OCR/model checks, real launcher operation,
fresh installation and recovery rehearsals remain separate acceptance checks.
The reference corpus test that requires byte-identical Mac rasterization is
explicitly skipped on other platforms. Its source/hash and digital extraction
checks still run; the full reference-byte test runs on the development Mac.
This distinction is not a claim of native Linux, Windows or staff-machine
acceptance. Repeat relevant native tests on the actual approved workstation.

The rc3 matrix is prepared and has not been pushed or dispatched during the
current local milestone. Windows wheel hashes/target metadata are verified on
the Mac staging host, which does not establish Windows execution. The local
fresh-install rehearsal used macOS 26.6.2 arm64/Python 3.13.2. Python 3.13.15
installer artifacts were hash-checked but not installed locally. The portable
rehearsal uses real HTTP and cookies; native browser/mobile/download tests remain
separate. Windows Server CI is not Windows 11 staff-device acceptance.

The Windows artifact-tampering test's symlink-creation case explicitly skips
because creating symlinks can require device privileges; the remaining corruption,
missing/extra-member, traversal and wrong-hash tests run. The native Mac raster
byte-equality fixture test remains skipped off macOS. No other OS test is marked
passed because its runner is unavailable. See [current runner labels](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
and [portable deployment](PORTABLE_DEPLOYMENT.md).

The FIFO replacement race test also explicitly skips Windows, where `mkfifo`
and POSIX nonblocking FIFO behavior are unavailable; the regular-descriptor
replacement test remains cross-platform. These are declared platform limits,
not successful Windows native results.
