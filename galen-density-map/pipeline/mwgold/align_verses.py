"""MW-Gold, stage 1b — give every DCS sentence the verse (or sūtra / kaṇḍikā) number Monier-Williams cites by.

The DCS dump (tokenize_dcs.py) knows chapters, not verses. Three references supply the verse level:
  gretil   a GRETIL plaintext (data/sanskrit_corpus/gretil/*.txt) whose verses end in a reference such as
           `// Manu_1.1`, `RV_1,001.01`, `bhp_01.01.004`, `sokss_1,1.64`, `hit_0.1`, `GG_1.1`, `BC_1.1`, `ps_1,1.1`, or
           the TITUS-style Atharvaveda `(AVŚ_1,14.2a) ...`. Within one chapter the DCS sentences and the GRETIL verses
           are reduced to CONSONANT SKELETONS (vowels, anusvāra, visarga, avagraha and punctuation removed: sandhi
           lives almost entirely in what is removed), the two skeleton strings are aligned with difflib, and each
           sentence takes the verse whose span receives most of its matched characters (coverage recorded).
  ambuda   an ambuda-org/dcs export (data/sanskrit_corpus/ambuda_dcs/*.txt): `# id = Ku.1.1` blocks of SLP1
           token\tlemma lines, i.e. the same DCS annotation with verse ids; aligned to the stream by LEMMA sequence.
  vpc      Hellwig's Vedic Prose Corpus (data/sanskrit_corpus/vpc/*.txt): `id\ttext` lines whose text is the DCS
           sentence text itself; joined by exact text within the chapter, skeleton alignment as fallback.
Texts whose DCS chapter already IS the unit Monier-Williams cites (TS anuvāka, MS, KS, AB khaṇḍa, PB, GB, KauśS,
GautDhS) need no alignment: relocate_mw.py uses the chapter window for them and flags it.

Writes the reference as `ref` (list of ints: chapter parts + verse, the shape MW's locus parts take) and `ref_cov`
(0-1 coverage, 1.0 for exact joins) into data/sanskrit_corpus/units/<stem>.json, and
data/sanskrit_corpus/align_summary.json (per text: sentences, aligned, coverage histogram, verses in the reference,
verses hit, chapters without a reference).

Run (.venv-skt): python -X utf8 -I pipeline/mwgold/align_verses.py [--only stem,stem]
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sktnorm import slp1_to_iast, key as skey  # noqa: E402

GDM = HERE.parent.parent
CORPUS = GDM / "data" / "sanskrit_corpus"
GRETIL = CORPUS / "gretil"
AMBUDA = CORPUS / "ambuda_dcs"
VPC = CORPUS / "vpc"

ORDINALS = {"prathamaḥ": 1, "dvitīyaḥ": 2, "tṛtīyaḥ": 3, "caturthaḥ": 4, "pañcamaḥ": 5, "ṣaṣṭhaḥ": 6, "pūrvameghaḥ": 1, "uttarameghaḥ": 2}


def chapter_parts(ch: str) -> tuple[int, ...]:
    """'ṚV, 1, 1' -> (1, 1); 'ManuS, 1' -> (1,); 'Megh, Pūrvameghaḥ' -> (1,); 'ṚtuS, Prathamaḥ sargaḥ' -> (1,)."""
    parts = [p.strip() for p in ch.split(",")[1:]]
    out = []
    for p in parts:
        if p.isdigit():
            out.append(int(p))
        else:
            w = p.lower().split()[0] if p else ""
            if w in ORDINALS:
                out.append(ORDINALS[w])
    return tuple(out)


# ---------------------------------------------------------------- config
# stem: (method, file, ref regex -> (chapter tuple, verse), keep_parts for vpc)
CFG = {
    "rgveda": ("gretil", "sa_Rgveda-edAufrecht.txt", r"RV_(\d+),(\d+)\.(\d+)", 2),
    "manusmrti": ("gretil", "sa_manusmRti.txt", r"Manu_(\d+)\.(\d+)", 1),
    "atharvaveda": ("gretil_av", "avs___u.htm", r"\(AVŚ_(\d+),(\d+)\.(\d+)[a-z]?\)", 2),
    "bhagavatapurana": ("gretil", "sa_bhAgavatapurANa.txt", r"bhp_(\d+)\.(\d+)\.(\d+)(?!/)", 2),
    "kathasaritsagara": ("gretil", "sa_somadeva-kathAsaritsAgara.txt", r"sokss_(\d+),(\d+)\.(\d+)", 2),
    "hitopadesa": ("gretil", "sa_nArAyaNa-hitopadeza.txt", r"hit_(\d+)\.(\d+)", 1),
    "gitagovinda": ("gretil", "sa_jayadeva-gItagovinda.txt", r"GG_(\d+)\.(\d+)", 1),
    "buddhacarita": ("gretil", "sa_azvaghoSa-buddhacarita.txt", r"BC_(\d+)\.(\d+)", 1),
    "astadhyayi": ("gretil", "sa_pANini-aSTAdhyAyI.txt", r"ps_(\d+),(\d+)\.(\d+)", 2),
    "kumarasambhava": ("ambuda", "kumarasambhavam.txt", r"Ku\.(\d+)\.(\d+)", 1),
    "kiratarjuniya": ("ambuda", "kiratarjuniyam.txt", r"Kira\.(\d+)\.(\d+)", 1),
    "satakatraya": ("ambuda", "shatakatrayam.txt", r"Shata\.(\d+)\.(\d+)", 1),
    "meghaduta": ("ambuda", "meghadutam-kale.txt", r"Megh\.(\d+)\.(\d+)", 1),
    "amarusataka": ("ambuda", "amarushatakam.txt", r"AmrShtk\.(\d+)", 0),
    "rtusamhara": ("ambuda", "rtusamharam.txt", r"Rtu\.(\d+)\.(\d+)", 1),
    "satapathabrahmana": ("vpc", "ŚBM.txt", None, 4),
    "katyayanasrautasutra": ("vpc", "KātyŚS.txt", None, 3),
    "apastambasrautasutra": ("vpc", "ĀpŚS.txt", None, 3),
    "latyayanasrautasutra": ("vpc", "LāṭŚS.txt", None, 3),
    "sankhayanasrautasutra": ("vpc", "ŚāṅkhŚS.txt", None, 3),
    "asvalayanasrautasutra": ("vpc", "ĀśvŚS.txt", None, 3),
    "asvalayanagrhyasutra": ("vpc", "ĀśvGS.txt", None, 3),
    "gobhilagrhyasutra": ("vpc", "GobhGS.txt", None, 3),
    "sankhayanagrhyasutra": ("vpc", "ŚāṅkhGS.txt", None, 3),
    "apastambadharmasutra": ("vpc", "ĀpDhS.txt", None, 3),
}

CONS = set("kgṅcjñṭḍṇtdnpbmyrlvśṣsh")


def skeleton(s: str) -> str:
    s = unicodedata.normalize("NFC", s or "").lower().replace("ḻ", "ḍ").replace("ḷh", "ḍh")
    s = "".join(ch for ch in unicodedata.normalize("NFD", s) if unicodedata.category(ch) != "Mn" or ch in ("̣", "́", "̃", "̊"))
    s = unicodedata.normalize("NFC", s)
    return "".join(ch for ch in s if ch in CONS)


# ---------------------------------------------------------------- references
def gretil_verses(path: Path, rx: str, n_chap: int, av: bool = False) -> dict[tuple, list[tuple[tuple, str]]]:
    """chapter tuple -> [(ref tuple, text)] in order."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    if av:
        raw = re.sub(r"<[^>]+>", " ", raw)
        import html as _h
        raw = _h.unescape(raw)
        out: dict[tuple, dict[tuple, list[str]]] = defaultdict(lambda: defaultdict(list))
        for m in re.finditer(rx + r"\s*([^\n]*)", raw):
            nums = tuple(int(x) for x in m.groups()[:-1])
            out[nums[:n_chap]][nums].append(m.group(m.lastindex))
        return {ch: [(ref, " ".join(t)) for ref, t in sorted(vs.items())] for ch, vs in out.items()}
    body = raw.split("# Text", 1)[1] if "# Text" in raw else raw
    body = re.sub(r"(?m)^\s*%.*$", " ", body)          # metre lines (Kathāsaritsāgara)
    body = re.sub(r"bhp_\d+\.\d+\.\d+/\d+[^\n]*", " ", body)  # Bhāgavata speaker lines carry a ref before the text
    out2: dict[tuple, list[tuple[tuple, str]]] = defaultdict(list)
    pos = 0
    for m in re.finditer(rx, body):
        nums = tuple(int(x) for x in m.groups())
        text = body[pos:m.start()]
        pos = m.end()
        out2[nums[:n_chap]].append((nums, text))
    return out2


