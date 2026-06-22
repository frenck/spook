FROM mcr.microsoft.com/devcontainers/python:3.14

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install dependencies needed by Home Assistant or its dependencies
RUN \
    apt-get update \
    && DEBIAN_FRONTEND=noninteractive \
        apt-get install -y --no-install-recommends \
            build-essential \
            clang \
            cmake \
            ffmpeg \
            gcc \
            git \
            libavcodec-dev \
            libavdevice-dev \
            libavfilter-dev \
            libavformat-dev \
            libavutil-dev \
            libffi-dev \
            liblzma-dev \
            libpcap-dev \
            libssl-dev \
            libswresample-dev \
            libswscale-dev \
            libturbojpeg0 \
            libudev-dev \
            libxml2 \
            libxmlsec1-dev \
            libyaml-dev \
            lzma-dev \
            uuid-dev \
            webp \
            xz-utils \
            zlib1g-dev
