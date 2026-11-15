# GitLab CI

`.gitlab-ci.yml` implements the source stages of the [pipeline contract](pipeline-contract.md): policy (authorship), lint, test with the coverage gate, Semgrep, Gitleaks, OSV-Scanner, Trivy config and a source SBOM. Every image is pinned by digest. No security step ends in `|| true`.

## Second remote

```bash
git remote add gitlab git@gitlab.com:<user>/bastion-pipeline.git
git push gitlab main
glab ci lint            # needs: glab auth login
```

## Evidence

| Check | Command | Date | Result |
| --- | --- | --- | --- |
| YAML lint | `yamllint --strict .gitlab-ci.yml` | 2026-11-15 | PASS |
| GitLab CI JSON schema | `uvx check-jsonschema==0.36.0 --builtin-schema vendor.gitlab-ci .gitlab-ci.yml` | 2026-11-15 | PASS |
| `glab ci lint` | | | NOT VERIFIED: glab not authenticated |
| Pipeline run on GitLab | | | NOT VERIFIED: no GitLab remote configured |
