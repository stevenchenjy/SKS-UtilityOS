# Private Provider Onboarding and Local Template Studio — 0.5.0

## Local authority

Staff obtains an authorized bill outside UtilityOS, imports it on the local
computer, checks the original and proposed fields, and approves the invoice.
The developer builds with fictional examples. No private source, local template,
account, meter, address, amount or portal credential is needed by the developer.

**Provider Management** holds private provider labels and immutable layout
versions. Built-in fictional templates remain in `provider_templates.py`.
School-local definitions live only in the external workspace's SQLite database.
They travel in confidential workspace backups, never in a source release or
ordinary diagnostic/quality export. Private layout text must not be pasted into
an AI tool or a public issue.

## Onboard a provider

1. Import a PDF. Open **Set up or inspect provider layout** from its review page,
   or use **Provider Management → Set up a provider**. Opening setup saves a
   pending bill's current review revision; it does not approve it.
2. Choose an existing local provider, or create a local label and commodity.
   Use this same provider label when approving the acceptance bills. A local
   provider's commodity and label are immutable; a different identity is a new
   registry entry. This registry is separate from the ledger's account mapping.
3. Select a text line in the rendered source or the searchable candidate list.
   Mark the provider identifier and, when available, a distinct layout marker.
   These are exact literal lines with explicit page/row constraints. They may
   contain private text and are never copied into the support bundle.
4. Choose **One service in the document** for an ordinary single-service bill.
   For multiple services, select the start of a repeated service section and
   choose **Numbered repeated service sections**. The supported form is a
   literal prefix followed by consecutive numbers `1`, `2`, and so on, including
   a numbered section `1`. The source need not use the fictional wording.
   Up to 50 sections can cross pages. Multiple unnumbered sections, arbitrary tables,
   multilingual documents and visually inferred associations require manual
   entry or a separately tested future rule extension.
5. For each source candidate, assign a semantic field and inspect the proposed
   literal label. Choose an inline value after a colon, a value below or to the
   right of a label, or one whole line in a selected region. Set the date format,
   expected unit where appropriate, and whether the field is required. Header
   locators normally use a selected row region; repeated service locators search
   within their section. Changing the source preserves the unsaved definition
   and disables the old editor while the new observations load.
6. Confirm document kind and quantity treatment. Supply-only charges use zero
   repeated consumption; oil/propane delivery represents purchased volume.
   Current totals and line charges must come from their own printed fields.
   Balances and amount due are separate supplementary values. An explicit
   inclusive-end setting proposes the following day as the ledger's exclusive
   end; the original string and coordinates remain in the evidence.
7. **Preview extraction**, compare the proposed values with the source, and
   **Save new draft layout**. A saved definition is immutable. A preview never
   replaces a retained extraction or silently changes an approved invoice.
8. Complete ordinary review of at least two representative PDF sources. The
   initial onboarding bills require manual entry; preview values help source
   comparison but are not copied into an approved record by the wizard. Use
   **Additional extracted bill details** for demand, due date, balance, address,
   components and other supplementary fields, including previously missing
   values. Check account interpretation, service mapping and every charge.

If text/OCR observations are unavailable, retain and review the PDF manually.
Optional OCR has the same pinned public model and local installation procedure
as 0.4.0. No model, engine or rule is downloaded automatically.

## Validate and activate

Open a saved version, select one to ten locally approved PDF sources, and choose
**Validate selected bills**. Only distinct retained PDFs approved under the same
local provider label and commodity are eligible. The latest approved review of
each source is the comparison target; a cancelled target cannot qualify.

The result records the selected source/review hashes and revisions privately,
plus exact matches, missing candidates, incorrect candidates requiring
correction, unit conflicts, layout conflicts and values entered manually because
the original import lacked them. Decimal numeric equality does not treat a
formatting difference such as `124.50` versus `124.5` as a correction. Optional
fields absent in both candidate and approved review count as an exact absence.
The selected-set results are not general model or real-provider accuracy.

Activation requires at least two distinct approved source hashes, an exact
nonmissing match for every required field in every service section, matching
service counts, matching provider/layout markers and explicit staff confirmation.
Core required fields cannot be omitted from the rule definition. Mark demand
and other consequential fields required when applicable. Optional field
failures remain visible for staff judgment. A newer validation or changed
approved review invalidates the earlier activation request. Stale status and
version-save requests fail; they cannot overwrite another decision.

At most five versions per provider may be active at once, within the pilot's
100-provider/1,000-version limits. Retire unused active versions before exceeding
that bound. Multiple matching active versions abstain with an ambiguity warning.
Required missing/conflicting values or changed marker geometry abstain as drift.
No activation creates a financial record. All future candidates still require
normal source comparison, mapping checks, stale-edit protection and approval.
Changing registry decisions while a file is being extracted requires a safe
import retry rather than committing candidates from a changed configuration.

