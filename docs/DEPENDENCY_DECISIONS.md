# Dependency decisions — 2026-09-06

The existing Python/FastAPI/SQLite and browser ES module architecture is retained. Corrections, private history, migrations, and backup controls use Python's standard library and existing dependencies. The 0.2/0.3 ledger work introduced no new parser/runtime. The 0.4.0 intake slice adds the separately reviewed local PDF/OCR components below; no cloud service, connector, JavaScript build system or paid dependency is required.

## Advisory-driven updates

The initial environment used FastAPI 0.128.2, Starlette 0.50.0, pytest 9.0.2, and pip 24.3.1. A live PyPI advisory scan with pip-audit 2.10.1 reported 15 records across Starlette, pytest, and pip; some advisory records duplicated identifiers. The complete raw scan remains with external development evidence. Relevant identifiers included Starlette URL/Host reconstruction and Windows StaticFiles advisories, pytest's temporary-directory issue, and pip archive/installation path handling issues.

The updated tested environment uses:

| Component | Version | License | Decision |
|---|---|---|---|
| FastAPI | 0.141.1 | MIT | Maintainer release permits a patched Starlette; installed base package without optional cloud/CLI extras |
| Starlette | 1.6.0 | BSD-3-Clause | Explicit pin replaces the advisory-affected 0.50.0 dependency |
| pytest | 9.1.1 | MIT | Development-only update beyond the reported fixed version |
| pip | 26.2.1 | MIT | Pinned project-venv installer; no global installation |
| Playwright | 1.57.0 | Apache-2.0 | Existing development dependency retained; isolated profile uses installed native Chrome |
| Uvicorn / defusedxml | 0.48.0 / 0.7.1 | BSD-3-Clause / PSFL | Existing runtime components retained |

License and active dependency metadata are recorded in `DEPENDENCY_INVENTORY.json`. Versions in `constraints-tested.txt` describe the tested macOS runtime; Windows-specific dependencies still need native target validation. Install scripts request wheels only and support a local wheelhouse without package-index access. The source release contains no dependency wheels or vendored package code.

The updated environment returned **no known vulnerabilities** from pip-audit's PyPI service on 2026-09-06, and `pip check` found no dependency conflicts. This is a dated advisory result, not a security certification. Staff must repeat it before installation. Two upstream test-client deprecation warnings remain (httpx and the AnyIO BlockingPortal alias); the tests pass. No new HTTP client was introduced solely to suppress warnings.

pip-audit was installed in an external disposable audit environment and received only public package names/versions. It is not a runtime dependency and the application makes no advisory-service requests. The tool is maintained by PyPA under Apache-2.0, with a June 2026 release at the time of review. The application does not call any external service while importing bills.

## Primary source notes

- [FastAPI 0.141.1 metadata and project links](https://pypi.org/project/fastapi/0.141.1/) and [maintainer release notes](https://fastapi.tiangolo.com/release-notes/).
- [Starlette 1.6.0 metadata](https://pypi.org/project/starlette/1.6.0/) and [maintainer advisories](https://github.com/Kludex/starlette/security/advisories).
- [pytest 9.1.1](https://pypi.org/project/pytest/9.1.1/), [pip 26.2.1](https://pypi.org/project/pip/26.2.1/), and [Playwright 1.57.0](https://pypi.org/project/playwright/1.57.0/).
- [pip-audit license, maintenance, advisory services, and limits](https://pypi.org/project/pip-audit/2.10.1/).

No fees or externally supported utility integrations are claimed. Installation still requires a trusted package source, school review, and an approved update decision.

## 0.3.0 decision

No runtime or development dependency was added or updated for this milestone.
Atomic storage, audit hashing, migration orchestration, configuration guards and
synthetic generation use the standard library and the existing project modules.
This avoids new installation, license and transitive-dependency obligations.
The existing pinned environment was rescanned with external pip-audit 2.10.1 on
2026-09-06: **no known vulnerabilities**, no ignored advisory IDs. The existing
license/maintenance inventory remains applicable. Git is used for local source
control and development index tests, not by the running ledger. Apple signing
research produced documentation only; it introduced no service or credential.

## 0.4.0 document extraction

Read `DOCUMENT_EXTRACTION_DEPENDENCIES.md` for the measured evaluation of
pdfplumber, invoice2data, Docling and Granite-Docling, the selected native-text/
small optional OCR path, licensing and native-library limits. `requirements.txt`
adds pdfplumber; `requirements-ocr.txt` adds optional tesserocr/cysignals; the
development corpus generator adds ReportLab. `constraints-tested.txt` and
`DEPENDENCY_INVENTORY.json` include the active closure and optional scope. No
AGPL code, cloud model, automatic weight download or vendor template was copied.


## 0.5.0 decision — 2026-09-07

No application, development or optional-OCR package was added or repinned for
Provider Studio. The existing PDF text/OCR worker exposes bounded observations;
project-owned declarative rules resolve them locally. Independent fictional
onboarding cases and the preserved 28-document benchmark exercise this boundary.
They did not demonstrate a need for Docling, Granite-Docling, Torch, MLX, a GPU,
a cloud extraction service or another model runtime. A future engine must first
satisfy the adapter and private A/B conditions in `PROVIDER_STUDIO.md`.

The installed base, development, bootstrap and optional-OCR distribution set was
scanned again with pip-audit 2.10.1 on 2026-09-07: no known vulnerabilities and no
ignored advisory IDs. Package metadata is public; no runtime records were sent.
This does not cover all bundled native libraries. Tesseract 5.5.1 remains older
than upstream 5.5.3; the strict pinned public English-model restriction and
school-side native engine review in `DOCUMENT_EXTRACTION_DEPENDENCIES.md` remain.

The only new external components referenced are first-party GitHub Actions for
public synthetic CI. Both are maintained MIT-licensed actions pinned to reviewed
full commit hashes. Their Node runtime is hosted-runner tooling, not an installed
application dependency. See `SYNTHETIC_CI.md` for exact reviewed releases,
permissions, install behavior and the distinction between local and hosted checks.
