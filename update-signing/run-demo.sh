#!/usr/bin/env bash
# Full demonstration inside the container: token setup, PKCS#11 signing, verification,
# negative cases and the persistence of the anti-rollback counter across runs.
set -euo pipefail
cd /work
source ./init-token.sh
export PKCS11_PIN_FILE=/tmp/hsm-secrets/user.pin
export COVERAGE_FILE=/tmp/.coverage
python3 -m pytest -q -p no:cacheprovider tests --cov=bastion_update --cov=build_update \
  --cov=verify_update --cov-report=term --cov-fail-under=85 -o pythonpath=.
