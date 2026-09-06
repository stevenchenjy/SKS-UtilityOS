# Dependency decisions — 2026-09-06

The existing Python/FastAPI/SQLite and browser ES module architecture is retained. Corrections, private history, migrations, and backup controls use Python's standard library and existing dependencies. No cloud service, connector, PDF parser, OCR library, JavaScript build system, or paid dependency was introduced into the application.

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
