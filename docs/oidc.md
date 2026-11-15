# OIDC without a cloud account

GitHub Actions can mint a short-lived OpenID Connect token for a job. A cloud provider exchanges that token for temporary credentials after checking its signature and claims against a role trust policy. This project performs the same checks with `scripts/oidc/verifier.py` and no cloud account.

## What the verifier checks

1. The header algorithm is in an explicit allowlist (`RS256`). `none`, `HS256` (key confusion), `ES256` and `RS512` are rejected.
2. The `kid` resolves against GitHub's JWKS, found through `https://token.actions.githubusercontent.com/.well-known/openid-configuration`. The discovery document must name the same issuer and host the JWKS under it.
3. An unknown `kid` triggers at most one JWKS refresh per 60 seconds, which handles key rotation without letting an attacker force constant refetching.
4. Signature, exact issuer, exact audience (a list containing the audience is rejected), `exp`, `nbf` and `iat` with 30 seconds of leeway. The maximum lifetime is one hour.
5. Mandatory claims: `iss`, `aud`, `exp`, `iat`, `nbf`, `sub`, `repository`, `repository_owner`, `ref`, `job_workflow_ref`, `event_name`.
6. Policy (`scripts/oidc/policy.toml`): repository, owner, `refs/heads/main` only, environment `oidc-demo`, events `push` or `workflow_dispatch`. The job must come from the `oidc-demo.yml` workflow.

The raw token is never printed. Printed claims mask identifiers (`repository_id`, `sub`, `jti` and others) and show the lifetime computed from `iat` and `exp`.

## Evidence

| Check | Command | Date | Result |
| --- | --- | --- | --- |
| Valid, wrong audience, expired, not yet valid, issued in the future, lifetime too long, wrong repository, owner, ref, environment, event, workflow, missing claims, bad signature, modified payload, disallowed algorithms, malformed tokens, missing and unknown `kid`, rotation, discovery validation, masking | `pytest scripts/oidc` (generated RSA keys, never real tokens) | 2026-11-15 | PASS, 44 tests |
| Real GitHub discovery document and JWKS load; unknown `kid` rejected | `pytest tests/integration/test_oidc_live.py -m network` | 2026-11-15 | PASS |
| Real token from `main` accepted | `.github/workflows/oidc-demo.yml` | | NOT VERIFIED (workflow not run yet) |
| Real token rejected for a wrong audience | same workflow, second step | | NOT VERIFIED |
| Run from a non-main ref fails the policy | run `oidc-demo` with "Use workflow from" set to another branch | | NOT VERIFIED |

Generated test tokens and real GitHub tokens are kept separate: unit tests never see a real token. The hosted run never uses generated keys.

## How a cloud provider uses the same claims

An AWS IAM role trust policy for this repository would contain conditions equivalent to the policy file:

```json
{
  "Condition": {
    "StringEquals": {
      "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
      "token.actions.githubusercontent.com:sub": "repo:siiick-brain/Bastion-Pipeline:environment:oidc-demo"
    }
  }
}
```

## Planned

Cloud federation with a real provider is PLANNED and out of scope. No cloud account is part of this project.
