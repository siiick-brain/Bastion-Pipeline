# GitOps notes

This document covers the deployment overlays, drift handling and rollback plan.

## Planned proof

- kustomize overlays for dev and prod.
- kubeconform checks in CI.
- ArgoCD sync and self-heal validation.
- kubectl scale drift recovery example.
- Rollback by git revert.
