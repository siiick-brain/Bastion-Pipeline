# Threat model

Scope: the delivery pipeline described in [the architecture](architecture.md). Method: one row per threat with the asset, actor, entry point, trust boundary (TB, defined in the architecture), impact, mitigation and the test that verifies it. Status uses the words in [the glossary](GLOSSARY.md). A mitigation is PASS only when its verification has run.

Last reviewed: 2026-11-15.

## T1. Malicious pull request

| Field | Value |
| --- | --- |
| Asset | Repository secrets, write token, signing identity, main branch |
| Actor | Anyone who can open a pull request from a fork |
| Entry point | Pull request workflows |
| Boundary | TB1 |
| Impact | Secret theft, poisoned cache, malicious code merged |
| Existing mitigation | `pull_request` only (no `pull_request_target`). `permissions: {}` at workflow level with read-only job tokens. `persist-credentials: false`. No secrets in PR jobs. SonarCloud and SARIF upload skipped for forks. Required checks and pull request rule on `main` (`scripts/apply-branch-protection.ps1`). |
| Additional mitigation | Require approval for first-time contributors in repository settings (manual). |
| Verification | `zizmor` and `actionlint` in the `policy` job (PASS locally 2026-11-15: no findings). Hosted fork PR run: NOT VERIFIED. Ruleset applied: NOT VERIFIED until `-Apply`. |

## T2. Compromised dependency

| Field | Value |
| --- | --- |
| Asset | Built image, developer machines, CI runners |
| Actor | Attacker who publishes a malicious version or takes over a package |
| Entry point | `pip install`, base images, tool images |
| Boundary | TB2 |
| Impact | Code execution in CI or in the shipped image |
| Existing mitigation | `--require-hashes` with `uv pip compile --generate-hashes` lock files. Base and tool images pinned by digest. Dependabot 7-day cooldown. OSV-Scanner PR gate. Dependency review on PRs. Runtime image contains only runtime dependencies. |
| Additional mitigation | Private package mirror (PLANNED, out of scope). |
| Verification | `tests/integration/test_container.py::test_no_dev_tools_in_image` (PASS 2026-11-15). OSV-Scanner on all lock files: no issues (PASS 2026-11-15). Gate demo `gate-demo/vuln-dependency`: OSV reports 6 vulnerabilities in jinja2 2.10 locally (PASS 2026-11-15). Hosted PR turning red: NOT VERIFIED. |

## T3. Compromised GitHub Action

| Field | Value |
| --- | --- |
| Asset | Workflow tokens, signing identity |
| Actor | Attacker who moves a tag or compromises an action repository |
| Entry point | `uses:` references |
| Boundary | TB2 |
| Impact | Arbitrary code in jobs with write or `id-token` permission |
| Existing mitigation | Every third-party action pinned to a full commit SHA from a release at least 7 days old. Permissions per job. Install scripts (`curl | sh`) removed from `release.yml`. |
| Additional mitigation | GitHub "require SHA pinning" repository policy (manual setting). |
| Verification | `zizmor --min-severity low`: no findings (PASS 2026-11-15). Gate demo `gate-demo/unpinned-action`: NOT VERIFIED until pushed. |

## T4. Compromised Jenkins agent

| Field | Value |
| --- | --- |
| Asset | Jenkins controller, host machine |
| Actor | Malicious build step or dependency running on the agent |
| Entry point | Agent process |
| Boundary | TB7 |
| Impact | Controller takeover, host escape through the Docker socket |
| Existing mitigation | Controller has zero executors. No service mounts `/var/run/docker.sock`. Agent has no published ports and only a read-only source mount. Job DSL pipeline runs in the Groovy sandbox. Both containers run with `no-new-privileges`. |
| Additional mitigation | Ephemeral agents per build (PLANNED). |
| Verification | `docker inspect` mount check in [Jenkins notes](jenkins.md). Local Jenkins run: see [Jenkins notes](jenkins.md) for status. |

## T5. Secret leakage

| Field | Value |
| --- | --- |
| Asset | Tokens, keys, PINs |
| Actor | Insider mistake, log reader |
| Entry point | Commits, logs, build output |
| Boundary | TB1, TB4 |
| Impact | Account or signing compromise |
| Existing mitigation | Gitleaks on full history in CI. No long-lived signing key (keyless). OIDC verifier never prints the token and masks identifiers. SoftHSM PINs generated per run and read from files. Jenkins secrets in a gitignored folder. |
| Additional mitigation | GitHub push protection (manual setting). |
| Verification | `gitleaks git .` on history: no leaks (PASS 2026-11-15). `scripts/oidc/test_verifier.py::test_masking_hides_identifiers_and_never_includes_token` (PASS). `update-signing/tests/test_pkcs11.py` asserts the PIN is not in output (PASS 2026-11-15, container). Gate demo `gate-demo/fake-secret`: NOT VERIFIED until pushed. |

