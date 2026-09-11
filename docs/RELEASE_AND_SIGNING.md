# Source releases and macOS signing

The current working candidate is **0.6.0-rc2**, unsigned and untagged.
The source push authorized on 2026-09-09 does not create a GitHub Release or
establish school deployment acceptance. The September 8 verification and local
archive receipts retain their original pre-publication status.
The schema-6 file slice requires explicit migration from the schema-5 baseline.
Retain the trusted `v0.5.0` source/manifest and use a distinct candidate archive
name. [UPDATE_REHEARSAL.md](UPDATE_REHEARSAL.md) describes the reproducible
synthetic code-folder switch and rollback. The 0.5.0 notes below describe the
retained baseline; no remote publication or unattended updater is implied.

## Current local release

0.5.0 is an **unsigned source ZIP** containing Python, browser modules, scripts,
tests and synthetic fixtures. Its manifest verifies the exact packaged bytes;
the local Git tags preserve reviewed source states. The trusted v0.4.0 tag was published under explicit authorization. Publishing
0.5.0 is a separate step; there is no automatic updater. Obtain the verifier and expected release through
a separately trusted school channel. A modified archive accompanied by a
modified manifest can still pass its own hashes; hashes alone do not establish
a publisher or safe behavior.

Prepare a new code folder and environment, verify the manifest, test a synthetic
demo, and obtain school IT approval before an installation or version switch.
The runtime diagnostic checks the unpacked source against its manifest and
flags extra executable modules in the application folders. Development edits
correctly show a changed manifest until a new release is built. The check does
not attest the installed Python interpreter, dependency environment or OS.

`python scripts/check_source_control.py` checks the Git index's source paths.
`python scripts/release.py build /external/SKS-UtilityOS-0.5.0.zip` creates a
source-only archive; `verify` validates its paths, membership and hashes. Review
contents as well as names. Generated archives, wheels, screenshots, logs,
workspaces, backups and credentials stay outside source control.

## Future macOS distribution decision

Developer ID signing binds a distributed app or installer to an Apple-issued
publisher certificate and enables Gatekeeper signature checks. Notarization
adds Apple's automated malware/signing checks and a ticket; it does not validate
utility accounting or approve access to school records. Apple's current workflow
uses Xcode or `notarytool`, with ticket stapling for distribution. See
[Apple's Developer ID guidance](https://developer.apple.com/developer-id/) and
[certificate requirements](https://developer.apple.com/help/account/certificates/create-developer-id-certificates).

A future self-contained app would need its Python runtime, native dependency
libraries and application bundle reviewed, packaged and signed consistently.
Signing a launcher alone would not authenticate mutable Python files loaded
from a separate folder. A signed installer package uses a Developer ID Installer
certificate; an application uses Developer ID Application signing. Choosing an
app bundle or installer and validating updates/rollback on the target Mac are
prerequisites; no packaging framework was added without that demonstrated need.
[Apple's certificate guidance](https://developer.apple.com/help/account/certificates/create-developer-id-certificates)
and [installer signing instructions](https://help.apple.com/xcode/mac/current/en.lproj/deve51ce7c3d.html).

As reviewed on 2026-09-06, Apple lists the Developer Program at USD 99 annually,
with possible fee waivers for eligible educational institutions. Eligibility and
approval cannot be assumed. School IT would own organizational enrollment,
certificate/key custody, build provenance, any notarization upload of software,
renewal/revocation and trusted distribution. No purchase, enrollment, certificate,
credential configuration or upload was performed.
[Apple enrollment](https://developer.apple.com/help/account/membership/program-enrollment/)
and [fee-waiver rules](https://developer.apple.com/help/account/membership/fee-waivers).

Until that decision, use the separately reviewed source-install process. Finder
quarantine/Gatekeeper behavior for a school-distributed download remains a target
acceptance check. Do not disable Gatekeeper or weaken browser/device policy to
make a demonstration run.

## Reproducible source archive

Pass the fixed release timestamp when building:

```sh
python scripts/release.py build /external/SKS-UtilityOS-0.5.0.zip \
  --source-date-epoch 1788652800
```

File order, timestamps, modes, manifest formatting and compression settings are
fixed. Two builds with unchanged inputs and the tested Python/zlib toolchain must
be byte-identical; changing the source timestamp changes the manifest. A standard
Git ZIP need not have identical container bytes, but its file contents must match
the same manifest. The source contains only reviewed code/docs/tests/fictional
fixtures, never OCR weights, wheels, logs or workspace data. Existing release tags remain immutable. A new trusted tag requires completed
release verification; an untagged candidate is not a completed release.
