"""Behavior tests for pat_helper.latex — flattening, comment stripping, line map."""

from pathlib import Path

import pytest

from pat_helper.latex import load_paper

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def paper():
    return load_paper(FIXTURES / "main.tex")


def test_input_files_are_resolved(paper):
    # Content from both \input'd files appears in the flattened text
    assert "Automation exposure has risen sharply since 2020." in paper.text
    assert "difference-in-differences design with staggered adoption" in paper.text


def test_comments_are_stripped(paper):
    assert "TODO: tighten this paragraph" not in paper.text
    assert "inline comment to strip" not in paper.text
    # But the content before an inline comment survives
    assert "Automation exposure has risen sharply since 2020." in paper.text


def test_escaped_percent_is_not_a_comment(paper):
    # \% must not start a comment: the rest of the sentence survives
    assert "of tasks in the sample are exposed" in paper.text
    assert r"42\%" in paper.text


def test_line_map_locates_input_file_content(paper):
    offset = paper.text.index("Standard errors are clustered")
    loc = paper.locate(offset)
    assert loc.file.endswith("methods.tex")
    assert loc.line == 4  # 1-indexed line in methods.tex


def test_line_map_locates_intro_content(paper):
    offset = paper.text.index("regional variation in broadband rollout")
    loc = paper.locate(offset)
    assert loc.file.endswith("intro.tex")
    assert loc.line == 5
