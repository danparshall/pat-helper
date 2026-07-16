"""Behavior tests for pat_helper.sourcecheck — content-built source index,
citation extraction, and deterministic citation→file matching.

No live API calls. The fake provider answers index calls by recognizing a
marker in the file head it is shown — mirroring how the real cheap-model read
extracts {authors, year, title} from the text itself, so filenames stay
irrelevant (the generalizability requirement from the design convo).

Plan: docs/active/source-check/plans/20260714_source_check_stage.md (Part A).
"""

from __future__ import annotations

import hashlib
import json

import pytest

from pat_helper.config import ReviewConfig
from pat_helper.models import SOURCE_INDEX_SCHEMA
from pat_helper.providers.base import Provider, user_text
from pat_helper.sourcecheck import AMBIGUOUS, build_index, extract_citation, match

SVANBERG_TEXT = """\
The Productivity Effects of Generative AI
Svanberg, M. (2024). Working paper.

Access to generative AI increases task completion by 14 percent.
The estimated effect is concentrated among less-experienced workers.
"""

ACEMOGLU_TEXT = """\
Tasks, Automation, and the Wage Structure
Acemoglu, D. (2024). Journal of Economic Perspectives.

Automation displaces routine task labor while creating new task categories.
"""

MARINESCU_TEXT = """\
Causal Inference for Labor Market Platforms
Kording, K. and Marinescu, I. (2025).

Platform experiments identify wage elasticities without parallel-trends
assumptions.
"""

IDENTITIES = {
    "Svanberg": {
        "authors": ["Svanberg"],
        "year": "2024",
        "title": "The Productivity Effects of Generative AI",
    },
    "Acemoglu": {
        "authors": ["Acemoglu"],
        "year": "2024",
        "title": "Tasks, Automation, and the Wage Structure",
    },
    "Marinescu": {
        "authors": ["Kording", "Marinescu"],
        "year": "2025",
        "title": "Causal Inference for Labor Market Platforms",
    },
}


class FakeIndexProvider(Provider):
    """Answers SOURCE_INDEX_SCHEMA calls by recognizing a marker in the text."""

    name = "fake-indexer"

    def __init__(self):
        self.calls = []  # user prompts, one per index call

    async def complete_json(self, system, user, schema, *, max_output_tokens=None):
        assert schema is SOURCE_INDEX_SCHEMA, "index call must pass SOURCE_INDEX_SCHEMA"
        self.calls.append(user)
        text = user_text(user)
        for marker, identity in IDENTITIES.items():
            if marker in text:
                return dict(identity)
        raise AssertionError(f"no known source marker in index call: {text[:120]!r}")


@pytest.fixture()
def sources_dir(tmp_path):
    """Three sources under deliberately unhelpful filenames — the index must
    be built from content, never from filename conventions."""
    d = tmp_path / "sources"
    d.mkdir()
    (d / "a.txt").write_text(SVANBERG_TEXT)
    (d / "download (3).txt").write_text(ACEMOGLU_TEXT)
    (d / "notes_final_v2.txt").write_text(MARINESCU_TEXT)
    return d


def _sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --- index build ---------------------------------------------------------


async def test_build_index_indexes_every_file_despite_filenames(sources_dir):
    prov = FakeIndexProvider()
    index = await build_index(sources_dir, prov, ReviewConfig())
    assert len(prov.calls) == 3
    # citation→file resolution works for every file, keyed purely by content
    assert match(("svanberg", "2024"), index) == sources_dir / "a.txt"
    assert match(("acemoglu", "2024"), index) == sources_dir / "download (3).txt"
    assert match(("kording", "2025"), index) == sources_dir / "notes_final_v2.txt"


async def test_build_index_writes_sidecar_keyed_by_content_hash(sources_dir):
    """The sidecar is a user-inspectable, hand-correctable artifact — its
    keying by file sha256 is part of the contract (rename-safe, edit-aware)."""
    prov = FakeIndexProvider()
    await build_index(sources_dir, prov, ReviewConfig())
    sidecar_path = sources_dir / "sources_index.json"
    assert sidecar_path.exists()
    sidecar = json.loads(sidecar_path.read_text())
    expected_hashes = {
        _sha256(p) for p in sources_dir.iterdir() if p.name != "sources_index.json"
    }
    assert set(sidecar.keys()) == expected_hashes


async def test_unchanged_folder_rebuild_makes_zero_provider_calls(sources_dir):
    await build_index(sources_dir, FakeIndexProvider(), ReviewConfig())
    fresh = FakeIndexProvider()
    index = await build_index(sources_dir, fresh, ReviewConfig())
    assert fresh.calls == []
    # cached index still resolves citations
    assert match(("svanberg", "2024"), index) == sources_dir / "a.txt"


