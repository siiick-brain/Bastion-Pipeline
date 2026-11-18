# Roadmap

## Next

1. Add `NVD_API_KEY` so the weekly Dependency-Check scan runs.
2. Open a pull request from a fork to exercise C33.
3. Apply future Dependabot updates through a pull request under the project author.
4. Capture the signed-in pages listed in [screenshots](screenshots.md).

## Planned (deferred ideas)

- Ephemeral Jenkins agents per build.
- Reproducible build comparison between two independent builds.
- Mutation testing for `scripts/oidc/verifier.py` and `update-signing/bastion_update/device.py`.
- Cloud federation with a real provider using the same OIDC claims.

## Not planned

- Real secure boot or a real HSM. These need hardware outside the project scope.
