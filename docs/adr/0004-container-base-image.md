# ADR 0004: Chainguard Python base image

Date: 2026-11-15. Status: Accepted.

## Context

The original Dockerfile built packages with `python:3.12.7-slim` and copied them into `gcr.io/distroless/python3-debian12`, whose interpreter is Python 3.11. The image built but did not start: `/usr/bin/python3.11: No module named uvicorn` (observed 2026-11-15).

Rebuilt correctly on distroless Debian 12, Trivy 0.76.2 reported 2 critical and 123 high findings, mostly in Debian 12 packages with no fix or with fixes not yet in the distroless image. Distroless Debian 13 reported 0 critical and 89 high (all without a fix).

## Decision

Use `cgr.dev/chainguard/python:latest-dev` for the build stage and `cgr.dev/chainguard/python:latest` for the runtime, both pinned by digest. Both come from the same vendor so the Python minor version always matches.

## Evidence

Trivy 0.76.2, 2026-11-15: hardened image 0 vulnerabilities at every severity, 122 MB. See [hardening](../hardening.md).

## Consequences

- The free Chainguard tier publishes only `latest`. The digest pin plus Dependabot docker updates keep the image reproducible and current.
- The image has no shell, runs as UID 65532 and uses `/usr/bin/python` as entrypoint.
- The runtime tests in `tests/integration/test_container.py` guard against a repeat of the interpreter mismatch.
