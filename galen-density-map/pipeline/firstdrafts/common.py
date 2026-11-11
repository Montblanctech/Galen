"""Shared paths, work table and helpers for Galen First Drafts (v0 spec firstdrafts_v0_spec.md; v0.2 spec firstdrafts_v02_spec.md)."""
from __future__ import annotations

import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
PIPE = HERE.parent
GDM = PIPE.parent
REPO = GDM.parent
sys.path.insert(0, str(PIPE))

WORKS = {
    "adversus-lycum": {
        "prior_translations": 'No earlier English translation found. A Spanish translation appeared in 2023 (M. Cerezo Magán, Lleida).',
        "tlg": "tlg093",
        "urn": "urn:cts:greekLit:tlg0057.tlg093.1st1K-grc1",
        "stem": "urn_cts_greekLit_tlg0057.tlg093.1st1K-grc1",
        "title_lat": "Adversus Lycum",
        "title_eng": "Against Lycus",
        "kuhn_vol": "XVIIIA",
        "kuhn_vol_short": "18a",
        "kuhn_pages": "196-245",
        "lemmatized_dir": "galen_nonmedical",
        "source_note": "First1KGreek tlg0057.tlg093.1st1K-grc1 (Kühn 1829, vol. 18.1 pp. 196-245; keyboarded by Digital Divide Data for the Digital Corpus for Graeco-Arabic Studies), CC BY-SA 4.0",
    },
    "comp-per-genera": {
        "prior_translations": 'No complete translation in any modern language. Parts exist in English: G. Baker 1574 (book 3, from a French epitome), M. Marai 2023 (substantial excerpts, Warwick PhD thesis) and ten reference passages (galen_project, 2026).',
        "tlg": "tlg077",
        "urn": "urn:cts:greekLit:tlg0057.tlg077.1st1K-grc1",
        "stem": "urn_cts_greekLit_tlg0057.tlg077.1st1K-grc1",
        "title_lat": "De compositione medicamentorum per genera",
        "title_eng": "On the Composition of Drugs by Kind",
        "kuhn_vol": "XIII",
        "kuhn_vol_short": "13",
        "kuhn_pages": "362-1058",
        "spec": "firstdrafts_v02_spec.md",
        "lemmatized_dir": "galen",
        "source_note": "First1KGreek tlg0057.tlg077.1st1K-grc1 (Kühn 1827, vol. 13 pp. 362-1058, seven books; keyboarded for the Digital Corpus for Graeco-Arabic Studies), CC BY-SA 4.0",
        "reference": {
            "name": "Zainaldin et al. 2026 reference translation of ten passages (Manuela Marai, CC BY 4.0)",
            "repo": "https://github.com/campattison/galen_project",
            "commit": "ad2d611c7505a3fb5c824d3fc8e07ae19065ded8",
        },
    },
    # cycle 3 (firstdrafts_v02_cycle3_note.md): the eight remaining works with translation_status = none in phase1/galen_ogl_census.csv
    "hirudinibus": {
        "prior_translations": 'No earlier English translation found. Italian: G. Ecca 2021 (complete). French: Bussemaker and Daremberg 1854, for the passages of Oribasius it is compiled from.',
        "tlg": "tlg071",
        "urn": "urn:cts:greekLit:tlg0057.tlg071.1st1K-grc1",
        "stem": "urn_cts_greekLit_tlg0057.tlg071.1st1K-grc1",
        "title_lat": "De hirudinibus, revulsione, cucurbitula, incisione et scarificatione",
        "title_eng": "On Leeches, Revulsion, Cupping, Incision and Scarification",
        "kuhn_vol": "XI",
        "kuhn_vol_short": "11",
        "kuhn_pages": "317-322",
        "spec": "firstdrafts_v02_spec.md",
        "lemmatized_dir": "galen",
        "source_note": "First1KGreek tlg0057.tlg071.1st1K-grc1 (Kühn 1826, vol. 11 pp. 317-322; keyboarded for the Digital Corpus for Graeco-Arabic Studies), CC BY-SA 4.0",
    },
    "quos-quibus": {
        "prior_translations": 'No earlier English translation found. French: Bussemaker and Daremberg 1854, in their Oribasius (book VII 23).',
        "tlg": "tlg073",
        "urn": "urn:cts:greekLit:tlg0057.tlg073.1st1K-grc1",
        "stem": "urn_cts_greekLit_tlg0057.tlg073.1st1K-grc1",
        "title_lat": "Quos quibus catharticis medicamentis et quando purgare oporteat",
        "title_eng": "Whom to Purge, with Which Cathartic Drugs, and When",
        "kuhn_vol": "XI",
        "kuhn_vol_short": "11",
        "kuhn_pages": "343-356",
        "spec": "firstdrafts_v02_spec.md",
        "lemmatized_dir": "galen",
        "source_note": "First1KGreek tlg0057.tlg073.1st1K-grc1 (Kühn 1826, vol. 11 pp. 343-356; keyboarded for the Digital Corpus for Graeco-Arabic Studies), CC BY-SA 4.0; First1KGreek also has tlg073.1st1K-grc2, the Oribasius excerpt of the same work (Kühn XI 343-356 ap. Oribasium, with Latin and German), not used here",
    },
    "purgantium-facultate": {
        "prior_translations": 'No translation in any modern language found.',
        "tlg": "tlg072",
        "urn": "urn:cts:greekLit:tlg0057.tlg072.1st1K-grc1",
        "stem": "urn_cts_greekLit_tlg0057.tlg072.1st1K-grc1",
        "title_lat": "De purgantium medicamentorum facultate",
        "title_eng": "On the Power of Purgative Drugs",
        "kuhn_vol": "XI",
        "kuhn_vol_short": "11",
        "kuhn_pages": "323-342",
        "spec": "firstdrafts_v02_spec.md",
        "lemmatized_dir": "galen",
        "source_note": "First1KGreek tlg0057.tlg072.1st1K-grc1 (Kühn 1826, vol. 11 pp. 323-342; keyboarded for the Digital Corpus for Graeco-Arabic Studies), CC BY-SA 4.0",
    },
    "morbi-temporibus": {
        "prior_translations": 'No translation in any modern language found.',
        "tlg": "tlg047",
        "urn": "urn:cts:greekLit:tlg0057.tlg047.1st1K-grc1",
        "stem": "urn_cts_greekLit_tlg0057.tlg047.1st1K-grc1",
        "title_lat": "De totius morbi temporibus",
        "title_eng": "On the Periods of the Whole Disease",
        "kuhn_vol": "VII",
        "kuhn_vol_short": "7",
        "kuhn_pages": "440-462",
        "spec": "firstdrafts_v02_spec.md",
        "lemmatized_dir": "galen",
        "source_note": "First1KGreek tlg0057.tlg047.1st1K-grc1 (Kühn 1824, vol. 7 pp. 440-462; keyboarded for the Digital Corpus for Graeco-Arabic Studies), CC BY-SA 4.0",
    },
    "adversus-typos": {
        "prior_translations": "No English translation found. Spanish: E. García Sola 2010.",
        "tlg": "tlg049",
        "urn": "urn:cts:greekLit:tlg0057.tlg049.1st1K-grc1",
        "stem": "urn_cts_greekLit_tlg0057.tlg049.1st1K-grc1",
        "title_lat": "Adversus eos qui de typis scripserunt vel de circuitibus",
        "title_eng": "Against Those Who Wrote on Types or on Periods (of Fever)",
        "kuhn_vol": "VII",
        "kuhn_vol_short": "7",
        "kuhn_pages": "475-512",
        "spec": "firstdrafts_v02_spec.md",
        "lemmatized_dir": "galen",
        "source_note": "First1KGreek tlg0057.tlg049.1st1K-grc1 (Kühn 1824, vol. 7 pp. 475-512; keyboarded for the Digital Corpus for Graeco-Arabic Studies), CC BY-SA 4.0",
    },
    "in-hipp-acut": {
        "claim": "The first English translation of books II–IV that we know of.",
        "prior_translations": "No English translation of books II\u2013IV found. Book I: French, J. Pietrobelli 2019 (Les Belles Lettres). Book II chapters 20\u201323: German excerpt, W. M\u00fcri 1979.",
        "tlg": "tlg087",
        "urn": "urn:cts:greekLit:tlg0057.tlg087.1st1K-grc1",
        "stem": "urn_cts_greekLit_tlg0057.tlg087.1st1K-grc1",
        "title_lat": "In Hippocratis De victu acutorum commentaria, libri II\u2013IV",
        "title_eng": "Commentary on Hippocrates' Regimen in Acute Diseases, Books II\u2013IV",
        "kuhn_vol": "XV",
        "kuhn_vol_short": "15",
        "kuhn_pages": "515-919",
        "books": ["2", "3", "4"],
        "spec": "firstdrafts_v02_spec.md",
        "lemmatized_dir": "galen_nonmedical",
        "source_note": "First1KGreek tlg0057.tlg087.1st1K-grc1 (K\u00fchn 1828, vol. 15 pp. 418-919, four books; this draft: books II-IV, pp. 515-919; keyboarded for the Digital Corpus for Graeco-Arabic Studies), CC BY-SA 4.0",
    },
    "de-plenitudine": {
        "prior_translations": "No English translation found. German: C. Otte 2001 (edition with translation).",
        "tlg": "tlg050",
        "urn": "urn:cts:greekLit:tlg0057.tlg050.1st1K-grc1",
        "stem": "urn_cts_greekLit_tlg0057.tlg050.1st1K-grc1",
        "title_lat": "De plenitudine",
        "title_eng": "On Plethora",
        "kuhn_vol": "VII",
        "kuhn_vol_short": "7",
        "kuhn_pages": "513-583",
        "spec": "firstdrafts_v02_spec.md",
        "lemmatized_dir": "galen",
        "source_note": "First1KGreek tlg0057.tlg050.1st1K-grc1 (K\u00fchn 1824, vol. 7 pp. 513-583; keyboarded for the Digital Corpus for Graeco-Arabic Studies), CC BY-SA 4.0",
    },
    "de-comate": {
        "prior_translations": "No English translation found. Spanish: J. M. Nieto Ib\u00e1\u00f1ez 2005.",
        "tlg": "tlg052",
        "urn": "urn:cts:greekLit:tlg0057.tlg052.1st1K-grc1",
        "stem": "urn_cts_greekLit_tlg0057.tlg052.1st1K-grc1",
        "title_lat": "De comate secundum Hippocratem",
        "title_eng": "On Coma according to Hippocrates",
        "kuhn_vol": "VII",
        "kuhn_vol_short": "7",
        "kuhn_pages": "643-665",
        "spec": "firstdrafts_v02_spec.md",
        "lemmatized_dir": "galen",
        "source_note": "First1KGreek tlg0057.tlg052.1st1K-grc1 (K\u00fchn 1824, vol. 7 pp. 643-665; keyboarded for the Digital Corpus for Graeco-Arabic Studies), CC BY-SA 4.0",
    },
    "in-hipp-salubri": {
        "prior_translations": 'No translation in any modern language found.',
        "tlg": "tlg086",
        "urn": "urn:cts:greekLit:tlg0057.tlg086.1st1K-grc1",
        "stem": "urn_cts_greekLit_tlg0057.tlg086.1st1K-grc1",
        "title_lat": "In Hippocratis vel Polybi opus De salubri victus ratione privatorum commentarius",
        "title_eng": "Commentary on Hippocrates' (or Polybus') Regimen in Health for Private Persons",
        "kuhn_vol": "XV",
        "kuhn_vol_short": "15",
        "kuhn_pages": "174-223",
        "spec": "firstdrafts_v02_spec.md",
        "lemmatized_dir": "galen_nonmedical",
        "source_note": "First1KGreek tlg0057.tlg086.1st1K-grc1 (Kühn 1828, vol. 15 pp. 174-223; keyboarded for the Digital Corpus for Graeco-Arabic Studies), CC BY-SA 4.0",
    },
    "de-humero": {
        "prior_translations": "No complete English translation found; R. Meiggs translated a short passage (Kühn XVIIIA 347–348). The text is part of Galen's commentary on the Hippocratic Joints, which M. Abballe translated into Italian (1972).",
        "tlg": "tlg096",
        "urn": "urn:cts:greekLit:tlg0057.tlg096.1st1K-grc1",
        "stem": "urn_cts_greekLit_tlg0057.tlg096.1st1K-grc1",
        "title_lat": "De humero iis modis prolapso quos Hippocrates non vidit",
        "title_eng": "On the Shoulder Dislocated in Ways Hippocrates Did Not See",
        "kuhn_vol": "XVIIIA",
        "kuhn_vol_short": "18a",
        "kuhn_pages": "346-423",
        "spec": "firstdrafts_v02_spec.md",
        "lemmatized_dir": "galen_nonmedical",
        "source_note": "First1KGreek tlg0057.tlg096.1st1K-grc1 (Kühn 1829, vol. 18a pp. 346-423; keyboarded for the Digital Corpus for Graeco-Arabic Studies), CC BY-SA 4.0",
    },
    "in-hipp-nat-hom": {
        "tlg": "tlg085",
        "urn": "urn:cts:greekLit:tlg0057.tlg085.1st1K-grc1",
        "stem": "urn_cts_greekLit_tlg0057.tlg085.1st1K-grc1",
        "title_lat": "In Hippocratis De natura hominis",
        "title_eng": "Commentary on Hippocrates' Nature of Man",
        "kuhn_vol": "XV",
        "kuhn_vol_short": "15",
        "kuhn_pages": "1-173",
        "spec": "firstdrafts_v02_spec.md",
        "lemmatized_dir": "galen_nonmedical",
        "source_note": "First1KGreek tlg0057.tlg085.1st1K-grc1 (Kühn 1828, vol. 15 pp. 1-173; keyboarded for the Digital Corpus for Graeco-Arabic Studies), CC BY-SA 4.0",
    },
    "difficultate-respirationis": {
        "prior_translations": 'No complete translation in any modern language. One paragraph (Kühn VII 781–782) is in English in A. A. Long 2021.',
        "tlg": "tlg056",
        "urn": "urn:cts:greekLit:tlg0057.tlg056.1st1K-grc1",
        "stem": "urn_cts_greekLit_tlg0057.tlg056.1st1K-grc1",
        "title_lat": "De difficultate respirationis",
        "title_eng": "On Difficulty of Breathing",
        "kuhn_vol": "VII",
        "kuhn_vol_short": "7",
        "kuhn_pages": "753-960",
        "spec": "firstdrafts_v02_spec.md",
        "lemmatized_dir": "galen",
        "source_note": "First1KGreek tlg0057.tlg056.1st1K-grc1 (Kühn 1824, vol. 7 pp. 753-960; keyboarded for the Digital Corpus for Graeco-Arabic Studies), CC BY-SA 4.0",
    },
}

