import httpx
import pytest

from sample_forge.eleven import Eleven, ElevenError


def client(handler, key="k", retries=3):
    return Eleven(key, retries=retries, http=httpx.Client(transport=httpx.MockTransport(handler)))


def test_sfx_request_shape():
    seen = []

    def handler(req):
        seen.append(req)
        return httpx.Response(200, content=b"audio")

    assert client(handler).sfx("boom", duration=2, loop=True) == b"audio"
    req = seen[0]
    assert req.url.path == "/v1/sound-generation" and req.url.params["output_format"] == "mp3_44100_128"
    assert req.headers["xi-api-key"] == "k"
    assert b'"duration_seconds":2' in req.content or b'"duration_seconds": 2' in req.content


def test_duration_omitted_when_auto():
    seen = []
    client(lambda r: (seen.append(r), httpx.Response(200, content=b"x"))[1]).sfx("boom")
    assert b"duration_seconds" not in seen[0].content


def test_retries_on_rate_limit_then_succeeds():
    codes = iter([429, 429, 200])
    n = []

    def handler(req):
        n.append(1)
        return httpx.Response(next(codes), headers={"retry-after": "0"}, content=b"ok")

    assert client(handler).tts("hola", "v" * 20) == b"ok"
    assert len(n) == 3


def test_auth_error_is_not_retried():
    n = []

    def handler(req):
        n.append(1)
        return httpx.Response(401, text="bad key")

    with pytest.raises(ElevenError, match="401"):
        client(handler).sfx("boom")
    assert len(n) == 1


def test_gives_up_after_retries():
    with pytest.raises(ElevenError, match="503"):
        client(lambda r: httpx.Response(503, headers={"retry-after": "0"}), retries=2).sfx("boom")


def test_missing_key(monkeypatch):
    monkeypatch.delenv("ELEVEN_API_KEY", raising=False)
    with pytest.raises(ElevenError, match="ELEVEN_API_KEY"):
        Eleven().sfx("boom")
