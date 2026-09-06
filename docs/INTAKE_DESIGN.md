# 0.4.0 intake engineering contract

## Baseline recorded before application changes

On 2026-09-06 the clean working tree and all 83 source-manifest entries matched
immutable `v0.3.0` commit `e61facf6c07079add53be46bf6e2f319b085f6df`.
The trusted source archive SHA-256 is
`41423c847f659132a9309c5c9cfd5ebf92501bf4641c5ed0743ae62f262e4f7b`.
All 144 tests passed both in development and a fresh wheel-only offline install.
Native Chrome repeated desktop/mobile login, CSV/manual PDF/XML intake,
approval/rejection, correction/rebill, downloads, export, logout and recovery
from a browser-created backup. Actual retained 0.2 code produced a new synthetic
workspace which the trusted 0.3 installer migrated successfully; source bytes
were unchanged and integrity checks passed. The two already documented upstream
deprecation warnings remain. No new baseline failure was found. The baseline
tag will not be moved or rewritten.

## Accepted scope

Authorized staff obtain files themselves, supply them locally, review the source
and approve a draft. No portal credential, portal browser automation, external
extraction service, unattended inbox watcher or template self-modification is
part of this release. All development sources are visibly fictional.

The existing invoice ledger, integer cents, decimal quantities, replacement
lineage, audit chain, saved revisions and explicit stopped-app migrations remain
the authority boundary. Extraction proposes values; it never posts invoices.
Missing current charges must not be replaced with a balance due. Supply-only
quantities do not become repeated consumption; delivery volume remains purchases.

## Implementation and acceptance sequence

1. Evaluate current local extraction projects and record licenses, dependencies,
   offline requirements and measured installation size. Exercise a small OCR
   fallback before choosing it; keep manual entry available without that model.
2. Add a bounded PDF worker, a formal candidate/evidence schema and versioned
   provider templates. Separate immutable extraction from staff-reviewed values.
   Recognize provider/layout anchors independently of account and meter values;
   unknown or changed layouts must require review, never silently match old rules.
3. Add durable intake attempts, picker/drop/batch import and explicit local inbox
   scanning. Keep per-file failure isolation, stable-file checks, duplicate guards,
   source atomicity and interruption recovery. Never recurse or follow symlinks.
4. Present a local rendered source beside editable fields, including page/region
   navigation and a mobile fallback. Preserve stale-edit protection, ancillary
   bill details, structured correction differences and immutable original evidence.
5. Add explicitly configured service cadence and a synthetic completeness view;
   do not infer expected bills from observed associations alone. Separate private
   local correction analysis from allowlisted diagnostics.
6. Generate and benchmark a deterministic fictional PDF corpus across utilities,
   scans, multiple meters/pages, credits/rebills, two layouts and drift/failures.
   Count exact field matches, false/missing values and wrong units by extraction
   method. Publish measured results with their synthetic-only limits.
7. Run regression, real process-interruption, migration, backup/restore, offline
   installation and native desktop/mobile checks. Review dependencies/advisories,
   create a reproducible source-only archive, and only then create `v0.4.0`.

Temporary evidence, models, environments and generated release ZIPs remain in a
new external development directory. No private staff location is opened by this
development work. Later school acceptance and real-layout validation remain
school-controlled decisions.
