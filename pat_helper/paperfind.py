"""Paper-finder: fill a library-only paper repo and hand a review its sources.

Three operations, all writing provenance to the library's `index.jsonl`:

- catalog(repo, lib): copy another repo's PAPER_SUMMARIES.md / PAPER_INDEX.md
  verbatim and write one catalog.jsonl row per summary entry, pointing back
  at the source PDF and text. Papers are not copied. Nothing else in the
  repo is read: other repos may hold their own reviews of the same drafts,
  and reading those would contaminate a pat-helper test.
- find(citation, lib, client): library and catalog first; otherwise an OpenAlex
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
import subprocess
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
        self.index_path = self.root / "index.jsonl"  # papers downloaded into the library
        self.catalog_path = self.root / "catalog.jsonl"  # pointers into other repos

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


# --- catalog -----------------------------------------------------------------
# Papers stay in their home repos. The library holds a verbatim copy of each
# repo's PAPER_SUMMARIES.md / PAPER_INDEX.md plus catalog.jsonl, one row per
# summary entry pointing back at the source PDF and text.

CATALOG_FILES = ("PAPER_SUMMARIES.md", "PAPER_INDEX.md")
_FILE_POINTER = re.compile(r"\*{0,2}File:\*{0,2}\s*`([^`]+)`")
_TITLE_LINE = re.compile(r"^\*\*Title:\*\*\s*(.+)$")
_YEAR = re.compile(r"\b(19\d{2}|20\d{2})\b")
_FILE_YEAR = re.compile(r"__(\d{4})(?:--|__)")


def _portable(path: Path) -> str:
    """'~/...' for paths under home, so the catalog works on every machine."""
    try:
        return "~/" + str(path.relative_to(Path.home()))
    except ValueError:
        return str(path)


def _git_head(repo: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return out.stdout.strip()


def _parse_summaries(text: str) -> list[dict]:
    """Split on '### ' headings; keep heading, optional **Title:** line, File pointer."""
    entries, current = [], None
    for lineno, line in enumerate(text.splitlines(), start=1):
        if line.startswith("### "):
            current = {"heading": line[4:].strip(), "line": lineno, "title_line": "", "file": None}
            entries.append(current)
            continue
        if current is None:
            continue
        m = _TITLE_LINE.match(line.strip())
        if m and not current["title_line"]:
            current["title_line"] = m.group(1)
        m = _FILE_POINTER.search(line)
        if m and current["file"] is None:
            current["file"] = m.group(1)
    return entries


def _entry_year(entry: dict) -> int | None:
    for text in (entry["heading"], entry["title_line"]):
        m = _YEAR.search(text)
        if m:
            return int(m.group(1))
    m = _FILE_YEAR.search(entry["file"] or "")
    return int(m.group(1)) if m else None


def catalog(repo: Path, lib: Library) -> list[dict]:
    """Copy repo's summary/index files and (re)write its catalog rows."""
    repo = Path(repo)
    dest = lib.root / "catalogs" / repo.name
    dest.mkdir(parents=True, exist_ok=True)
    for name in CATALOG_FILES:
        if (repo / name).exists():
            shutil.copyfile(repo / name, dest / name)

    sha, now = _git_head(repo), _now()
    rows = []
    summaries = repo / "PAPER_SUMMARIES.md"
    for e in _parse_summaries(summaries.read_text()) if summaries.exists() else []:
        if e["file"]:
            rid = Path(e["file"]).stem
            pdf = repo / "papers" / e["file"]
            text = repo / "papers" / "text" / f"{rid}.txt"
            pdf_path, pdf_exists = _portable(pdf), pdf.exists()
            text_path = _portable(text) if text.exists() else None
        else:  # summary with no File: line — kept visible, never silently dropped
            rid = f"{repo.name}:L{e['line']}"
            pdf_path, pdf_exists, text_path = None, False, None
        rows.append({
            "id": rid,
            "repo": repo.name,
            "heading": e["heading"],
            "title_line": e["title_line"],
            "file": e["file"],
            "year": _entry_year(e),
            "pdf_path": pdf_path,
            "pdf_exists": pdf_exists,
            "text_path": text_path,
            "summary_line": e["line"],
            "source_sha": sha,
            "cataloged_at": now,
        })

    kept = [r for r in catalog_entries(lib) if r["repo"] != repo.name]
    lib.catalog_path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in kept + rows))
    return rows


def catalog_entries(lib: Library) -> list[dict]:
    if not lib.catalog_path.exists():
        return []
    lines = lib.catalog_path.read_text().splitlines()
    return [json.loads(line) for line in lines if line.strip()]


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


