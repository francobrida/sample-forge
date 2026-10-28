import numpy as np
import pytest
from audio import SR, tone, wav

from sample_forge import analyze


def test_pitch_detects_known_notes():
    for f, want in [(440, "A4"), (261.63, "C4"), (110, "A2"), (987.77, "B5")]:
        got = analyze.pitch(tone(f), SR)
        assert got and abs(got - f) / f < 0.01, (f, got)
        assert analyze.note_name(got)[0] == want


def test_noise_has_no_pitch():
    noise = np.random.default_rng(0).uniform(-0.5, 0.5, SR)
    assert analyze.pitch(noise, SR) is None


def test_process_trims_and_normalizes():
    x, sr, m = analyze.process(wav(tone(440, 1.0, lead=0.3)))
    assert 0.98 < m["duration"] < 1.05            # sin los 0,3 s de silencio
    assert m["peak_db"] == pytest.approx(-1, abs=0.1)
    assert m["note"] == "A4"
    _, _, loop = analyze.process(wav(tone(440, 1.0, lead=0.3)), loop=True)
    assert loop["duration"] == pytest.approx(1.3, abs=0.01)    # un loop no se recorta
