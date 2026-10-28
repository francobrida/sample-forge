import io

import numpy as np
import soundfile as sf

SR = 44100


def wav(x):
    b = io.BytesIO()
    sf.write(b, x.astype("float32"), SR, format="WAV")
    return b.getvalue()


def tone(f, dur=1.0, lead=0.0):
    t = np.arange(int(SR * dur)) / SR
    return np.concatenate([np.zeros(int(SR * lead)), 0.5 * np.sin(2 * np.pi * f * t)])
