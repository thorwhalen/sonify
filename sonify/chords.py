"""Tools for chords and chord progressions."""

from mido import MidiFile, MidiTrack, Message
import subprocess
from typing import Sequence, Tuple, Callable, Mapping, Dict
import os
import re
from config2py import process_path
from sonify.util import get_config

Note = int
Notes = Sequence[Note]
Chord = str
ChordTimed = Tuple[Chord, Notes]
ChordSequence = Sequence[ChordTimed]
# ChordDefinitions = Mapping[Chord, Notes]
ChordDefinitions = Callable[[Chord], Notes]
ChordRenderer = Callable[[Notes, MidiTrack, int], None]

DFLT_OUTPUT_NAME = 'audio_output'
DFLT_MIDI_OUTPUT = f"{DFLT_OUTPUT_NAME}.mid"
DFLT_WAV_OUTPUT = f"{DFLT_OUTPUT_NAME}.wav"
DFLT_SOUNDFONT = process_path(
    get_config('SONIFY_DFLT_SOUNDFONT_PATH'),
)

DFLT_CHORD_SEQUENCE = [
    ('Bdim', 120),
    ('Em11', 120),
    ('Amin9', 120),
    ('Dm7', 120),
    'G7',
    'Cmaj7',
]



# Define root notes to MIDI note numbers
root_notes: Dict[str, int] = {
    'C': 60,
    'C#': 61,
    'Db': 61,
    'D': 62,
    'D#': 63,
    'Eb': 63,
    'E': 64,
    'F': 65,
    'F#': 66,
    'Gb': 66,
    'G': 67,
    'G#': 68,
    'Ab': 68,
    'A': 69,
    'A#': 70,
    'Bb': 70,
    'B': 71,
}

# Define quality and extension intervals
quality_extensions: Dict[str, Sequence[int]] = {
    'maj': [0, 4, 7],  # Major triad
    'min': [0, 3, 7],  # Minor triad
    'dim': [0, 3, 6],  # Diminished triad
    'aug': [0, 4, 8],  # Augmented triad
    '7': [0, 4, 7, 10],  # Dominant 7th
    'maj7': [0, 4, 7, 11],  # Major 7th
    'min7': [0, 3, 7, 10],  # Minor 7th
    'minmaj7': [0, 3, 7, 11],  # Minor major 7th
    'dim7': [0, 3, 6, 9],  # Diminished 7th
    'hdim7': [0, 3, 6, 10],  # Half-diminished 7th
    'aug7': [0, 4, 8, 10],  # Augmented 7th
    '6': [0, 4, 7, 9],  # Major 6th
    'min6': [0, 3, 7, 9],  # Minor 6th
    '9': [0, 4, 7, 10, 14],  # Dominant 9th
    'maj9': [0, 4, 7, 11, 14],  # Major 9th
    'min9': [0, 3, 7, 10, 14],  # Minor 9th
    '11': [0, 4, 7, 10, 14, 17],  # Dominant 11th
    'maj11': [0, 4, 7, 11, 14, 17],  # Major 11th
    'min11': [0, 3, 7, 10, 14, 17],  # Minor 11th
    '13': [0, 4, 7, 10, 14, 17, 21],  # Dominant 13th
    'maj13': [0, 4, 7, 11, 14, 17, 21],  # Major 13th
    'min13': [0, 3, 7, 10, 14, 17, 21],  # Minor 13th
}

# add aliases
# TODO: Make a framework for user-defined aliases


def add_aliases(quality_extensions):
    for _qe in quality_extensions:
        if _qe.startswith('maj'):
            yield _qe.replace('maj', 'M'), quality_extensions[_qe]
        elif _qe.startswith('min'):
            yield _qe.replace('min', 'm'), quality_extensions[_qe]
        elif _qe.startswith('dim'):
            yield _qe.replace('dim', '°'), quality_extensions[_qe]


quality_extensions.update(dict(add_aliases(quality_extensions)))

# TODO: Change extension definitions to base one, and define chord inversions on top

# chord_pattern = re.compile(r'([A-Ga-g][#b]?)(maj|min|dim|aug)?([0-9]*)')
chord_note_pattern = re.compile(r'([A-Ga-g][#b]?)')


def parse_root(chord: str) -> str:
    match = chord_note_pattern.match(chord)
    if match:
        return match.group(1)
    else:
        raise ValueError(f"Invalid chord: {chord}")


def chord_to_notes(chord: Chord) -> Notes:
    """
    Parse a chord string and return the corresponding sequence of MIDI note numbers.

    :param chord: The chord string (e.g., 'Cmaj7').
    :return: A sequence of MIDI note numbers representing the chord.
    """
    root = parse_root(chord)
    quality_extension = chord[len(root) :]
    root_midi = root_notes.get(root)
    print(root, root_midi, quality_extension)

    if root_midi is None:
        raise ValueError(f"Unknown root note: {root}")

    intervals = quality_extensions.get(quality_extension)

    if intervals is None:
        raise ValueError(f"Unknown quality/extension: {quality_extension}")

    return [root_midi + interval for interval in intervals]


