# Update signing

This folder contains the PKCS#11 and SoftHSM2 flow for signed update packages.

## Planned proof

- SoftHSM2 token generation with a per-run PIN.
- EC P-256 key generation on a non-extractable token.
- Manifest signing and verification checks.
- Negative tests for downgrade, tampering and invalid signatures.
