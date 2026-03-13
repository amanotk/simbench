FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive

ARG FLAP_VERSION=1.2.16
ARG CATCH2_REF=v3.13.0
ARG MDSPAN_REF=mdspan-0.6.0
ARG XTL_REF=0.8.2
ARG XSIMD_REF=14.0.0
ARG XTENSOR_REF=0.27.1
ARG TOML11_REF=v4.4.0
ARG FORTRAN_STDLIB_REF=v0.6.1
ARG TOML_F_REF=v0.4.2
ARG FACE_REV=1455c549ae0c1ead96961ca61a73131d8176b6a4
ARG PENF_REV=a519e6cb58873efa85a81b4cf0a547870f510629

# Keep numerical performance reproducible-ish by default.
ENV OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    VECLIB_MAXIMUM_THREADS=1 \
    NUMEXPR_NUM_THREADS=1

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    bash ca-certificates coreutils curl git jq time wget unzip zip \
    make cmake ninja-build pkg-config \
    g++ gfortran clang-format \
    libfftw3-dev libopenblas-dev liblapack-dev \
    openmpi-bin libopenmpi-dev \
    libcxxopts-dev \
    nodejs npm \
    python3 python3-pip python3-venv \
    python3-numpy python3-scipy python3-matplotlib python3-pytest python3-toml \
  && python3 -m pip install --break-system-packages --no-cache-dir fypp \
  && rm -rf /var/lib/apt/lists/* \
  && mkdir -p /tmp/catch2-src \
  && curl -LsSf "https://api.github.com/repos/catchorg/Catch2/tarball/${CATCH2_REF}" \
    | tar -xz --strip-components=1 -C /tmp/catch2-src \
  && cmake -S /tmp/catch2-src -B /tmp/catch2-build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr/local -DBUILD_TESTING=OFF \
  && cmake --build /tmp/catch2-build -j"$(nproc)" \
  && cmake --install /tmp/catch2-build \
  && rm -rf /tmp/catch2-src /tmp/catch2-build \
  && mkdir -p /tmp/mdspan-src \
  && curl -LsSf "https://api.github.com/repos/kokkos/mdspan/tarball/${MDSPAN_REF}" \
    | tar -xz --strip-components=1 -C /tmp/mdspan-src \
  && cp -a /tmp/mdspan-src/include/. /usr/local/include/ \
  && rm -rf /tmp/mdspan-src \
  && mkdir -p /tmp/xtl-src \
  && curl -LsSf "https://api.github.com/repos/xtensor-stack/xtl/tarball/refs/tags/${XTL_REF}" \
    | tar -xz --strip-components=1 -C /tmp/xtl-src \
  && cp -a /tmp/xtl-src/include/. /usr/local/include/ \
  && rm -rf /tmp/xtl-src \
  && mkdir -p /tmp/xsimd-src \
  && curl -LsSf "https://api.github.com/repos/xtensor-stack/xsimd/tarball/refs/tags/${XSIMD_REF}" \
    | tar -xz --strip-components=1 -C /tmp/xsimd-src \
  && cp -a /tmp/xsimd-src/include/. /usr/local/include/ \
  && rm -rf /tmp/xsimd-src \
  && mkdir -p /tmp/xtensor-src \
  && curl -LsSf "https://api.github.com/repos/xtensor-stack/xtensor/tarball/refs/tags/${XTENSOR_REF}" \
    | tar -xz --strip-components=1 -C /tmp/xtensor-src \
  && cp -a /tmp/xtensor-src/include/. /usr/local/include/ \
  && rm -rf /tmp/xtensor-src \
  && mkdir -p /tmp/toml11-src \
  && curl -LsSf "https://api.github.com/repos/ToruNiina/toml11/tarball/refs/tags/${TOML11_REF}" \
    | tar -xz --strip-components=1 -C /tmp/toml11-src \
  && cmake -S /tmp/toml11-src -B /tmp/toml11-build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr/local \
  && cmake --build /tmp/toml11-build -j"$(nproc)" \
  && cmake --install /tmp/toml11-build \
  && rm -rf /tmp/toml11-src /tmp/toml11-build \
  && mkdir -p /tmp/stdlib-src \
  && curl -LsSf "https://api.github.com/repos/fortran-lang/stdlib/tarball/refs/tags/${FORTRAN_STDLIB_REF}" \
    | tar -xz --strip-components=1 -C /tmp/stdlib-src \
  && cmake -S /tmp/stdlib-src -B /tmp/stdlib-build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr/local -DCMAKE_MAXIMUM_RANK=4 -DBUILD_TESTING=OFF \
  && cmake --build /tmp/stdlib-build -j"$(nproc)" \
  && cmake --install /tmp/stdlib-build \
  && rm -rf /tmp/stdlib-src /tmp/stdlib-build \
  && mkdir -p /tmp/toml-f-src \
  && curl -LsSf "https://api.github.com/repos/toml-f/toml-f/tarball/refs/tags/${TOML_F_REF}" \
    | tar -xz --strip-components=1 -C /tmp/toml-f-src \
  && cmake -S /tmp/toml-f-src -B /tmp/toml-f-build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr/local -DBUILD_TESTING=OFF \
  && cmake --build /tmp/toml-f-build -j"$(nproc)" \
  && cmake --install /tmp/toml-f-build \
  && rm -rf /tmp/toml-f-src /tmp/toml-f-build \
  && mkdir -p "/tmp/FLAP-v${FLAP_VERSION}" \
  && curl -LsSf "https://api.github.com/repos/szaghi/FLAP/tarball/refs/tags/v${FLAP_VERSION}" \
    | tar -xz --strip-components=1 -C "/tmp/FLAP-v${FLAP_VERSION}" \
  && mkdir -p "/tmp/FLAP-v${FLAP_VERSION}/src/third_party/FACE" \
  && curl -LsSf "https://api.github.com/repos/szaghi/FACE/tarball/${FACE_REV}" \
    | tar -xz --strip-components=1 -C "/tmp/FLAP-v${FLAP_VERSION}/src/third_party/FACE" \
  && mkdir -p "/tmp/FLAP-v${FLAP_VERSION}/src/third_party/PENF" \
  && curl -LsSf "https://api.github.com/repos/szaghi/PENF/tarball/${PENF_REV}" \
    | tar -xz --strip-components=1 -C "/tmp/FLAP-v${FLAP_VERSION}/src/third_party/PENF" \
  && cmake -S "/tmp/FLAP-v${FLAP_VERSION}" -B /tmp/flap-build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr/local \
  && cmake --build /tmp/flap-build -j"$(nproc)" \
  && cmake --install /tmp/flap-build \
  && rm -rf /tmp/flap-build "/tmp/FLAP-v${FLAP_VERSION}" \
  && curl -LsSf https://astral.sh/uv/install.sh | env UV_UNMANAGED_INSTALL=/usr/local/bin sh \
  && uv pip install --system --break-system-packages --no-cache ruff fprettify \
  && npm install -g opencode-ai @anthropic-ai/claude-code @openai/codex @github/copilot \
  && uv --version

WORKDIR /work
