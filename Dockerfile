# syntax=docker/dockerfile:1.7
# Hardened image for the notes service. See docs/adr/0004-container-base-image.md.
# Build and runtime stages come from the same vendor so the Python minor version always matches.

FROM cgr.dev/chainguard/python:latest-dev@sha256:50bef4bfe98ea2f3c8c146a04847c8857e0afb1c8803e2047f140f10c028a7ee AS build
WORKDIR /src
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
COPY app/requirements.txt ./requirements.txt
RUN python -m pip install --require-hashes --only-binary=:all: --no-compile --target /home/nonroot/deps -r requirements.txt
COPY app/__init__.py app/main.py /home/nonroot/out/app/

FROM cgr.dev/chainguard/python:latest@sha256:6a467605cd347cb7af8404af3648d01c2b39a967c342b70bbd5ef39dd0b74f5c AS final
LABEL org.opencontainers.image.source="https://github.com/siiick-brain/Bastion-Pipeline" \
      org.opencontainers.image.description="Bastion Pipeline notes service" \
      org.opencontainers.image.licenses="MIT"
ENV PYTHONPATH=/deps PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
COPY --from=build --chown=0:0 --chmod=0755 /home/nonroot/deps /deps
COPY --from=build --chown=0:0 --chmod=0755 /home/nonroot/out/app /srv/app
USER 65532:65532
EXPOSE 8000
ENTRYPOINT ["/usr/bin/python", "-m", "uvicorn", "app.main:app"]
CMD ["--host", "0.0.0.0", "--port", "8000", "--no-server-header"]
