"""Cliente mínimo de ElevenLabs (sound effects y text-to-speech) con reintentos."""
import os
import time

import httpx

BASE = "https://api.elevenlabs.io/v1"
FORMAT = "mp3_44100_128"        # el WAV/PCM de 44,1 kHz exige plan Pro; el mp3 sirve en el gratis
RETRY_STATUS = {429, 500, 502, 503, 504}


class ElevenError(RuntimeError):
    pass


class Eleven:
    def __init__(self, api_key=None, retries=4, http=None):
        self.key, self.retries = api_key or os.environ.get("ELEVEN_API_KEY"), retries
        self.http = http or httpx.Client(timeout=90)

    def _post(self, path, body):
        if not self.key:
            raise ElevenError("Falta la variable de entorno ELEVEN_API_KEY")
        for attempt in range(self.retries):
            r = self.http.post(f"{BASE}{path}", params={"output_format": FORMAT}, json=body,
                               headers={"xi-api-key": self.key})
            if r.status_code == 200:
                return r.content
            if r.status_code not in RETRY_STATUS or attempt == self.retries - 1:
                raise ElevenError(f"ElevenLabs {r.status_code}: {r.text[:300]}")
            wait = float(r.headers.get("retry-after") or 2**attempt)   # 1, 2, 4 s si no avisa
            time.sleep(min(wait, 30))

    def sfx(self, text, duration=None, influence=0.3, loop=False):
        body = {"text": text, "prompt_influence": influence, "loop": loop}
        if duration:
            body["duration_seconds"] = duration
        return self._post("/sound-generation", body)

    def tts(self, text, voice, model="eleven_multilingual_v2"):
        return self._post(f"/text-to-speech/{voice}", {"text": text, "model_id": model})

    def voices(self):
        r = self.http.get(f"{BASE}/voices", headers={"xi-api-key": self.key or ""})
        if r.status_code != 200:
            raise ElevenError(f"ElevenLabs {r.status_code}: {r.text[:300]}")
        return [(v["voice_id"], v["name"]) for v in r.json()["voices"]]
