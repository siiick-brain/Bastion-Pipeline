# Roadmap

## Next (needs the owner)

1. Release `v0.2.1`, promote it through a pull request, then revert that pull request to verify rollback to `v0.2.0`.
2. Apply Dependabot base image updates (pull request 16) through a pull request under the owner identity.
3. Run the DAST demo workflow and wait for the first scheduled scans.
4. Optional: add `NVD_API_KEY` and a GitLab remote.
5. Capture the remaining screenshots in [the screenshot plan](screenshots.md).

## Planned (deferred ideas)

- Admission-time signature verification with a Sigstore policy controller.
- Ephemeral Jenkins agents per build.
- Reproducible build comparison between two independent builds.
- Mutation testing for `scripts/oidc/verifier.py` and `update-signing/bastion_update/device.py`.
- Cloud federation with a real provider using the same OIDC claims.

## Not planned

- Real secure boot or a real HSM. These need hardware outside the project scope.
