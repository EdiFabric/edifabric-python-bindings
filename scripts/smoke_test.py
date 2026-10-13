"""Load the bundled native library from an installed edifabric-x12 wheel and print its version."""

import os
import sys
from pathlib import Path

os.chdir(Path.home())  # keep a library in the repository root from being picked up instead
sys.path = [p for p in sys.path if Path(p or ".").resolve() != Path(__file__).resolve().parent.parent]

import edifabric_x12 as ef  # noqa: E402

library = ef.load_library()
loaded = Path(library._name).resolve()
package = Path(ef.__file__).resolve().parent
if loaded.parent != package:
    raise SystemExit(f"expected the bundled library in {package}, loaded {loaded}")
print(f"loaded {loaded}")
print(f"get_app_version -> {ef.get_app_version()}")
