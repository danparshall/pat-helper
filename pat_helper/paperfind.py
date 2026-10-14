"""Paper-finder: fill a library-only paper repo and hand a review its sources.

Three operations, all writing provenance to the library's `index.jsonl`:

- collect(repo, lib): copy PDFs (and any extracted text) from another repo's
  `papers/` folder. Reads nothing outside `papers/` — other repos may hold
  their own reviews of the same drafts, and reading those would contaminate
  a pat-helper test.
- find(citation, lib, client): local library first; otherwise an OpenAlex
  title search, an open-access PDF (best OA location, any location, or
  arXiv), a check that the bytes really are a PDF, and text extraction. A
  candidate is added only if title, author and year all match the citation;
  otherwise the result says why nothing was added.
- export(ids, lib, dest): copy texts into a per-review sources folder with a
  manifest, the input the source-check stage expects.

CLI: python -m pat_helper.paperfind {collect,find,export} ... (see --help).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pymupdf

OPENALEX_WORKS = "https://api.openalex.org/works"
USER_AGENT = "pat-helper-paperfind/0.1"
TITLE_THRESHOLD = 0.8  # Jaccard similarity of title word sets
YEAR_TOLERANCE = 1  # preprint vs publication year
SEARCH_RESULTS = 25  # the right paper is often not OpenAlex's top hit
SLUG_WORDS = 8
_STOPWORDS = {"the", "and", "for", "with", "from", "into", "are", "its"}
_ARXIV_ABS = re.compile(r"arxiv\.org/abs/([^\s?#]+)")


class Library:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.text_dir = self.root / "papers" / "text"
        self.pdf_dir = self.root / "data" / "pdfs"
        self.index_path = self.root / "index.jsonl"

    def records(self) -> list[dict]:
        if not self.index_path.exists():
            return []
        lines = self.index_path.read_text().splitlines()
        return [json.loads(line) for line in lines if line.strip()]

    def add(self, record: dict, pdf_bytes: bytes, text: str) -> dict:
        self.text_dir.mkdir(parents=True, exist_ok=True)
        self.pdf_dir.mkdir(parents=True, exist_ok=True)
        (self.pdf_dir / f"{record['id']}.pdf").write_bytes(pdf_bytes)
        (self.text_dir / f"{record['id']}.txt").write_text(text)
        with self.index_path.open("a") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")
        return record


@dataclass
class FindResult:
    # local | local-ambiguous | downloaded | no-open-pdf | download-failed
    # | no-confident-match | no-results
    status: str
    record: dict | None = None
    candidate: dict | None = None
    detail: str = ""


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _STOPWORDS]


def _surname(display_name: str) -> str:
    if "," in display_name:  # "Surname, Given"
        return display_name.split(",")[0].strip().split()[-1]
    return display_name.split()[-1]


def paper_id(authors: list[str], year: int | str, title: str) -> str:
    first = _surname(authors[0])
    last = _surname(authors[-1])
    slug = "-".join(_words_keep_all(title)[:SLUG_WORDS])
    return f"{first}_{last}__{year}--{slug}"


def _words_keep_all(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def extract_text(pdf_bytes: bytes) -> str:
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        return "\n".join(page.get_text() for page in doc)


# --- collect -----------------------------------------------------------------


def collect(repo: Path, lib: Library) -> list[dict]:
    repo = Path(repo)
    papers = repo / "papers"
    known = {r["pdf_sha256"] for r in lib.records()}
    added = []
    for pdf in sorted(papers.glob("*.pdf")):
        data = pdf.read_bytes()
        digest = _sha256(data)
        if digest in known:
            continue
        existing_text = papers / "text" / f"{pdf.stem}.txt"
        if existing_text.exists():
            text, method = existing_text.read_text(errors="replace"), "copied"
        else:
            text, method = extract_text(data), "pymupdf"
        record = {
            "id": pdf.stem,
            "origin": "copied",
            "source_repo": repo.name,
            "source_path": str(pdf),
            "pdf_sha256": digest,
            "text_method": method,
            "collected_at": _now(),
        }
        added.append(lib.add(record, data, text))
        known.add(digest)
    return added


# --- find --------------------------------------------------------------------
# A candidate is accepted only if it passes all three checks. Free-text search
# plus word overlap fetched the wrong paper in live tests (2026-10-14), and a
# wrong source is worse than no source.


@dataclass
class Citation:
    title: str
    author: str  # surname of any author, usually the first
    year: int

    def as_dict(self) -> dict:
        return {"title": self.title, "author": self.author, "year": self.year}


def title_similarity(a: str, b: str) -> float:
    """Jaccard similarity of the two titles' word sets."""
    wa, wb = set(_words(a)), set(_words(b))
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def _author_tokens(names: list[str]) -> set[str]:
    return {tok for name in names for tok in _words_keep_all(name)}


def _year_ok(cited: int, found) -> bool:
    try:
        return abs(int(found) - int(cited)) <= YEAR_TOLERANCE
    except (TypeError, ValueError):
        return False


def _parse_id(rid: str) -> tuple[list[str], str, str]:
    """'{First}_{Last}__{Year}--{slug}' -> (author parts, year, slug)."""
    head, _, rest = rid.partition("__")
    year, _, slug = rest.partition("--")
    return head.split("_"), year, slug


