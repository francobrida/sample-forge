import pytest
from fakes import FakeEleven

from sample_forge.core import BudgetExceeded, Forge, Req


@pytest.fixture
def forge(tmp_path):
    return Forge(FakeEleven(), data_dir=tmp_path, budget=1000)


def test_generate_caches_and_stores(forge):
    r = Req(kind="sfx", prompt="riser épico", n=2, duration=1.0)
    first = forge.generate(r)
    assert [s["cached"] for s in first] == [False, False]
    assert first[0]["id"] != first[1]["id"]                 # variantes distintas
    assert forge.client.calls == 2
    assert all(s["cached"] for s in forge.generate(r))      # misma petición: cero llamadas nuevas
    assert forge.client.calls == 2
    assert forge.status()["spent"] == 2 * 20                # 20 créditos/s * 1 s, por 2 tomas


def test_generated_sample_is_analyzed_and_tagged(forge):
    (s,) = forge.generate(Req(kind="sfx", prompt="door slam", duration=1.0, tags=["Foley"]))
    assert s["note"] == "A4" and 0.98 < s["duration"] < 1.05
    assert {"door", "slam", "foley", "sfx", "A4"} <= set(s["tags"].split())
    assert forge.db.search("slam")[0]["id"] == s["id"]
    assert (forge.dir / s["file"]).exists()


def test_vox_uses_tts(forge):
    (s,) = forge.generate(Req(kind="vox", prompt="yeah"))
    assert s["kind"] == "vox" and s["note"] == "C4" and s["credits"] == 4


def test_estimate_counts_only_uncached(forge):
    r = Req(kind="sfx", prompt="boom", n=3, duration=2.0)
    assert forge.estimate(r)["credits"] == 3 * 40
    forge.generate(Req(kind="sfx", prompt="boom", n=1, duration=2.0))
    e = forge.estimate(r)
    assert (e["new"], e["cached"], e["credits"]) == (2, 1, 80)


def test_budget_blocks_before_calling_api(tmp_path):
    f = Forge(FakeEleven(), data_dir=tmp_path, budget=30)
    with pytest.raises(BudgetExceeded):
        f.generate(Req(kind="sfx", prompt="boom", duration=2.0))     # cuesta 40 > 30
    assert f.client.calls == 0


def test_request_validation():
    for bad in [dict(prompt=""), dict(prompt="x", n=9), dict(prompt="x", duration=0.1), dict(prompt="x", voice="../x")]:
        with pytest.raises(ValueError):
            Req(kind="sfx", **bad)
