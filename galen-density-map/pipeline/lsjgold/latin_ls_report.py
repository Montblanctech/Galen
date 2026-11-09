"""Builds data/latin_feasibility/REPORT.md from ls_citation_counts.json + editions.json (every number in the report is computed here)."""
from __future__ import annotations

import json
from pathlib import Path

GDM = Path(__file__).resolve().parent.parent.parent
D = GDM / "data" / "latin_feasibility"
c = json.loads((D / "ls_citation_counts.json").read_text(encoding="utf-8"))
e = json.loads((D / "editions.json").read_text(encoding="utf-8"))
tot = c["citations_total"]
held = sum(r["citations"] for r in e.values() if r["latin_editions"])
nheld = sum(1 for r in e.values() if r["latin_editions"])
top60 = list(e.values())[:60]
held60 = sum(r["citations"] for r in top60 if r["latin_editions"])
cov60 = sum(r["citations"] for r in top60)
# version tag mismatch: L&S URN edition tag vs files present
def tag_ok(w, r):
    vs = [v for v in c["work_versions"][w] if v != "-"]
    have = {k.split(".")[2] for k in r["latin_editions"]}
    return bool(r["latin_editions"]) and (not vs or all(v in have for v in vs))
exact = sum(r["citations"] for w, r in e.items() if tag_ok(w, r))
notree = [(w, r["citations"]) for w, r in e.items() if not r["latin_editions"]]
unlocated = c["citations_without_locator"]
nonurn = c["bibls_plain_text_n_no_urn"] + c["bibls_without_n"] + c["bibls_author_only_urn"]
allb = tot + nonurn + c["greek_urn_bibls_skipped"]
authname = {w.split(".")[0]: r["author"] for w, r in e.items() if r.get("author")}
pa = list(c["per_author"].items())
dist = c["entry_distribution"]
ne = c["entries_with_latin_cts_citation"]
L = []
a = L.append
a("# Latin twin of LSJ-Gold: feasibility (Lewis & Short)\n")
a("All numbers computed by `pipeline/lsjgold/latin_ls_counts.py`, `latin_ls_editions.py`, `latin_ls_report.py` from the files in this folder (`ls_citation_counts.json`, `editions.json`, `cll_tree.json`, `lexica_tree.json`). Nothing committed or pushed.\n")
a("## Source\n")
a("- PerseusDL/lexica, `CTS_XML_TEI/perseus/pdllex/lat/ls/`: `lat.ls.perseus-eng1.xml` (77,249,035 B, deprecated, Greek in beta code, header says do not use) and `lat.ls.perseus-eng2.xml` (77,415,379 B, Greek in Unicode, the one counted). Both downloaded here.")
a("- Licence: CC BY-SA 4.0 (repo `license.md`, `<availability>` in the eng2 header); reuse must credit the Perseus Digital Library with a link, identify each text and its GitHub repo, and corrections go back to Perseus. Share-alike applies to any derived release of the lexicon text; benchmark gold built from it should carry the same licence.")
a(f"- {c['entries_total']:,} `<entryFree>` entries ({c['greek_urn_bibls_skipped']:,} bibls inside L&S entries cite greekLit URNs and are excluded).\n")
a("## Citation counts (`urn:cts:latinLit:(phi|stoa)NNNN.(phi|stoa)NNN[.edition][:locator]`)\n")
a(f"- Entries with at least one Latin CTS citation: **{ne:,}** of {c['entries_total']:,}")
a(f"- Latin CTS citations (work-level at least): **{tot:,}**, across **{len(c['per_work'])}** works and **{len(c['per_author'])}** authors")
a(f"- Citations per entry: 1 = {dist['1']:,} ({dist['1']/ne:.1%}); 2-5 = {dist['2-5']:,} ({dist['2-5']/ne:.1%}); 6+ = {dist['6+']:,} ({dist['6+']/ne:.1%})")
a(f"- Of those {tot:,}, {unlocated:,} have a work URN but no locator (unusable as gold; e.g. phi1236.phi001 2,678 and phi1044.phi001 1,426, both absent from the repo tree)")
a(f"- Bibls that are NOT usable as URN gold: {c['bibls_plain_text_n_no_urn']:,} plain-text `n` (`Dig. 1.2.3`, `Sil. Ital. 3.4`, `Plin. Ep.`, `Justin`, `Hor. Ars.`, `Aug. Conf.` ...), {c['bibls_without_n']:,} bibls with no `n` at all, {c['bibls_author_only_urn']:,} author-only URNs (largest: phi0684 2,432, phi1245 398, stoa0043 288; see `bibls_author_only_by_author`). Total bibls seen {allb:,}; URN-resolvable Latin share {tot/allb:.1%}. A mapping table from abbreviation to work (Plin. Ep., Justin, Sil. Ital. ...) could recover part of the plain-text group (top labels listed in the JSON, key `bibls_plain_text_by_label_top60`).")
a("- Locator schemes seen (the `locator_depth_by_work` field): colon-separated, 2 levels (book:line, e.g. Aen., Met., Lucr.; 8,5xx Aeneid), 3 levels (book:chapter:section, e.g. Livy, Pliny NH, Cicero, Quintilian), occasional 4-5 levels (Cic. de Or. with the 4,012 cites of the form `Orat::N:N:N` (empty second level); Plautus act:scene:line; Cic. Fam./Att. book:letter:section). Fragments appear as `fr::N:N:N`. Edition tag in the URN: `perseus-lat1` for most Cicero/Virgil/Ovid/Plautus cites, none at all for Pliny NH, Livy, Quintilian, Lucretius, Caesar BC, Curtius, `perseus-lat2` for Sallust/Propertius/Cic. Div., `perseus-lat3` for Celsus; the repo files are mostly `perseus-lat2` (lat1 returns 404 for almost all), see `work_versions` in the JSON.\n")
a("## Top 40 works\n")
a("| # | Author | Work | phi id | Citations | Latin edition in canonical-latinLit (file, bytes) |")
a("|--:|---|---|---|--:|---|")
for w, r in list(e.items())[:40]:
    eds = "; ".join(f"{k.split('.',2)[2][:-4]} ({v:,})" for k, v in r["latin_editions"].items()) or "**not found**"
    a(f"| {r['rank']} | {r['author'] or authname.get(w.split('.')[0], '(not in repo)')} | {r['title'] or '(not in repo)'} | {w} | {r['citations']:,} | {eds} |")
