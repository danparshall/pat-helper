"""Behavior tests for pat_helper.quotecheck — mechanical quote grounding."""

from pathlib import Path

import pytest

from pat_helper.latex import load_paper
from pat_helper.quotecheck import check_quote

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def paper():
    return load_paper(FIXTURES / "main.tex")


def test_exact_quote_is_found_with_location(paper):
    m = check_quote("Standard errors are clustered at the region level.", paper)
    assert m.found
    assert m.score == pytest.approx(1.0)
    assert m.location is not None
    assert m.location.file.endswith("methods.tex")


def test_normalized_quote_matches_curly_quotes_and_dashes(paper):
    # Model quoted with an em dash where source has LaTeX '---'
    quote = "The effect size is 0.31 standard deviations—large by conventional standards."
    m = check_quote(quote, paper)
    assert m.found
    assert m.score == pytest.approx(1.0)


def test_normalized_quote_matches_escaped_percent(paper):
    # Model naturally writes '42%' where source has '42\%'
    m = check_quote("We estimate that 42% of tasks in the sample are exposed.", paper)
    assert m.found
    assert m.score == pytest.approx(1.0)


def test_fuzzy_quote_matches_with_sub_1_score(paper):
    # Slightly misremembered quote: singular/plural drift
    quote = "The effect size is 0.31 standard deviation, large by conventional standard"
    m = check_quote(quote, paper)
    assert m.found
    assert 0.85 <= m.score < 1.0


def test_fabricated_quote_is_not_found(paper):
    m = check_quote("The authors fabricate a causal claim about tariff pass-through.", paper)
    assert not m.found
    assert m.location is None
