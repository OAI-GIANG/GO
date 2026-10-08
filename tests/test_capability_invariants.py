"""Capability-transfer invariants.

Enforces that HG stays provider-agnostic and contains no hidden model/vendor
lock (D16: Deep independence) and no parallel "deep" subsystem namespace (D18).
"""
from __future__ import annotations

import pathlib

RUNTIME = pathlib.Path(__file__).resolve().parents[1] / "runtime"
VENDOR_MARKERS = ("deepseek", "deep-brai", "deepbrain")


def _runtime_sources():
    for path in RUNTIME.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        yield path


def test_runtime_has_no_vendor_locked_provider_default():
    hits = [
        str(p.relative_to(RUNTIME))
        for p in _runtime_sources()
        if any(marker in p.read_text(encoding="utf-8-sig").lower() for marker in VENDOR_MARKERS)
    ]
    assert hits == [], f"vendor-locked references in runtime: {hits}"


def test_no_parallel_deep_subsystem_namespace():
    names = sorted(p.name for p in RUNTIME.rglob("*") if "deep" in p.name.lower())
    assert names == [], f"unexpected 'deep' module/file namespace: {names}"
