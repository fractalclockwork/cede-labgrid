# syntax=docker/dockerfile:1
ARG BASE_IMAGE=python:3.12-slim-bookworm
FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="cede-orchestration-dev"

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    pyserial \
    pytest \
    pyyaml \
    jsonschema

WORKDIR /workspace
