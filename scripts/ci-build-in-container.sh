#!/usr/bin/env bash
# Runs inside a python:3.12-slim-bullseye container in CI (any architecture): prepares the
# toolchain and then calls scripts/build-binary.sh. Not meant for local use.
set -euo pipefail
cd "$(dirname "$0")/.."

# bullseye is end-of-life: its packages live on archive.debian.org now, and the security
# suite has not been archived, so use main + updates only.
printf '%s\n' \
  "deb http://archive.debian.org/debian bullseye main" \
  "deb http://archive.debian.org/debian bullseye-updates main" \
  > /etc/apt/sources.list
rm -rf /etc/apt/sources.list.d/*
apt-get -o Acquire::Check-Valid-Until=false update

archived_version() {
  # First (highest) version available from the configured sources.
  apt-cache madison "$1" | awk -F'|' 'NR == 1 { gsub(/ /, "", $2); print $2 }'
}

packages=(binutils) # PyInstaller needs objdump.
pins=()
if [ "$(uname -m)" = "armv7l" ]; then
  # pyinstaller and pycryptodomex have no armv7l wheels and are compiled from source.
  # The image ships libc6/zlib1g from bullseye-security, but the -dev packages require
  # exactly matching library versions, so pin both to the archived versions (a downgrade
  # within the same upstream release).
  packages+=(gcc libc6-dev zlib1g-dev)
  for pkg in libc6 zlib1g; do
    pins+=("${pkg}=$(archived_version "$pkg")")
  done
fi
apt-get install -y --no-install-recommends --allow-downgrades "${pins[@]}" "${packages[@]}"

pip install --no-cache-dir uv
./scripts/build-binary.sh
