"""Paper-finder: fill a library-only paper repo and hand reviews a sources folder.

Plan/convo: docs/active/paper-finder/. Network calls go through an injected
httpx client; tests use httpx.MockTransport with canned OpenAlex responses and
real PDFs generated with pymupdf — the parsing, selection, provenance and
file-layout logic under test is ours, not the transport's.
"""

from __future__ import annotations

import json

import httpx
import pymupdf as fitz
import pytest

from pat_helper import paperfind as pf

# --- helpers -------------------------------------------------------------


def make_pdf(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


SUMMARIES = """# PAPER_SUMMARIES

### Rahman (2026) — "Does Distributed Training Undermine Compute Governance?"
**File:** `RahmanR__2026--distributed.pdf` | **Text:** `text/RahmanR__2026--distributed.txt`
Rahman summary body.

### Hart (1992) — "Nonintrusive Appliance Load Monitoring"

- Authors: George Hart
- File: `Hart__1992--nilm.pdf`

### vending-bench

**Title:** Vending-Bench: Long-Term Coherence of Agents (Backlund & Petersson, 2025)

- **File:** `Backlund_Petersson__2025--vending_bench.pdf`

### Orphan (2020) — "Entry Whose PDF Is Missing"
- File: `Orphan__2020--missing.pdf`

### Davis / Dallas Fed (2026) — "Wage Data Entry With No File Line"
Summary only; the repo never recorded a PDF.
"""


def make_source_repo(tmp_path, name="verification"):
    repo = tmp_path / name
    (repo / "papers" / "text").mkdir(parents=True)
    (repo / "docs").mkdir()
    (repo / "papers" / "RahmanR__2026--distributed.pdf").write_bytes(make_pdf("Rahman body"))
    (repo / "papers" / "text" / "RahmanR__2026--distributed.txt").write_text("Rahman text")
    (repo / "papers" / "Hart__1992--nilm.pdf").write_bytes(make_pdf("Hart nonintrusive"))
    (repo / "papers" / "Backlund_Petersson__2025--vending_bench.pdf").write_bytes(make_pdf("vb"))
    (repo / "PAPER_SUMMARIES.md").write_text(SUMMARIES)
    (repo / "PAPER_INDEX.md").write_text("| Rahman (2026) | one line |\n")
    (repo / "docs" / "claims_ledger.csv").write_text("SECRET FINDINGS")
    (repo / "STATUS.md").write_text("SECRET STATUS")
    return repo


def openalex_work(title, year=2024, authors=("Ada Lovelace", "Bo Chen"), pdf_url=None,
                  locations=(), doi="https://doi.org/10.1/x", wid="https://openalex.org/W1"):
    return {
        "id": wid,
        "doi": doi,
        "display_name": title,
        "publication_year": year,
        "authorships": [{"author": {"display_name": a}} for a in authors],
        "best_oa_location": {"pdf_url": pdf_url} if pdf_url else None,
        "locations": list(locations),
    }


def client_for(routes: dict):
    """routes: {(host, path_prefix): httpx.Response or callable(request)}"""

    def handler(request: httpx.Request):
        for (host, prefix), resp in routes.items():
            if request.url.host == host and request.url.path.startswith(prefix):
                return resp(request) if callable(resp) else resp
        return httpx.Response(404)

    return httpx.Client(transport=httpx.MockTransport(handler))


# --- library layout -------------------------------------------------------


def test_library_layout_and_empty_index(tmp_path):
    lib = pf.Library(tmp_path / "lib")
    assert lib.text_dir == tmp_path / "lib" / "papers" / "text"
    assert lib.pdf_dir == tmp_path / "lib" / "data" / "pdfs"
    assert lib.records() == []


def test_paper_id_follows_naming_format():
    assert pf.paper_id(["Ada Lovelace", "Bo Chen"], 2024, "Detecting Hidden ML Training!") == (
        "Lovelace_Chen__2024--detecting-hidden-ml-training"
    )
    assert pf.paper_id(["Ada Lovelace"], 2024, "Solo") == "Lovelace_Lovelace__2024--solo"


def test_paper_id_handles_surname_comma_given_names():
    """OpenAlex returned 'Grattafiori, Aaron' for Llama 3 (live, 2026-10-14)."""
    assert pf.paper_id(["Grattafiori, Aaron", "Valko, Michal"], 2024, "The Llama 3 Herd") == (
        "Grattafiori_Valko__2024--the-llama-3-herd"
    )


# --- catalog: point at another repo's papers, don't copy them ----------------
# Dan (2026-10-14): copy each repo's PAPER_SUMMARIES/PAPER_INDEX, not its
# papers; every entry must point back to the source PDF and text.


def test_catalog_copies_summaries_and_index_verbatim(tmp_path):
    repo = make_source_repo(tmp_path)
    lib = pf.Library(tmp_path / "lib")
    pf.catalog(repo, lib)
    assert (lib.root / "catalogs" / "verification" / "PAPER_SUMMARIES.md").read_text() == SUMMARIES
    assert (lib.root / "catalogs" / "verification" / "PAPER_INDEX.md").exists()


def test_catalog_entries_point_back_to_source_files(tmp_path):
    repo = make_source_repo(tmp_path)
    lib = pf.Library(tmp_path / "lib")
    rows = pf.catalog(repo, lib)
    entries = {e["file"]: e for e in rows if e["file"]}
    assert set(entries) == {
        "RahmanR__2026--distributed.pdf",
        "Hart__1992--nilm.pdf",
        "Backlund_Petersson__2025--vending_bench.pdf",
        "Orphan__2020--missing.pdf",
    }
    rahman = entries["RahmanR__2026--distributed.pdf"]
    assert rahman["pdf_path"] == str(repo / "papers" / "RahmanR__2026--distributed.pdf")
    assert rahman["text_path"] == str(repo / "papers" / "text" / "RahmanR__2026--distributed.txt")
    assert rahman["year"] == 2026
    assert rahman["repo"] == "verification"
    assert entries["Hart__1992--nilm.pdf"]["text_path"] is None  # no extracted text yet
    assert entries["Backlund_Petersson__2025--vending_bench.pdf"]["year"] == 2025
    assert entries["Orphan__2020--missing.pdf"]["pdf_exists"] is False
    assert len(pf.catalog_entries(lib)) == 5


def test_catalog_keeps_entries_without_file_pointer_visible(tmp_path):
    """67 real entries lacked a File: line and were silently dropped (2026-10-14)."""
    repo = make_source_repo(tmp_path)
    lib = pf.Library(tmp_path / "lib")
    [row] = [r for r in pf.catalog(repo, lib) if r["file"] is None]
    assert row["heading"].startswith("Davis / Dallas Fed (2026)")
    assert row["pdf_path"] is None and row["text_path"] is None
    assert row["pdf_exists"] is False
    assert row["id"] == "verification:L21"  # repo + summary line: unique, findable
    with pytest.raises(ValueError, match="no File pointer"):
        pf.export([row["id"]], lib, tmp_path / "sources")


def test_catalog_paths_under_home_are_portable(tmp_path, monkeypatch):
    """Dan's Macs use /Users/dan, tarragon /home/dan: store '~/...'."""
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = make_source_repo(tmp_path / "code")
    lib = pf.Library(tmp_path / "lib")
    row = next(r for r in pf.catalog(repo, lib) if r["file"] == "RahmanR__2026--distributed.pdf")
    assert row["pdf_path"] == "~/code/verification/papers/RahmanR__2026--distributed.pdf"
    pf.export(["RahmanR__2026--distributed"], lib, tmp_path / "sources")
    assert (tmp_path / "sources" / "RahmanR__2026--distributed.txt").read_text() == "Rahman text"


def test_catalog_copies_no_papers_and_reads_nothing_else(tmp_path):
    repo = make_source_repo(tmp_path)
    lib = pf.Library(tmp_path / "lib")
    pf.catalog(repo, lib)
    files = [p for p in (tmp_path / "lib").rglob("*") if p.is_file()]
    assert not any(p.suffix == ".pdf" for p in files)
    assert "SECRET" not in "".join(p.read_text(errors="ignore") for p in files)


def test_catalog_rerun_replaces_that_repos_entries(tmp_path):
    repo = make_source_repo(tmp_path)
    other = make_source_repo(tmp_path, name="econ-impact")
    lib = pf.Library(tmp_path / "lib")
    pf.catalog(repo, lib)
    pf.catalog(other, lib)
    pf.catalog(repo, lib)
    repos = [e["repo"] for e in pf.catalog_entries(lib)]
    assert repos.count("verification") == 5
    assert repos.count("econ-impact") == 5


def test_same_paper_in_two_repos_is_not_ambiguous(tmp_path):
    """Rahman 2026 sits in verification and policy-levers, with file names
    differing only in '-' vs '_' (live, 2026-10-14)."""
    a = make_source_repo(tmp_path, name="verification")
    b = make_source_repo(tmp_path, name="policy-levers")
    src = b / "papers" / "RahmanR__2026--distributed.pdf"
    src.rename(b / "papers" / "RahmanR__2026--distributed_.pdf")
    (b / "PAPER_SUMMARIES.md").write_text(
        SUMMARIES.replace("RahmanR__2026--distributed.pdf", "RahmanR__2026--distributed_.pdf")
    )
    lib = pf.Library(tmp_path / "lib")
    pf.catalog(a, lib)
    pf.catalog(b, lib)
    cite = pf.Citation("Does distributed training undermine compute governance?", "Rahman", 2026)
    result = pf.find(cite, lib, _no_network())
    assert result.status == "catalog"
    assert result.record["text_path"]  # prefers the copy that has extracted text


# --- find: local first, then open access ----------------------------------
# A citation is structured (title, first-author surname, year). Live smoke
# tests on 2026-10-14 showed free-text queries + word overlap fetch the WRONG
# paper (Follum's PNNL report for Follum & Pierre; a 2012 Wiley paper for
# Hart 1992), so a candidate must pass title, author and year checks.


def search_ok(*works):
    return httpx.Response(200, json={"results": list(works)})


def _no_network():
    def boom(request):
        raise AssertionError("network used for a local hit")

    return client_for({("api.openalex.org", "/"): boom})


def test_find_returns_catalog_pointer_without_network(tmp_path):
    repo = make_source_repo(tmp_path)
    lib = pf.Library(tmp_path / "lib")
    pf.catalog(repo, lib)
    cite = pf.Citation(
        title="Does distributed training undermine compute governance?", author="Rahman", year=2026
    )
    result = pf.find(cite, lib, _no_network())
    assert result.status == "catalog"
    assert result.record["pdf_path"] == str(repo / "papers" / "RahmanR__2026--distributed.pdf")


def test_find_catalog_needs_author_and_year_too(tmp_path):
    repo = make_source_repo(tmp_path)
    lib = pf.Library(tmp_path / "lib")
    pf.catalog(repo, lib)
    work = openalex_work("Nonintrusive Appliance Load Monitoring", year=1992, authors=("X Y",))
    client = client_for({("api.openalex.org", "/works"): search_ok(work)})
    wrong_author = pf.Citation("Nonintrusive appliance load monitoring", "Kolter", 1992)
    assert pf.find(wrong_author, lib, client).status != "catalog"
    wrong_year = pf.Citation("Nonintrusive appliance load monitoring", "Hart", 2005)
    assert pf.find(wrong_year, lib, client).status != "catalog"


def test_find_downloads_open_access_pdf_and_records_provenance(tmp_path):
    lib = pf.Library(tmp_path / "lib")
    work = openalex_work(
        "Detection of Periodic Forced Oscillations in Power Systems",
        year=2015,
        authors=("Jim Follum", "John Pierre"),
        pdf_url="https://example.org/follum.pdf",
    )
    client = client_for({
        ("api.openalex.org", "/works"): search_ok(work),
        ("example.org", "/follum.pdf"): httpx.Response(200, content=make_pdf("forced oscillation")),
    })
    cite = pf.Citation(
        title="Detection of periodic forced oscillations in power systems",
        author="Follum",
        year=2015,
    )
    result = pf.find(cite, lib, client)
    assert result.status == "downloaded"
    rid = "Follum_Pierre__2015--detection-of-periodic-forced-oscillations-in-power-systems"
    assert result.record["id"] == rid
    assert "forced oscillation" in (lib.text_dir / f"{rid}.txt").read_text()
    rec = lib.records()[0]
    assert rec["origin"] == "openalex"
    assert rec["pdf_url"] == "https://example.org/follum.pdf"
    assert rec["openalex_id"] == "https://openalex.org/W1"
    assert rec["doi"] == "https://doi.org/10.1/x"
    assert rec["citation"] == {"title": cite.title, "author": "Follum", "year": 2015}
    assert "retrieved_at" in rec


def test_find_picks_the_matching_result_not_the_top_ranked(tmp_path):
    lib = pf.Library(tmp_path / "lib")
    decoy = openalex_work(
        "Textual Aspect Sentiment Analysis Based on Llama-3",
        pdf_url="https://example.org/decoy.pdf",
        wid="https://openalex.org/W0",
    )
    real = openalex_work(
        "The Llama 3 Herd of Models",
        authors=("Aaron Grattafiori", "Zhiyu Ma"),
        locations=[{"pdf_url": None, "landing_page_url": "https://arxiv.org/abs/2407.21783"}],
    )
    client = client_for({
        ("api.openalex.org", "/works"): search_ok(decoy, real),
        ("arxiv.org", "/pdf/2407.21783"): httpx.Response(200, content=make_pdf("llama herd")),
    })
    cite = pf.Citation(title="The Llama 3 Herd of Models", author="Grattafiori", year=2024)
    result = pf.find(cite, lib, client)
    assert result.status == "downloaded"
    assert lib.records()[0]["pdf_url"] == "https://arxiv.org/pdf/2407.21783"


def test_find_rejects_candidate_missing_cited_author(tmp_path):
    """Same-looking title by different authors is a different source."""
    lib = pf.Library(tmp_path / "lib")
    work = openalex_work(
        "Detection of Periodic Forced Oscillations in Power Systems",
        year=2015,
        authors=("USDOE", "Jim Follum"),
        pdf_url="https://example.org/f.pdf",
    )
    client = client_for({
        ("api.openalex.org", "/works"): search_ok(work),
        ("example.org", "/f.pdf"): httpx.Response(200, content=make_pdf("x")),
    })
    cite = pf.Citation(
        title="Detection of periodic forced oscillations in power systems",
        author="Pierre",
        year=2015,
    )
    assert pf.find(cite, lib, client).status == "no-confident-match"
    assert lib.records() == []


def test_find_rejects_title_superset(tmp_path):
    """Hart 1992 must not resolve to 'NILM based on integer programming'."""
    lib = pf.Library(tmp_path / "lib")
    work = openalex_work(
        "Nonintrusive appliance load monitoring based on integer programming",
        year=1992,
        authors=("George Hart",),
        pdf_url="https://example.org/h.pdf",
    )
    client = client_for({
        ("api.openalex.org", "/works"): search_ok(work),
        ("example.org", "/h.pdf"): httpx.Response(200, content=make_pdf("x")),
    })
    cite = pf.Citation(title="Nonintrusive appliance load monitoring", author="Hart", year=1992)
    assert pf.find(cite, lib, client).status == "no-confident-match"


def test_find_rejects_year_mismatch_beyond_one(tmp_path):
    lib = pf.Library(tmp_path / "lib")
    work = openalex_work("Solar Flares", year=2010, authors=("Ada Lovelace",),
                         pdf_url="https://example.org/s.pdf")
    client = client_for({
        ("api.openalex.org", "/works"): search_ok(work),
        ("example.org", "/s.pdf"): httpx.Response(200, content=make_pdf("x")),
    })
    assert pf.find(pf.Citation("Solar flares", "Lovelace", 2015), lib, client).status == (
        "no-confident-match"
    )


def test_find_accepts_year_off_by_one(tmp_path):
    """Preprint vs publication year."""
    lib = pf.Library(tmp_path / "lib")
    work = openalex_work("Solar Flares", year=2014, authors=("Ada Lovelace",),
                         pdf_url="https://example.org/s.pdf")
    client = client_for({
        ("api.openalex.org", "/works"): search_ok(work),
        ("example.org", "/s.pdf"): httpx.Response(200, content=make_pdf("x")),
    })
    assert pf.find(pf.Citation("Solar flares", "Lovelace", 2015), lib, client).status == (
        "downloaded"
    )


def test_find_reports_metadata_only_when_no_open_pdf(tmp_path):
    lib = pf.Library(tmp_path / "lib")
    work = openalex_work("Electric Power Distribution Handbook", authors=("Tom Short",))
    client = client_for({("api.openalex.org", "/works"): search_ok(work)})
    cite = pf.Citation("Electric power distribution handbook", "Short", 2024)
    result = pf.find(cite, lib, client)
    assert result.status == "no-open-pdf"
    assert result.candidate["display_name"] == "Electric Power Distribution Handbook"
    assert lib.records() == []


def test_find_rejects_non_pdf_download(tmp_path):
    """Paywalls and bot walls often return HTML with a 200."""
    lib = pf.Library(tmp_path / "lib")
    work = openalex_work("Some Paper", pdf_url="https://example.org/p.pdf")
    client = client_for({
        ("api.openalex.org", "/works"): search_ok(work),
        ("example.org", "/p.pdf"): httpx.Response(200, content=b"<html>Access denied</html>"),
    })
    result = pf.find(pf.Citation("Some paper", "Lovelace", 2024), lib, client)
    assert result.status == "download-failed"
    assert lib.records() == []


# --- export: per-review sources folder -------------------------------------


def test_export_reads_catalog_sources_in_place(tmp_path):
    """Catalog ids are PDF stems; text comes from the source repo (extracted if
    the repo has none), and the manifest keeps the pointer."""
    repo = make_source_repo(tmp_path)
    lib = pf.Library(tmp_path / "lib")
    pf.catalog(repo, lib)
    dest = tmp_path / "sources"
    pf.export(["RahmanR__2026--distributed", "Hart__1992--nilm"], lib, dest)
    assert (dest / "RahmanR__2026--distributed.txt").read_text() == "Rahman text"
    assert "Hart nonintrusive" in (dest / "Hart__1992--nilm.txt").read_text()
    manifest = {m["id"]: m for m in json.loads((dest / "manifest.json").read_text())}
    assert manifest["Hart__1992--nilm"]["pdf_path"] == str(repo / "papers" / "Hart__1992--nilm.pdf")


def test_export_downloaded_record(tmp_path):
    lib = pf.Library(tmp_path / "lib")
    work = openalex_work("Solar Flares", authors=("Ada Lovelace",), pdf_url="https://example.org/s.pdf")
    client = client_for({
        ("api.openalex.org", "/works"): search_ok(work),
        ("example.org", "/s.pdf"): httpx.Response(200, content=make_pdf("sunspots")),
    })
    rid = pf.find(pf.Citation("Solar flares", "Lovelace", 2024), lib, client).record["id"]
    pf.export([rid], lib, tmp_path / "sources")
    assert "sunspots" in (tmp_path / "sources" / f"{rid}.txt").read_text()


def test_export_unknown_id_raises(tmp_path):
    lib = pf.Library(tmp_path / "lib")
    with pytest.raises(KeyError, match="nope"):
        pf.export(["nope"], lib, tmp_path / "sources")
