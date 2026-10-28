"""Decodifica, limpia y mide un sample. Todo con numpy: sin librosa."""
import io
import math

import numpy as np
import soundfile as sf

NOTES = "C C# D D# E F F# G G# A A# B".split()


def decode(data: bytes):
    x, sr = sf.read(io.BytesIO(data), dtype="float32", always_2d=True)
    return x.mean(axis=1), sr


def db(v):
    return 20 * math.log10(max(float(v), 1e-9))


def trim(x, sr, floor_db=-50, pad=0.005):
    """Quita el silencio de los extremos (floor_db relativo al pico) dejando 5 ms de margen."""
    idx = np.flatnonzero(np.abs(x) > np.abs(x).max() * 10 ** (floor_db / 20))
    if not len(idx):
        return x
    p = int(pad * sr)
    return x[max(idx[0] - p, 0): idx[-1] + p + 1]


def fade(x, sr, ms=3):
    """Rampa corta en los extremos para que no haya clics."""
    n = min(int(sr * ms / 1000), len(x) // 2)
    x, ramp = x.copy(), np.linspace(0, 1, n, dtype=x.dtype)
    x[:n] *= ramp
    x[len(x) - n:] *= ramp[::-1]
    return x


def normalize(x, peak_db=-1):
    p = np.abs(x).max()
    return x if p == 0 else x * (10 ** (peak_db / 20) / p)


def pitch(x, sr, fmin=50, fmax=2000, min_conf=0.6):
    """f0 por autocorrelación en la ventana más fuerte (0,25 s). None si no hay tono claro (ruido, percusión)."""
    win = int(0.25 * sr)
    if len(x) > win:
        c = np.cumsum(x.astype("float64") ** 2)
        start = int(np.argmax(c[win:] - c[:-win]))
        x = x[start: start + win]
    x = (x - x.mean()) * np.hanning(len(x))
    n = len(x)
    spec = np.fft.rfft(x, 2 * n)
    ac = np.fft.irfft(spec * np.conj(spec))[:n]
    if ac[0] <= 0:
        return None
    ac = ac / ac[0]
    neg = np.flatnonzero(ac < 0)            # el pico de lag 0 tiene que haber caído antes de buscar el siguiente
    lo, hi = max(int(sr / fmax), int(neg[0]) if len(neg) else n), min(int(sr / fmin), n - 2)
    if hi <= lo:
        return None
    seg = ac[lo:hi]
    if seg.max() < min_conf:
        return None
    mid = seg[1:-1]     # el primer pico local casi tan alto como el máximo evita errores de octava (f/2, f/3...)
    peaks = np.flatnonzero((mid > seg[:-2]) & (mid >= seg[2:]) & (mid >= 0.9 * seg.max()))
    lag = lo + 1 + int(peaks[0]) if len(peaks) else lo + int(np.argmax(seg))
    a, b, c_ = ac[lag - 1], ac[lag], ac[lag + 1]
    den = a - 2 * b + c_
    shift = 0.5 * (a - c_) / den if den else 0.0     # interpolación parabólica del pico
    return sr / (lag + shift)


def note_name(f0):
    m = 69 + 12 * math.log2(f0 / 440)
    k = round(m)
    return f"{NOTES[k % 12]}{k // 12 - 1}", round((m - k) * 100)


def process(data: bytes, loop=False):
    """bytes de audio -> (señal lista para guardar, sr, medidas). Los loops no se recortan: perderían el ciclo."""
    x, sr = decode(data)
    if not loop:
        x = fade(trim(x, sr), sr)
    x = normalize(x)
    f0 = pitch(x, sr)
    note, cents = note_name(f0) if f0 else (None, None)
    return x, sr, dict(duration=len(x) / sr, peak_db=db(np.abs(x).max()), rms_db=db(np.sqrt(np.mean(x**2))),
                       f0=f0, note=note, cents=cents)


def save(path, x, sr):
    sf.write(path, x, sr, subtype="PCM_24")
