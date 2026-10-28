"""Generar -> analizar -> guardar -> exportar. Lo comparten la CLI y la API."""
import hashlib
import io
import json
import os
import re
import shutil
import time
import unicodedata
import zipfile
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from . import analyze
from .db import DB, month_start

# ponytail: costos estimados en créditos (el panel de ElevenLabs manda); ajustar aquí si cambian las tarifas
SFX_AUTO, SFX_PER_SEC, TTS_PER_CHAR = 40, 20, 1
DEFAULT_VOICE = os.environ.get("SF_VOICE", "21m00Tcm4TlvDq8ikWAM")   # "Rachel", una voz predefinida


class BudgetExceeded(RuntimeError):
    pass


class Req(BaseModel):
    kind: Literal["sfx", "vox"]
    prompt: str = Field(min_length=1, max_length=450)
    n: int = Field(1, ge=1, le=8)                       # variantes: cada una es una generación (gasta créditos)
    duration: float | None = Field(None, ge=0.5, le=30)  # solo sfx; vacío = lo decide el modelo
    loop: bool = False                                    # solo sfx
    influence: float = Field(0.3, ge=0, le=1)             # solo sfx
    voice: str = Field(DEFAULT_VOICE, pattern=r"^[A-Za-z0-9]{10,40}$")   # solo vox
    tags: list[str] = []


def slug(text, words=3):
    ascii_ = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return "_".join(w.capitalize() for w in re.findall(r"[A-Za-z0-9]+", ascii_)[:words]) or "Sample"


class Forge:
    def __init__(self, client, data_dir=None, budget=None):
        self.client = client
        self.dir = Path(data_dir or os.environ.get("SF_DATA", "data"))
        (self.dir / "samples").mkdir(parents=True, exist_ok=True)
        self.db = DB(self.dir / "forge.db")
        self.budget = int(budget or os.environ.get("SF_MONTHLY_CREDITS", 8000))

    def sample_id(self, r: Req, i):
        # ponytail: el hash define la caché; las variantes (i) hacen que n=4 sean 4 tomas distintas
        key = [r.kind, r.prompt, i] + ([r.duration, r.loop, r.influence] if r.kind == "sfx" else [r.voice])
        return hashlib.sha1(json.dumps(key).encode()).hexdigest()[:12]

    def cost(self, r: Req):
        if r.kind == "vox":
            return len(r.prompt) * TTS_PER_CHAR
        return round(SFX_PER_SEC * r.duration) if r.duration else SFX_AUTO

    def status(self):
        spent = self.db.spent_since(month_start())
        return dict(spent=spent, budget=self.budget, left=self.budget - spent)

    def estimate(self, r: Req):
        new = sum(self.db.get(self.sample_id(r, i)) is None for i in range(r.n))
        return dict(new=new, cached=r.n - new, credits=new * self.cost(r), **self.status())

    def generate(self, r: Req):
        out = []
        for i in range(r.n):
            id = self.sample_id(r, i)
            if s := self.db.get(id):
                out.append(dict(s, cached=True))
                continue
            cost = self.cost(r)
            if self.status()["left"] < cost:
                raise BudgetExceeded(f"Presupuesto mensual agotado ({self.budget} créditos; esta toma cuesta ~{cost})")
            data = (self.client.sfx(r.prompt, r.duration, r.influence, r.loop) if r.kind == "sfx"
                    else self.client.tts(r.prompt, r.voice))
            x, sr, m = analyze.process(data, loop=r.loop and r.kind == "sfx")
            file = f"samples/{id}.wav"
            analyze.save(self.dir / file, x, sr)
            words = [w for w in re.findall(r"\w+", r.prompt.lower()) if len(w) > 2]
            tags = " ".join(dict.fromkeys(words + [t.lower() for t in r.tags] + [r.kind] + ([m["note"]] if m["note"] else [])
                                          + (["loop"] if r.loop else [])))
            s = dict(id=id, kind=r.kind, prompt=r.prompt, file=file, loop=int(r.loop), duration=m["duration"],
                     peak_db=m["peak_db"], rms_db=m["rms_db"], f0=m["f0"], note=m["note"], tags=tags,
                     credits=cost, created=time.time())
            self.db.add(s)
            out.append(dict(s, cached=False))
        return out

    def filename(self, s):
        parts = [slug(s["prompt"]), s["note"], f"{s['duration']:.1f}s", s["id"][:4]]
        return "_".join(p for p in parts if p) + ".wav"

    def export(self, ids, dest):
        """Copia los WAV a dest con nombres tipo Riser_Am_2.4s_ab12.wav (Ableton no lee tags de WAV: va en el nombre)."""
        dest = Path(dest)
        dest.mkdir(parents=True, exist_ok=True)
        written = []
        for id in ids:
            if s := self.db.get(id):
                shutil.copyfile(self.dir / s["file"], dest / self.filename(s))
                written.append(dest / self.filename(s))
        return written

    def zip(self, ids):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:    # el WAV no se comprime
            for id in ids:
                if s := self.db.get(id):
                    z.write(self.dir / s["file"], self.filename(s))
        return buf.getvalue()
