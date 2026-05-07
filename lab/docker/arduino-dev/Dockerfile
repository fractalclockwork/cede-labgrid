# syntax=docker/dockerfile:1
ARG BASE_IMAGE=debian:bookworm-slim
FROM ${BASE_IMAGE}

ARG ARDUINO_CLI_VERSION=1.0.4
LABEL org.opencontainers.image.title="cede-arduino-dev"
LABEL cede.arduino-cli-version="${ARDUINO_CLI_VERSION}"

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    avr-libc \
    binutils-avr \
    gcc-avr \
    avrdude \
    ca-certificates \
    curl \
    git \
    python3 \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL \
    "https://github.com/arduino/arduino-cli/releases/download/v${ARDUINO_CLI_VERSION}/arduino-cli_${ARDUINO_CLI_VERSION}_Linux_64bit.tar.gz" \
    | tar xz -C /usr/local/bin arduino-cli \
    && chmod +x /usr/local/bin/arduino-cli

RUN arduino-cli config init \
    && arduino-cli core update-index \
    && arduino-cli core install arduino:avr

WORKDIR /workspace