def ambuda_verses(path: Path, rx: str, n_chap: int) -> dict[tuple, list[tuple[tuple, list[str]]]]:
    """chapter tuple -> [(ref tuple, [lemma keys])]."""
    out: dict[tuple, list[tuple[tuple, list[str]]]] = defaultdict(list)
    cur = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# id ="):
            m = re.search(rx, line)
            cur = None
            if m:
                nums = tuple(int(x) for x in m.groups())
                cur = (nums, [])
                out[nums[:n_chap] if n_chap else (1,)].append(cur)
        elif cur is not None and "\t" in line:
            cols = line.split("\t")
            cur[1].append(skey(slp1_to_iast(cols[1])))
    return out


def vpc_lines(path: Path, keep: int) -> dict[tuple, list[tuple[tuple, str]]]:
    out: dict[tuple, list[tuple[tuple, str]]] = defaultdict(list)
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or "\t" not in line:
            continue
        cid, text = line.split("\t", 1)
        parts = cid.strip().split(".")
        try:
            nums = tuple(int(p.strip("[]")) for p in parts)
        except ValueError:
            continue
        ref = nums[:keep]
        out[nums[:keep - 1] if keep > 1 else (nums[0],)].append((ref, text.strip()))
    return out


# ---------------------------------------------------------------- alignment
def align_by_skeleton(sent_texts: list[str], verses: list[tuple[tuple, str]]) -> list[tuple[tuple | None, float]]:
    a_parts = [skeleton(t) for t in sent_texts]
    b_parts = [skeleton(t) for _, t in verses]
    A, B = "".join(a_parts), "".join(b_parts)
    if not A or not B:
        return [(None, 0.0)] * len(sent_texts)
    a_off, b_off = [0], [0]
    for p in a_parts:
        a_off.append(a_off[-1] + len(p))
    for p in b_parts:
        b_off.append(b_off[-1] + len(p))
    sm = difflib.SequenceMatcher(None, A, B, autojunk=False)
    blocks = [b for b in sm.get_matching_blocks() if b.size]
    # for every A position in a block, which verse does its B position fall in
    res = []
    bi = 0
    import bisect
    for s in range(len(sent_texts)):
        lo, hi = a_off[s], a_off[s + 1]
        if hi == lo:
            res.append((None, 0.0))
            continue
        cover: Counter = Counter()
        for b in blocks:
            if b.a + b.size <= lo or b.a >= hi:
                continue
            x0, x1 = max(lo, b.a), min(hi, b.a + b.size)
            # B positions x0..x1 shifted
            y0 = b.b + (x0 - b.a)
            y1 = y0 + (x1 - x0)
            # split across verse boundaries
            v = bisect.bisect_right(b_off, y0) - 1
            while y0 < y1 and v < len(verses):
                seg_end = min(y1, b_off[v + 1])
                cover[v] += seg_end - y0
                y0 = seg_end
                v += 1
        if not cover:
            res.append((None, 0.0))
            continue
        v, n = cover.most_common(1)[0]
        res.append((verses[v][0], round(sum(cover.values()) / (hi - lo), 3)))
    return res


