# DDTM-QAS Experiment Runner
# Ubuntu 24.04 with Go 1.25, Python 3.12
# Note: Foundry is NOT included (GitHub download too slow from this network).
#       Use host Foundry or the ghcr.io/foundry-rs/foundry image for contract tests.
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=Asia/Shanghai \
    PATH=/usr/local/go/bin:${PATH} \
    GOPATH=/root/go \
    GOTOOLCHAIN=local

# ------------------------------------------------------------------
# Layer 1: System dependencies
# ------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    jq \
    ca-certificates \
    pkg-config \
    libssl-dev \
    clang \
    cmake \
    python3.12 \
    python3.12-venv \
    python3.12-dev \
    python3-pip \
    bash \
    && rm -rf /var/lib/apt/lists/* \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1 \
    && update-alternatives --install /usr/bin/python python /usr/bin/python3.12 1

# ------------------------------------------------------------------
# Layer 2: Go 1.25.6
# ------------------------------------------------------------------
ARG GO_VERSION=1.25.7
RUN ARCH=$(uname -m | sed 's/x86_64/amd64/;s/aarch64/arm64/') && \
    curl -fsSL "https://go.dev/dl/go${GO_VERSION}.linux-${ARCH}.tar.gz" -o /tmp/go.tar.gz && \
    rm -rf /usr/local/go && \
    tar -C /usr/local -xzf /tmp/go.tar.gz && \
    rm /tmp/go.tar.gz && \
    go version

# ------------------------------------------------------------------
# Layer 3: Python packages (install from project requirements)
# ------------------------------------------------------------------
COPY experiments/requirements.txt /tmp/requirements.txt
RUN python3 -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt && \
    rm /tmp/requirements.txt

ENV PATH=/opt/venv/bin:${PATH}

# ------------------------------------------------------------------
# Runtime
# ------------------------------------------------------------------
WORKDIR /workspace
CMD ["/bin/bash"]
