# Source check (strict mode)

You have in front of you the full text of a SOURCE that a working paper
cites. Another reviewer flagged the paper's characterization of this source
as **unverifiable** — the claim could not be confirmed or refuted from the
paper's own text. You can now settle it: you are reading the actual source.

The critique below tells you what the paper claims about the source and why
the reviewer was suspicious. Answer one question: **does the source support
the critique, or does it exonerate the paper?**

Work in this order:

1. **Identify the source from its own text.** Report its authors, year, and
   title as printed — not what the critique says they should be. If the
   document you are reading is not the work the critique cites (wrong paper,
   different version, different year), say so via
   `identity_matches_citation: false` and stop at "unresolved"; a verdict
   from the wrong source is worse than no verdict.
2. **Find the load-bearing passage.** Locate what the source actually says
   about the disputed claim. Copy it VERBATIM into `source_quote` — it will
   be mechanically checked against the source text, and a resolution whose
   quote cannot be located will not be honored.
3. **Resolve.**

Resolution. A critique usually makes several distinct charges — check each
one against the source separately before choosing:

- "critique-confirmed": the source, read directly, shows the paper's
  characterization is wrong in the way the critique alleges (misstated
  number, inverted direction, construct mismatch, overclaimed scope). The
  critique was right.
- "critique-narrowed": the source kills the critique's central charge, but
  at least one actionable point survives contact with the text — for
  example, the number and its causal story check out, yet the paper states
  a scoped result (one domain, one population, one metric) in unscoped
  language. The author still wants that reminder; do not bury it. Say
  explicitly which charges died and which survive, and quote the passage
  that settles the surviving point.
- "critique-contradicted": EVERY substantive charge fails — the critique's
  suspicion dissolves entirely on contact with the actual text, leaving
  nothing an author would act on. Quote the passage that exonerates the
  paper. If you find yourself writing "minor caveat" in your reasoning,
  that caveat is usually a surviving point: use "critique-narrowed".
- "unresolved": the source does not settle it — the relevant material is
  absent, ambiguous, or you are not confident this is the right document.
  When in doubt, resolve nothing: "unresolved" keeps the finding flagged for
  the author, which is the safe failure mode.

Be specific in your reasoning: quote and cite what the source says, and state
what the paper claimed it says.
