from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPTS_DIR = Path(__file__).parent.parent

# Das Skript traegt bewusst einen Bindestrich im Dateinamen ("seed-opencloud-demo.py", siehe
# specs/features/0009-local-opencloud-demo-stack.md) - kein gueltiger Python-Modulname, daher per
# Pfad statt per "import" geladen. Der Loader liegt hier in conftest.py statt in einem Testmodul,
# weil Fixtures aus einem Testmodul modul-lokal sind und mehrere Testmodule dasselbe Skript
# brauchen.
_SEED_SCRIPT_PATH = _SCRIPTS_DIR / "seed-opencloud-demo.py"


def _load_module(module_name: str, script_path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def seed_module() -> ModuleType:
    return _load_module("seed_opencloud_demo", _SEED_SCRIPT_PATH)
