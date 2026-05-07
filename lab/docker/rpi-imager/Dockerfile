# Host-side Raspberry Pi OS imaging (rpi-imager CLI, loop mounts). Run with --privileged
# and bind-mount /dev when flashing SD cards (see lab/docker/Makefile shell-rpi-imager).
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        coreutils \
        mount \
        parted \
        python3 \
        python3-jsonschema \
        python3-yaml \
        rpi-imager \
        util-linux \
        xz-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
