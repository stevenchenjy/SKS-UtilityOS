# Explicit account billing schedules

The schema-6 candidate extends **Bill completeness** with account statement
schedules. Every-two-month invoices use a selected anchor month (January gives
January/March/May/July/September/November), an issue day, grace days and inclusive
effective dates. A day beyond month end is clamped to that month's final day.
The issue date is not a service-period boundary and does not imply a 60-day
consumption period. Public Cornwall dates are research context, not an automatic
configuration for school accounts; see [provider evidence](PROVIDER_FILE_WORKFLOWS.md).

Choose an account with an already reviewed meter relationship, confirm the
cadence and dates, give a reason, and acknowledge the decision. One expected
statement is counted per account and invoice month, even when it contains
multiple service points. Separate statements under one account in the same
month are not modeled as multiple expected invoices in this slice. Receiving a
statement does not establish complete service coverage.

The report distinguishes approved, under review, not due, missing, and not
scheduled. An expected invoice becomes missing only after its issue date plus
the inclusive grace period. Dates are assessed against the local application's
calendar date, displayed as **as of**. A month outside the schedule is not
missing and does not imply zero use. Already received or approved documents can
be shown in unscheduled months without increasing the expected-statement count.
Unconfigured accounts never produce missing-bill assertions.

Account-specific exceptions can skip a chosen month or set an extra/rescheduled
issue within that invoice month. Each exception needs a reason; up to 24 are
supported. Monthly, delivery and irregular behavior remains available. Delivery
and irregular services are not marked missing unless an explicit exception
establishes an expected statement.

The selected retrieval plan is a reminder of staff's intended manual workflow.
It does not download anything, start scanning, connect a portal or schedule a
background job. Usage sampling belongs to the timestamps and delta/cumulative
semantics of each operational source, not to invoice or retrieval cadence.

## History, existing expectations and recovery

Legacy meter-level expectations remain retained. Their account statement count
is grouped by account; conflicting meter cadence decisions require confirmation
and establish no expected count. A new account schedule explicitly replaces
that account's legacy expectations in the current report. Original meter
relationships and old expectation history are unchanged.

Every schedule edit appends an immutable version with its reason, a hash and an
audit binding. The latest schedule is the current operator decision applied to
the selected months; older versions are retained review history, not an
automatically reconstructed historical calendar. Review the complete effective
range and exceptions when changing a schedule, including historical months that
should remain expected. There is no inferred continuation of an expired rule.

Revision checks reject stale edits. Integrity verification checks both the
journal and corresponding audit events so missing decisions cannot silently
restore an earlier rule. Startup, backup, restore, migration and stopped-app
`check` include schedule verification. Private backups include the schedule
and history; diagnostics omit their fields, reasons and account identifiers.
Schema 5 remains readable only by old code until an explicitly confirmed,
backup-first migration creates the schema-6 tables.

## Synthetic checks

Backend tests cover account-level multi-meter counting, anchor parity, leap-year
month ends, inclusive grace/effective dates, quiet months, delivery exceptions,
legacy conflicts, invalid/stale decisions, missing history, diagnostics and
backup/restore. `scripts/native_schedule_smoke.py` creates a new external demo
and exercises desktop/mobile configuration, saved exceptions, exact dates,
unchanged charges, logout and restored schedules. It requires no provider or
private record. Results are recorded in [verification](VERIFICATION.md).