PUNCT_RE = re.compile(r"[\.\,\;\:\·\!\?\(\)\[\]«»“”\"'’‘]")
SENTENCE_END = (".", ";")  # Greek full stop and question mark; the raised dot is a colon


def out_dir(slug: str) -> Path:
    """outputs/firstdrafts/<slug>; FIRSTDRAFTS_OUT=<dir> redirects every stage to another root (dry runs on copies)."""
    import os

    root = Path(os.environ["FIRSTDRAFTS_OUT"]) if os.environ.get("FIRSTDRAFTS_OUT") else GDM / "outputs" / "firstdrafts"
    p = root / slug
    p.mkdir(parents=True, exist_ok=True)
    return p


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s or "")


def strip_punct(tok: str) -> str:
    return PUNCT_RE.sub("", tok)


def read_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    with p.open(encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def write_jsonl(p: Path, rows) -> int:
    n = 0
    with p.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            n += 1
    return n


def sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def token_proxy_greek(words: int) -> int:
    """Pre-registered proxy (spec): Greek words x 4.5 tokens."""
    return int(round(words * 4.5))


def token_proxy_english(words: int) -> int:
    return int(round(words * 1.3))


PRICES_PER_MTOK = {  # claude-api skill table, cached 2026-10-06
    "claude-fable-5-1": (10.0, 50.0),
    "claude-opus-5-5": (4.0, 20.0),
    "claude-sonnet-5-5": (2.0, 10.0),
}


def draft_words(slug: str) -> int:
    """Greek words in the drafted units (2026-11-11). units_meta's n_tei_words counts the whole TEI file, which for a work
    drafted in part (in-hipp-acut: books II-IV only) includes text that was never drafted."""
    return sum(int(u.get("n_tokens", 0)) for u in read_jsonl(out_dir(slug) / "units.jsonl"))