def _local_hit(cite: Citation, lib: Library) -> FindResult | None:
    surname = cite.author.lower()
    cite_words = set(_words(cite.title))
    scored = []
    for rec in lib.records():
        if rec.get("title"):
            authors, year, title = rec.get("authors", []), rec.get("year"), rec["title"]
            if surname not in _author_tokens(authors):
                continue
            overlap = title_similarity(cite.title, title)
            if overlap < TITLE_THRESHOLD:
                continue
        else:  # copied record: only the filename-style id is known
            parts, year, slug = _parse_id(rec["id"])
            if not any(p.lower().startswith(surname) for p in parts):
                continue
            slug_words = set(_words(slug.replace("-", " ")))
            overlap = len(cite_words & slug_words) / max(len(cite_words), 1)
            if overlap == 0:
                continue
        if not _year_ok(cite.year, year):
            continue
        scored.append((overlap, rec))
    if not scored:
        return None
    scored.sort(key=lambda t: t[0], reverse=True)
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        ids = ", ".join(r["id"] for _, r in scored)
        return FindResult("local-ambiguous", detail=f"several library papers match: {ids}")
    return FindResult("local", record=scored[0][1])


def _authors(work: dict) -> list[str]:
    return [a["author"]["display_name"] for a in work.get("authorships") or []]


def _accepts(cite: Citation, work: dict) -> tuple[bool, float]:
    sim = title_similarity(cite.title, work.get("display_name") or "")
    ok = (
        sim >= TITLE_THRESHOLD
        and cite.author.lower() in _author_tokens(_authors(work))
        and _year_ok(cite.year, work.get("publication_year"))
    )
    return ok, sim


def _pdf_urls(work: dict) -> list[str]:
    urls = []
    best = work.get("best_oa_location") or {}
    if best.get("pdf_url"):
        urls.append(best["pdf_url"])
    for loc in work.get("locations") or []:
        if loc.get("pdf_url") and loc["pdf_url"] not in urls:
            urls.append(loc["pdf_url"])
    for loc in work.get("locations") or []:
        m = _ARXIV_ABS.search(loc.get("landing_page_url") or "")
        if m:
            url = f"https://arxiv.org/pdf/{m.group(1)}"
            if url not in urls:
                urls.append(url)
    return urls


def find(cite: Citation, lib: Library, client: httpx.Client) -> FindResult:
    local = _local_hit(cite, lib)
    if local:
        return local

    resp = client.get(OPENALEX_WORKS, params={"search": cite.title, "per-page": SEARCH_RESULTS})
    resp.raise_for_status()
    results = resp.json().get("results") or []
    if not results:
        return FindResult("no-results", detail=f"OpenAlex returned nothing for {cite.title!r}")

    judged = [(work, *_accepts(cite, work)) for work in results]
    accepted = sorted((t for t in judged if t[1]), key=lambda t: t[2], reverse=True)
    if not accepted:
        closest = max(judged, key=lambda t: t[2])[0]
        return FindResult(
            "no-confident-match",
            candidate=closest,
            detail="no result matched title, author and year together",
        )
    work, _, sim = accepted[0]

    urls = _pdf_urls(work)
    if not urls:
        return FindResult("no-open-pdf", candidate=work, detail="no open-access PDF location")

    failures = []
    for url in urls:
        try:
            r = client.get(url, follow_redirects=True)
        except httpx.HTTPError as exc:
            failures.append(f"{url}: {type(exc).__name__}")
            continue
        if r.status_code != 200 or not r.content.startswith(b"%PDF"):
            failures.append(f"{url}: HTTP {r.status_code}, not a PDF")
            continue
        authors = _authors(work) or [cite.author]
        record = {
            "id": paper_id(authors, work.get("publication_year", cite.year), work["display_name"]),
            "origin": "openalex",
            "title": work["display_name"],
            "authors": authors,
            "year": work.get("publication_year"),
            "doi": work.get("doi"),
            "openalex_id": work.get("id"),
            "pdf_url": url,
            "pdf_sha256": _sha256(r.content),
            "text_method": "pymupdf",
            "citation": cite.as_dict(),
            "title_similarity": round(sim, 3),
            "retrieved_at": _now(),
        }
        lib.add(record, r.content, extract_text(r.content))
        return FindResult("downloaded", record=record, candidate=work)
    return FindResult("download-failed", candidate=work, detail="; ".join(failures))


# --- export ------------------------------------------------------------------


def export(ids: list[str], lib: Library, dest: Path) -> list[dict]:
    by_id = {r["id"]: r for r in lib.records()}
    missing = [i for i in ids if i not in by_id]
    if missing:
        raise KeyError(f"not in library: {', '.join(missing)}")
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    manifest = []
    for i in ids:
        shutil.copyfile(lib.text_dir / f"{i}.txt", dest / f"{i}.txt")
        manifest.append(by_id[i])
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    return manifest


# --- CLI ---------------------------------------------------------------------


def _default_library() -> Path:
    return Path(os.environ.get("PAPER_LIBRARY", Path.home() / "code" / "paper-library"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="paperfind")
    parser.add_argument("--library", type=Path, default=_default_library())
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("collect", help="Copy papers/ from another repo")
    c.add_argument("repo", type=Path)
    f = sub.add_parser("find", help="Find a paper locally or via open access")
    f.add_argument("--title", required=True)
    f.add_argument("--author", required=True, help="surname of any author")
    f.add_argument("--year", type=int, required=True)
    e = sub.add_parser("export", help="Copy texts into a review's sources folder")
    e.add_argument("ids", nargs="+")
    e.add_argument("--dest", type=Path, required=True)
    args = parser.parse_args(argv)
    lib = Library(args.library)

    if args.command == "collect":
        added = collect(args.repo, lib)
        print(f"{len(added)} added from {args.repo}")
    elif args.command == "find":
        with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=60) as client:
            result = find(Citation(args.title, args.author, args.year), lib, client)
        print(result.status, (result.record or {}).get("id", ""), result.detail)
        if result.candidate and not result.record:
            print("  candidate:", result.candidate.get("display_name"), result.candidate.get("doi"))
    elif args.command == "export":
        export(args.ids, lib, args.dest)
        print(f"{len(args.ids)} exported to {args.dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