def title_coverage(cited: str, haystack: str) -> float:
    """Share of the cited title's words present in a heading (which also
    carries authors and venue, so Jaccard would understate a true match)."""
    wc, wh = set(_words(cited)), set(_words(haystack))
    return len(wc & wh) / len(wc) if wc else 0.0


def _catalog_author_ok(surname: str, entry: dict) -> bool:
    tokens = set(_words_keep_all(f"{entry['heading']} {entry['title_line']}"))
    file_parts = Path(entry["file"]).stem.split("__")[0].split("_") if entry["file"] else []
    return surname in tokens or any(p.lower().startswith(surname) for p in file_parts)


def _local_hit(cite: Citation, lib: Library) -> FindResult | None:
    """Downloaded papers first, then catalog pointers. Same three checks as
    remote candidates: title, author, year."""
    surname = cite.author.lower()
    scored = []
    for rec in lib.records():
        sim = title_similarity(cite.title, rec.get("title", ""))
        if (
            sim >= TITLE_THRESHOLD
            and surname in _author_tokens(rec.get("authors", []))
            and _year_ok(cite.year, rec.get("year"))
        ):
            scored.append((sim, "local", rec))
    for entry in catalog_entries(lib):
        cov = title_coverage(cite.title, f"{entry['heading']} {entry['title_line']}")
        if (
            cov >= TITLE_THRESHOLD
            and _catalog_author_ok(surname, entry)
            and _year_ok(cite.year, entry.get("year"))
        ):
            scored.append((cov, "catalog", entry))
    if not scored:
        return None
    best = max(s for s, _, _ in scored)
    top = [(status, rec) for s, status, rec in scored if s == best]
    if len({_paper_key(rec) for _, rec in top}) > 1:
        where = ", ".join(f"{r.get('repo', 'library')}:{r['id']}" for _, r in top)
        return FindResult("local-ambiguous", detail=f"several papers match: {where}")
    # One paper, possibly held in several repos: prefer a copy with extracted text.
    status, record = max(top, key=lambda t: bool(t[1].get("text_path") or t[0] == "local"))
    return FindResult(status, record=record)


def _paper_key(rec: dict) -> str:
    """Same paper across repos: file stems equal up to case, '-' and '_'."""
    stem = Path(rec["file"]).stem if rec.get("file") else rec["id"]
    return re.sub(r"[-_]+", "", stem.lower())


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
    """Write a review's sources folder: downloaded papers from the library,
    catalog papers read in place from their home repo."""
    downloaded = {r["id"]: r for r in lib.records()}
    cataloged = {r["id"]: r for r in catalog_entries(lib)}
    missing = [i for i in ids if i not in downloaded and i not in cataloged]
    if missing:
        raise KeyError(f"not in library: {', '.join(missing)}")
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    manifest = []
    for i in ids:
        out = dest / f"{i}.txt"
        if i in downloaded:
            shutil.copyfile(lib.text_dir / f"{i}.txt", out)
            manifest.append(downloaded[i])
            continue
        entry = cataloged[i]
        if entry["pdf_path"] is None:
            raise ValueError(f"{i} ({entry['heading']}) has no File pointer in its summary")
        if entry["text_path"]:
            shutil.copyfile(Path(entry["text_path"]).expanduser(), out)
        else:
            out.write_text(extract_text(Path(entry["pdf_path"]).expanduser().read_bytes()))
        manifest.append(entry)
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    return manifest


# --- CLI ---------------------------------------------------------------------


def _default_library() -> Path:
    return Path(os.environ.get("PAPER_LIBRARY", Path.home() / "code" / "paper-library"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="paperfind")
    parser.add_argument("--library", type=Path, default=_default_library())
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("catalog", help="Catalog another repo's PAPER_SUMMARIES/INDEX")
    c.add_argument("repos", type=Path, nargs="+")
    f = sub.add_parser("find", help="Find a paper locally or via open access")
    f.add_argument("--title", required=True)
    f.add_argument("--author", required=True, help="surname of any author")
    f.add_argument("--year", type=int, required=True)
    e = sub.add_parser("export", help="Copy texts into a review's sources folder")
    e.add_argument("ids", nargs="+")
    e.add_argument("--dest", type=Path, required=True)
    args = parser.parse_args(argv)
    lib = Library(args.library)

    if args.command == "catalog":
        for repo in args.repos:
            rows = catalog(repo, lib)
            no_ptr = sum(r["file"] is None for r in rows)
            no_pdf = sum(r["file"] is not None and not r["pdf_exists"] for r in rows)
            no_text = sum(r["pdf_exists"] and r["text_path"] is None for r in rows)
            print(
                f"{repo.name}: {len(rows)} entries ({no_ptr} without File pointer, "
                f"{no_pdf} pointing at a missing PDF, {no_text} without extracted text)"
            )
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
