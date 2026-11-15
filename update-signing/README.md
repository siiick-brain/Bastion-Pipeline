# Update signing

PKCS#11 signing of update packages with SoftHSM2, verification with anti-rollback and atomic installation. SoftHSM is a software token, not hardware. Details and evidence: [PKCS#11 and SoftHSM](../docs/pkcs11-softhsm.md).

```powershell
docker build -t bastion-update-signing:local .
docker run --rm --read-only --tmpfs /tmp:rw,mode=1777 --tmpfs /home/signer:rw,uid=10001,gid=10001 --cap-drop ALL bastion-update-signing:local
```
