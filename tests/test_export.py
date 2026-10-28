import pytest
from fakes import FakeEleven

from sample_forge.core import Forge, Req, slug


@pytest.fixture
def forge(tmp_path):
    return Forge(FakeEleven(), data_dir=tmp_path / "data")


def test_slug_strips_accents_and_limits_words():
    assert slug("Riser épico muy largo y fuerte") == "Riser_Epico_Muy"
    assert slug("!!!") == "Sample"


def test_export_names_and_zip(forge, tmp_path):
    s = forge.generate(Req(kind="sfx", prompt="Riser épico largo", duration=1.0))[0]
    (p,) = forge.export([s["id"]], tmp_path / "out")
    assert p.name == f"Riser_Epico_Largo_A4_{s['duration']:.1f}s_{s['id'][:4]}.wav"
    assert p.exists() and forge.zip([s["id"]])[:2] == b"PK"


def test_export_skips_unknown_ids(forge, tmp_path):
    assert forge.export(["f" * 12], tmp_path / "out") == []
