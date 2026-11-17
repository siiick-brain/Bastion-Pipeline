# GitOps on kind

## Layout

| Path | Purpose |
| --- | --- |
| `deploy/base` | Namespace (Pod Security `restricted`), service account without token, deployment, ClusterIP service, default-deny NetworkPolicy |
| `deploy/overlays/dev` | One replica. Image digest set by `scripts/promote.ps1` |
| `deploy/overlays/prod` | Two replicas |
| `infra/kind/cluster.yaml` | Single node, API server on 127.0.0.1, node image pinned by digest, registry mirror for `localhost:5001` |
| `infra/argocd/versions.env` | ArgoCD v3.6.1 install manifest URL and SHA-256 |
| `infra/argocd/application.yaml` | Application `bastion-dev`: automated sync, prune, self-heal |

## Commands

```powershell
pwsh -File scripts/kind-up.ps1 -WithArgoCD          # cluster, local registry, ArgoCD (manifest hash checked)
pwsh -File scripts/kind-demo.ps1                    # local end to end: push, sign, promote, deploy, verify
```

After the first GitHub release:

```powershell
pwsh -File scripts/promote.ps1 -Image ghcr.io/siiick-brain/bastion-pipeline@sha256:<digest> -Tag v0.2.0
git commit -am "chore(dev): promote <digest prefix>"
git push
kubectl apply -f infra/argocd/application.yaml
pwsh -File scripts/verify-deployment.ps1 -Overlay dev -Tag v0.2.0
```

## Drift and rollback

- Drift: `verify-deployment.ps1` scales the deployment to 3 replicas and waits for ArgoCD self-heal to restore the committed count.
- Rollback: `git revert <promotion commit>` on a branch and merge it through a pull request (the `main` ruleset blocks direct pushes). ArgoCD syncs the previous digest.

## Status

| Check | Date | Result |
| --- | --- | --- |
| Overlays render, kubeconform strict | 2026-11-16 | PASS locally and in the hosted `manifests` job (GitHub `ci` run 43815627919 onwards) |
| Local end to end on kind (`kind-demo.ps1`) | 2026-11-15 | PASS, see [deployment verification](deployment-verification.md) |
| ArgoCD installed with a verified manifest hash | 2026-11-15 | PASS |
| Release `v0.2.0` promoted with a verified keyless signature (`promote.ps1`); a wrong tag is refused | 2026-11-17 | PASS |
| Promoted overlay applied to kind: image pulled anonymously from GHCR, Pod Security `restricted`, `/health` and `POST /notes` answer | 2026-11-17 | PASS |
| ArgoCD Synced and Healthy for `bastion-dev`, deploying commit `87fb5bc` from GitHub | 2026-11-17 | PASS |
| Drift healed: scaled to 3 replicas, ArgoCD restored 1 | 2026-11-17 | PASS |
| Release `v0.2.1` promoted by pull request 26; ArgoCD ran `sha256:dbba11b2...` and `/health` answered | 2026-11-17 | PASS |
| Rollback by `git revert`: pull request 27 reverted the promotion; ArgoCD returned to `v0.2.0` (`sha256:706f6b48...`) | 2026-11-17 | PASS |

## Limits

Local cluster only. Signatures are verified before promotion. With `kind-up.ps1 -WithAdmission`, Kyverno verifies them again at admission ([ADR 0006](adr/0006-admission-signature-policy.md)). Cluster-admin can still remove the policy.