## Revisions, drift and correction evidence

For a changed design, inspect the known provider, create a new version, select
the changed source, update its marker/field locators, and independently validate
that version. Prior versions and extraction bindings remain. **Retire this
version** is explicit and permanent for that version; another proposal is a new
draft. There is no historical-definition deletion or silent historical reparse.

Management shows selected validation date/counts, state, future sources that
were approved using the layout, field corrections and provider-level drift.
Repeated corrections to the same field (two or more), or provider drift observed after a version was created, flag investigation.
The provider-level drift count retains older history; initial onboarding without
an active layout is marked inactive and is not counted as drift. The latest approved interpretation of an original
source counts once; repeated saves or a correction draft do not inflate the
number of reviewed sources. Prior validation and status decisions are retained.
These counts propose investigation; they never change rules, fine-tune a model
or automatically deactivate/approve a record.

## Exact, value-free support preview

**Provider Extraction Support Bundle** constructs a separate strict allowlist:
application/schema version, random anonymous provider/layout IDs, version/hash,
state, bounded semantic/rule names, selected-set evidence categories, fixed
parser code and integer counts. `provider-support-schema.json` is the contract.

Choose **Preview safe bundle**, inspect the complete JSON and its SHA-256, then
explicitly download it. The browser downloads those exact displayed bytes;
later validation changes do not substitute another report. The export excludes
PDFs/images/OCR text, source snippets, rule labels/coordinates/definitions,
provider labels, filenames/paths, account/meter/address values, invoice references
or dates, quantities, demand, charges, balances and credentials. Anonymous IDs
and the hash can correlate repeated reports; the UI makes that visible.

Optional label-bearing export is deliberately not provided. School IT should
construct a fictional reproduction with the same bounded locator/ambiguity
pattern when the safe counts alone are insufficient. Ordinary diagnostics and
the older extraction-quality export continue to exclude local definitions.

## Storage, integrity and recovery

Schema 5 adds `local_provider_records`, an append-only journal with distinct
provider, layout, validation, status and extraction-link record kinds. Each has
an immutable random ID, UTC creation time, a canonical content hash and an audit
binding committed in the same transaction. Layout records include staff-setup
provenance and parent-version identity. Indexed parent references link decisions
to the provider/layout, and source links bind the original extraction hash.
The original schema-4 evidence contract and immutable source storage remain.

Updating or deleting a journal row is rejected. Missing records, altered hashes,
broken definitions or removed journal guards quarantine the entire local
registry, preventing an older activation from silently becoming effective.
Manual/built-in review remains available. The management screen reports the
problem without exposing private exception data. Integrity checks and backup
creation fail on damaged templates; preserve the directory and restore a known
intact private backup into a new recovery directory with authorized local IT.
Hash/audit checks detect accidental modification, not a privileged attacker who
can rewrite the database, application and audit chain together.

Backups carry definitions, all versions, validation/status history, source
bindings and normal ledger data. Software installation leaves that directory
untouched. Explicit migration adds schema 5 without fabricating local templates
or reparsing old bills. Old code cannot read schema 5. Rollback to 0.4 uses its
retained code and pre-upgrade schema-4 backup in a separate directory; preserve
the schema-5 workspace for recovery of later work. There is no schema downgrade.

## Extraction adapter for future private A/B evaluation

`pdf_extract.task(..., action='observe')` is the bounded observation boundary.
It accepts retained PDF bytes through private IPC, returns validated
`Observations` (adapter version 1, native/OCR lines, page/point boxes, rotations,
methods and fixed codes), or a fixed manual-fallback result. Existing page, byte,
text, memory/concurrency and child-process deadlines remain. Unknown-provider
OCR now retains readable observations even without fictional label matches.
An observation is untrusted source data, not an instruction or a ledger record.

`provider_rules.py` interprets the validated declarative `Definition` contract
in `local-layout-schema.json`. There are no operator regexes, executable plugins,
SQL expressions or scripting hooks. Rules use exact literal comparisons and
bounded page/region/distance searches. The compiler emits the unchanged
canonical candidate/evidence schema; metadata defaults are marked for review.
Ambiguity never selects an arbitrary account or service value.

A future local engine must implement this boundary or produce the same strict
candidate contract with source-backed evidence and fixed failure categories.
School-side A/B evaluation must use separately selected, approved local sources,
preserve both candidate outputs independently, compare exact typed fields with
the same immutable reviewed target, record engine/model/hash/resource limits,
and export only the dedicated safe count schema. No new engine may approve,
rewrite old extraction or learn rules silently. No Docling, Granite, Torch, MLX
or other model/runtime was added in 0.5.0; the independent synthetic cases were
handled by the existing local engine plus bounded rules.
