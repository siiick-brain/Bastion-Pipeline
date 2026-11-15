# Roadmap

## Next (needs the owner)

1. Review and commit the hardening work, then push to `main` so the hosted workflows run.
2. Create the `production` and `oidc-demo` environments and apply the branch ruleset.
3. Push the first tag (`v0.2.0`) and verify the release with [the verify guide](verify.md).
4. Promote the released digest and verify ArgoCD sync, drift healing and rollback.
5. Push the gate demo branches and record the red checks.
6. Optional: add `SONAR_TOKEN`, `NVD_API_KEY` and a GitLab remote.
7. Capture the screenshots in [the screenshot plan](screenshots.md).

## Planned (deferred ideas)

- Admission-time signature verification with a Sigstore policy controller.
- Ephemeral Jenkins agents per build.
- Reproducible build comparison between two independent builds.
- Mutation testing for `scripts/oidc/verifier.py` and `update-signing/bastion_update/device.py`.
- Cloud federation with a real provider using the same OIDC claims.

## Not planned

- Real secure boot or a real HSM. These need hardware outside the project scope.
