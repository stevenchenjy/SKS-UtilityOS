---
name: local-utility-engineering
description: Build and maintain a staff-local school utility ledger with reviewed bill imports, correct meter/account relationships, free file-based data sources, privacy-safe diagnostics, and tested operator-controlled releases. Use for UtilityOS accounting, importers, security, deployment, and support changes.
---

# Local utility engineering

Read the repository instructions and inspect the affected workflow. Use the smallest coherent implementation that a future school IT maintainer can understand. Complete an end-to-end slice, test it with synthetic data, and record what remains unverified.

## Design invariants

The developer workspace contains synthetic data. Staff workspaces contain school data and remain outside source control, AI tools, and unsanctioned cloud synchronization. Portal secrets are never needed for file-based imports. Local staff approval controls every committed invoice and new measurement mapping.

An invoice is a financial document; meter readings are measurements. Preserve their separate identities and reconcile totals explicitly. Keep invoice dates, exclusive-end service periods, current charges, balance-due semantics, supplier identities, and stable meter codes understandable in both data and UI.

Use decimal arithmetic and known units. Record delivery volume separately from consumption. Detect duplicate invoices, overlapping consumption, and revised intervals. Preserve unsupported data as a staff-visible validation failure rather than inventing missing semantics.

## Workflow

1. Inspect the current implementation and existing tests. Create a small plan with concrete acceptance checks and identify any real external decision.
2. Use official primary documentation for standards, APIs, dependency licenses, and current fees. Capture a short source note. Read any third-party skill or install script before executing it.
3. Implement the data path, validation, useful UI, and tests together. Maintain working backups and reproducible fixtures.
4. Verify calculations and failure cases. Exercise the browser workflow and inspect the rendered result. Clearly label any transport bridge or mocked dependency used in testing.
5. Update the operational guide and release notes. Package reviewed code and synthetic fixtures only; keep source data, logs, databases, and credentials outside the release.

## Connection admission check

Before adding any automatic connector, obtain its exact utility coverage, supported account class, available fields, interval granularity, publication lag, consent procedure, registration requirements, authentication method, fees, retention conditions, and failure/revocation behavior. A royalty-free standard supplies no guarantee about a particular utility or hosted service. Keep the file-only workflow usable when a connector is absent.

## Private support

Diagnostics must use a positive allowlist. Unit-test with sentinel identifiers, document names, account strings, amounts, and secrets to show their exclusion. Keep full backups and ledger exports clearly classified as private. When sanitized diagnostics cannot reproduce an issue, ask school IT to perform the private inspection and provide a synthetic failure case.

## Deployment gate

Before staff use, verify the chosen operating system, dependency advisories, native browser behavior, correction and rebill semantics, backup/restore, school data-retention policy, and named maintenance ownership. Any multi-user network deployment needs an explicit design for TLS, identity, role permissions, concurrency, and audit attribution.
