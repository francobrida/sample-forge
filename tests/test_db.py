import time

import pytest

from sample_forge.db import DB, month_start


def sample(id, prompt, kind="sfx", note="A4", duration=1.0, credits=20, created=None):
    return dict(id=id, kind=kind, prompt=prompt, file=f"samples/{id}.wav", loop=0, duration=duration, peak_db=-1.0,
                rms_db=-6.0, f0=440.0, note=note, tags=f"{prompt} {kind} {note}", credits=credits,
                created=created or time.time())


@pytest.fixture
def db(tmp_path):
    d = DB(tmp_path / "t.db")
    d.add(sample("a" * 12, "door slam", note="C4", duration=2.0))
    d.add(sample("b" * 12, "yeah", kind="vox", note="A#4", duration=0.5))
    return d


def test_text_search_with_prefix(db):
    assert [s["prompt"] for s in db.search("slam")] == ["door slam"]
    assert [s["prompt"] for s in db.search("do")] == ["door slam"]
    assert db.search("nothing") == []


def test_filters(db):
    assert [s["prompt"] for s in db.search(kind="vox")] == ["yeah"]
    assert [s["prompt"] for s in db.search(max_dur=1)] == ["yeah"]
    assert len(db.search(note="C")) == 1 and len(db.search(note="C4")) == 1
    assert db.search(note="C5") == []
    assert db.search(note="A") == []        # "A" no debe confundirse con "A#"
    assert len(db.search(note="A#")) == 1


def test_fts_syntax_cannot_leak(db):
    assert db.search('x" OR "y') == []


def test_ledger_counts_spend_by_period(db):
    assert db.spent_since(0) == 40
    assert db.spent_since(time.time() + 10) == 0
    db.add(sample("c" * 12, "old", created=month_start() - 86400, credits=100))   # el mes pasado no cuenta
    assert db.spent_since(month_start()) == 40
