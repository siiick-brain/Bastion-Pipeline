# Deployment manifests

`base/` holds the hardened namespace, deployment, service and network policies. `overlays/dev` and `overlays/prod` pin the image by digest; `scripts/promote.ps1` sets the digest after verifying the signature. See [GitOps](../docs/gitops.md).
