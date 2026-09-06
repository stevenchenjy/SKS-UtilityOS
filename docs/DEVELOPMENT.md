# Development and local release process

## Trusted baseline

On 2026-09-06 the existing Git repository was clean at initial commit
`593b317`. All 66 source files in its 0.2.0 release manifest exactly matched
the previously verified source archive, SHA-256
`a59014f04e399f6558bd9eec1c98b81502a992f5e0d73c6b4ea9d8d759c25842`.
The existing commit also contains `.gitattributes` and the manifest itself.
The local annotated tag `v0.2.0` now preserves that baseline before application
changes. The repository already had an `origin` remote when inspected; this
work did not create, contact, or push to it. No history was rewritten.

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