if not os.path.exists(DFLT_SOUNDFONT):
    from warnings import warn

    warn(f"Soundfont not found at {DFLT_SOUNDFONT}")


chord_renders = {}


def register_chord_render(chord_renderer: ChordRenderer, name=None):
    if name is None:
        name = chord_renderer.__name__
    chord_renders[chord_renderer.__name__] = chord_renderer
    return chord_renderer


@register_chord_render
def play_simultaneously(notes: Sequence[int], track: MidiTrack, duration: int):
    for note in notes:
        track.append(Message('note_on', note=note, velocity=64, time=0))
    for note in notes:
        track.append(Message('note_off', note=note, velocity=64, time=duration))


@register_chord_render
def play_arpeggio(notes: Sequence[int], track: MidiTrack, duration: int):
    note_duration = duration // len(notes)
    current_time = 0
    for note in notes:
        track.append(Message('note_on', note=note, velocity=64, time=current_time))
        current_time += note_duration
        track.append(Message('note_off', note=note, velocity=64, time=current_time))


def resolve_chord_render(chord_renderer: ChordRenderer) -> ChordRenderer:
    if isinstance(chord_renderer, str):
        name = chord_renderer
        chord_renderer = chord_renders.get(name)
        if chord_renderer is None:
            raise ValueError(
                f'Unknown chord renderer: {name}. '
                '(Available: {", ".join(chord_renders)}). '
                'You can register a new chord renderer with `register_chord_render`.'
            )
        return chord_renderer
    return chord_renderer


def process_chord_sequence(chord_sequence: ChordSequence, default_duration=240):
    """Preprocess a chord sequence, to make sure to add time, etc."""
    for chord in chord_sequence:
        if isinstance(chord, str):
            yield chord, default_duration
        elif isinstance(chord, tuple):
            yield chord
        else:
            raise ValueError(f"Invalid chord: {chord}")


def chords_to_midi(
    chord_sequence: ChordSequence = DFLT_CHORD_SEQUENCE,
    *,
    output_file: str = DFLT_MIDI_OUTPUT,
    render_chord: ChordRenderer = play_simultaneously,
    chord_definitions: ChordDefinitions = chord_to_notes,
):
    """
    Generate a MIDI file from a chord sequence.

    :param chord_sequence: List of tuples containing chords and their duration.
    :param chord_definitions: Dictionary mapping chords to MIDI note patterns.
    :param output_file: Name of the output MIDI file.
    :param render_chord: Function defining how the chords should be played.
    """
    midi = MidiFile()
    track = MidiTrack()
    midi.tracks.append(track)

    render_chord = resolve_chord_render(render_chord)
    chord_sequence = process_chord_sequence(chord_sequence)

    track.append(Message('program_change', program=0, time=0))  # Acoustic Grand Piano

    for chord, duration in chord_sequence:
        pattern = chord_definitions(chord)
        if pattern:
            render_chord(pattern, track, duration)

    midi.save(output_file)


def midi_to_wav(
    midi_file: str = DFLT_MIDI_OUTPUT,
    soundfont: str = DFLT_SOUNDFONT,
    output_wav: str = DFLT_WAV_OUTPUT,
):
    """
    Synthesize audio from a MIDI file using FluidSynth.

    :param midi_file: Name of the input MIDI file.
    :param soundfont: Path to the SoundFont file.
    :param output_wav: Name of the output WAV file.
    """
    subprocess.run(
        ['fluidsynth', '-ni', soundfont, midi_file, '-F', output_wav, '-r', '44100']
    )


def chords_to_wav(
    chord_sequence: ChordSequence = DFLT_CHORD_SEQUENCE,
    name: str = DFLT_OUTPUT_NAME,
    *,
    chord_definitions: ChordDefinitions = chord_to_notes,
    soundfont: str = DFLT_SOUNDFONT,
    render_chord: ChordRenderer = play_simultaneously,
):
    """
    Generate a WAV file directly from a chord sequence.

    :param chord_sequence: List of tuples containing chords and their duration.
    :param name: Base name for the output MIDI and WAV files.
    :param chord_definitions: Dictionary mapping chords to MIDI note patterns.
    :param soundfont: Path to the SoundFont file.
    :param render_chord: Function defining how the chords should be played.
    """
    midi_file = f'{name}.mid'
    wav_file = f'{name}.wav'

    chords_to_midi(
        chord_sequence,
        chord_definitions=chord_definitions,
        output_file=midi_file,
        render_chord=render_chord,
    )
    midi_to_wav(midi_file=midi_file, soundfont=soundfont, output_wav=wav_file)
    return wav_file
