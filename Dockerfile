# syntax=docker/dockerfile:1.7

FROM python:3.12.7-slim AS build
WORKDIR /app

COPY app/requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip && \
    python -m pip install --no-cache-dir -r requirements.txt

FROM gcr.io/distroless/python3-debian12:nonroot AS final
WORKDIR /app

COPY --from=build /usr/local /usr/local
COPY app/ /app/
USER nonroot:nonroot

EXPOSE 8000
CMD ["-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
