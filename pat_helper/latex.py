"""LaTeX loader: resolve \\input, strip comments, keep a line map.

The flattened text is what lens models see and what quotes are checked
against; the line map converts an offset in the flattened text back to a
(file, line) location in the original sources.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from pat_helper.models import SourceLocation

# % starts a comment unless escaped as \%
_COMMENT_RE = re.compile(r"(?<!\\)%.*$")
_INPUT_RE = re.compile(r"\\input\{([^}]+)\}")
_BEGIN_DOC_RE = re.compile(r"\\begin\{document\}")
_END_DOC_RE = re.compile(r"\\end\{document\}")

MAX_INPUT_DEPTH = 10


@dataclass
class FlattenedPaper:
    name: str
    text: str
    line_origins: list[SourceLocation]  # one entry per line of `text`

    def locate(self, offset: int) -> SourceLocation:
        """Map an offset into the flattened text to a source (file, line)."""
        if not 0 <= offset <= len(self.text):
            raise ValueError(f"offset {offset} out of range")
        line_idx = self.text.count("\n", 0, offset)
        return self.line_origins[min(line_idx, len(self.line_origins) - 1)]


def _strip_comment(line: str) -> str:
    return _COMMENT_RE.sub("", line).rstrip()


def _flatten_file(path: Path, root: Path, depth: int = 0) -> list[tuple[str, SourceLocation]]:
    if depth > MAX_INPUT_DEPTH:
        raise ValueError(f"\\input nesting deeper than {MAX_INPUT_DEPTH} at {path}")
    out: list[tuple[str, SourceLocation]] = []
    rel = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
    for lineno, raw in enumerate(path.read_text().splitlines(), start=1):
        line = _strip_comment(raw)
        loc = SourceLocation(file=rel, line=lineno)
        m = _INPUT_RE.search(line)
        if m:
            before = line[: m.start()].strip()
            after = line[m.end() :].strip()
            if before:
                out.append((before, loc))
            child_name = m.group(1)
            child = (path.parent / child_name).with_suffix(".tex")
            if not child.exists():
                child = path.parent / child_name  # already had an extension
            if not child.exists():
                raise FileNotFoundError(f"\\input{{{child_name}}} in {rel}:{lineno} not found")
            out.extend(_flatten_file(child, root, depth + 1))
            if after:
                out.append((after, loc))
        else:
            out.append((line, loc))
    return out


def _strip_document_envelope(
    lines: list[tuple[str, SourceLocation]],
) -> list[tuple[str, SourceLocation]]:
    """Drop preamble (before \\begin{document}) and postamble (from \\end{document}).

    Pandoc-generated .tex files carry ~50 lines of package-loading boilerplate
    before the actual content; keeping them in flattened text taxes lens agents'
    context budget on material a reviewer would never comment on. Fragments
    without either marker (e.g. an \\input'd child, or a hand-authored snippet)
    pass through unchanged.
    """
    begin = next((i for i, (ln, _) in enumerate(lines) if _BEGIN_DOC_RE.search(ln)), None)
    end = next((i for i, (ln, _) in enumerate(lines) if _END_DOC_RE.search(ln)), None)
    start = begin + 1 if begin is not None else 0
    stop = end if end is not None else len(lines)
    return lines[start:stop]


def load_text_source(path: str | Path) -> FlattenedPaper:
    """Load a plain-text file (e.g. a pdftotext extraction) as a FlattenedPaper.

    Source texts must NOT go through `load_paper`: its LaTeX comment-stripping
    would truncate any line containing a bare '%' (ubiquitous in extracted
    econ text). No flattening, no envelope stripping — the text as-is, with a
    line map so quote grounding can report (file, line) locations.
    """
    p = Path(path).resolve()
    lines = p.read_text(errors="replace").splitlines()
    return FlattenedPaper(
        name=p.stem,
        text="\n".join(lines),
        line_origins=[SourceLocation(file=p.name, line=i) for i in range(1, len(lines) + 1)],
    )


def load_paper(main_tex: str | Path) -> FlattenedPaper:
    main = Path(main_tex).resolve()
    lines = _strip_document_envelope(_flatten_file(main, main.parent))
    return FlattenedPaper(
        name=main.stem,
        text="\n".join(line for line, _ in lines),
        line_origins=[loc for _, loc in lines],
    )
