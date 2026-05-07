# syntax=docker/dockerfile:1
ARG BASE_IMAGE=debian:bookworm-slim
FROM ${BASE_IMAGE}

ARG PICO_SDK_VERSION=2.1.1
LABEL org.opencontainers.image.title="cede-pico-dev"
LABEL cede.pico-sdk-version="${PICO_SDK_VERSION}"

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    ninja-build \
    gcc-arm-none-eabi \
    libnewlib-arm-none-eabi \
    libstdc++-arm-none-eabi-newlib \
    python3 \
    python3-venv \
    git \
    ca-certificates \
    pkg-config \
    libusb-1.0-0 \
    libudev-dev \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 --branch "${PICO_SDK_VERSION}" --recursive \
    https://github.com/raspberrypi/pico-sdk.git /opt/pico-sdk

ENV PICO_SDK_PATH=/opt/pico-sdk

# picotool (optional but useful for UF2 info / reboot)
RUN git clone --depth 1 https://github.com/raspberrypi/picotool.git /tmp/picotool \
    && cd /tmp/picotool \
    && mkdir build && cd build \
    && cmake -GNinja .. \
    && ninja \
    && cp picotool /usr/local/bin/picotool \
    && rm -rf /tmp/picotool

WORKDIR /workspace
