"""Smoke tests: importing the package and its modules shouldn't blow up.

These are deliberately dependency-free so they run everywhere. They are also
the tests that would have caught the failure that kept CI red since Aug 2025:
a module inside the package importing something the package never declared.
"""

import importlib
import pkgutil

import pytest


def test_import():
    import sonification  # noqa: F401


@pytest.mark.parametrize(
    "module_name",
    ["sonification.chords", "sonification.converters", "sonification.util"],
)
def test_submodules_import(module_name):
    """Every shipped submodule must import using only declared dependencies."""
    assert importlib.import_module(module_name) is not None


def test_no_shipped_module_needs_undeclared_deps():
    """Nothing directly under the package may need an undeclared dependency.

    ``scrap/`` is excluded on purpose: it is the parking spot for code that is
    kept for reference but is not part of the installed surface, and it is
    excluded from linting, testing and docs everywhere else too.
    """
    import sonification

    failures = {}
    for module_info in pkgutil.iter_modules(sonification.__path__):
        if module_info.name == "scrap":
            continue
        try:
            importlib.import_module(f"sonification.{module_info.name}")
        except Exception as exc:  # noqa: BLE001 - we want to report any failure
            failures[module_info.name] = f"{type(exc).__name__}: {exc}"

    assert not failures, f"modules failed to import: {failures}"


def test_facade_reexports_resolve_to_tonal():
    """The three re-exported names are the package's whole public contract."""
    import sonification

    expected_homes = {
        "chords_to_wav": "tonal.chords",
        "register_chord_render": "tonal.chords",
        "convert": "tonal.converters",
    }
    for name, home in expected_homes.items():
        obj = getattr(sonification, name, None)
        assert obj is not None, f"sonification.{name} is missing"
        assert callable(obj), f"sonification.{name} is not callable"
        assert obj.__module__ == home, f"sonification.{name} moved off {home}"
