#!/usr/bin/env bash
# Build the platform wheels, smoke-test the one for this machine, and upload them.
#
# Usage: scripts/release.sh [--dry-run] [--testpypi] [--skip-fetch]
# Uploads with twine; set TWINE_USERNAME=__token__ and TWINE_PASSWORD=<PyPI API token>.
set -euo pipefail
cd "$(dirname "$0")/.."

dry_run=0; repository=pypi; fetch=1
for arg in "$@"; do
  case "$arg" in
    --dry-run) dry_run=1 ;;
    --testpypi) repository=testpypi ;;
    --skip-fetch) fetch=0 ;;
    *) echo "unknown argument $arg" >&2; exit 2 ;;
  esac
done

python=${PYTHON:-python3}
"$python" -m pip install --quiet --upgrade build wheel twine

[ "$fetch" = 1 ] && bash scripts/fetch-natives.sh natives
"$python" scripts/build_wheels.py
"$python" -m twine check --strict dist/*.whl

venv="$(mktemp -d)"
trap 'rm -rf "$venv"' EXIT
"$python" -m venv "$venv"
"$venv/bin/python" -m pip install --quiet --no-index --find-links dist edifabric-x12
"$venv/bin/python" scripts/smoke_test.py

if [ "$dry_run" = 1 ]; then
  echo "Dry run: built $(ls dist/*.whl | wc -l) wheels, nothing uploaded."
  exit 0
fi
"$python" -m twine upload --repository "$repository" dist/*.whl