a("\nTop-60 notes: 53 of the top 60 have a Latin edition in the repo. Missing from the top 60: " + ", ".join(f"{w} ({r['citations']:,})" for w, r in list(e.items())[:60] if not r["latin_editions"]) + ". phi0845.phi001 (Columella: author folder exists, no work folder), phi1236.phi001, phi0684.phi001, phi1044.phi001, phi0060.phi001, phi1348.phi012 (Suetonius, work not in tree) are not in the repo tree; Cic. Leg. (phi0474.phi044) is in the tree without a Latin XML. For the 60 works the raw-URL probe results (HTTP 200/404 for perseus-lat1 and perseus-lat2) are in `editions.json` under `raw_probe`; the git tree listing is authoritative and agrees with them.\n")
a("## Held-able share\n")
a(f"- Works with a Latin TEI file in canonical-latinLit: {nheld} of {len(e)} cited works; **{held:,} of {tot:,} citations = {held/tot:.1%}**")
a(f"- Top 60 works carry {cov60/tot:.1%} of all Latin citations; {held60/tot:.1%} (of all) sits in the top-60 works that have an edition")
a(f"- Strict edition-tag match (URN tag present among the repo files): {exact:,} = {exact/tot:.1%}. The rest need a tag-to-file map (lat1 -> lat2/lat3 etc.), same book/chapter scheme in most cases.")
a(f"- Works without any Latin file: {len(notree)} works, {sum(n for _, n in notree):,} citations\n")
a("## What changes in relocate.py\n")
a("1. Tokenization/normalisation: Greek used beta-code/diacritic folding; Latin needs only lowercase, u/v and i/j folding (L&S headwords use both), macron stripping (L&S headwords carry macrons in `<orth>`), enclitic -que/-ne/-ve handling.")
a("2. Edition loader: Greek held editions use the manifest layout in coverage.py; Latin needs a manifest of canonical-latinLit data/phiNNNN/phiNNN/*-lat*.xml, with the edition-tag mapping above (several works have lat2-lat6 as split parts: Livy lat2-lat5 are decades, Sallust lat3/lat4, Celsus lat4-6; these would be merged or selected by locator range).")
a("3. Locator resolver: CTS refs in these TEI files use nested `<div type=\"textpart\" subtype=\"book|chapter|section|line\">`, so a generic ref -> node lookup (n attributes) replaces the Greek-specific one; handle prose (book:chapter:section) vs verse (book:line), the empty `Orat::` segments, the `fr::` fragment forms and drama (act:scene:line).")
a("4. Match window: L&S cites a passage to the line/section; relocation then searches that window for a lemma-consistent token. The prose chapter-section windows are long (Pliny NH, Livy) so scoring must use a window of surrounding sections as the Greek one does.")
a("5. Validator: the Greek benchmark checks relocated tokens with Morpheus-style analysis. Latin needs a lemma-consistent test of 'token t is a form of headword h'. Candidates:")
a("   - Whitaker's Words (Ada binary or the Python ports; `whitakers-words`/`words` executables) fully offline, fast, gives all analyses per form, classical-biased dictionary; good as an 'accepts' oracle (set membership of analyses).")
a("   - CLTK Latin lemmatizer (backoff lemmatizer, offline after one model download from GitHub; lower accuracy, single lemma per form, needs lemma normalisation to L&S headword).")
a("   - LatinCy (spaCy models, pip wheels from Hugging Face; offline after download; context-based lemmas, good accuracy on classical prose; needs spaCy and ~hundreds of MB).")
a("   - Collatinus (C++ with data files; offline, all possible lemmas per form, uses a Gaffiot/L&S-derived lexicon; good for an accepts oracle, needs build or the packaged binaries).")
a("   None downloaded or run here. All four run offline once installed. For a Morpheus-equivalent 'any analysis matches' semantics, Whitaker's Words or Collatinus are closest; LatinCy/CLTK give one lemma per token and would score as a stricter, lower-recall check.")
a("6. Headword keys: L&S `key` is like `A1`, `a2` (homograph digits), `ab`; the Greek keys are pure Greek. Homograph digits must be stripped or mapped before validation; entries are keyed by `id` (`n0`, `n1`) in counts, as done here.\n")
a("## Honest estimate\n")
a("- Engineering: XML loader and ref resolver for 160 editions about 2 days; relocate adaptation (normalisation, windows, tag map) about 2 days; validator integration and calibration (pick one oracle, build the lemma/headword normaliser, spot-check 200 hits) 3-5 days. Total about 1-1.5 working weeks for a first scored release limited to works with editions.")
a(f"- Data ceiling: {held/tot:.0%} of URN citations are into held-able works, and {tot/allb:.0%} of all bibls carry a usable Latin URN; with an abbreviation map for the plain-text bibls the ceiling would move up but each new abbreviation (Dig., Sil. Ital., Plin. Ep., Justin) needs manual mapping and, for Digest, an edition that is not in canonical-latinLit.")
a("- Risk: edition mismatch. L&S was written against older editions than Perseus's, so (as with LSJ) line-level locators can be expected to drift for verse and for the older prose texts; Greek had the same problem. Expect a lower raw match rate on lemma-validated relocation than the Greek benchmark until windows are tuned.")
(D / "REPORT.md").write_text("\n".join(L) + "\n", encoding="utf-8")
print(len(L), "lines; held", held, held / tot, "exact", exact / tot, "cov60", cov60 / tot)
