"""Content-built source index + deterministic citation matching (stage 3.5).

The author supplies a flat directory of extracted-text source files. Each
file's identity ({authors, year, title}) is read from its own text by a
model — filenames are never trusted — and cached in a `sources_index.json`
sidecar keyed by file sha256, so an unchanged folder re-indexes for free and
a renamed file is a cache hit. The sidecar is deliberately human-readable:
inspect it, hand-correct it, learn from it.

Citation → file matching is pure code (`extract_citation` + `match`): the
model never picks which file to read. Zero or ambiguous matches leave the
finding unresolved rather than guessing.

Design: docs/convos/main/20260713_unverifiable_verdict_design.md
Plan:   docs/active/source-check/plans/20260714_source_check_stage.md
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path

from pat_helper.config import ReviewConfig
from pat_helper.models import SOURCE_INDEX_SCHEMA
from pat_helper.providers.base import Provider


class _Ambiguous:
    def __repr__(self) -> str:  # pragma: no cover — debugging nicety
        return "AMBIGUOUS"


# Sentinel: the citation matches more than one indexed source.
AMBIGUOUS = _Ambiguous()

SIDECAR_NAME = "sources_index.json"

# How much of each file the index read sees. Identity (authors/year/title)
# lives on page 1 of any extracted paper; 2,000 chars is plenty and keeps the
# read cheap enough to run on the main review providers (no separate
# cheap-model plumbing — revisit if source folders get huge).
HEAD_CHARS = 2000

INDEX_PROMPT = """\
You will receive the beginning of a text file extracted from an academic or
policy document. Identify the document from its own text: author surnames (in
the order listed), publication year as printed, and title. Report them as JSON
matching the schema you have been given. Read only what the text says — do
not guess from style or infer missing fields; if a field is genuinely absent,
use an empty string (or empty list for authors).
"""

# Author-year citation forms: "Svanberg et al. (2024)", "Kording & Marinescu
# (2025)", "Kording and Marinescu (2025)", "Acemoglu (2024)". Group 1 is the
# first-author surname (unicode letters allowed), group 2 the year.
_CITATION_RE = re.compile(
    r"(?<![\w.])"
    r"([^\W\d_][\w'’-]+)"  # first-author surname (starts with a letter)
    r"(?:\s*,?\s*et al\.?|\s+(?:&|and)\s+[^\W\d_][\w'’-]+)?"  # et al. / 2nd author
    r"\s*\((\d{4})\)"
)


def _fold(s: str) -> str:
    """NFC-normalize + casefold — diacritics and case never block a match."""
    return unicodedata.normalize("NFC", s).casefold()


# Name tokens: runs of letters, keeping internal hyphens/apostrophes
# ("garcía-márquez" is one token; "svanberg, m." tokenizes to svanberg + m).
_NAME_TOKEN_RE = re.compile(r"[^\W\d_][\w'’\-]*")


def _surname_matches(surname_folded: str, author: str) -> bool:
    """True if the citation surname is a whole name-token of the author string.

    Models render authors as printed — 'Svanberg, M.', 'Kording, K.' — not as
    bare surnames, so equality against the full string false-rejects honest
    identities (observed live, 2026-07-16 fixture gate). Token match keeps the
    gate mechanical without being brittle about name formatting; substrings
    ('berg' vs 'Svanberg') still do not match.
    """
    return surname_folded in _NAME_TOKEN_RE.findall(_fold(author))


def extract_citation(text: str) -> tuple[str, str] | None:
    """Extract the single (surname, year) citation from critique text.

    Returns None when no citation is present (e.g. a critique about the
    paper's own replication package) or when more than one DISTINCT work is
    cited — resolving against the wrong source is worse than not resolving.

    Critique quotes are verbatim LaTeX, so citation markup arrives as
    `et al.~(2024)` (tie) and `Kording \\& Marinescu` (escaped ampersand);
    fold both to their plain-text forms before matching (observed live on
    the step-15 specimens, 2026-07-16).
    """
    text = text.replace("~", " ").replace("\\&", "&")
    found = {
        (_fold(m.group(1)), m.group(2))
        for m in _CITATION_RE.finditer(text)
        # Surnames in citations are capitalized; this filters prose false
        # positives like "rose 25 percent (2024)". isupper() is unicode-aware,
        # so diacritic initials (Gómez, Åberg) pass.
        if m.group(1)[0].isupper()
    }
    if len(found) != 1:
        return None
    return found.pop()


def file_sha256(path: Path) -> str:
    """Content hash used both for sidecar cache keys and provenance notes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def build_index(
    sources_dir: str | Path, provider: Provider, config: ReviewConfig
) -> dict[Path, dict]:
    """Read (or reuse) each source file's identity; return {path: identity}.

    The sidecar cache is keyed by content hash, so only new/changed files cost
    a provider call, and entries whose file vanished are pruned on rebuild.
    """
    sources_dir = Path(sources_dir)
    sidecar_path = sources_dir / SIDECAR_NAME
    cached: dict[str, dict] = {}
    if sidecar_path.exists():
        cached = json.loads(sidecar_path.read_text())

    index: dict[Path, dict] = {}
    sidecar: dict[str, dict] = {}
    for path in sorted(p for p in sources_dir.iterdir() if p.is_file()):
        if path.name == SIDECAR_NAME or path.name.startswith("."):
            continue
        digest = file_sha256(path)
        identity = cached.get(digest)
        if identity is None:
            head = path.read_text(errors="replace")[:HEAD_CHARS]
            identity = await provider.complete_json(INDEX_PROMPT, head, SOURCE_INDEX_SCHEMA)
        index[path] = identity
        sidecar[digest] = identity
    # Rewrite the sidecar from what is actually on disk: stale entries pruned.
    sidecar_path.write_text(json.dumps(sidecar, indent=2, ensure_ascii=False) + "\n")
    return index


def match(citation: tuple[str, str], index: dict[Path, dict]) -> Path | None | _Ambiguous:
    """Deterministically resolve a citation to exactly one indexed source.

    The surname must appear among the source's authors (casefolded) and the
    year must match exactly — a ±1 near-miss may be a different version of the
    work, and silently matching the wrong version is a wrong-source check.
    Zero hits → None; multiple hits → AMBIGUOUS.
    """
    surname, year = citation
    surname = _fold(surname)
    hits = [
        path
        for path, identity in index.items()
        if identity.get("year") == year
        and any(_surname_matches(surname, a) for a in identity.get("authors", []))
    ]
    if not hits:
        return None
    if len(hits) > 1:
        return AMBIGUOUS
    return hits[0]


def has_year_near_miss(citation: tuple[str, str], index: dict[Path, dict]) -> bool:
    """True if a source matches the surname but is ±1 year off the citation —
    likely a working-paper-vs-published version mismatch. The caller should
    say so rather than guess: checking the wrong version silently is worse
    than leaving the finding unresolved."""
    surname, year = citation
    surname = _fold(surname)
    if not year.isdigit():
        return False
    return any(
        identity.get("year", "").isdigit()
        and abs(int(identity["year"]) - int(year)) == 1
        and any(_surname_matches(surname, a) for a in identity.get("authors", []))
        for identity in index.values()
    )
