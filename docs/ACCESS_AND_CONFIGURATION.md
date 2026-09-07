# Access and local configuration

## 0.4.0 access decision (preserved from 0.3.0)

Named users and role enforcement are **deferred**. The supported installation
has one designated operator, one school-controlled OS account, a local app
passphrase and memory-only browser sessions. There is no shared service, school
SSO, user-administration UI or second independently authenticated approver.
Adding role labels to this shared credential would not establish who acted or
separate their authority. A school must first designate the operators,
maintenance owner, recovery authority and need for distinct local identities.
This release cannot be used as a multi-user or role-separated deployment.

The current operator can import and review bills/intervals, edit drafts and
mappings, approve/reject, inspect originals and histories, export, and create
backups. Cancelling an approved invoice or approving a replacement/rebill in
staff mode additionally requires the current local app passphrase in that
request. Login rate limiting also covers failed confirmations. Confirmation
only proves current knowledge of the shared app passphrase; it is not a second
person's approval. The public synthetic demo keeps its existing one-click flow.

Restore and migration remain unavailable through HTTP. They require the stopped
workspace, OS-level access, its exclusive lock and explicit confirmation flags.
Only the designated local IT maintainer should run them. Application settings
cannot grant remote maintenance. There is no user or role change API to audit;
local passphrase creation/change through the existing internal setup function
is now audited without recording the credential or hash.

## Proposed role contract for a later authorized local multi-user release

This table is a design decision, **not an implemented authorization promise**.
Every future endpoint must deny by default and enforce this policy in the
backend, including exports and original-file access. Named local authentication
and audited provisioning/revocation must exist before these roles are exposed.

| Operation | Administrator | Finance | Facilities | Read-only reviewer |
|---|---|---|---|---|
| View approved ledger, dashboard and audit | Yes | Yes | Yes | Yes |
| View/download original bills and private ledger CSV | Yes | Yes | Yes | No |
| Import bills and save/reject pending bill drafts | Yes | Yes | Yes | No |
| Approve financial invoices and independent credits | Yes | Yes | No | No |
| Approve corrections/rebills or cancel invoices | Confirm passphrase | Confirm passphrase | No | No |
| Import, map, approve or reject interval files | Yes | No | Yes | No |
| Edit existing building or physical meter mapping | Yes | No | Yes | No |
| Record observed account/service relationships as part of bill approval | Yes | Yes | No | No |
| Export allowlisted diagnostics | Yes | Yes | Yes | Yes |
| Create/download full private backups | Confirm passphrase | No | No | No |
| Migrate schema, restore, provision/revoke users or change roles | Stopped local maintenance with OS authorization | No | No | No |

New meter creation during invoice approval will need explicit mapping review
under this contract; existing mappings cannot be silently changed by invoice
entry. The school may revise the proposed matrix before implementing it.

## Configuration and secrets

Current executable configuration is the small `Config` dataclass: selected
mode, data directory, loopback port and an optional external OCR model directory. The SQLite settings table contains the
schema/mode, local password salt/hash, explicit inbox location and fixed internal state. Cadence has dedicated versioned tables. There are no
portal passwords, provider tokens, external endpoints, environment-driven
connectors or developer telemetry. Diagnostic and ledger exports select their
own fields; they never dump settings. Access/traceback logging is disabled.

Runtime records and configuration belong outside Git and code folders on an
approved local encrypted disk. `.gitignore`, the Git index check and release
membership rules reject the normal runtime/export/credential locations. These
are accident-prevention controls: a developer must still review file contents.
Do not put a secret in a source file under an allowed code name. Do not force-add
runtime data. Browser downloads and full backups are private operational
artifacts and intentionally contain authorized records; backups include the
current local app password hash.

For a future separately authorized integration, use the operating system's
credential store under school IT ownership. Keep only an opaque credential
reference and strictly allowlisted nonsecret options in an external owner-only
`local-config` file. Never put actual secrets in command arguments, source,
SQLite application settings, JSON diagnostics, browser assets, ledger exports
or logs. Fail on unknown configuration keys. Credentials should be reprovisioned
by authorized IT after recovery, not embedded in source releases or document
backups. This is the required future pattern, not an installed connector or
credential-store implementation. No credentials were requested or configured.
