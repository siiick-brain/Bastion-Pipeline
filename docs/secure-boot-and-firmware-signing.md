# Secure boot and firmware signing

`firmware-sim/boot_sim.py` is a simulation. It runs no firmware and is not real secure boot. It models the decisions a boot ROM makes so they can be tested.

## Chain of trust

The ROM is immutable and holds the SHA-256 of the root public key, as if fused into one-time programmable memory. The root key signs a key certificate for an image-signing key. The image-signing key signs the image header. The header binds the payload by SHA-256 and size. Each stage trusts only what the previous stage verified.

## Key hierarchy

| Key | Where it lives | Signs | Rotation |
| --- | --- | --- | --- |
| Root | Offline, in an HSM, used in a signing ceremony | Key certificates | Rare; requires new devices or a fused root key list |
| Image signing | HSM, online for builds | Image headers | Routine; issue a new certificate, revoke the old key id |

## Rollback protection

The image header carries a security version. One-way fuses store the minimum accepted security version. A boot with `commit=True` advances the fuse after a successful boot. A lower security version is refused even when validly signed.

## Revocation

Revoked key ids are burned into fuses. A certificate for a revoked key fails even though the root signature is valid.

## Measured boot

Each verified stage is extended into a PCR-like register: `pcr = SHA-256(pcr || SHA-256(stage))`. The final value depends on every stage and their order, so a remote verifier can attest what booted.

## Signing ceremony

Root key operations happen offline with at least two custodians, a scripted procedure, recorded hashes of every input and output. The HSM audit log is archived. The simulation does not model the ceremony.

## Evidence

| Case | Expected | Command | Date | Result |
| --- | --- | --- | --- | --- |
| Valid image | Boots, two measurements logged | `pytest firmware-sim` | 2026-11-15 | PASS |
| Tampered payload or header | Rejected | same | 2026-11-15 | PASS |
| Unsigned image | Rejected | same | 2026-11-15 | PASS |
| Downgraded image | Rejected | same | 2026-11-15 | PASS |
| Revoked key | Rejected | same | 2026-11-15 | PASS |
| Wrong chain (other root, swapped issuer key) | Rejected | same | 2026-11-15 | PASS |
| Additional: uncertified signer, expired certificate, wrong role, key id mismatch, missing certificate, garbage signature, fuse never decreases | Rejected | same | 2026-11-15 | PASS (20 tests, 100 percent coverage) |

Demo output (`python firmware-sim/boot_sim.py`, 2026-11-15):

```text
SIMULATION ONLY: not real secure boot.
ACCEPT  valid image        PCR=83c39a6e02bb55a2...
REJECT  tampered payload   image payload does not match signed header (tampered)
REJECT  unsigned image     image is unsigned
REJECT  downgraded image   downgrade: security_version 1 < fuse 2
REJECT  revoked key        signing key revoked
REJECT  wrong chain        wrong chain: certificate issuer is not the ROM root key
```

The PCR value differs per run because keys are generated per run.

## Limits of the simulation

No hardware root of trust, no real fuses, no TPM, no firmware update capsule format, no anti-glitching or side-channel protection. Ed25519 is used for brevity where real ROMs often use ECDSA or RSA.