def align_by_lemmas(sent_lemmas: list[list[str]], verses: list[tuple[tuple, list[str]]]) -> list[tuple[tuple | None, float]]:
    A = [l for s in sent_lemmas for l in s]
    B = [l for _, v in verses for l in v]
    a_off, b_off = [0], [0]
    for s in sent_lemmas:
        a_off.append(a_off[-1] + len(s))
    for _, v in verses:
        b_off.append(b_off[-1] + len(v))
    if not A or not B:
        return [(None, 0.0)] * len(sent_lemmas)
    sm = difflib.SequenceMatcher(None, A, B, autojunk=False)
    blocks = [b for b in sm.get_matching_blocks() if b.size]
    import bisect
    res = []
    for s in range(len(sent_lemmas)):
        lo, hi = a_off[s], a_off[s + 1]
        if hi == lo:
            res.append((None, 0.0))
            continue
        cover: Counter = Counter()
        for b in blocks:
            if b.a + b.size <= lo or b.a >= hi:
                continue
            x0, x1 = max(lo, b.a), min(hi, b.a + b.size)
            y0 = b.b + (x0 - b.a)
            y1 = y0 + (x1 - x0)
            v = bisect.bisect_right(b_off, y0) - 1
            while y0 < y1 and v < len(verses):
                seg_end = min(y1, b_off[v + 1])
                cover[v] += seg_end - y0
                y0 = seg_end
                v += 1
        if not cover:
            res.append((None, 0.0))
            continue
        v, n = cover.most_common(1)[0]
        res.append((verses[v][0], round(sum(cover.values()) / (hi - lo), 3)))
    return res


