# Hardening notes

This document records the planned comparison of a naive single-stage image and a hardened multi-stage image.

## Planned method

- Build a baseline image with the naive configuration.
- Build the hardened image with the same app.
- Run Trivy with the same version and same day.
- Compare counts for high, medium and low findings.
- Record the difference in the README results table.

## Container model

The hardened image uses a multi-stage build, a pinned Python base, a non-root runtime user and a final distroless image without a shell. The app is started through an exec form so no shell is required at runtime.

## Kubernetes security context

```yaml
securityContext:
  runAsNonRoot: true
  readOnlyRootFilesystem: true
  allowPrivilegeEscalation: false
  seccompProfile:
    type: RuntimeDefault
  capabilities:
    drop:
      - ALL
  resources:
    limits:
      cpu: 250m
      memory: 256Mi
    requests:
      cpu: 100m
      memory: 128Mi
```

## Trivy comparison

The result should be recorded as a small table with the same Trivy version and the same day. The expected comparison is a naive image versus the hardened image, with the final values posted in the repo README after a real run.

Status: Not verified until the local Trivy run is complete.
