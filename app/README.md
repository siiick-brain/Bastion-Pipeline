# Notes service

FastAPI service used as the pipeline payload: `/health` and in-memory CRUD on `/notes`.

- Validation: title 1 to 200 and content 1 to 2000 characters after trimming, control characters rejected, unknown fields rejected, note IDs 1 to 2^31 minus 1, at most 1000 notes.
- Every response carries `Cache-Control: no-store`, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Content-Security-Policy` and `Cross-Origin-Resource-Policy`. Interactive docs are disabled.
- Dependencies: `requirements.in` (runtime) and `requirements-dev.in` (tools), locked with hashes. See [ADR 0005](../docs/adr/0005-hash-locked-dependencies.md).
- Tests: `pytest app` (49 tests including Hypothesis property tests), 100 percent line and branch coverage on 2026-11-15.
