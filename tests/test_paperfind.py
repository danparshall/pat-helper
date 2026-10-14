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


def make_source_repo(tmp_path, name="verification"):
    repo = tmp_path / name
    (repo / "papers" / "text").mkdir(parents=True)
    (repo / "docs").mkdir()
    (repo / "papers" / "RahmanR__2026--distributed.pdf").write_bytes(make_pdf("Rahman body"))
    (repo / "papers" / "text" / "RahmanR__2026--distributed.txt").write_text("Rahman text")
    (repo / "papers" / "Hart__1992--nilm.pdf").write_bytes(make_pdf("Hart nonintrusive"))
    (repo / "docs" / "claims_ledger.csv").write_text("SECRET FINDINGS")
    (repo / "PAPER_SUMMARIES.md").write_text("SECRET SUMMARY")
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


# --- collect: copy from another repo's papers/ only -------------------------


def test_collect_copies_pdfs_and_texts_with_provenance(tmp_path):
    repo = make_source_repo(tmp_path)
    lib = pf.Library(tmp_path / "lib")
    added = pf.collect(repo, lib)
    assert sorted(r["id"] for r in added) == ["Hart__1992--nilm", "RahmanR__2026--distributed"]
    assert (lib.pdf_dir / "RahmanR__2026--distributed.pdf").exists()
    # existing extracted text is copied verbatim, missing text is extracted
    assert (lib.text_dir / "RahmanR__2026--distributed.txt").read_text() == "Rahman text"
    assert "Hart nonintrusive" in (lib.text_dir / "Hart__1992--nilm.txt").read_text()
    rec = {r["id"]: r for r in lib.records()}["Hart__1992--nilm"]
    assert rec["origin"] == "copied"
    assert rec["source_path"].endswith("papers/Hart__1992--nilm.pdf")
    assert rec["text_method"] == "pymupdf"
    assert len(rec["pdf_sha256"]) == 64


def test_collect_never_reads_outside_papers(tmp_path):
    repo = make_source_repo(tmp_path)
    lib = pf.Library(tmp_path / "lib")
    pf.collect(repo, lib)
    everything = "".join(
        p.read_text(errors="ignore") for p in (tmp_path / "lib").rglob("*") if p.is_file()
    )
    assert "SECRET" not in everything


def test_collect_is_idempotent(tmp_path):
    repo = make_source_repo(tmp_path)
    lib = pf.Library(tmp_path / "lib")
    pf.collect(repo, lib)
    assert pf.collect(repo, lib) == []
    assert len(lib.records()) == 2


# --- find: local first, then open access ----------------------------------
# A citation is structured (title, first-author surname, year). Live smoke
# tests on 2026-10-14 showed free-text queries + word overlap fetch the WRONG
# paper (Follum's PNNL report for Follum & Pierre; a 2012 Wiley paper for
# Hart 1992), so a candidate must pass title, author and year checks.


def search_ok(*works):
    return httpx.Response(200, json={"results": list(works)})


def test_find_returns_local_hit_without_network(tmp_path):
    repo = make_source_repo(tmp_path)
    lib = pf.Library(tmp_path / "lib")
    pf.collect(repo, lib)

    def boom(request):
        raise AssertionError("network used for a local hit")

    cite = pf.Citation(title="Distributed training", author="Rahman", year=2026)
    result = pf.find(cite, lib, client_for({("api.openalex.org", "/"): boom}))
    assert result.status == "local"
    assert result.record["id"] == "RahmanR__2026--distributed"


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


def test_export_copies_texts_to_sources_folder(tmp_path):
    repo = make_source_repo(tmp_path)
    lib = pf.Library(tmp_path / "lib")
    pf.collect(repo, lib)
    dest = tmp_path / "sources"
    pf.export(["Hart__1992--nilm"], lib, dest)
    assert "Hart nonintrusive" in (dest / "Hart__1992--nilm.txt").read_text()
    manifest = json.loads((dest / "manifest.json").read_text())
    assert manifest[0]["id"] == "Hart__1992--nilm"


def test_export_unknown_id_raises(tmp_path):
    lib = pf.Library(tmp_path / "lib")
    with pytest.raises(KeyError, match="nope"):
        pf.export(["nope"], lib, tmp_path / "sources")
