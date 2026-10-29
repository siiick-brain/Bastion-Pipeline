# PKCS#11 and SoftHSM notes

This file records the update-signing flow with the SoftHSM2 container.

## Planned proof

- Generate a per-run PIN.
- Create an EC P-256 key on the token.
- Sign a manifest through PKCS#11.
- Verify the signature, hash and rollback counter.
- Note that SoftHSM is software and not a real HSM.
