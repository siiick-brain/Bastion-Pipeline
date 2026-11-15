# ADR 0005: Hash-locked dependencies

Date: 2026-11-15. Status: Accepted.

## Context

`app/requirements.txt` held runtime and development tools together with a "pin with hashes before release" TODO. The test client dependency was missing, so the test suite could not start on any platform.

## Decision

- `app/requirements.in` (runtime) and `app/requirements-dev.in` (tools, constrained by the runtime lock) are compiled with `uv pip compile --universal --python-version 3.11 --generate-hashes`.
- Every install uses `pip install --require-hashes`.
- The image installs only `app/requirements.txt`. `tests/integration/test_container.py::test_no_dev_tools_in_image` enforces this.
- `update-signing/requirements.txt` is a separate lock for the signing container.

## Consequences

- uv is a developer tool for regenerating locks only. CI installs with plain pip.
- Dependabot updates the `.in` inputs. Locks must be regenerated with the command in each `.in` header.
