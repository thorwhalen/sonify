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
"""

import os
import shutil


def _audio_render_available() -> bool:
    """Whether a real chords-to-WAV render can run in this environment."""
    if shutil.which("fluidsynth") is None:
        return False
    try:
        from tonal import DFLT_SOUNDFONT
    except Exception:
        return False
    return bool(DFLT_SOUNDFONT) and os.path.exists(DFLT_SOUNDFONT)


def pytest_collection_modifyitems(config, items):
    """Deselect audio-render tests when fluidsynth or a SoundFont is missing."""
    if _audio_render_available():
        return

    selected, deselected = [], []
    for item in items:
        if item.get_closest_marker("requires_audio_render"):
            deselected.append(item)
        else:
            selected.append(item)

    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = selected