## T6. Build artifact tampering

| Field | Value |
| --- | --- |
| Asset | Container image, Windows zip, SBOMs |
| Actor | Attacker with registry or storage access |
| Entry point | GHCR, release assets |
| Boundary | TB4, TB5 |
| Impact | Users run modified code |
| Existing mitigation | Push and reference by digest. Keyless signatures on image and checksums. SBOMs attested to the digest. `sbom_check.py` binds SBOMs to the digest. Windows `Test-Checksum` rejects path traversal. |
| Additional mitigation | Admission-time signature policy with Kyverno ([ADR 0006](adr/0006-admission-signature-policy.md)). |
| Verification | `tests/integration/test_supply_chain.py::test_modified_blob_fails_signature` (PASS 2026-11-15). `windows/tests/build.tests.ps1` checksum tamper cases (PASS 2026-11-15). Hosted release `tamper_rejected`: NOT VERIFIED. |

## T7. Signing credential compromise

| Field | Value |
| --- | --- |
| Asset | Signing identity |
| Actor | Attacker who can run a workflow in this repository |
| Entry point | Any workflow with `id-token: write` |
| Boundary | TB3 |
| Impact | Malicious artifact with a valid signature |
| Existing mitigation | Verification requires the exact identity `.../release.yml@refs/tags/<tag>` and issuer. Provenance policy checks workflow path, ref, commit and runner. A signature from `ci.yml` or another ref fails. |
| Additional mitigation | Tag protection rules (manual setting). |
| Verification | `scripts/release/test_verify_provenance.py` (10 tamper cases on a real attestation, PASS 2026-11-15). `tests/integration/test_supply_chain.py::test_keyless_signature_rejects_wrong_identity` (4 cases against real Sigstore, PASS 2026-11-15). |

## T8. Malicious release promotion

| Field | Value |
| --- | --- |
| Asset | Production release |
| Actor | Contributor who pushes a tag |
| Entry point | `release.yml` |
| Boundary | TB3, TB4 |
| Impact | Release of untested or unapproved code |
| Existing mitigation | `guard` job requires a semantic tag on a commit reachable from `main`. Gate runs in the `production` environment with a required reviewer. `gate.py` blocks on any mandatory control that is FAIL or NOT VERIFIED. Publish runs only after the gate. |
| Additional mitigation | None. |
| Verification | `scripts/release/test_gate.py` (26 cases including missing evidence, PASS 2026-11-15). Hosted release run: NOT VERIFIED. `production` environment reviewer: NOT VERIFIED (manual setting, see [screenshots](screenshots.md)). |

## T9. Unauthorized deployment

| Field | Value |
| --- | --- |
| Asset | Running workload |
| Actor | Anyone with cluster access or overlay write access |
| Entry point | `deploy/overlays/*`, `kubectl` |
| Boundary | TB5, TB6 |
| Impact | Unsigned or privileged workload runs |
| Existing mitigation | `promote.ps1` refuses tags and unverified digests. Namespace enforces Pod Security `restricted`. Default-deny NetworkPolicy. ClusterIP service only. ArgoCD self-heal reverts manual changes. |
| Additional mitigation | Admission-time signature verification with Kyverno ([ADR 0006](adr/0006-admission-signature-policy.md)): only the project image by digest, signed by the release workflow. |
| Verification | `scripts/kind-demo.ps1` on 2026-11-15: unsigned image refused by `promote.ps1` (PASS). `scripts/verify-deployment.ps1`: privileged pod rejected by admission (PASS). ArgoCD drift heal: PASS on 2026-11-17. `scripts/verify-admission.ps1` on 2026-11-17: signed releases admitted, tag reference, foreign registry and unsigned object rejected (PASS). |

## T10. Software update rollback

| Field | Value |
| --- | --- |
| Asset | Device running signed updates |
| Actor | Attacker who replays an old, validly signed package |
| Entry point | `update-signing` verifier |
| Boundary | Device |
| Impact | Reintroduction of a fixed vulnerability |
| Existing mitigation | Persistent anti-rollback state written atomically. Rollback floor never decreases. Corrupt state refuses all updates. Expiry and revocation checks. Staged install re-verifies the copy. |
| Additional mitigation | Hardware monotonic counter (not available in a software demonstration). |
| Verification | `update-signing/tests/test_update.py` (50 cases, PASS 2026-11-15). Persistence across two container runs on a named volume (PASS 2026-11-15). `firmware-sim/tests/test_boot_sim.py::test_downgraded_image_is_rejected` (PASS). |
