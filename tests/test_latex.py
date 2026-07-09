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


def test_preamble_stripped_when_document_markers_present(tmp_path):
    """Everything before \\begin{document} is boilerplate the reviewer shouldn't see."""
    tex = tmp_path / "main.tex"
    tex.write_text(
        r"\PassOptionsToPackage{unicode}{hyperref}" + "\n"
        r"\documentclass[11pt]{article}" + "\n"
        r"\usepackage{xcolor}" + "\n"
        r"\usepackage{amsmath,amssymb}" + "\n"
        r"\begin{document}" + "\n"
        r"\maketitle" + "\n"
        "The paper body starts here.\n"
        r"\end{document}" + "\n"
    )
    paper = load_paper(tex)
    assert "PassOptionsToPackage" not in paper.text
    assert "documentclass" not in paper.text
    assert "usepackage" not in paper.text
    # Body content survives; document markers themselves are stripped
    assert "The paper body starts here." in paper.text
    assert r"\begin{document}" not in paper.text
    assert r"\end{document}" not in paper.text


def test_postamble_stripped_when_end_document_present(tmp_path):
    """Anything after \\end{document} (bib appendix, trailing junk) is discarded."""
    tex = tmp_path / "main.tex"
    tex.write_text(
        r"\begin{document}" + "\n"
        "Body content.\n"
        r"\end{document}" + "\n"
        "% trailing note that shouldn't reach the reviewer\n"
        r"\typeout{diagnostic}" + "\n"
    )
    paper = load_paper(tex)
    assert "Body content." in paper.text
    assert "trailing note" not in paper.text
    assert "typeout" not in paper.text


def test_no_document_markers_passes_through_unchanged(tmp_path):
    """Fragments without \\begin{document} (e.g. an \\input'd child) still work."""
    tex = tmp_path / "fragment.tex"
    tex.write_text("Just a body fragment.\nNo document markers here.\n")
    paper = load_paper(tex)
    assert "Just a body fragment." in paper.text
    assert "No document markers here." in paper.text


def test_line_map_still_locates_after_preamble_strip(tmp_path):
    """locate() must return correct (file, line) even though preamble was removed."""
    tex = tmp_path / "main.tex"
    tex.write_text(
        r"\documentclass{article}" + "\n"
        r"\usepackage{amsmath}" + "\n"
        r"\begin{document}" + "\n"
        "First body line.\n"
        "Second body line.\n"
        r"\end{document}" + "\n"
    )
    paper = load_paper(tex)
    offset = paper.text.index("Second body line.")
    loc = paper.locate(offset)
    assert loc.file.endswith("main.tex")
    assert loc.line == 5  # 1-indexed in the original file
