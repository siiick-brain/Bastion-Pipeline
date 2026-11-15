# syntax=docker/dockerfile:1.7
# SoftHSM2 signing environment for update packages. SoftHSM is a software token: it
# demonstrates the PKCS#11 interface, not hardware key protection (docs/pkcs11-softhsm.md).
FROM debian:trixie-slim@sha256:a72b4433de1cf7d6bae0c4cee74d0547f58601a643b3375f070c51600d63b6b2
# Package versions follow the pinned base image digest; Dependabot bumps the digest.
# hadolint ignore=DL3008
RUN apt-get update \
 && apt-get install -y --no-install-recommends softhsm2 opensc python3 python3-venv ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --uid 10001 --create-home signer \
 && install -d -o 10001 -g 10001 -m 0700 /state
COPY requirements.txt /tmp/requirements.txt
RUN python3 -m venv /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir --require-hashes --only-binary=:all: -r /tmp/requirements.txt
ENV PATH=/opt/venv/bin:$PATH \
    SOFTHSM2_CONF=/home/signer/softhsm2.conf \
    PKCS11_MODULE=/usr/lib/softhsm/libsofthsm2.so \
    PYTHONDONTWRITEBYTECODE=1
USER 10001:10001
WORKDIR /work
COPY --chown=10001:10001 . /work
ENTRYPOINT ["/work/run-demo.sh"]
