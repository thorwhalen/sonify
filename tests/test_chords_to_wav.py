"""Tests for the chords-to-audio path this package re-exports.

Two different things are covered here, deliberately kept apart:

* the *import contract* between ``tonal`` and ``sonification``, which is pure
  and runs everywhere;
* the *real render*, which needs the ``fluidsynth`` binary and a SoundFont and
  is deselected by ``conftest.py`` when either is missing.
"""

import wave

import pytest


def test_midi_to_wav_is_reachable_via_sonification_converters():
    """``tonal.chords.chords_to_wav`` imports this at call time -- keep it live.

    ``chords_to_wav`` does ``from sonification.converters import midi_to_wav``
    inside the function body, so a rename or a dropped star-import here breaks
    ``tonal`` at runtime rather than at import time, where nothing would notice
    until someone actually rendered audio.
    """
    from sonification.converters import midi_to_wav

    assert callable(midi_to_wav)


@pytest.mark.requires_audio_render
@pytest.mark.xfail(
    strict=True,
    reason=(
        "Upstream bug in tonal.converters.midi_to_wav (thorwhalen/tonal#4): it "
        "invokes fluidsynth with the output options placed AFTER the positional "
        "soundfont/MIDI arguments, which fluidsynth 2.x rejects. fluidsynth "
        "still exits 0, and midi_to_wav passes no check=True and never asserts "
        "the file appeared, so it returns a path to a WAV that was never "
        "written. Cannot be fixed from sonification -- midi_to_wav lives in "
        "tonal and is only star-imported here. strict=True on purpose: once "
        "tonal is fixed this test XPASSes and fails, telling you to drop this "
        "marker."
    ),
)
def test_chords_to_wav_roundtrip(tmp_path, monkeypatch):
    """A short chord sequence renders to a non-empty, readable WAV file."""
    from sonification import chords_to_wav

    monkeypatch.chdir(tmp_path)

    wav_name = chords_to_wav([("Cmaj7", 120), ("G7", 120)], name="test_output")

    wav_path = tmp_path / wav_name
    assert wav_path.exists(), f"expected {wav_name} to be written"
    assert wav_path.stat().st_size > 0, "rendered WAV is empty"

    # The intermediate MIDI is written alongside it.
    assert (tmp_path / "test_output.mid").exists()

    with wave.open(str(wav_path)) as wav_file:
        assert wav_file.getnframes() > 0, "rendered WAV has no audio frames"
        assert wav_file.getframerate() > 0
