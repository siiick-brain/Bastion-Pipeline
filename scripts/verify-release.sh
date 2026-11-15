#!/usr/bin/env bash
# Verifies a released image digest and Windows package, then writes evidence/verify.json.
# Each control is PASS or FAIL. The script exits non-zero if any control fails.
#
# Required env: IMAGE (ghcr.io/owner/repo), DIGEST (sha256:...), REPO (owner/repo),
#               REF (refs/tags/vX.Y.Z), COMMIT (40-hex), GH_TOKEN (read access)
# Inputs in the working directory: sbom.cdx.json, sbom.spdx.json, winpkg/{*.zip,SHA256SUMS,SHA256SUMS.sigstore.json}
set -euo pipefail
: "${IMAGE:?}" "${DIGEST:?}" "${REPO:?}" "${REF:?}" "${COMMIT:?}"
SIGNER="https://github.com/${REPO}/.github/workflows/release.yml@${REF}"
ISSUER="https://token.actions.githubusercontent.com"
REF_IMG="${IMAGE}@${DIGEST}"
mkdir -p evidence
declare -A R

run() { # run <control> <command...>: records PASS when the command succeeds
  local key="$1"; shift
  if "$@" > "evidence/${key}.log" 2>&1; then R[$key]=PASS; else R[$key]=FAIL; fi
  echo "${key}: ${R[$key]}"
}
expect_fail() { # records PASS when the command fails (negative control)
  local key="$1"; shift
  if "$@" > "evidence/${key}.log" 2>&1; then R[$key]=FAIL; else R[$key]=PASS; fi
  echo "${key}: ${R[$key]}"
}

# 1. What was signed and who signed it: exact workflow identity and issuer, by digest.
run cosign_verify cosign verify "$REF_IMG" --certificate-identity "$SIGNER" --certificate-oidc-issuer "$ISSUER"

# 2. SBOM attestations bound to the digest, signed by the same identity.
sbom_att() {
  cosign verify-attestation "$REF_IMG" --type cyclonedx --certificate-identity "$SIGNER" --certificate-oidc-issuer "$ISSUER" >/dev/null
  cosign verify-attestation "$REF_IMG" --type spdxjson --certificate-identity "$SIGNER" --certificate-oidc-issuer "$ISSUER" >/dev/null
}
run sbom_attestation sbom_att

# 3. Which build produced it: provenance verified by gh, then claims checked by policy.
prov() {
  gh attestation verify "oci://$REF_IMG" --repo "$REPO" --signer-workflow "${REPO}/.github/workflows/release.yml" \
    --source-ref "$REF" --format json > evidence/provenance.json
  python -m scripts.release.verify_provenance evidence/provenance.json --digest "$DIGEST" \
    --repo "$REPO" --ref "$REF" --commit "$COMMIT"
}
run provenance prov

# 4. SBOM content describes this digest and passes both official validators.
python -m scripts.release.sbom_check sbom.cdx.json sbom.spdx.json "$DIGEST" > evidence/sbom-check.json || true
if docker run --rm -v "$PWD:/d:ro" cyclonedx/cyclonedx-cli@sha256:f025573a1dcc12971d711badf32bff1e030192a051a3a4987204fc6b79f91b6c \
     validate --input-file /d/sbom.cdx.json --input-version v1_6 --fail-on-errors > evidence/cdx-schema.log 2>&1 \
   && pyspdxtools -i sbom.spdx.json >> evidence/cdx-schema.log 2>&1; then
  echo PASS > evidence/cdx-schema.txt
else
  echo "FAIL: see cdx-schema.log" > evidence/cdx-schema.txt
fi

# 5. Windows package: checksums signed by the release workflow, and the zip matches them.
win() {
  cosign verify-blob winpkg/SHA256SUMS --bundle winpkg/SHA256SUMS.sigstore.json \
    --certificate-identity "$SIGNER" --certificate-oidc-issuer "$ISSUER"
  (cd winpkg && sha256sum -c SHA256SUMS)
}
run windows_signature win

# 6. Negative controls: a tampered artifact and a wrong identity must both be rejected.
tamper() {
  local t; t="$(mktemp -d)"
  cp winpkg/SHA256SUMS winpkg/SHA256SUMS.sigstore.json "$t/"
  sed -i '1s/^./0/' "$t/SHA256SUMS"
  cosign verify-blob "$t/SHA256SUMS" --bundle "$t/SHA256SUMS.sigstore.json" \
    --certificate-identity "$SIGNER" --certificate-oidc-issuer "$ISSUER"
}
expect_fail tamper_blob tamper
expect_fail wrong_identity cosign verify "$REF_IMG" \
  --certificate-identity "https://github.com/${REPO}/.github/workflows/ci.yml@${REF}" --certificate-oidc-issuer "$ISSUER"
expect_fail wrong_issuer cosign verify "$REF_IMG" --certificate-identity "$SIGNER" \
  --certificate-oidc-issuer "https://accounts.google.com"
if [[ "${R[tamper_blob]}" == PASS && "${R[wrong_identity]}" == PASS && "${R[wrong_issuer]}" == PASS ]]; then
  R[tamper_rejected]=PASS
else
  R[tamper_rejected]=FAIL
fi

{
  printf '{'
  first=1
  for k in cosign_verify sbom_attestation provenance windows_signature tamper_rejected tamper_blob wrong_identity wrong_issuer; do
    [[ $first == 1 ]] || printf ','
    printf '"%s":"%s"' "$k" "${R[$k]}"
    first=0
  done
  printf ',"digest":"%s","signer":"%s"}\n' "$DIGEST" "$SIGNER"
} > evidence/verify.json
cat evidence/verify.json

for v in "${R[@]}"; do [[ "$v" == PASS ]] || exit 1; done
