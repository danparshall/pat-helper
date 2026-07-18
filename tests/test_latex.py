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


# --- load_text_source: page-furniture stripping ---------------------------
#
# pdftotext extractions interleave running headers/footers with body text.
# Observed live (step-15 Svanberg specimen, 2026-07-17): the running header,
# spliced mid-sentence at a page break, dragged a genuine 403-char checker
# quote to 0.834 — under the 0.85 grounding floor — turning a correct
# resolution into a Gate B false negative. Headers repeat once per page, so
# repetition (digit-masked, to catch 'Working Paper 16' / '17' variants) is
# the mechanical signal.

HEADER = "Svanberg et al.: Which Tasks are Cost-Effective to Automate?"
BODY = [
    "Even with those extremely aggressive assumptions, the amount of",
    "economically attractive automation only increases to 49%.",
    "This reflects the extremely fragmented distribution of tasks",
    "in the economy, which can make development costs prohibitive.",
    "Material Moving Workers, Except Aircraft",
]


def _furnished_source(tmp_path, n_pages=6):
    """Body lines interleaved with per-page furniture, splicing a sentence."""
    lines = []
    for page in range(n_pages):
        lines.append(BODY[page % len(BODY)])
        lines.append(HEADER)
        lines.append(f"{page + 10} Working Paper")
        lines.append(BODY[(page + 1) % len(BODY)])
    src = tmp_path / "source.txt"
    src.write_text("\n".join(lines) + "\n")
    return src


def test_text_source_strips_repeated_page_furniture(tmp_path):
    from pat_helper.latex import load_text_source

    paper = load_text_source(_furnished_source(tmp_path))
    assert HEADER not in paper.text
    assert "Working Paper" not in paper.text
    for body_line in BODY:
        assert body_line in paper.text


def test_text_source_keeps_infrequent_and_short_repeats(tmp_path):
    """Repetition alone must not nuke content: lines under the repeat
    threshold (table rows) and short math/number fragments survive."""
    from pat_helper.latex import load_text_source

    lines = (
        ["Unique sentence number %d here." % i for i in range(10)]
        + ["Material Moving Workers, Except Aircraft"] * 4  # under threshold
        + ["t=0"] * 8  # repeated but too few letters
        + ["(3)"] * 8
        + ["17"]
    )
    src = tmp_path / "source.txt"
    src.write_text("\n".join(lines) + "\n")
    paper = load_text_source(src)
    assert "Material Moving Workers, Except Aircraft" in paper.text
    assert "t=0" in paper.text
    assert "(3)" in paper.text
    assert "17" in paper.text


def test_text_source_line_map_survives_furniture_strip(tmp_path):
    """locate() still reports the ORIGINAL file line after stripping."""
    from pat_helper.latex import load_text_source

    paper = load_text_source(_furnished_source(tmp_path))
    offset = paper.text.index("This reflects the extremely fragmented")
    loc = paper.locate(offset)
    assert loc.file == "source.txt"
    # BODY[2] first appears as page 1's fourth slot: line 8 of the original
    assert loc.line == 8


def test_furniture_spliced_quote_grounds_after_strip(tmp_path):
    """The live failure shape: a verbatim multi-line quote spanning a page
    break must ground once furniture is stripped."""
    from pat_helper.latex import load_text_source
    from pat_helper.quotecheck import check_quote

    filler = ["filler line %d." % p for p in range(17, 21)]
    furniture = [HEADER, "16 Working Paper"]
    lines = [BODY[0]] + furniture + [BODY[1], BODY[2]]
    for p, fill in enumerate(filler, start=17):
        lines += [HEADER, f"{p} Working Paper", fill]
    src = tmp_path / "source.txt"
    src.write_text("\n".join(lines) + "\n")
    quote = " ".join([BODY[0], BODY[1], BODY[2]])
    paper = load_text_source(src)
    match = check_quote(quote, paper)
    assert match.found
    assert match.score > 0.95
