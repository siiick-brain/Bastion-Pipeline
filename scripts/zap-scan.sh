#!/usr/bin/env bash
# Runs a ZAP scan from the pinned ZAP image against a target on a local Docker network only.
# Usage: scripts/zap-scan.sh <baseline|full> <target-url> <report-name>
# Env: DAST_NETWORK (default bastion-scan). Refuses targets that are not local container names.
set -euo pipefail
mode="${1:?mode}"; target="${2:?target}"; name="${3:?report name}"
network="${DAST_NETWORK:-bastion-scan}"
zap_image="ghcr.io/zaproxy/zaproxy@sha256:9624669db72f54d86c4b46a7064518bd9bf79d8c61a4c31befa9923489f328af"

if [[ ! "$target" =~ ^http://(app|juice):[0-9]+$ ]]; then
  echo "Refusing to scan '$target': only local demo containers (app, juice) are in scope." >&2
  exit 2
fi
case "$mode" in
  baseline) script=zap-baseline.py ;;
  full) script=zap-full-scan.py ;;
  *) echo "mode must be baseline or full" >&2; exit 2 ;;
esac

mkdir -p zap-out
# ZAP runs as its own uid and writes the report here.
chmod 0777 zap-out # NOSONAR
host_dir="$PWD/zap-out"
if command -v cygpath >/dev/null 2>&1; then
  # Git Bash on Windows: stop path mangling and give Docker a Windows path.
  export MSYS_NO_PATHCONV=1
  host_dir="$(cygpath -w "$PWD")\\zap-out"
fi
rules=()
ignore_warn=()
if [[ "$name" != juice-shop ]]; then
  cp .zap/rules.tsv zap-out/rules.tsv
  rules=(-c rules.tsv)
else
  ignore_warn=(-I)  # demo target: report findings without failing
fi
docker run --rm --network "$network" -v "$host_dir:/zap/wrk:rw" "$zap_image" \
  "$script" -t "$target" "${rules[@]}" -r "$name.html" -J "$name.json" "${ignore_warn[@]}"