async def test_changed_file_reindexes_only_itself(sources_dir):
    await build_index(sources_dir, FakeIndexProvider(), ReviewConfig())
    # New content (distinct hash — identical content would be a legitimate
    # cache hit under sha256 keying), new identity: Svanberg → Marinescu
    (sources_dir / "a.txt").write_text(MARINESCU_TEXT + "\nRevised draft, new appendix.\n")
    fresh = FakeIndexProvider()
    index = await build_index(sources_dir, fresh, ReviewConfig())
    assert len(fresh.calls) == 1
    assert "Marinescu" in user_text(fresh.calls[0])
    # the swapped file now answers to its new identity...
    assert match(("svanberg", "2024"), index) is None
    # ...and two files sharing Kording/Marinescu 2025 makes that citation ambiguous
    assert match(("kording", "2025"), index) is AMBIGUOUS


# --- citation extraction (pure) ------------------------------------------


def test_extract_citation_et_al_form():
    text = "The paper's reading of Svanberg et al. (2024) cannot be verified from the text."
    assert extract_citation(text) == ("svanberg", "2024")


def test_extract_citation_ampersand_two_author_form():
    text = "This contradicts the estimates in Kording & Marinescu (2025)."
    assert extract_citation(text) == ("kording", "2025")


def test_extract_citation_single_author_form():
    text = "Acemoglu (2024) is characterized as supporting displacement effects."
    assert extract_citation(text) == ("acemoglu", "2024")


def test_extract_citation_none_when_no_citation():
    """A finding about the paper's own artifact ('replication package') has no
    (surname, year) to extract — unresolved by construction, per the plan."""
    text = "The complete replication package is asserted to contain the version pins."
    assert extract_citation(text) is None


def test_extract_citation_none_on_multiple_distinct_citations():
    text = "Svanberg et al. (2024) is conflated with Acemoglu (2024) throughout."
    assert extract_citation(text) is None


def test_extract_citation_repeated_same_citation_is_one_citation():
    """'Distinct' means distinct: the same work cited twice is still one
    citation, not an ambiguity."""
    text = "Svanberg et al. (2024) reports 14%; the paper claims Svanberg et al. (2024) found 25%."
    assert extract_citation(text) == ("svanberg", "2024")


def test_extract_citation_latex_tie_et_al_form():
    """Critique quotes are verbatim LaTeX; `et al.~(2024)` uses a tie, not a
    space. Observed live on both step-15 specimens (reverify rows 6-7,
    2026-07-16) — without tie handling, both abort at extraction."""
    text = "Svanberg et al.~(2024) demonstrate that even ``free'' AI systems achieve only 49\\%."
    assert extract_citation(text) == ("svanberg", "2024")


def test_extract_citation_latex_tie_single_author_form():
    text = "As Acemoglu~(2024) argues, displacement dominates."
    assert extract_citation(text) == ("acemoglu", "2024")


def test_extract_citation_latex_escaped_ampersand_two_author_form():
    """LaTeX source escapes the ampersand: `Kording \\& Marinescu~(2025)`.
    Same markup class as the tie — quotes lifted from .tex carry both."""
    text = "This contradicts Kording \\& Marinescu~(2025) on sector growth."
    assert extract_citation(text) == ("kording", "2025")


# --- matching (deterministic; the model never picks the file) -------------


async def test_match_zero_hits_returns_none(sources_dir):
    index = await build_index(sources_dir, FakeIndexProvider(), ReviewConfig())
    assert match(("smith", "1999"), index) is None


async def test_match_year_must_match_exactly(sources_dir):
    """Working-paper-vs-published year drift must not silently match the wrong
    version — a near-miss year is not a hit."""
    index = await build_index(sources_dir, FakeIndexProvider(), ReviewConfig())
    assert match(("svanberg", "2025"), index) is None


def test_match_tolerates_comma_initial_author_strings(tmp_path):
    """Models render authors as printed ('Svanberg, M.'), not as bare
    surnames — the mechanical identity gate must match on the surname token,
    or it false-rejects honest confirmations (observed live on the 2026-07-16
    fixture-gate run: checker said critique-confirmed, gate forced
    unresolved over 'Svanberg, M.' != 'svanberg')."""
    path = tmp_path / "s.txt"
    index = {
        path: {
            "authors": ["Svanberg, M."],
            "year": "2024",
            "title": "The Productivity Effects of Generative AI",
        }
    }
    assert match(("svanberg", "2024"), index) == path


def test_match_does_not_fire_on_substring_of_a_longer_name(tmp_path):
    """Token match, not substring match: 'berg' must not hit 'Svanberg'."""
    path = tmp_path / "s.txt"
    index = {path: {"authors": ["Svanberg, M."], "year": "2024", "title": "t"}}
    assert match(("berg", "2024"), index) is None


async def test_match_two_same_author_year_files_is_ambiguous(tmp_path):
    d = tmp_path / "sources"
    d.mkdir()
    (d / "one.txt").write_text(SVANBERG_TEXT)
    (d / "two.txt").write_text(SVANBERG_TEXT + "\nAppendix tables.\n")
    index = await build_index(d, FakeIndexProvider(), ReviewConfig())
    assert match(("svanberg", "2024"), index) is AMBIGUOUS
