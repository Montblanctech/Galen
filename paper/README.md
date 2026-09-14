# Galen Phase 2 preprint — LaTeX scaffold

ACL-style arXiv-ready port of `../paper_draft.md`, with bibliography from `references.bib`.

## Engine & Greek

**Build with XeLaTeX** (not pdfLaTeX).

- Unicode polytonic Greek is entered directly in `main.tex`.
- Main font: **Times New Roman** (Windows; covers polytonic Greek).
- ACL officially supports XeLaTeX/LuaLaTeX for non-Latin scripts (`acl_lualatex.tex` in the upstream style repo). We chose XeLaTeX + `fontspec` + Times New Roman for a clean offline Windows build without installing extra Greek font packages.

## Vendored ACL style

From [acl-org/acl-style-files](https://github.com/acl-org/acl-style-files) (master at vendoring time):

- `acl.sty`
- `acl_natbib.bst`

Bibliography uses ACL natbib (`\citep` / `\citet`) via `\bibliography{references}`.

## Build command (exact)

From this directory (`paper/`):

```bash
xelatex -interaction=nonstopmode main.tex
bibtex main
xelatex -interaction=nonstopmode main.tex
xelatex -interaction=nonstopmode main.tex
```

Or with latexmk:

```bash
latexmk -xelatex -interaction=nonstopmode main.tex
```

Output: `main.pdf` (verified XeLaTeX builds: 5 pages on 2026-07-25; §5 machine-bounded accuracy
added 2026-08-27; acknowledgments added 2026-09-13, now 7 pages).

## TODOs

None. The former `\papertodo` H3 accuracy blocker was cleared 2026-08-27: §5 now reports the
machine-bounded range (Morpheus admissibility floor / Stanza agreement / LSJ-citation rare-stratum
gold; sources in `../galen-density-map/data/qc/h3m/`). The `\papertodo` macro was removed with it.
`references.bib` here is a copy of the root `../references.bib` — edit the root file and re-copy
(new keys 2026-08-27: `qi-etal-2020-stanza`, `crane-1991-morpheus`).

MQM / Galen-MT citation resolved: `galen-mt-mqm-2026` → arXiv:2602.24119 (Zainaldin et al., 2026).

## Dependencies

- TeX Live or MiKTeX with XeLaTeX
- Packages used beyond the ACL bundle: `fontspec`, `microtype`, `graphicx`, `booktabs`, `xcolor`, `enumitem` (auto-installed by MiKTeX on first build if enabled)
- System font: Times New Roman (Consolas for monospace)
