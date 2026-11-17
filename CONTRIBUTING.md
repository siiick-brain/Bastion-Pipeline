# Contributing

This is a personal repository. Changes go through a branch, the local checks and a pull request.

## Local checks

1. `git config core.hooksPath scripts/hooks`
2. `pwsh -File scripts/validate-pipeline.ps1`

## Commit rules

- Author and committer must match an identity in `.github/allowed-author`. The first line is the current identity (the GitHub no-reply address); later lines cover the earlier address of existing commits and the GitHub display name that web merges record as committer.
- Conventional Commit titles, at most 72 characters.
- No co-author or tool attribution trailers.
- Never bypass hooks with `--no-verify`.
