# Contributing

This is a personal repository. Changes go through a branch, the local checks and a pull request.

## Local checks

1. `git config core.hooksPath scripts/hooks`
2. `pwsh -File scripts/validate-pipeline.ps1`

## Commit rules

- Author and committer must match `.github/allowed-author`.
- Conventional Commit titles, at most 72 characters.
- No co-author or tool attribution trailers.
- Never bypass hooks with `--no-verify`.
