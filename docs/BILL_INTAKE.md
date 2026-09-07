# Local bill intake — 0.4.0

## Authority and scope

An authorized operator obtains a file outside UtilityOS, supplies it locally,
compares the proposed fields with the retained source, and approves the draft.
Only approval posts financial records. No portal access, credentials, scraping,
cloud OCR, paid API, automatic approval or unattended folder watcher is included.
Development uses only visibly fictional documents.

The shipped templates recognize **five fictional providers and two labelled
layouts each**. They demonstrate a testable adapter contract; they do not claim
compatibility with real utilities. Unknown providers/layouts may yield candidates
from generic literal labels, always marked for review. A missing value stays
missing. Scans use optional local English OCR; manual completion works without it.
The older `demo-invoice.pdf` remains a useful manual-entry example.

## Import and review

Use **Import files** in **Utility Inbox**, the ordinary picker, or drag files onto
the import dialog. A batch accepts up to 25 CSV, XML or PDF files, 8 MiB each.
The dialog processes one file at a time and reports each result independently.
Use its fictional PDF links to download examples, then supply them through the
picker. Demo imports require a synthetic-data confirmation.

Intake records new/processing attempts before parsing. The history shows the
latest 200 attempts, extracted/needs-entry information, needs mapping/review,
duplicates, unsupported documents, safe failures, rejected drafts and approvals. A CSV whose drafts are split between approval and rejection reports partially approved.
A duplicate links to its retained drafts; it does not create a second invoice.
The single-file legacy API still returns the explicit duplicate rejection.
Unreadable or unsupported PDFs can retain a manual draft and the original source;
malformed CSV/XML produces a failed attempt without partial document records.

On desktop, the source appears beside the bill form. Select an evidence button
to navigate to the page and highlight the original line; use page/zoom controls
or download the unchanged original. A raster preview avoids running PDF content
in the browser. On a narrow screen the panes stack, selection scrolls to the
source and a toggle frees space for entry. Canvas zoom scrolls inside its pane.

Evidence states are deterministic: **high evidence (verify)**, **requires
review**, **missing**, **conflict**, and **manually corrected**. They are not
probability estimates. OCR always requires review. All PDF approvals require the
source/mapping acknowledgement. Editing any main or supplementary field clears
that acknowledgement. **Save draft** persists incomplete entry and its revision;
a stale browser cannot save or approve over a newer revision.

**Additional extracted bill details** holds demand, readings, due dates, address,
charge components, balances, amount due, currency and document kind. These stay
with the reviewed record; current invoice/line charges and quantity treatment in
the main form control ledger reports. Evidence paths refer to original candidate
service positions. Replacing or reordering service lines does not rewrite those
original observations; compare the full source and supplementary values again.

## Optional UtilityOS Inbox directory

Create a dedicated local directory outside both code and the utility workspace.
In **Utility Inbox → Optional local inbox directory**, enter its absolute path,
confirm the location and save. A blank location disables it. Staff mode rejects
common cloud-folder names; IT must also check the actual synchronization policy.
Directory symlinks, nested code/data paths and paths containing symlinks are
rejected. Configuration and scan require the authenticated session and CSRF.

Place only completed authorized files there. Explicitly confirm **Scan Inbox**.
Scanning is non-recursive, ignores hidden/unsupported-extension entries, limits
the directory to 1,000 entries and handles at most 25 candidates per action.
**Scan next files** continues the snapshot position; if the directory changes,
rescan from the start to avoid missing shifted entries. Hash duplicates are safe.
Files are never moved or deleted. A changed location must be reopened/confirmed.

Each candidate must be a regular non-symlink file within the upload limit, at
least two seconds old. The scanner verifies identity, size and timestamps before,
during and after the bounded read. A paused incomplete write cannot be proven
complete from timestamps alone: use completed downloads or copy by temporary
name then rename. Unsafe/unreadable/changing files report a bounded failure and
remain available for a deliberate retry. There is no permanent background task.

## Extraction and validation contracts

`extraction_schema.py` is the strict canonical schema; the corresponding JSON
Schema is in `extraction-schema.json`. It separates header and service fields,
raw strings, normalized strings, source page/point coordinates, method, exact
parser/model and template versions, and evidence states. Pages record dimensions
and OCR rotation. Money and quantities normalize with Decimal, never float.
The existing financial ledger still stores integer cents and decimal quantities.

