from audio import tone, wav


class FakeEleven:
    calls = 0

    def sfx(self, text, duration=None, influence=0.3, loop=False):
        self.calls += 1
        return wav(tone(440, duration or 1.0, lead=0.3))     # 0,3 s de silencio inicial que hay que recortar

    def tts(self, text, voice):
        self.calls += 1
        return wav(tone(261.63, 0.5))
