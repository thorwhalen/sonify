"""Data sonification tools.

Map data to sound so it can be interpreted in an auditory manner.

The chord and conversion machinery this package was built around now lives in
the ``tonal`` package; ``sonification`` re-exports it so existing imports keep
working:

>>> from sonification import chords_to_wav, convert, register_chord_render
>>> all(callable(f) for f in (chords_to_wav, convert, register_chord_render))
True

Every re-exported name resolves to its ``tonal`` home:

>>> chords_to_wav.__module__
'tonal.chords'
>>> register_chord_render.__module__
'tonal.chords'
>>> convert.__module__
'tonal.converters'
"""

from tonal.chords import chords_to_wav, register_chord_render
from tonal.converters import convert
