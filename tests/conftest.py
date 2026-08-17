"""Test configuration for sonification.

Audio rendering here is not pure Python: turning a chord sequence into a WAV
goes through the ``fluidsynth`` binary and needs a SoundFont file on disk.
Neither is present on a stock CI runner, so tests that need them are marked
``requires_audio_render`` and **deselected** (not skipped) when unavailable.

Deselect rather than skip is the deliberate ecosystem convention: a skip
reports a test that "ran" and stayed permanently yellow, which trains everyone
to ignore it. A deselect states plainly that the test was never applicable to
this environment, while the same test still runs for real wherever fluidsynth
and a SoundFont exist.

The same treatment covers ``requires_repo_checkout``: the tests that assert
things about ``.github/workflows/ci.yml`` are meaningful in a git checkout and
meaningless in an unpacked sdist, which ships ``tests/`` but no ``.github/``.
CI always runs from a checkout, so those guards stay hard there.
"""

import os
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _audio_render_available() -> bool:
    """Whether a real chords-to-WAV render can run in this environment."""
    if shutil.which("fluidsynth") is None:
        return False
    try:
        from tonal import DFLT_SOUNDFONT
    except Exception:
        return False
    return bool(DFLT_SOUNDFONT) and os.path.exists(DFLT_SOUNDFONT)


def _repo_checkout_available() -> bool:
    """Whether the repo's CI workflow file is present to be inspected."""
    return (REPO_ROOT / ".github" / "workflows" / "ci.yml").is_file()


# marker name -> predicate saying the marked tests are applicable here
_AVAILABILITY = {
    "requires_audio_render": _audio_render_available,
    "requires_repo_checkout": _repo_checkout_available,
}


def pytest_collection_modifyitems(config, items):
    """Deselect tests whose environment prerequisites are absent."""
    unavailable = {
        marker for marker, available in _AVAILABILITY.items() if not available()
    }
    if not unavailable:
        return

    selected, deselected = [], []
    for item in items:
        if any(item.get_closest_marker(marker) for marker in unavailable):
            deselected.append(item)
        else:
            selected.append(item)

    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = selected
