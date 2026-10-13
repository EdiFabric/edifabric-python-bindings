"""
Build one platform wheel per ediFabric Native library in natives/<rid>/.

Each wheel contains the edifabric_x12 package plus the native library for one
platform, tagged py3-none-<platform> so pip picks the right one.

Usage:
    python scripts/build_wheels.py              # every platform found in natives/
    python scripts/build_wheels.py --rid win-x64
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "edifabric_x12"
NATIVES = ROOT / "natives"
DIST = ROOT / "dist"

# rid -> (library file, wheel platform tag). The tags match the native builds:
# Linux needs glibc 2.34 or later, macOS needs 12.0 or later.
PLATFORMS = {
    "win-x64": ("edifabric-x12-tools.dll", "win_amd64"),
    "linux-x64": ("edifabric-x12-tools.so", "manylinux_2_34_x86_64"),
    "linux-arm64": ("edifabric-x12-tools.so", "manylinux_2_34_aarch64"),
    "osx-arm64": ("edifabric-x12-tools.dylib", "macosx_12_0_arm64"),
}
LIBRARY_FILES = {name for name, _ in PLATFORMS.values()}


def run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def clean_package() -> None:
    for name in LIBRARY_FILES:
        (PACKAGE / name).unlink(missing_ok=True)
    shutil.rmtree(ROOT / "build", ignore_errors=True)
    for info in ROOT.glob("*.egg-info"):
        shutil.rmtree(info, ignore_errors=True)


def build(rid: str) -> Path:
    library, tag = PLATFORMS[rid]
    source = NATIVES / rid / library
    if not source.is_file():
        raise SystemExit(f"{source} is missing. Run scripts/fetch-natives first.")

    clean_package()
    shutil.copy2(source, PACKAGE / library)
    try:
        with tempfile.TemporaryDirectory() as out:
            run(sys.executable, "-m", "build", "--wheel", "--outdir", out)
            (wheel,) = Path(out).glob("*.whl")
            run(sys.executable, "-m", "wheel", "tags", "--python-tag", "py3", "--abi-tag", "none",
                "--platform-tag", tag, "--remove", str(wheel))
            (tagged,) = Path(out).glob("*.whl")
            DIST.mkdir(exist_ok=True)
            target = DIST / tagged.name
            shutil.move(str(tagged), target)
    finally:
        clean_package()

    with zipfile.ZipFile(target) as archive:
        bundled = [n for n in archive.namelist() if Path(n).name in LIBRARY_FILES]
    if bundled != [f"edifabric_x12/{library}"]:
        raise SystemExit(f"{target.name} has unexpected native files: {bundled}")
    print(f"built {target.relative_to(ROOT)}")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rid", choices=sorted(PLATFORMS), action="append", help="platform to build (repeatable)")
    args = parser.parse_args()

    rids = args.rid or [rid for rid in PLATFORMS if (NATIVES / rid).is_dir()]
    if not rids:
        raise SystemExit("natives/ is empty. Run scripts/fetch-natives first.")
    for wheel in DIST.glob("*.whl"):
        wheel.unlink()
    for rid in rids:
        build(rid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
