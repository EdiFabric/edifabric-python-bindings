#!/usr/bin/env bash
# Download the ediFabric Native X12 library for every platform into <dest>/<rid>/.
#
# Usage: scripts/fetch-natives.sh [dest]        (default dest: natives)
# EDIFABRIC_DOWNLOAD_URL overrides the download location.
set -euo pipefail

base="${EDIFABRIC_DOWNLOAD_URL:-https://www.edifabric.com/download}"
dest="${1:-natives}"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

for rid in win-x64 linux-x64 linux-arm64 osx-arm64; do
  echo "Downloading $rid"
  curl -fsSL "$base/edifabric-x12-tools-$rid.zip" -o "$work/$rid.zip"
  rm -rf "${work:?}/$rid" "$dest/$rid"
  unzip -q "$work/$rid.zip" -d "$work/$rid"
  mkdir -p "$dest/$rid"
  # Keep the library and its signature; the zip's README.txt is not redistributed.
  find "$work/$rid" -type f -name 'edifabric-x12-tools.*' -exec cp {} "$dest/$rid/" \;
  ls -l "$dest/$rid"
done
