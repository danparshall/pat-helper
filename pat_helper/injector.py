"""Planted-error defect injection for the validation harness.

Takes a directory of .tex sources and a defect list; writes a mutated copy
and returns a manifest locating every planted defect, so recall can be
scored later (did the review pipeline find what we planted?).
"""

from __future__ import annotations

import shutil
from pathlib import Path


def inject(src_dir: Path, defects: list[dict], out_dir: Path) -> list[dict]:
    """Apply defects to a copy of src_dir; return a manifest with locations.

    Each defect: {id, file, original, mutated, ...}. The first occurrence of
    `original` in `file` is replaced by `mutated`. Missing text is a hard
    error — a silently unplanted defect would corrupt recall scoring.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    for f in src_dir.iterdir():
        if f.is_file():
            shutil.copy(f, out_dir / f.name)

    manifest: list[dict] = []
    for defect in defects:
        target = out_dir / defect["file"]
        if not target.exists():
            raise ValueError(f"defect {defect['id']!r}: file {defect['file']!r} not found")
        text = target.read_text()
        pos = text.find(defect["original"])
        if pos == -1:
            raise ValueError(
                f"defect {defect['id']!r}: original text not found in {defect['file']!r}"
            )
        line = text.count("\n", 0, pos) + 1
        target.write_text(
            text[:pos] + defect["mutated"] + text[pos + len(defect["original"]) :]
        )
        manifest.append(
            {
                "id": defect["id"],
                "file": defect["file"],
                "line": line,
                "original": defect["original"],
                "mutated": defect["mutated"],
                "lens_expected": defect.get("lens_expected"),
                "description": defect.get("description"),
            }
        )
    return manifest
