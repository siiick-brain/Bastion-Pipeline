# Roadmap

## Next

1. Apply future Dependabot updates through a pull request under the project author.
2. Optional: an `NVD_API_KEY` secret for the weekly Dependency-Check scan.

## Planned (deferred ideas)

- Ephemeral Jenkins agents per build.
- Reproducible build comparison between two independent builds.
- Mutation testing for `scripts/oidc/verifier.py` and `update-signing/bastion_update/device.py`.
- Cloud federation with a real provider using the same OIDC claims.

## Not planned

- Real secure boot or a real HSM. These need hardware outside the project scope.
