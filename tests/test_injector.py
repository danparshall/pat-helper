"""Behavior tests for pat_helper.injector — planted-error defect injection."""

import shutil
from pathlib import Path

import pytest

from pat_helper.injector import inject

FIXTURES = Path(__file__).parent / "fixtures"

DEFECTS = [
    {
        "id": "wrong-number",
        "file": "methods.tex",
        "original": "0.31 standard deviations",
        "mutated": "3.1 standard deviations",
        "lens_expected": "empirical-rigor",
        "description": "Effect size inflated 10x",
    },
    {
        "id": "weakened-id",
        "file": "intro.tex",
        "original": "regional variation in broadband rollout",
        "mutated": "national trends in broadband rollout",
        "lens_expected": "causal-id",
        "description": "Identification strategy no longer has cross-sectional variation",
    },
]


@pytest.fixture()
def workdir(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    for f in FIXTURES.glob("*.tex"):
        shutil.copy(f, src / f.name)
    return src


def test_injection_applies_exactly_the_specified_mutations(workdir, tmp_path):
    out = tmp_path / "mutated"
    inject(workdir, DEFECTS, out)
    methods = (out / "methods.tex").read_text()
    intro = (out / "intro.tex").read_text()
    assert "3.1 standard deviations" in methods
    assert "0.31 standard deviations" not in methods
    assert "national trends in broadband rollout" in intro
    # Untouched file is copied verbatim
    assert (out / "main.tex").read_text() == (workdir / "main.tex").read_text()


def test_injection_returns_manifest_locating_every_defect(workdir, tmp_path):
    manifest = inject(workdir, DEFECTS, tmp_path / "mutated")
    assert {m["id"] for m in manifest} == {"wrong-number", "weakened-id"}
    by_id = {m["id"]: m for m in manifest}
    assert by_id["wrong-number"]["file"] == "methods.tex"
    assert by_id["wrong-number"]["line"] == 3
    assert by_id["weakened-id"]["line"] == 5


def test_injection_fails_loudly_if_original_text_missing(workdir, tmp_path):
    bad = [dict(DEFECTS[0], original="text that is not there")]
    with pytest.raises(ValueError, match="wrong-number"):
        inject(workdir, bad, tmp_path / "mutated")
