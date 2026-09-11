# Provider-informed local file workflows

Evidence checked on **2026-09-10** from public provider, municipality, vendor and
government pages. This is technical development guidance. No authenticated
tenant, school account, private statement, supplier contact or school fee
agreement was inspected. The supported application paths use files already on
the local computer. No portal, mailbox, API or Portfolio Manager connection is
enabled by this work.

## Public evidence and its limits

| Source | Confirmed public statement | What remains unverified |
|---|---|---|
| [Central Hudson 2025 DSIP, printed p. 194](https://jointutilitiesofny.org/sites/default/files/2025%20Central%20Hudson%20Distributed%20System%20Implementation%20Plan.pdf) | Green Button Download is enabled inside customer online accounts. | School account eligibility, commodity, units, intervals, quality flags, retention and the exact downloaded XML variant. Download support does not establish a Connect My Data API. |
| [Central Hudson eBills](https://www.cenhud.com/en/account-resources/billing-payments/ebills/) | Email tells the customer that a bill is ready; statements are available online. | PDF attachments, batch statements and scheduled file delivery. Do not implement attachment acquisition from this description. |
| [Central Hudson MyMeter](https://www.cenhud.com/en/my-energy/save-energy-money/mymeter-portal/) | Meter groups can use individual accounts/meters or whole-building aggregated usage. The page describes sharing and transfer to ENERGY STAR Portfolio Manager. | School account coverage, recurrence, commodities, aggregation, fees and granularity. This establishes neither invoice-image retrieval nor tested local synchronization. |
| [Industrial customer resources](https://www.cenhud.com/en/business-customers/industrial-customer-resources/) and [usage/hourly-pricing structures](https://www.cenhud.com/en/business-customers/industrial-customer-resources/usage-and-hourly-pricing-reports/) | Energy Manager is linked for industrial electric/gas customers and large-customer billing data. Public field structures distinguish energy kWh from demand kW, timestamps and status fields. | School eligibility and supported current exports. These structures have not been implemented as a dedicated adapter. |
| [Energy Manager guide, dated 2010-09-01](https://www.cenhud.com/globalassets/pdf/fall2010hpp_energymanagersguide.pdf) | The historical guide describes comma-delimited text and Excel exports. | Current file extension, interface, schema and operating conditions. Historical documentation is not present-day acceptance evidence. |
| [NYSERDA IEDR report through 2026-06-30](https://www.nyserda.ny.gov/-/media/Project/Nyserda/Files/Programs/IEDR/IEDR-2026-Q2.pdf) | The report describes continuing ingestion/query development and projects public query-tool version 1 for Q4 2026. | A currently available, free, school-eligible Central Hudson account API. A projected release is not a deployed service. |
| [Cornwall billing changes](https://cornwall-on-hudson.gov/Departments/Water/Billing-Changes) | The standard issue dates are January, March, May, July, September and November 15, effective with the 2024 transition. Statements can be viewed/printed, and consumption-portal registration is described as free. | School exceptions, service-period boundaries and billing units. The issue schedule is not a rule that every measured period is exactly 60 days. |
| [Cornwall eBills introduction](https://cornwall-on-hudson.gov/Departments/Water/Pay-Your-Utility-Bill) | The 2021 introduction describes electronic delivery and access to 24 months of bills. | Attachment versus secure link and any bulk delivery. Its older monthly wording does not override the more specific 2024 schedule notice. |
| [Cornwall consumption portal](https://cornwall-on-hudson.gov/Departments/Water/Water-Meter-Portal) | My360 supports multiple properties/meters, usage thresholds and potential-leak alerts. | Campus meter inventory, tenant export configuration, synchronization latency and school submeter inclusion. Continuous access is not a guarantee of real-time measurements. |
| [Neptune My360 usage help](https://help.my360-app.com/Content/D_Consumer%20Portal/Water%20Usage.htm) | Usage can be exported to Excel or PDF, with meter and time-range selection. Changing the displayed unit does not change the account default unit. | Cornwall's export extension/schema, the exported unit, sampling and history. The default 13-month graph does not establish a retention limit. |
| [Neptune360 SDK access](https://prod2-help.neptune360.com/Content/B_Procedure%20Topics/SDK%20Access.htm) | Utility-side credentials and API bundles are separate; core readings/consumption APIs are listed within the Advanced subscription. | A free customer-facing school API, school-only credential scope, and any scheduled export under the municipality's current arrangement. Never accept a utility-wide key and filter other customers locally. |
| [EPA web services](https://portfoliomanager.energystar.gov/webservices/home) and [meter consumption retrieval](https://portfoliomanager.energystar.gov/webservices/home/api/meter/consumptionData/get) | EPA documents web services and meter-consumption retrieval. | A permitted end-to-end MyMeter → school Portfolio Manager → UtilityOS path. API existence is not school approval, provider recurrence or a guarantee of meter-level data. |

Before any later connection decision, authorized staff and the provider must
confirm coverage, account classes, fields, units, resolution, publication lag,
history, consent/renewal, credentials, revocation, fees and operating ownership.
Keep private compatibility checks inside the school installation. Request a
public specification or invented example for developer reproduction. No provider
questions were sent as part of this slice.

## Financial statements and operational readings

Central Hudson separates charges for the current billing period from the
account amount due, which can include adjustments and other balances. Its
explanation also says separately billed supplier charges may be absent from
the utility invoice. Use each document's current charges, retain balance/due
values in supplementary review fields, and preserve stable meter identity when
another supplier bills that meter. Supplier-only lines have zero repeated
consumption. [Central Hudson bill explanation](https://www.cenhud.com/en/account-resources/rates/your-bill-explained/)

Cornwall's public [Village example](https://cornwall-on-hudson.gov/Portals/1/Sample%20Village%20Bill.pdf)
contains water, sewer, garbage and sewer-capital charges. Its water charge is
$44.40; all current charges total $176.78, with a $354.70 previous balance and
$531.48 total due. The [Town example](https://cornwall-on-hudson.gov/Portals/1/Example%20town%20Water%20Bill.pdf)
shows a water-only current charge of $83.20 and separately shows a previous
balance offset by payment. Those are public example amounts, not campus data.
They illustrate distinct financial fields; the original documents and branding
were not copied into the synthetic corpus.

**Combined municipal statements remain unsupported for financial posting.**
The current ledger has water but no sewer, garbage or sewer-capital charge
categories. Keep the full original pending locally until a reviewed accounting
extension can classify every charge and reconcile the whole current invoice.
Do not make a partial water invoice, call all charges water, invent meters for
non-metered services, subtract lines silently, or replace the current total
with the balance due. Existing reconciliation refuses a full current total
paired with only the water subtotal; unsupported service categories also fail.
This is a safe refusal, not combined-statement compatibility or automatic
recognition of every possible non-water charge. Human source comparison remains
essential: internally consistent but deliberately misclassified edits cannot
be identified merely by adding their numbers.

Use **Provider Studio** for supported PDF layouts: author bounded declarative
rules privately, preview the source fields, independently review at least two
sources, validate and activate. Amount-due and current-charge rules must be
separate. Required demand fields retain kW separately from electricity kWh;
demand is not additional energy consumption. An unqualified gas label such as
“units” establishes neither CCF/Mcf volume nor therm/MMBtu energy. Resolve the
source unit rather than guessing a conversion. A master/shared meter remains
unassigned until staff supplies a defensible building mapping. See the
[Provider Studio contract](PROVIDER_STUDIO.md).

Financial invoice dates, actual exclusive-end service periods, retrieval
cadence and operational measurement timestamps have separate meanings.
Configure account invoice expectations only after staff confirmation. A
statement with multiple service points is still one document. A quiet month
does not establish zero use, and an unconfigured account is not a missing bill.
The original PDF and reviewed periods remain authoritative evidence; charts
continue to use invoice months.

## Structured usage groundwork and spreadsheet conversion

The generic mapped usage CSV workflow is an operational-evidence path; it is
not a certified My360 or Central Hudson connector. It has no invoice-charge
posting path. See the [mapped usage guide](MAPPED_USAGE.md) for the local mapping
preview and reconciliation controls. Keep commodity, source unit, meter mapping, time boundaries,
timezone, delta/cumulative semantics, quality and original source together.
Repeated exports must not repeat consumption; conflicting readings require
explicit reconciliation. Billing-period quantities and operational intervals
are alternative evidence when their coverage overlaps, never additive usage.
Different boundaries and incomplete interval coverage preclude a claim that
the invoice quantity has been reconciled. The existing Green Button importer
remains limited to its tested forward-delta electricity Wh subset; changing a
label does not make water/gas XML supported.

Direct Excel parsing was not added because the actual tenant file type and
schema have not been verified. If authorized staff receives a spreadsheet,
keep its original bytes in the approved local source folder. Use a
school-approved local viewer that can inspect literal cells with macros,
external links, data refresh and formula recalculation disabled. If that
inspection cannot be assured, request a plain CSV export instead. Do not open
the file through a cloud conversion service or change global security settings.

Export only confirmed literal readings to UTF-8 CSV; do not treat formulas or
their cached values as measured observations. Preserve identifiers, decimal
precision, units, timezone/UTC offsets, period boundaries and quality columns.
Keep text identifiers as text and dates/times in unambiguous ISO form. Retain
both the original workbook and converted CSV in the school-controlled folder,
record the conversion locally, and compare the preview with the original
before approval. The mapped importer retains the CSV it received; it does not
claim to retain a workbook that was never imported. A missing or ambiguous
unit, time basis or measurement meaning requires clarification rather than
an inferred conversion.

## Original synthetic corpus and evidence

[`samples/provider-semantics/`](../samples/provider-semantics/) contains seven
original, visibly fictional, single-page PDFs and an independent expected-data
file. [`scripts/synthetic_provider_semantics.py`](../scripts/synthetic_provider_semantics.py)
reproduces their bytes using the existing reportlab development dependency. No
runtime provider plugin, new extraction dependency or built-in real-provider
layout was added. The combined municipal and ambiguous gas cases intentionally
describe refused documents rather than approved invoice truth.

[`tests/test_provider_semantics.py`](../tests/test_provider_semantics.py) checks:

- independent current charges, retained previous balance/amount due, source
  bytes and an activation failure for a wrong amount-due rule;
- water-only Provider Studio activation, and a retained unposted combined
  municipal statement with full reconciliation preserved;
- supplier-only charges and electricity demand without extra consumption;
- one stable shared meter across two providers without building allocation;
- ambiguous gas-unit refusal and unchanged explicit volume/energy units;
- original service periods of 62, 60 and 62 days, separate from issue dates;
- deterministic PDF hashes and visible fictional markings.
- source-package inclusion and the scoped Git ignore exception.

Fresh focused run on 2026-09-10: **12 passed**, with the existing two framework
deprecation warnings. All seven PDFs were rendered with local Poppler and
visually inspected. Provider-specific school acceptance, authenticated export
compatibility, current account eligibility and fees remain externally
unverified. This corpus result is not a general accuracy estimate or completion
of the 0.6 analytics milestone. See [verification](VERIFICATION.md) for the
broader slice checks and the separate native-browser evidence.

## Optional polling decision

This slice retains the existing explicit stable-folder scan. Files can be scanned
when the app is next opened; no automatic watcher or daemon is added. The provider
evidence does not establish unattended delivery, and no measured benefit justifies
a polling lifecycle yet. A future opt-in poller would still require a dedicated
confirmed folder, pause/resume and the existing stability/duplicate protections;
it would neither retrieve bills nor approve them.
