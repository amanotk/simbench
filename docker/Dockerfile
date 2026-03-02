FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive

# Keep numerical performance reproducible-ish by default.
ENV OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    VECLIB_MAXIMUM_THREADS=1 \
    NUMEXPR_NUM_THREADS=1

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    bash ca-certificates coreutils curl git jq time \
    make cmake ninja-build pkg-config \
    g++ gfortran \
    nodejs npm \
    python3 python3-pip python3-venv \
    python3-numpy python3-scipy python3-pytest \
  && npm install -g opencode-ai @anthropic-ai/claude-code @openai/codex @github/copilot \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /work
