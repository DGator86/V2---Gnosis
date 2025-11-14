"""Gnosis / DHPE Engine Package."""

import importlib
from types import ModuleType
from typing import Dict

__all__ = ["dhpe", "liquidity", "orderflow"]

_CACHE: Dict[str, ModuleType] = {}


def __getattr__(name: str) -> ModuleType:
    if name in __all__:
        module = _CACHE.get(name)
        if module is None:
            module = importlib.import_module(f"{__name__}.{name}")
            _CACHE[name] = module
        return module
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
