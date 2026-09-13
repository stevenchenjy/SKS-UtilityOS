# Portfolio Manager connector preparation

The staff application reports **ENERGY STAR Portfolio Manager: connector
disabled**. `PortfolioManagerBoundary` rejects configuration and manual sync,
and accepts no credentials. There is no HTTP transport, API-account setup,
scheduled sync, remote worker, or portal automation in rc3. File workflows remain
available. My360 credentials and undocumented endpoints are not implemented.

`AGENTS.md` requires a specific school-approved decision before external APIs.
That applies to EPA TEST too. This milestone therefore uses only a deterministic
local fixture client. It has not contacted EPA TEST or LIVE and does not claim
verified EPA or utility integration.

## Local synthetic preparation

`utilityos/connectors.py` contains a small consumption-client interface and an
explicitly synthetic `PortfolioFixtureRehearsal`. Tests supply in-memory XML;
fixture identifiers must begin with `fixture-`. The concrete fixture client has
no endpoint, credential or network implementation. Configuration rejects extra
fields such as passwords, tokens and schedules.

The preparation demonstrates:

- Explicit property/meter selection, supported commodity/unit declarations and
  manual pulls. Unselected meters are not fetched.
- Bounded pagination, original response bytes and SHA-256 provenance, and
  operational candidate normalization. Financial cost fields are not normalized
  or posted; there is no invoice writer.
- An observational per-meter high-water timestamp. Every pull rereads the full
  selected history so corrections to old periods are not missed. This is a local
  policy, not an undocumented server-side modified-since feature.
- Idempotency by record identity and normalized contents. Changed records retain
  prior versions and produce pending revision review; nothing auto-approves.
- Atomic processing per selected meter: incomplete, cyclic or conflicting page
  sets do not advance that meter or partially add its candidates. Other meters
  may succeed. The overall last-success time advances only on complete success.
- Explicit disconnect clears selections, high-water state and sync status,
  retaining the already reviewed/pending evidence sink. No credential material
  exists to retain. Status uses a fixed value-free selection/error schema.

The sink is disposable memory for developer tests, not staff persistence or a
new authoritative ledger. Restarting this harness discards its state. A future
approved implementation must commit evidence and cursor state atomically through
staff-local storage and reuse the existing operational review/import services.
The source-adapter boundary supplies this separation; the fixture never enables
a production ingestion route.

EPA consumption dates remain provider date strings with
`time_basis=provider_date_period_uninterpreted`. A later implementation must
verify timezone, end-date convention and interval meaning before converting them
to UtilityOS UTC/exclusive-end readings. The generic boundary does not infer
these details from date labels.

## Public evidence and limits

The [EPA consumption retrieval documentation](https://portfoliomanager.energystar.gov/webservices/home/api/meter/consumptionData/get)
documents shared-meter access, Basic authentication, date filters, pages of up to
120 records and consumption records with source IDs and audit modification times.
It also distinguishes bulk deliveries. The prepared normalizer covers metered
consumption only; source IDs, units, dates and estimation status stay explicit.
Returned pagination links are future transport inputs that would require an
origin/path allowlist. No response link is followed by this fixture.

The [EPA API terms](https://portfoliomanager.energystar.gov/pdf/reference/Web%20Services%20API%20Terms%20of%20Use.pdf)
describe the API itself as free and require development/testing in TEST before
requesting LIVE access. This does not establish free Central Hudson transfers or
account-specific eligibility. The [Central Hudson MyMeter page](https://www.cenhud.com/en/my-energy/save-energy-money/mymeter-portal/)
describes sharing meter/account groups or whole-building usage with Portfolio
Manager; school coverage, recurrence, resolution and fees remain unverified.

[EPA's January 2025 testing guide](https://portfoliomanager.energystar.gov/pdf/reference/Testing_Web_Services_en_US.pdf)
uses the TEST UI to create accounts and enable test-provider API access. It
explains connection/share workflows for GET-only integrations and separate EPA
approval for LIVE. Older instructions for creating TEST accounts through a
special API call are superseded. All sources were checked on 2026-09-13 without
logging in or exchanging API data.

## Later acceptance procedure after separate approval

1. Record school approval for TEST and an owner for support/maintenance. Confirm
   utility account eligibility, selected properties/meters versus whole-building
   aggregation, available fields, units, dates, resolution, publication lag,
   recurrence, fees, consent, retention and revocation. Do not combine overlapping
   whole-building and individual-meter evidence.
2. Following the current EPA testing guide, authorized staff creates fictional
   provider/customer accounts in the official TEST UI, enables provider API
   access, and sets up fictional properties/meters. Perform the documented
   connection and sharing workflow with the minimum read access needed.
3. Implement/review the absent HTTPS transport with fixed official origins,
   redirect and pagination restrictions, timeouts, size/page limits and safe
   error handling. Verify meter metadata/consumption against the TEST UI. Check
   authentication failures, removed sharing, missing meters, 429 retry policy,
   provider downtime and interrupted pages. Use no school records.
4. Put any future credential in an approved OS secret store outside the source,
   workspace backup/export and diagnostic paths; persist only a reference. Test
   removal/revocation and sentinel exclusion from logs, API responses, support,
   Git and release archives. Implementing a secret store is a separate reviewed
   change; rc3 does not pretend to provide one.
5. Verify stable repeated pulls, historical corrections and deletions, provenance,
   mapping reuse, candidate review, timestamp conventions, cursor recovery,
   backup/restore and zero financial effects using fictional data. Record exact
   endpoint/schema versions and retain a synthetic test receipt.
6. Obtain EPA LIVE approval and separate school/provider consent before any
   production setup. Verify utility transfer fees meet the user's no-recurring-
   data-access-fee requirement. Staff confirms the selected school meter/building
   mapping locally. Manual sync comes first; any optional schedule requires its
   own approval and visible pause/disconnect controls.

The [EPA error guide](https://portfoliomanager.energystar.gov/webservices/home/errors?lang=en)
documents status codes for authentication/access failures, rate limits and
service unavailability. Do not copy a provider's free-form errors into support
bundles. Unknown cases should stop processing and retain a local staff-visible
failure without leaking response text.
