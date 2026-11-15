# Glossary

| Term | Use | Avoid |
| --- | --- | --- |
| PASS | A control was executed and the evidence shows it worked. Name the command, date and artifact. | "done", "working", "green" without evidence |
| FAIL | A control was executed and it did not work. | "broken" without evidence |
| NOT VERIFIED | The control exists but no evidence shows it worked, often because it needs a hosted run. | marking a control PASS because a file exists |
| PLANNED | Not implemented yet. Listed in the roadmap. | "coming soon" |
| NOT APPLICABLE | Out of scope, with the reason stated. | silently omitting a control |
| Artifact | A build output that is released: the container image, the Windows zip, the SBOM files. | "binary" for everything |
| Digest | The SHA-256 content address of an artifact, written `sha256:<64 hex>`. The only way this project refers to an image it deploys. | deploying by tag |
| SBOM | Software bill of materials: the list of components inside an artifact. Produced in CycloneDX and SPDX formats. | "dependency list" |
| CycloneDX | An OWASP SBOM format. This project emits version 1.6 JSON. | |
| SPDX | A Linux Foundation SBOM format. This project emits version 2.3 JSON. | |
| Provenance | A signed statement of how an artifact was built: source repository, commit, workflow and builder. This project uses SLSA v1 provenance from GitHub artifact attestations. | "build log" |
| Attestation | A signed in-toto statement about an artifact digest, such as provenance or an SBOM. | |
| Keyless signing | Sigstore signing with a short-lived certificate bound to an OIDC identity (here, the release workflow) instead of a stored private key. | "unsigned" |
| Certificate identity | The workflow URI inside a keyless signing certificate, for example `https://github.com/siiick-brain/Bastion-Pipeline/.github/workflows/release.yml@refs/tags/v0.2.0`. Verification must check it exactly. | checking that "a signature exists" |
| Issuer | The OIDC provider that vouched for the identity: `https://token.actions.githubusercontent.com`. | |
| OIDC token | A short-lived JSON Web Token that GitHub Actions issues to a job. A relying party verifies its signature and claims. | "access key" |
| Audience | The `aud` claim. The relying party accepts only tokens minted for it. | |
| Trust boundary | A line where data or control passes between parties that trust each other differently, for example a fork pull request entering CI. | |
| Gate | A check that blocks a merge or a release when it fails. | "scan" when the check does not block |
| Exception | An accepted finding recorded in `security/exceptions.toml` with reason, risk, owner and expiry. | ignoring a finding in tool configuration only |
| Anti-rollback counter | Persistent device state that refuses any update older than the last installed version or the rollback floor. | "version check" |
| Rollback floor | The minimum version a device may run after an update raises it. It never decreases. | |
| SoftHSM | A software implementation of a PKCS#11 token. It demonstrates the interface only. It is not a hardware security module. | "HSM" alone |
| PKCS#11 | The standard API for cryptographic tokens. Keys stay inside the token and only operations cross the interface. | |
| Simulation | `firmware-sim/` models secure boot decisions in Python. It is not real secure boot. | "secure boot implementation" |
| kind | Kubernetes in Docker: a local single-node cluster used for the deployment demonstration. | "production cluster" |
| GitOps | Deployment where a controller (ArgoCD) applies the state committed in Git and reverts drift. | |
| Drift | A difference between the running cluster and the state in Git, for example after `kubectl scale`. | |
