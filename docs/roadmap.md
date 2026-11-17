# Roadmap

## Next (needs the owner)

1. Check the first weekly run of `scheduled-scans.yml`.
2. Apply future Dependabot updates through a pull request under the owner identity.
3. Optional: add `NVD_API_KEY` and a GitLab remote; open a pull request from a fork to exercise C33.
4. Capture the remaining screenshots in [the screenshot plan](screenshots.md).

## Planned (deferred ideas)

- Ephemeral Jenkins agents per build.
- Reproducible build comparison between two independent builds.
- Mutation testing for `scripts/oidc/verifier.py` and `update-signing/bastion_update/device.py`.
- Cloud federation with a real provider using the same OIDC claims.

## Not planned

- Real secure boot or a real HSM. These need hardware outside the project scope.
