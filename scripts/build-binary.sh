#!/usr/bin/env bash
# Build a standalone single-file `keep` binary for the current platform with PyInstaller.
#
# Output: dist/keep-linux-<arch> and dist/keep-linux-<arch>.sha256
# Requires: uv (https://docs.astral.sh/uv/), binutils (objdump) for PyInstaller.
set -euo pipefail

cd "$(dirname "$0")/.."

case "$(uname -m)" in
  x86_64) ARCH=amd64 ;;
  aarch64 | arm64) ARCH=arm64 ;;
  armv7l) ARCH=armv7 ;;
  *) echo "unsupported architecture: $(uname -m)" >&2; exit 1 ;;
esac
OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
NAME="keep-${OS}-${ARCH}"

uv sync --frozen --group build
rm -rf build dist
uv run --frozen pyinstaller \
  --onefile --clean --noconfirm \
  --name keep \
  --copy-metadata gpsoauth \
  --copy-metadata gkeepapi \
  --specpath build \
  src/keep_cli/__main__.py

mv "dist/keep" "dist/${NAME}"
(cd dist && sha256sum "${NAME}" > "${NAME}.sha256")

echo "built dist/${NAME}"
"dist/${NAME}" --version
"dist/${NAME}" --help > /dev/null
