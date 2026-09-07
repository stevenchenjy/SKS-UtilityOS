# 0.5.0 engineering plan and baseline

Development uses synthetic records only. This milestone adapts local bill
layouts through authenticated staff setup, with immutable versions and explicit
validation/activation. It does not authorize school deployment or private-data
access by the developer.

## Recorded baseline — 2026-09-07

- Clean `main` at `57a293b2c33f1bbd667c995f3885b2ec9778b0ee` before application changes.
- Annotated `v0.4.0` object `48498efc0cf4021216f0062969e795b063b5bd1d`
  peels to that exact trusted commit.
- `origin` is `https://github.com/stevenchenjy/SKS-UtilityOS.git`.
  Its release tag was absent. The user-authorized, non-forced push of only
  `refs/tags/v0.4.0` succeeded; remote tag and peeled commit were verified.
  No branch or other tag was pushed.
- The preserved 0.4.0 source archive has SHA-256
  `a8098d4236b6a616b142986459ecce940d0d649f0ea23c7e41d954a6fb01df6e`.
  Its 135 manifest entries match the trusted Git blobs. The archive and original
  manifest remain outside the working tree and in the immutable tagged release.
- Baseline regression: **201 passed**, two existing test-client deprecation
  warnings, 20.37 seconds on the development Mac.

## Delivery and acceptance checks

1. Preserve the bounded PDF worker and canonical evidence contract. Expose a
   bounded observation adapter for local setup. No new runtime dependency or
   model is planned. Retest native/OCR fallback and existing intake first.
2. Add schema 5 private provider/layout tables. Definitions and validation
   snapshots are immutable and audit-bound; status changes append events.
   Startup never migrates. Damaged rules are quarantined from extraction while
   manual review remains usable. Test backup/restore and an explicit 4 → 5
   upgrade plus rollback to the pre-upgrade snapshot.
3. Implement a bounded, literal/region rule vocabulary with typed parsers,
   repeatable service sections and explicit units. Reject ambiguity and unknown
   structure. Test independent unknown-provider, changed-layout, multi-service,
   scan, supply-only and delivered-fuel fixtures through authenticated APIs.
4. Extend the existing evidence viewer and navigation with setup and management.
   Operators select source candidates and roles, preview a draft, save a version,
   select approved local bills for exact comparisons, and explicitly activate or
   retire it. Require at least two distinct approved sources and exact required
   fields before activation. Candidates always require ordinary ledger review.
5. Aggregate scoped validation and approved correction evidence. Flag repeated
   failures for a new proposed version; never rewrite prior extraction or rules.
   Preview and export exactly the same fixed-schema, value-free support JSON.
   Test privacy sentinels, stale actions, ambiguity, corruption and recovery.
6. Add minimal synthetic-only CI if it fits the reviewed dependencies. Keep
   native Mac acceptance separate. Run regression, native desktop setup/mobile
   review, current advisories, fresh install, source checks and reproducible
   packaging. Record actual results before creating `v0.5.0` locally.

No real provider compatibility or general extraction accuracy is claimed from
the synthetic corpus. School IT must validate its own layouts and distribution.

## Implementation result

The complete slice and measured acceptance results are recorded in
`PROVIDER_STUDIO.md`, `CHANGELOG.md` and `VERIFICATION.md`. The registry is one
append-only typed journal rather than several mutable configuration tables.
Both single-service and numbered repeated-section rules are supported. No new
application/model dependency was needed; public synthetic CI uses separately
reviewed pinned first-party actions. All local definitions in development were
created through authenticated application workflows using fictional PDFs.
