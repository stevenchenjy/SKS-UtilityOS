# Development and local release process

## Trusted baseline

On 2026-09-06 an existing Git repository was present at initial commit
`593b317`. The 66 manifested working files matched the trusted 0.2.0 archive,
SHA-256 `a59014f04e399f6558bd9eec1c98b81502a992f5e0d73c6b4ea9d8d759c25842`.
A later object-level check found that the existing `text=auto` attribute had
normalized four synthetic CSV files inside Git. Baseline preservation commit
`38d20e6` retains the archive's exact bytes, preserves launcher permissions and
uses byte-preserving checkout attributes. All 66 manifest entries now match the
Git objects as well as the original release. The annotated local `v0.2.0` tag
identifies this corrected baseline; the original initial commit remains its
parent and remains in the main branch history. The local tag created during this
work was corrected before any publishing.

The repository already had an `origin` remote when inspected. This work did not
create, contact, fetch or push a remote. The `v0.3.0` local release tag identifies
the verified readiness implementation with its tests, technical documentation
and source manifest. Runtime workspaces and release archives remain external.

The following housekeeping commit strengthens `.gitignore`. Runtime databases,
source uploads, backups, exports, credentials, environments, machine settings,
and generated archives/evidence belong outside the repository. Only reviewed
synthetic CSV/XML/PDF fixtures under `samples` are exceptions. Git ignore rules
are an accident-prevention aid, not an access control: inspect the staged file
list before every commit and never force-add private material.

Use the existing Python environment and run `python -m pytest -q`. Verify browser
flows with a fresh external synthetic workspace as described in `README.md`.
Keep code, automated tests, and technical documentation in the same reviewable
change. Check `git diff --check` and the staged file list before committing.
Never publish or connect a remote as part of local release verification.

Before packaging, stage reviewed source and run:

```sh
python scripts/check_source_control.py
git diff --cached --check
python -m pytest -q
python scripts/release.py build /external/SKS-UtilityOS-0.4.0.zip
python scripts/release.py verify /external/SKS-UtilityOS-0.4.0.zip
```

Copy the generated source manifest into the repository, verify each indexed blob
against it, commit, and create the local annotated release tag only after the
installation/browser/migration checks pass. Check the source-only membership of
a Git archive as well as the working folder; checkout normalization must not
invalidate the manifest. Source manifests exclude themselves to avoid a
self-referential hash. A clean Git index is not a substitute for content review.

## Immutable 0.3 baseline and 0.4 release

The 0.4 work began with a clean tree at `v0.3.0`, commit
`e61facf6c07079add53be46bf6e2f319b085f6df`. All 83 manifested source files and the
archive hash `41423c847f659132a9309c5c9cfd5ebf92501bf4641c5ed0743ae62f262e4f7b`
were verified before behavior changed. `docs/INTAKE_DESIGN.md` records that
baseline and the acceptance sequence in a separate local commit. Do not move
`v0.3.0` or rewrite its history.

The 0.4 source build uses `--source-date-epoch 1788652800`; reproduce it twice and
compare archive bytes with the tested toolchain. Preserve the generated manifest
inside Git and check every blob, including the deterministic 28-PDF corpus,
against it. Run the old regression/readiness checks plus `native_intake_smoke.py`
and `benchmark_extraction.py` from a separately unpacked wheelhouse installation.
Use the actual retained 0.3 code to create a synthetic upgrade/rollback fixture.
No school data, real model-training examples or non-development artifacts belong
in these checks. All release operations remain local; no remote is contacted.
