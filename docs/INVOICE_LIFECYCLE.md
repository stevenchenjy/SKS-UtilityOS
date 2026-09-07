# Invoice lifecycle and correction contracts

## Financial records and reporting

An approved bill's reviewed payload, source, invoice fields, and lines remain immutable. The bill has a lifecycle state: `active`, `superseded`, or `cancelled`. Dashboard totals, quantities, anomaly comparisons, overlap checks, and the ledger CSV use active records only. The invoice ledger exposes all retained versions. Correction chains link each replacement through `supersedes_id`; a version has at most one successor.

A transcription correction creates a pending draft from the original reviewed payload and retains the same immutable source. A new supplier document is imported normally, then explicitly linked to the active original through **Use as replacement / rebill**. The staff reason and target invoice are saved with the draft. A replacement contains the complete corrected invoice, including every meter and service line; it is not a difference-only adjustment.

Approval revalidates the draft, current target state, invoice identity, units, meter mapping, charge reconciliation, and consumption periods inside one SQLite write transaction. Only the selected original is excluded from the replacement's overlap check. Its ancestors are permitted to have the same invoice number; unrelated invoice identities and overlaps remain blocking. After validation, the original is superseded and the full replacement is inserted atomically. A failed approval leaves the original active and the draft pending. A rejected correction has no reporting effect.

Only one pending correction per original is created through the application. If the original is cancelled or superseded after a draft was opened, that draft cannot be approved; reopen the current invoice or reject the draft. Closed drafts cannot be edited. HTTP approvals carry the current draft revision, preventing a stale browser view from overwriting a saved review. A caller that omits the revision is treated as revision zero for the original API contract; it cannot approve over a saved revision.

## Cancellation and credits

Cancellation requires a reason and a separate confirmation. It excludes the entire active invoice from current reporting and records a private history event. It preserves source bytes, reviewed values, prior versions, and draft history. It does not create a credit document, restore a superseded predecessor, or delete an audit event. Repeating a cancellation or cancelling a superseded version is rejected.

An independent supplier credit uses its own invoice reference, negative current charges, and `charges_only` lines with zero quantity. It can coexist with the original bill. If the supplier instead issues a full corrected invoice, use the replacement workflow to avoid counting both full invoices. A credit-only replacement removes the original's quantities as well as its charges; use it only when the source actually replaces the whole original. Finance must privately confirm that interpretation.

An invoice with several meters is replaced as one financial document. A separate supply account may share the delivery account's stable meter; its charges-only lines add no repeated consumption. Stable meter identity survives account changes. Original account-meter associations retain observed service history even when their invoice is later superseded; they are not assertions of currently active contractual service.

## Saved entry and audit data

**Save draft** stores incomplete field entry without treating it as a valid invoice. Financial validation remains mandatory at approval. The raw imported payload is retained separately from saved reviewed values. Each save and approval appends a revision containing the reviewed payload, reason, and correction target. Review history reflects explicit saves and approval, not every keystroke. Rejecting a draft preserves saved revisions; save first if uncommitted entry needs retention.

Bill history records approval, supersession, cancellation, related versions, UTC time, and reason. These histories are private application records included in backups. They never enter the safe diagnostic schema. The pilot has a single local operator, not per-person audit attribution or tamper-proof storage. Staff should keep reasons brief and avoid unnecessary personal information.

## Building and service mapping corrections

Inventory edits require the expected previous value, a reason, and acknowledgement of the reporting effect. A stale mapping edit is rejected. Renaming a building changes the current label for its meters; assigning a meter to a building changes reporting for all invoice months. A blank mapping represents unassigned/shared service. Before/after values are retained in `inventory_history` and shown in the app.

Prior approved review snapshots are not rewritten by inventory edits. To correct a wrong account or service-point code on an invoice, create an invoice correction. Commodity/unit changes to an existing meter and automatic sharing allocations remain unsupported. This release does not add a physical meter replacement lifecycle or a free-form account association editor.

## Extraction evidence in 0.4.0

PDF proposals retain immutable raw/normalized fields, page coordinates, parser/
model and template versions. Saved review snapshots and structured differences
share the draft revision. An approved correction starts with the previous human
values, including supplementary demand, dates, readings and balances, while the
original machine observation remains unchanged. A new-source rebill has its own
extraction snapshot and explicit replacement target. Only main current charges
and service quantities affect the financial ledger; amount due and prior balance
do not substitute for current charges. Changing any field clears the browser
review acknowledgement. Source evidence remains usable on closed versions and
after recovery from a verified backup.
