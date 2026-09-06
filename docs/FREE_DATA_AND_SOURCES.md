# Data access, fees, and technical references

Research date: September 6, 2026. This document separates an application's license costs from utility-specific availability and hosted-service charges. The school has supplied no confirmed utility providers, account classes, or portal capabilities.

## Current zero-service-fee scope

The starter reads files already obtained by authorized staff. It includes no metered API, paid bill aggregator, cloud OCR, model inference service, hosted database, or commercial license key. Runtime internet access is unnecessary for local import and reporting.

Python/FastAPI/Uvicorn/SQLite/defusedxml are the selected local components. FastAPI is MIT licensed, Uvicorn is BSD-3-Clause, defusedxml uses the Python Software Foundation license, and SQLite's core is public domain. Exact installed package metadata is recorded in `DEPENDENCY_INVENTORY.json`. Package distribution, hardware, IT labor, backups, code signing, and the user's separate Codex subscription can still incur costs.

Sources: [FastAPI official documentation](https://fastapi.tiangolo.com/), [Uvicorn source license](https://github.com/Kludex/uvicorn/blob/main/LICENSE.md), [defusedxml repository](https://github.com/tiran/defusedxml), and [SQLite copyright statement](https://www.sqlite.org/copyright.html). Dependency versions require current advisory review before staff installation.

## Green Button

The Green Button Alliance states that its open standard can be implemented without royalties or mandatory Alliance membership. That supports a local file reader with no Green Button platform subscription. The Alliance also describes customer-downloaded XML as a file that the customer can retain and share with an application.

Sources: [Green Button technical FAQ](https://www.greenbuttonalliance.org/faqs-technical) and [Download My Data](https://www.greenbuttonalliance.org/green-button-download-my-data-dmd).

The standard's terms do not establish whether any particular school utility account can download XML, whether the available fields match the parser, or whether that utility imposes a fee. These questions remain unverified until staff identifies the providers. Staff can continue using CSV or manual PDF entry regardless of Green Button availability.

Connect My Data involves customer authorization and utility-specific third-party qualification/onboarding. A third-party aggregator or hosted connector can add its own conditions or charges. Certification, memberships, paid publications, and hosted services are separate offerings. The current starter enables none of them and makes no certification claim.

The local parser is an independent limited implementation. It was tested against synthetic documents representing forward delta electricity readings in Wh, explicit power multipliers, and linked ReadingType resources. It has not been tested against an actual school provider's export. Consult the [official technical documentation](https://greenbuttonalliance.github.io/OpenESPI-GreenButton-API-Documentation/) and [power-of-ten guidance](https://www.greenbuttonalliance.org/poweroftenmultiplier) when extending it.

## Connection admission record

Before enabling an automatic source, document its provider and customer class, available download/API, fees, exact fields, reading granularity, publication lag, authorization procedure, third-party registration, certificate requirements, revocation, and retention. Obtain a school-approved statement that the chosen route creates no added recurring access fee. Until these facts are confirmed, keep that connector disabled.

| Source | Starter decision | Unresolved item |
|---|---|---|
| Staff-supplied canonical CSV | Enabled, local parsing | Staff process for preparing rows |
| PDF invoice already held by staff | Enabled, attachment and manual entry | Supplier-specific extraction templates |
| Green Button DMD XML | Enabled for supported electricity subset | Actual utility availability, account coverage, fee, schema |
| Green Button CMD/OAuth | Disabled | Utility registration, consent, credentials, coverage and fees |
| Commercial bill/interval aggregator | Excluded | Any approved service arrangement and pricing |
| Staff email or portal automation | Excluded | School authorization, credential custody and retrieval reliability |
| Real-time metering/BAS | Excluded | Existing hardware, protocols, installation and access costs |
| ENERGY STAR Portfolio Manager | Optional future integration | Approval to transmit school records externally |

## Open-source alternatives considered

The [OpenESPI Java reference project](https://github.com/GreenButtonAlliance/OpenESPI-GreenButton-Java) provides an Apache-2.0 implementation reference. Its server/third-party authorization stack is unnecessary for the initial local file workflow. No OpenESPI server was deployed or installed in this starter.

[MyEMS](https://github.com/MyEMS/myems) provides a broad energy-management codebase. Its current [license file](https://github.com/MyEMS/myems/blob/master/LICENSE) contains MIT language plus an additional requirement concerning the MyEMS logo and copyright information. This starter includes no MyEMS fork or copied source. A future adoption requires review of the exact license and project fit.

## Codex project instructions

The archive includes `AGENTS.md` and a project-local `SKILL.md`. OpenAI's official [AGENTS.md guide](https://developers.openai.com/codex/guides/agents-md/) and [skills guide](https://developers.openai.com/codex/skills/) describe these instruction mechanisms. If the installed Codex version does not automatically surface the local skill, ask it to read the file explicitly; the master prompt supplies its exact path.

No plugin, user machine configuration, utility account, or remote repository was changed while creating the source archive. Any additional installation should be chosen after inspecting its instructions, license, dependencies, and actual necessity.
