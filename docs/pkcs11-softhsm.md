# Signed updates with PKCS#11 and SoftHSM2

SoftHSM2 is a software implementation of the PKCS#11 interface. It demonstrates how signing code talks to a token. It does not provide hardware key protection.

## Flow

1. `update-signing/init-token.sh` writes a SoftHSM config, generates a user PIN and a security officer PIN with `secrets.token_hex(16)` into mode 0600 files in a tmpfs. It then initialises the token. PINs are never printed or passed on a command line visible to other users (the `softhsm2-util` call is the exception, inside a single-user container).
2. `Pkcs11Signer.generate()` creates an EC P-256 key pair on the token with `SENSITIVE=true`, `EXTRACTABLE=false`, `SIGN=true`.
3. `build_update.py` writes `payload.bin`, a canonical `manifest.json` (format, name, version, min_version, sha256, size, key_id, created, expires) and `manifest.sig` (ECDSA P-256 SHA-256, raw r||s, signed on the token).
4. `verify_update.py` checks, in order: manifest schema and canonical form, key not revoked, key trusted, signature, expiry and creation time, payload size and SHA-256, then anti-rollback.
5. `Device.install()` copies the package to `staging/`, verifies the staged copy again, renames it into `versions/<version>/`, then atomically replaces `state.json` and only then `current` (temporary file, `fsync`, `os.replace`, directory `fsync` on POSIX). The anti-rollback state advances first, so a crash between the two writes can never leave a new version running with a counter that still accepts older ones; reinstalling the same package finishes the interrupted activation.

## Anti-rollback

`state.json` holds `installed_version` and `rollback_floor`. A package is refused when its version is below the floor, equal to the installed version (repeated installation) or below the installed version. The floor is raised to `min_version` and never decreases. A corrupt state file refuses all updates instead of resetting to zero.

## Evidence

| Check | Command | Date | Result |
| --- | --- | --- | --- |
| Key generated on the token: sensitive, not extractable, never extractable, always sensitive, local | container `tests/test_pkcs11.py` | 2026-11-15 | PASS |
| Wrong PIN refused | same | 2026-11-15 | PASS |
| Token signature verifies with the exported public key, a modified message fails | same | 2026-11-15 | PASS |
| CLI build, sign, verify, install, downgrade refused, PIN absent from output | same | 2026-11-15 | PASS |
| Counter persists across two container runs on a named volume | `docker run ... -e DEMO_RUN=1` then `DEMO_RUN=2` with `-v bastion-update-state:/state` | 2026-11-15 | PASS |
| Tampered payload, appended payload, unsigned, invalid signature, garbage signature, wrong key, wrong key with trusted key id, revoked key, missing manifest, missing payload, 14 malformed manifest cases, non-canonical manifest, expired, created in the future, downgrade, downgrade below floor, repeated installation, corrupt state, interrupted install, failed state write, package swapped during install | `pytest update-signing` | 2026-11-15 | PASS, 50 tests |
| Container suite coverage | `run-demo.sh` | 2026-11-15 | 96.78 percent |

Reproduce:

```powershell
docker build -t bastion-update-signing:local update-signing
docker volume create bastion-update-state
docker run --rm --read-only --tmpfs /tmp:rw,mode=1777 --tmpfs /home/signer:rw,uid=10001,gid=10001 --cap-drop ALL --security-opt no-new-privileges -e DEMO_RUN=1 -v bastion-update-state:/state bastion-update-signing:local
docker run --rm --read-only --tmpfs /tmp:rw,mode=1777 --tmpfs /home/signer:rw,uid=10001,gid=10001 --cap-drop ALL --security-opt no-new-privileges -e DEMO_RUN=2 -v bastion-update-state:/state bastion-update-signing:local
```

The token and its key are recreated on every run. The second run proves that the device state, not the key, carries the rollback protection.

## What a real HSM adds

- Keys protected by tamper-resistant hardware with physical attack resistance.
- Certified security level (for example FIPS 140-3 Level 3).
- Hardware-enforced key usage policy, authentication by multiple custodians and audit logs.
- A hardware monotonic counter for rollback protection, which a file on a volume cannot match: an attacker with write access to the volume can roll the file back.
- Key backup and cloning only under the HSM vendor's controlled procedure.
