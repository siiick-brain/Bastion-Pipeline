#!/usr/bin/env bash
# Initialises a SoftHSM2 token with PINs generated for this run and creates a
# non-extractable EC P-256 signing key on it. PINs are written to files with mode 0600 in a
# private tmpfs directory and are never printed.
set -euo pipefail
umask 077
secrets_dir="${SECRETS_DIR:-/tmp/hsm-secrets}"
token_dir="${TOKEN_DIR:-/home/signer/tokens}"
mkdir -p "$secrets_dir" "$token_dir"
printf 'directories.tokendir = %s\nobjectstore.backend = file\nlog.level = ERROR\n' "$token_dir" > "$SOFTHSM2_CONF"

python3 -c 'import secrets; print(secrets.token_hex(16))' > "$secrets_dir/user.pin"
python3 -c 'import secrets; print(secrets.token_hex(16))' > "$secrets_dir/so.pin"

softhsm2-util --init-token --free --label "${PKCS11_TOKEN:-bastion-update}" \
  --pin "$(cat "$secrets_dir/user.pin")" --so-pin "$(cat "$secrets_dir/so.pin")" > /dev/null
export PKCS11_PIN_FILE="$secrets_dir/user.pin"
python3 -c '
import os
from pathlib import Path
from bastion_update.pkcs11_signer import Pkcs11Signer
s = Pkcs11Signer(os.environ["PKCS11_MODULE"], os.environ.get("PKCS11_TOKEN", "bastion-update"),
                 Path(os.environ["PKCS11_PIN_FILE"]).read_text().strip(),
                 os.environ.get("PKCS11_KEY_LABEL", "update-signing"))
s.generate()
print("key attributes:", s.private_attributes())
'
echo "token initialised; PIN file: $PKCS11_PIN_FILE"