def norm_text(s: str) -> str:
    return " ".join(unicodedata.normalize("NFC", s).split())


def run(stem: str) -> dict:
    method, fname, rx, n = CFG[stem]
    units_path = CORPUS / "units" / f"{stem}.json"
    units = json.loads(units_path.read_text(encoding="utf-8"))
    sents = units["sentences"]
    refs: list = [None] * len(sents)
    covs: list = [0.0] * len(sents)
    by_chapter: dict[str, list[int]] = defaultdict(list)
    for i, s in enumerate(sents):
        by_chapter[s[1]].append(i)
    missing_chapters = []
    if method in ("gretil", "gretil_av"):
        ref = gretil_verses(GRETIL / fname, rx, n, av=(method == "gretil_av"))
        for ch, idxs in by_chapter.items():
            verses = ref.get(chapter_parts(ch))
            if not verses:
                missing_chapters.append(ch)
                continue
            al = align_by_skeleton([sents[i][5] for i in idxs], verses)
            for i, (r, c) in zip(idxs, al):
                refs[i], covs[i] = (list(r) if r else None), c
    elif method == "ambuda":
        ref = ambuda_verses(AMBUDA / fname, rx, n)
        lem_path = CORPUS / "tokens" / f"{stem}.jsonl"
        sent_lemmas: dict[int, list[str]] = defaultdict(list)
        with lem_path.open(encoding="utf-8") as fh:
            for line in fh:
                t = json.loads(line)
                sent_lemmas[t["sent_pos"], t["chapter"]].append(skey(t["lemma"]))
        for ch, idxs in by_chapter.items():
            verses = ref.get(chapter_parts(ch) if n else (1,))
            if not verses:
                missing_chapters.append(ch)
                continue
            al = align_by_lemmas([sent_lemmas[(sents[i][2], ch)] for i in idxs], verses)
            for i, (r, c) in zip(idxs, al):
                refs[i], covs[i] = (list(r) if r else None), c
    elif method == "vpc":
        ref = vpc_lines(VPC / fname, n)
        for ch, idxs in by_chapter.items():
            lines = ref.get(chapter_parts(ch))
            if not lines:
                missing_chapters.append(ch)
                continue
            exact = {norm_text(t): r for r, t in lines}
            todo = []
            for i in idxs:
                r = exact.get(norm_text(sents[i][5]))
                if r is not None:
                    refs[i], covs[i] = list(r), 1.0
                else:
                    todo.append(i)
            if todo:
                al = align_by_skeleton([sents[i][5] for i in todo], lines)
                for i, (r, c) in zip(todo, al):
                    refs[i], covs[i] = (list(r) if r else None), c
    units["refs"] = refs
    units["ref_cov"] = covs
    units["ref_method"] = method
    units["ref_source"] = fname
    units_path.write_text(json.dumps(units, ensure_ascii=False), encoding="utf-8")
    hist = Counter("exact" if c == 1.0 else ">=0.8" if c >= 0.8 else ">=0.5" if c >= 0.5 else ">0" if c > 0 else "none" for c in covs)
    n_ref = sum(len(v) for v in ref.values())
    return {"method": method, "source": fname, "sentences": len(sents), "aligned": sum(1 for r in refs if r), "coverage": dict(hist),
            "reference_units": n_ref, "reference_units_hit": len({tuple(r) for r in refs if r}),
            "chapters": len(by_chapter), "chapters_without_reference": len(missing_chapters), "missing_examples": missing_chapters[:5]}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    only = set(a.only.split(",")) if a.only else None
    sp = CORPUS / "align_summary.json"
    summary = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else {}
    t0 = time.time()
    for stem in CFG:
        if only and stem not in only:
            continue
        if not (CORPUS / "units" / f"{stem}.json").exists():
            print(f"{stem}: no units file", flush=True)
            continue
        r = run(stem)
        summary[stem] = r
        print(f"{stem}: {r['aligned']}/{r['sentences']} sentences aligned ({100*r['aligned']/max(1,r['sentences']):.1f}%), {r['coverage']}, ref units {r['reference_units']} hit {r['reference_units_hit']}, chapters w/o ref {r['chapters_without_reference']} ({time.time()-t0:.0f}s)", flush=True)
    sp.write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
