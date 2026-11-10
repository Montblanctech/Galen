"""MW-Gold, stage 1a — freeze the project's Sanskrit token stream from the Digital Corpus of Sanskrit (DCS).

Source: data/sanskrit_corpus/dcs_repo/dcs/data/conllu/files/<Text>/<Text>-NNNN-<chapter citation>-<id>.conllu
(OliverHellwig/sanskrit, CC BY 4.0). Each file is one chapter; each sentence carries `# text = <unsandhied words>`
and `# sent_id = <text_line id>_<n>`; each token line is CoNLL-U with the DCS lemma in column 3, UPOS in column 4,
`Case=Cpd` in the features for a compound member, and `Unsandhied=` in the misc column. The DCS word (one line) is
the token: sandhi is already resolved and compounds are split into members by the DCS annotators, so the
benchmark's token unit is the DCS word, not the orthographic word of a printed edition (README, honesty section).

Output, per text stem (TEXTS below): data/sanskrit_corpus/tokens/<stem>.jsonl, one line per token
{"i", "surface" (the DCS form), "unsandhied", "lemma", "upos", "cpd", "lemma_id", "sent_id", "chapter", "sent_pos"},
and data/sanskrit_corpus/units/<stem>.json {"sentences": [[sent_id, chapter, sent_pos, first_i, n_tokens, text], ...],
"chapters": {chapter citation: [first sentence index, n sentences]}}. Verse numbers are NOT in the DCS dump; stage
1b (align_verses.py) adds them by aligning each sentence to a verse-numbered open edition.

Run (.venv-skt): python -X utf8 -I pipeline/mwgold/tokenize_dcs.py [--only stem,stem]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
GDM = HERE.parent.parent
CORPUS = GDM / "data" / "sanskrit_corpus"
DCS_FILES = CORPUS / "dcs_repo" / "dcs" / "data" / "conllu" / "files"

# stem -> DCS text directory. Stems are ASCII so that cache and gold files travel.
TEXTS = {
    "rgveda": "Ṛgveda", "manusmrti": "Manusmṛti", "atharvaveda": "Atharvaveda (Śaunaka)", "bhagavatapurana": "Bhāgavatapurāṇa",
    "kathasaritsagara": "Kathāsaritsāgara", "kumarasambhava": "Kumārasaṃbhava", "kiratarjuniya": "Kirātārjunīya", "meghaduta": "Meghadūta",
    "satakatraya": "Śatakatraya", "hitopadesa": "Hitopadeśa", "gitagovinda": "Gītagovinda", "buddhacarita": "Buddhacarita",
    "amarusataka": "Amaruśataka", "rtusamhara": "Ṛtusaṃhāra",
    "satapathabrahmana": "Śatapathabrāhmaṇa", "taittiriyasamhita": "Taittirīyasaṃhitā", "aitareyabrahmana": "Aitareyabrāhmaṇa",
    "maitrayanisamhita": "Maitrāyaṇīsaṃhitā", "kathakasamhita": "Kāṭhakasaṃhitā", "pancavimsabrahmana": "Pañcaviṃśabrāhmaṇa",
    "gopathabrahmana": "Gopathabrāhmaṇa", "katyayanasrautasutra": "Kātyāyanaśrautasūtra", "apastambasrautasutra": "Āpastambaśrautasūtra",
    "latyayanasrautasutra": "Lāṭyāyanaśrautasūtra", "sankhayanasrautasutra": "Śāṅkhāyanaśrautasūtra", "asvalayanasrautasutra": "Āśvālāyanaśrautasūtra",
    "kausikasutra": "Kauśikasūtra", "asvalayanagrhyasutra": "Āśvalāyanagṛhyasūtra", "gobhilagrhyasutra": "Gobhilagṛhyasūtra",
    "sankhayanagrhyasutra": "Śāṅkhāyanagṛhyasūtra", "gautamadharmasutra": "Gautamadharmasūtra", "apastambadharmasutra": "Āpastambadharmasūtra",
    "astadhyayi": "Aṣṭādhyāyī",
    "mahabharata": "Mahābhārata", "ramayana": "Rāmāyaṇa", "harivamsa": "Harivaṃśa",
}
FILE_RE = re.compile(r"^(?P<text>.+?)-(?P<pos>\d{4})-(?P<chapter>.+)-(?P<id>\d+)\.conllu$")


def parse_conllu(path: Path):
    chapter = None
    sent = None
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line.startswith("## chapter:"):
                chapter = line.split(":", 1)[1].strip()
            elif line.startswith("# text ="):
                sent = {"text": line.split("=", 1)[1].strip(), "sent_id": None, "tokens": []}
            elif line.startswith("# sent_id ="):
                if sent is not None:
                    sent["sent_id"] = line.split("=", 1)[1].strip()
            elif line.startswith("#") or not line.strip():
                if not line.strip() and sent is not None and sent["tokens"]:
                    yield chapter, sent
                    sent = None
            else:
                cols = line.split("\t")
                if len(cols) < 10 or not cols[0].isdigit():
                    continue
                misc = dict(kv.split("=", 1) for kv in cols[9].split("|") if "=" in kv)
                if sent is None:
                    sent = {"text": "", "sent_id": None, "tokens": []}
                sent["tokens"].append({"surface": cols[1], "lemma": cols[2], "upos": cols[3], "cpd": "Case=Cpd" in cols[5],
                                       "unsandhied": misc.get("Unsandhied", cols[1]), "lemma_id": misc.get("LemmaId", "")})
        if sent is not None and sent["tokens"]:
            yield chapter, sent


def build(stem: str, dirname: str) -> dict:
    d = DCS_FILES / dirname
    files = []
    for p in d.iterdir():
        m = FILE_RE.match(p.name)
        if m:
            files.append((int(m.group("pos")), m.group("chapter"), p))
    files.sort()
    (CORPUS / "tokens").mkdir(parents=True, exist_ok=True)
    (CORPUS / "units").mkdir(parents=True, exist_ok=True)
    i = 0
    sentences = []
    chapters: dict[str, list[int]] = {}
    with (CORPUS / "tokens" / f"{stem}.jsonl").open("w", encoding="utf-8") as out:
        for pos, chap_from_name, p in files:
            sent_pos = 0
            for chapter, s in parse_conllu(p):
                chapter = chapter or chap_from_name
                if chapter not in chapters:
                    chapters[chapter] = [len(sentences), 0]
                chapters[chapter][1] += 1
                first = i
                for t in s["tokens"]:
                    out.write(json.dumps({"i": i, **t, "sent_id": s["sent_id"], "chapter": chapter, "sent_pos": sent_pos}, ensure_ascii=False) + "\n")
                    i += 1
                sentences.append([s["sent_id"], chapter, sent_pos, first, i - first, s["text"]])
                sent_pos += 1
    (CORPUS / "units" / f"{stem}.json").write_text(json.dumps({"text": dirname, "sentences": sentences, "chapters": chapters}, ensure_ascii=False), encoding="utf-8")
    return {"text": dirname, "files": len(files), "chapters": len(chapters), "sentences": len(sentences), "tokens": i}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    only = set(a.only.split(",")) if a.only else None
    t0 = time.time()
    summary_path = CORPUS / "tokenize_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    for stem, dirname in TEXTS.items():
        if only and stem not in only:
            continue
        if not (DCS_FILES / dirname).is_dir():
            print(f"{stem}: DCS directory missing ({dirname})", flush=True)
            continue
        r = build(stem, dirname)
        summary[stem] = r
        print(f"{stem}: {r['files']} files, {r['chapters']} chapters, {r['sentences']} sentences, {r['tokens']} tokens ({time.time()-t0:.0f}s)", flush=True)
    summary_path.write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"total tokens {sum(v['tokens'] for v in summary.values()):,}")


if __name__ == "__main__":
    main()
