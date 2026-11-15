# ADR 0001: Keyless signing with one release authority

Date: 2026-11-15. Status: Accepted.

## Context

The original release workflow signed an image tag with cosign but never verified who signed it. A signature alone proves only that some key or identity signed some bytes. Three CI platforms exist, so the question is also which of them may produce trusted artifacts.

## Decision

- Sign with Sigstore keyless signing from `.github/workflows/release.yml` only. No private signing key exists to steal or rotate.
- Sign and attest the image digest, never a tag.
- Verification requires the exact certificate identity `https://github.com/siiick-brain/Bastion-Pipeline/.github/workflows/release.yml@refs/tags/<tag>` and the issuer `https://token.actions.githubusercontent.com`.
- Provenance claims (workflow path, ref, commit, runner, subject digest) are checked by `scripts/release/verify_provenance.py` after `gh attestation verify`.
- GitLab CI and Jenkins run the source stages only. They never sign.

## Consequences

- A signature produced by any other workflow, branch or tag fails verification, which the negative tests prove.
- Signing depends on the public Sigstore infrastructure. Rekor entries are public and reveal the repository and digest.
- Offline verification is possible with the bundle but needs the Sigstore trust root.

## Alternatives considered

- **Long-lived cosign key in a secret.** Rejected: key theft and rotation become the main risk.
- **Signing from all three platforms.** Rejected: three identities to trust and three policies to keep aligned.
