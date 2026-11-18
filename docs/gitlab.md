# GitLab CI

`.gitlab-ci.yml` implements the source stages of the [pipeline contract](pipeline-contract.md): policy (authorship), lint, test with the coverage gate, Semgrep, Gitleaks, OSV-Scanner, Trivy config and a source SBOM. Every image is pinned by digest. No security step ends in `|| true`.

## Second remote

```bash
git remote add gitlab https://gitlab.com/siiick-brain/bastion-pipeline.git
git push gitlab main
```

## Evidence

| Check | Command | Date | Result |
| --- | --- | --- | --- |
| YAML lint | `yamllint --strict .gitlab-ci.yml` | 2026-11-15 | PASS |
| GitLab CI JSON schema | `uvx check-jsonschema==0.36.0 --builtin-schema vendor.gitlab-ci .gitlab-ci.yml` | 2026-11-15 | PASS |
| Pipeline run on GitLab | pipeline 3083481172 on `gitlab.com/siiick-brain/bastion-pipeline` | 2026-11-18 | PASS: policy, lint, test, Semgrep, Gitleaks, OSV-Scanner, Trivy config and SBOM |
