from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

# Das Skript heisst bewusst "seed-opencloud-demo.py" (Bindestrich, siehe
# specs/features/0009-local-opencloud-demo-stack.md) - kein gueltiger Python-Modulname, daher per
# Pfad statt per "import" geladen.
_SCRIPT_PATH = Path(__file__).parent.parent / "seed-opencloud-demo.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("seed_opencloud_demo", _SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def seed_module() -> ModuleType:
    return _load_module()
