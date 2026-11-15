#!/usr/bin/env bash
# Creates per-setup secrets (admin password and agent SSH key pair) and starts Jenkins.
# Secrets live in infra/jenkins/secrets/ which is gitignored. Nothing secret is printed.
set -euo pipefail
cd "$(dirname "$0")"
umask 077
mkdir -p secrets
if [[ ! -f secrets/admin_password ]]; then
  # No trailing newline: CasC reads the file verbatim, so a newline would become part of the password.
  head -c 24 /dev/urandom | base64 | tr -d '/+=\r\n' > secrets/admin_password
fi
[[ -f secrets/agent_ssh_key ]] || ssh-keygen -q -t ed25519 -N '' -C bastion-jenkins-agent -f secrets/agent_ssh_key
# Pinned agent host key: the controller verifies it with known_hosts (no trust on first use).
[[ -f secrets/agent_host_key ]] || ssh-keygen -q -t ed25519 -N '' -C bastion-agent-host -f secrets/agent_host_key
printf 'agent %s\n' "$(cut -d' ' -f1,2 secrets/agent_host_key.pub)" > secrets/known_hosts
docker compose up -d --build --wait
echo "Jenkins: http://127.0.0.1:${JENKINS_PORT:-8080}/ (user admin, password in infra/jenkins/secrets/admin_password)"
