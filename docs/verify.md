# Verifying a release

A signature alone is not proof of origin. Verification must establish what was signed (the digest), who signed it (the release workflow identity and issuer) and which build produced it (provenance: repository, workflow, ref, commit, runner). The release `verify` job runs all of this with `scripts/verify-release.sh` and the gate refuses to publish unless it passes.

Status: the commands below are verified against real Sigstore data (see "Evidence"). Release `v0.2.0` (image `sha256:706f6b48b24903b5b8e97bcc70e3619a682acd41ab0fb9667a2be9ac52ec3c00`, commit `128bf3f`) passed the release `verify` job and an independent run of every command below on 2026-11-17.

## Variables

```bash
TAG=v0.2.0
REPO=siiick-brain/Bastion-Pipeline
IMAGE=ghcr.io/siiick-brain/bastion-pipeline
DIGEST=sha256:...            # from the release notes
COMMIT=...                   # git rev-list -n1 "$TAG"
SIGNER="https://github.com/$REPO/.github/workflows/release.yml@refs/tags/$TAG"
ISSUER=https://token.actions.githubusercontent.com
```

## 1. Image signature, identity and issuer

```bash
cosign verify "$IMAGE@$DIGEST" --certificate-identity "$SIGNER" --certificate-oidc-issuer "$ISSUER"
```

## 2. SBOM attestations bound to the digest

```bash
cosign verify-attestation "$IMAGE@$DIGEST" --type cyclonedx --certificate-identity "$SIGNER" --certificate-oidc-issuer "$ISSUER"
cosign verify-attestation "$IMAGE@$DIGEST" --type spdxjson  --certificate-identity "$SIGNER" --certificate-oidc-issuer "$ISSUER"
python -m scripts.release.sbom_check sbom.cdx.json sbom.spdx.json "$DIGEST"
```

## 3. Provenance: which build produced it

```bash
gh attestation verify "oci://$IMAGE@$DIGEST" --repo "$REPO" \
  --signer-workflow "$REPO/.github/workflows/release.yml" --source-ref "refs/tags/$TAG" --format json > provenance.json
python -m scripts.release.verify_provenance provenance.json --digest "$DIGEST" \
  --repo "$REPO" --ref "refs/tags/$TAG" --commit "$COMMIT"
```

`verify_provenance.py` rejects a valid attestation whose subject digest, certificate identity, issuer, source repository, ref, commit, workflow path, builder id or runner environment differs from the expected values.

## 4. Windows package

```bash
cosign verify-blob SHA256SUMS --bundle SHA256SUMS.sigstore.json --certificate-identity "$SIGNER" --certificate-oidc-issuer "$ISSUER"
sha256sum -c SHA256SUMS
```

## A tamper that fails

```bash
sed -i '1s/^./0/' SHA256SUMS
cosign verify-blob SHA256SUMS --bundle SHA256SUMS.sigstore.json --certificate-identity "$SIGNER" --certificate-oidc-issuer "$ISSUER"
# Error: ... invalid signature ...   (exit code 1)
```

## Evidence

| Check | Command | Date | Result |
| --- | --- | --- | --- |
| Keyless verify with the expected identity (real Chainguard image) | `pytest tests/integration/test_supply_chain.py -m network` | 2026-11-15 | PASS |
| Wrong workflow, wrong ref, wrong issuer, wrong repository rejected | same | 2026-11-15 | PASS (4 cases) |
| Modified blob fails signature verification | same, `test_modified_blob_fails_signature` | 2026-11-15 | PASS |
| Provenance policy on a real GitHub attestation (GitHub CLI v2.104.0) | `pytest scripts/release/test_verify_provenance.py` | 2026-11-15 | PASS, with 10 tampered and 5 policy-mismatch cases rejected |
| Real Syft SBOMs validate (cyclonedx-cli, pyspdxtools) and a corrupted copy fails | manual run, see [control matrix](control-matrix.md) | 2026-11-15 | PASS |
| Full release verification of `v0.2.0` | release `verify` job, GitHub release run 43983071969 | 2026-11-16 | PASS (8 controls in `verify.json`) |
| Independent verification of `v0.2.0` from a separate machine (steps 1 to 4, tampered checksums, wrong identity) | commands above, cosign 3.1.4, GitHub CLI | 2026-11-17 | PASS (9 checks, both negative cases rejected) |
| Release `v0.2.1` (image `sha256:dbba11b288a6a0b8d0a556b89fa331a21fdd312ef2d5f77212859a058a6c7916`, commit `e0f153d`) | GitHub release run 44092986387; production approval submitted on the owner's instruction | 2026-11-17 | PASS, gate ALLOWED with SonarCloud PASS |
| Independent verification of `v0.2.1` (signature, SBOM digest binding, attestation, provenance policy, Windows signature; the `v0.2.0` identity is rejected) | commands above | 2026-11-17 | PASS |

## Reproducible builds

Not claimed. Two builds of the same commit are not compared byte for byte. Provenance identifies the build; it does not make it reproducible.
