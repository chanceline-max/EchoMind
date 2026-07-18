# Third-party dependency license audit

Audit date: 2026-07-18

This inventory is an engineering aid, not legal advice. EchoMind is licensed under Apache-2.0; third-party packages remain under their own licenses. Versions below are the packages installed or locked in the Stage 12 audit environment.

## Evidence method

- Python: installed distribution `METADATA` (`License-Expression`, then `License`/classifier) and the distribution-owned license file.
- npm: `frontend/package-lock.json` for version/integrity and installed package `package.json` for `license`.
- npm optional platform packages without a local license field: exact-version npm registry metadata (`npm view`) was used and recorded below.
- No dependency license text is copied into this repository. Re-run the audit after dependency updates.

## Python runtime dependencies

| Package | Installed version | License | Evidence |
|---|---:|---|---|
| alembic | 1.18.5 | MIT | installed `METADATA` License-Expression and package LICENSE |
| fastapi | 0.139.2 | MIT | installed `METADATA` License-Expression and package LICENSE |
| fastapi-cli | 0.0.32 | MIT | installed `METADATA` License-Expression and package LICENSE |
| httpx | 0.28.1 | BSD-3-Clause | installed `METADATA` License and `LICENSE.md` |
| pydantic-settings | 2.14.2 | MIT | installed classifier/License-Expression and package LICENSE |
| python-multipart | 0.0.32 | Apache-2.0 | installed `METADATA` License-Expression and `LICENSE.txt` |
| SQLAlchemy | 2.0.51 | MIT | installed `METADATA` License and package LICENSE |
| tzdata | 2026.3 | Apache-2.0 | installed `METADATA` License and package license directory |
| uvicorn | 0.51.0 | BSD-3-Clause | installed `METADATA` License-Expression and `LICENSE.md` |

## Frontend runtime dependencies

| Package | Locked version | License | Evidence |
|---|---:|---|---|
| @tanstack/react-query | 5.101.2 | MIT | lockfile plus installed package metadata/LICENSE |
| react | 19.2.7 | MIT | lockfile plus installed package metadata/LICENSE |
| react-dom | 19.2.7 | MIT | lockfile plus installed package metadata/LICENSE |
| react-router-dom | 7.18.1 | MIT | lockfile plus installed package metadata/LICENSE |

## Direct development dependencies

Python tools: mypy 2.3.0 (MIT), pytest 9.1.1 (MIT), and Ruff 0.15.21 (MIT), based on installed distribution metadata and license files. The release build resolved Hatchling 1.31.0 (MIT) within the declared isolated build-backend range `>=1.27,<2`.

Frontend direct development dependencies:

| Package | Locked version | License |
|---|---:|---|
| @eslint/js | 10.0.1 | MIT |
| @playwright/test | 1.61.1 | Apache-2.0 |
| @testing-library/jest-dom | 6.9.1 | MIT |
| @testing-library/react | 16.3.2 | MIT |
| @testing-library/user-event | 14.6.1 | MIT |
| @types/node | 26.1.1 | MIT |
| @types/react | 19.2.17 | MIT |
| @types/react-dom | 19.2.3 | MIT |
| @vitejs/plugin-react | 6.0.3 | MIT |
| eslint | 10.7.0 | MIT |
| eslint-plugin-react-hooks | 7.1.1 | MIT |
| eslint-plugin-react-refresh | 0.5.3 | MIT |
| globals | 17.7.0 | MIT |
| jsdom | 29.1.1 | MIT |
| typescript | 6.0.3 | Apache-2.0 |
| typescript-eslint | 8.64.0 | MIT |
| vite | 8.1.5 | MIT |
| vitest | 4.1.10 | MIT |

Versions and licenses in this table come from `package-lock.json` and each installed package's metadata/license files.

## Transitive review

The audit inspected 49 installed Python distributions and 277 npm lockfile packages. No GPL, AGPL, SSPL or Commons Clause identifier was found, and no Python distribution remained UNKNOWN.

Thirty-two npm optional/platform entries lacked a local lockfile license field. Exact-version registry metadata resolved them as:

- MIT: `@emnapi/*`, `@napi-rs/wasm-runtime`, `@rolldown/binding-*`, `@tybys/wasm-util`, and `fsevents` 2.3.2/2.3.3.
- MPL-2.0: `lightningcss-*` 1.32.0 platform packages.
- 0BSD: `tslib` 2.8.1.

After that verification, UNKNOWN count is zero. MPL-2.0 packages are unmodified build-tool transitive binaries; this audit found no copied MPL source in EchoMind and no release blocker from their current use. Re-review is required if those files are modified or redistributed outside their package terms.

## Embedded-material review

The tracked repository contains project source, Markdown documentation, configuration, and synthetic JSON/CSV/TXT samples. No copied third-party source tree, font, icon, image, binary template, or large external text requiring an additional EchoMind `NOTICE` attribution was found. The standard Apache-2.0 text in `LICENSE` is project licensing material, not an embedded dependency.

## Result

No UNKNOWN or potentially incompatible direct dependency license remains in this audit. No GPL, AGPL, SSPL or Commons Clause dependency was identified. This result applies only to the versions listed above and does not replace review after dependency changes.
