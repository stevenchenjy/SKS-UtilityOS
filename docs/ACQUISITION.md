# Portable local acquisition — 0.6.0-rc3

The **Acquisition** page gives the local operator one view of folder state,
recent file processing, pending review, failures and installation health.
Only authenticated local sessions can read it or change controls; changes also
require the existing same-origin and CSRF checks. This page contains private
filenames and folder paths for the operator. It is not a support export.

## Folder operation

Create a separate authorized local folder outside code, the ledger workspace and
cloud synchronization. Save that folder and explicitly enable watching. Demo
mode additionally requires synthetic-file acknowledgement. The worker exists
only within the running UtilityOS process, starts **disabled on every launch**,
and stops with the application. A stored folder does not imply permission to
resume after restart or restore.

- Checks occur every five seconds, with at most 1,000 directory entries and one
  parser import per poll. There is no recursive traversal.
- Dotfiles, browser temporary suffixes and subdirectories are ignored. Ordinary
  files must retain the same identity, size and modification time across polls,
  at least two seconds apart. They must also be at least two seconds old.
- Reads are bounded to eight MB. Symlinks and nonregular files are rejected;
  file-descriptor and path identities are checked before and after the read.
- Originals are fingerprinted and published through existing non-overwriting
  source storage. The downloaded file is never renamed, changed or deleted.
- Unchanged already-attempted files are not repeatedly parsed in the same
  session. Repeated bytes reuse their retained source. A changed file is a new
  acquisition attempt; conflicts still require explicit review.
- Pause and disable prevent subsequent work; a file already being parsed may
  finish. Disable before changing folders. A missing folder produces a bounded
  error and is rechecked. Unchanged failed imports can be retried through the
  explicit scan or picker after the operator resolves the issue.

The worker has no portal, credential, email, external API or approval capability.
Review and explicit financial approval remain mandatory. A watcher error never
authorizes financial posting, changes source evidence or changes provider rules.

## Source adapter contract

`SourceAdapters.import_file(filename, raw)` chooses a format-specific candidate
workflow. Its result identifies the adapter, retained review IDs and duplicate
status. Every successful path retains the exact original through the common
document store, with source hash, file metadata and importer version. Normalized
candidate/provenance shapes remain specific to their measurement meaning:

| Adapter | Retained candidate / provenance | Required next action |
|---|---|---|
| PDF invoice | Financial draft, field evidence and immutable extraction | Compare source, resolve fields/mapping, explicitly approve invoice |
| Canonical invoice CSV | Financial drafts and original rows | Review each invoice and approve separately |
| Green Button XML | Interval delta channels, resolved ESPI relationships and raw reading evidence | Confirm local meter and approve operational intervals |
| CSV usage | Literal rows, mapping revision, normalized operational observations | Confirm mapping and approve usage |
| XLSX usage | Exact workbook, visible sheet/region, cell evidence and mapping version | Inspect/map literal data and approve usage |
| Future remote connector | Disabled Portfolio Manager boundary; local fictional response rehearsal only | Separate school authorization and external acceptance |

CSV dispatch recognizes canonical invoice headers, keeping incomplete
invoice-shaped files on the invoice validation path. Other CSV files enter
generic mapped usage. Dispatch never infers an authoritative unit, timestamp,
provider eligibility or meter relationship. PDF balances/payments remain
supplementary review fields; they do not replace current charges. Operational
delta and cumulative readings remain separate, with no counter differencing and
no addition to invoice quantities or charges. XML and mapped delta coverage may
not overlap on the same local meter without reconciliation.

The status table counts all pending retained sources, including direct mapped
usage uploads. Error history covers the latest 200 intake attempts and labels
that scope. Review queues retain their own complete pending records. The privacy-safe
health report uses fixed categories and omits those filenames, paths and values.
See [mapped usage](MAPPED_USAGE.md), [Green Button](GREEN_BUTTON.md),
[Portfolio Manager preparation](PORTFOLIO_MANAGER.md) and
[portable installation](PORTABLE_DEPLOYMENT.md).

## Water invoice field meanings

Synthetic water review tests preserve these independent meanings:

| Source meaning | Retained review field |
|---|---|
| Service from / exclusive service to | `services.N.period_start` / `period_end` |
| Printed service-day count | `services.N.service_days` |
| Previous / present cumulative reading | `services.N.previous_reading` / `current_reading` |
| Billed-period consumption and unit | `services.N.consumption_quantity` / `consumption_unit` |
| Current water charge | `services.N.current_charge` |
| Previous balance | `previous_balance` |
| Payments received | `payments_received` |
| Balance credits / adjustments | `balance_adjustments` (signed amount) |
| Current charges due | `invoice_total` |
| Total account amount due | `amount_due` |

Payments, adjustments and service-day count are optional supplementary evidence;
older retained extractions need not contain them and are not rewritten. The
operator can review them explicitly or define bounded Provider Studio rules.
A reading difference is a nonblocking investigation flag, not an instruction to
replace billed usage. Replacement, rollover, multiplier or adjustment semantics
may explain a difference. Missing source units block financial approval. Payment
stamps, handwriting and chart graphics are not authoritative measured history.
No school screenshots or private statements are included as fixtures.
