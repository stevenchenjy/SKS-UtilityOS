# Local Green Button Download My Data

The rc3 parser uses explicit ESPI relationships and a bounded set of forward
interval deltas. These are synthetic file tests, not Green Button certification
or verified Central Hudson school-account compatibility. The importer does not
contact identifiers inside a file, log into a portal, or implement CMD/OAuth.

## Accepted measurement combinations

All rows require `flowDirection=1`, `accumulationBehaviour=4`, an explicit
`powerOfTenMultiplier` in −12…12, and each reading's UTC start and positive
duration. The multiplier applies before the listed unit conversion.

| Commodity | ESPI commodity | kind | uom | Retained quantity unit |
|---|---:|---:|---:|---|
| Electricity | 1 | 12 (energy) | 72 (Wh) | kWh; divide scaled Wh by 1,000 |
| Natural gas | 7 | 12 (energy) | 169 (therm) | therm |
| Drinkable water | 9 | 58 (volume) | 42 (m³) | m3 |
| Drinkable water | 9 | 58 (volume) | 128 (US gallons) | US_gal |

The [GBA schema reference](https://www.greenbuttonalliance.org/usage-data) defines
these commodity, unit, measurement, direction, accumulation and quality codes.
The [GBA gas function-block tests](https://www.greenbuttonalliance.org/fb10)
explicitly describe forward-delta natural-gas energy in therms. These primary
sources were checked on 2026-09-13. Implementing the subset does not establish
conformance to every schema rule or function block.

Gas volume, gas-to-energy conversion, imperial gallons, wastewater, demand,
net/export, phase-specific streams, cumulative counters, forecasts and
weather-adjusted readings remain unsupported here. Cumulative input is never
automatically differenced; the separate mapped-usage workflow retains counters
under its own explicit rules.

Optional normal/not-applicable data qualifiers, neutral tariff fields and the
supported phase/time fields are checked if supplied. Nontrivial aggregation,
unknown ReadingType extensions and unsupported qualifiers fail closed. Allowed
quality codes are 0, 7, 8, 9, 11, 14, 17, 18 and 19. The original codes remain
visible evidence; they are not relabeled as universally actual. Missing quality
remains `unknown`. Code 17 may include edited or estimated readings. Invalid,
forecast, mixed/other, weather-adjusted and unknown codes require review outside
this subset. No quality code authorizes invoice posting.

## Relationship and evidence retention

The [official developer guide](https://greenbuttonalliance.github.io/OpenESPI-GreenButton-API-Documentation/)
describes MeterReading as the container for IntervalBlocks and shows the Atom
links to ReadingType and UsagePoint. The parser resolves relative references
against inherited `xml:base`, including a link's own base. Query and fragment
identifiers are kept distinct. A supplied parent link must resolve inside the
same file; the exact collection suffix is handled without guessing from a
provider URL. UsagePoint service category must agree with commodity when present.
Older bounded feeds omitting the UsagePoint resource retain that omission.

A staged channel preserves UsagePoint, MeterReading and ReadingType resource
references and their Atom IDs. Block provenance retains the IntervalBlock ID,
Atom ID and declared block period. Each normalized reading retains its source
block, one-based reading index, raw integer value, multiplier and quality codes.
The exact original bytes are published through normal source storage. Changing
the file's block ID does not change stable measurement metadata. Legacy pending
electricity drafts are compared against the exact earlier payload shape without
rewriting their historical source or review record.

The parser rejects DTDs/entities, oversized files/resources/readings, duplicate
resource identifiers, unresolved or ambiguous parents, duplicate fields,
noninteger/negative/out-of-range forward values, inconsistent durations,
readings outside a declared block and overlapping intervals. Interval values
use decimal arithmetic. The original Int48 field and normalized value have
explicit bounds. Normalized quantities must fit the existing nine-decimal review
precision; smaller nonzero values fail before a draft is created, with no
rounding. Trailing zeros may be removed to fit that exact representation. Quality
lists are bounded to the review text limit. Optional currency codes and raw
interval costs remain explicitly non-posting provenance; neither creates an
invoice or changes an operational quantity.

## Local review

Upload XML through normal intake or the enabled local acquisition watcher. Map
each source stream to a confirmed meter of the same commodity and review the
explicit channel unit. Interval units are independent of an invoice meter's
billing unit: US_gal is never silently converted to a generic `gal` label.
Approve operational intervals separately from financial documents.

One stream per local meter and one meter per source stream prevent duplicate
mapping. Repeated identical intervals are skipped; changed value, duration,
quality or stable metadata is a blocking revision conflict. Overlap with mapped
operational usage is also blocked for reconciliation. A revised source remains
pending and retained; it does not silently replace approved history.

`demo-water-intervals.xml` and `demo-gas-intervals.xml` are fictional short
examples. Existing `demo-intervals.xml` remains the legacy electricity example.
`tests/test_green_button_standards.py` covers the new subset and its failure
boundaries; existing parser/ledger tests retain electricity, duplication and
accounting checks. Authorized school-side testing of real exported files remains
required before asserting provider compatibility.