`provider_templates.py` contains independent literal labels and public layout
anchors. Provider fingerprints use known fictional company names. Layout hashes
use public label positions, never account/meter numbers or field values. Known
matching requires header anchors and expected label regions. Missing anchors,
relocated account fields, renamed labels or ambiguous matches abstain from the
old template. This narrow geometry contract does not detect every possible
redesign, spoofed anchor or table structure; source review remains necessary.

Templates have immutable version identifiers and an active flag. To revise one,
add a new version and independent fictional fixtures, test drift/negative cases,
run the benchmark and regression/browser checks, then review a code release.
An inactive template remains in the registry for historical provenance. Neither
staff corrections nor the quality report automatically modify parsing rules.
Existing extraction snapshots are never silently reprocessed by an update.

Approval preserves date ordering, supported units, active invoice identity,
source-hash duplication, exact invoice/line reconciliation, stable meter mapping
and overlap checks. New account/service mapping needs acknowledgement. USD is
the only ledger currency; an uncorrected supporting-document classification is
blocked. Demand units/negative values, unknown units and negative consumption
are rejected. Explicit credits use negative charges with zero repeated quantity.
Supply-only printed usage remains source evidence but posts zero consumption;
oil/propane delivery quantity represents purchases. Previous balance and amount
due never fill absent current charges. Complete charge components and reading
differences produce review warnings when they disagree; they cannot establish
unprinted conversions, meter rollover or inclusive/end-date conventions.

## History, corrections and recovery

Schema 4 adds `document_extractions`, `intake_reviews`, `intake_attempts`,
`bill_expectations` and `expectation_history`. Original extraction is immutable,
hash-checked and bound to its extraction audit event. Review snapshots append
alongside the same draft revision and approval transaction. Corrections keep the
original machine observation and prior approved values, including supplementary
fields; a supplier rebill has its own source/extraction and explicit target.
The original financial version stays active until replacement approval succeeds.

A killed extraction worker cannot post an invoice. On app restart, an unfinished
attempt is marked failed safely for retry, or linked to an already committed
source if its response was lost. Worker timeout/failure leaves manual entry.
Source publication, draft/extraction insertion and financial approval preserve
the existing atomic retention and rollback rules. Original hashes and extraction
audit bindings are checked during backup, restore and maintenance. Model files
are public software assets, not part of a utility backup. Restored inbox settings
do not trigger a scan; confirm the location again. See `OPERATIONS.md`.

## Correction analysis and completeness

**Local extraction quality** counts documents, suspected layout drift, failures
and final approved field corrections by fixed provider/template/field keys.
Multiple saves are not multiple approved corrections; retained superseded and
cancelled versions remain historical samples. Two corrections to a field, or a
layout drift, propose developer investigation. Counts do not train a model or
change a template. Unknown providers are grouped as unknown. The report includes
no account, filename, document text, value or bounding box. It remains a separate
authenticated, explicitly exported report, not part of safe diagnostics; school
IT decides what to share and supplies fictional reproductions.

**Bill completeness** requires an explicitly confirmed account/meter relationship,
monthly/delivery/irregular cadence, active invoice-month range and reason.
Configuration retains history and rejects stale revisions. The experimental
view counts monthly Expected, Received, Under review, Approved and Missing for
that selected invoice month. Delivery/irregular relationships have no scheduled
monthly missing count. A replacement pending beside an active invoice is shown
without double counting. Rejected/cancelled invoices do not satisfy expectations.
There are no inferred whole-campus, service-period or real-data completeness
claims. New installations start without expectations; configure fictional
relationships to demonstrate the dashboard.

## Resources, offline use and known limits

Digital text uses pdfplumber/pdfminer; PDFium renders source evidence. A disposable
child processes bytes through private memory/IPC; there are no filenames in its
arguments, document logs, HTTP downloads, prompts or persisted page-image caches.
The parent allows one worker at a time, a 60-second deadline, 20 PDF pages, 4,000
point dimensions, 12 million render pixels and bounded text/response sizes.
The child also sets a 45-second CPU and 1 GiB address-space limit where supported.
These limits reduce risk; this is not an independently sandboxed OS process or
a promise against every hostile document. Memory/page-limit failures remain
manual drafts. IT may enforce network egress restrictions for the installation.

Optional OCR uses Tesseract's English LSTM model with a pinned revision/hash.
There is no automatic download. Prepare the public weights and reviewed wheels
in advance as described in `STAFF_INSTALL_AND_UPDATES.md`. OCR recognizes narrow
literal fields, not arbitrary tables, handwriting, multilingual documents or
supplier accounting logic. No Docling/Granite inference is claimed. The corpus
and benchmark in `VERIFICATION.md` are development evidence, not real-bill accuracy.
