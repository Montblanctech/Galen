"""MW-Gold — the independent lexicon oracle: every lemma vidyut-kosha (Ambuda, Pāṇinian generation) allows for a form.

Oracle(cache_path).lemmas(form_iast) -> sorted list of sktnorm.key(lemma) over every PadaEntry the kosha returns.
The kosha speaks SLP1 and stores padas in pausa with final -s (not -ḥ) and with the class nasal (not anusvāra), so a
DCS unsandhied form is tried in these variants until one answers: as is; ḥ -> s; ḥ -> r; ṃ -> m; ṃ -> n; ṃ -> ṅ/ñ/ṇ
by the following stop. Context-free: all readings, no disambiguation. Returns [] when nothing answers (the form is a
sandhi-internal shape, a Vedic form, or simply absent from the generator's lists).

Cache: JSONL {"form", "lemmas"} at cache_path, loaded on construction, appended as new forms are seen.
first(form) -> the first lemma as the kosha prints it (IAST), for the context-free baseline row.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sktnorm import key, iast_to_slp1, slp1_to_iast  # noqa: E402

GDM = HERE.parent.parent
KOSHA = GDM / "data" / "sanskrit_corpus" / "vidyut_data" / "kosha"
_NAS = {"k": "ṅ", "kh": "ṅ", "g": "ṅ", "gh": "ṅ", "c": "ñ", "ch": "ñ", "j": "ñ", "jh": "ñ", "ṭ": "ṇ", "ṭh": "ṇ", "ḍ": "ṇ", "ḍh": "ṇ",
        "t": "n", "th": "n", "d": "n", "dh": "n", "p": "m", "ph": "m", "b": "m", "bh": "m"}


def variants(form: str) -> list[str]:
    f = form.strip().lower().replace("'", "").replace("ṁ", "ṃ")
    out = [f]
    if f.endswith("ḥ"):
        out += [f[:-1] + "s", f[:-1] + "r"]
    if "ṃ" in f:
        g = re.sub(r"ṃ(?=([kgcjṭḍtdpb]h?))", lambda m: _NAS.get(m.group(1), "ṃ"), f)
        out += [g, f.replace("ṃ", "m"), f.replace("ṃ", "n")]
        if g.endswith("ḥ"):
            out.append(g[:-1] + "s")
    seen, uniq = set(), []
    for v in out:
        if v not in seen:
            seen.add(v)
            uniq.append(v)
    return uniq


class Oracle:
    def __init__(self, cache_path: Path, kosha_path: Path = KOSHA):
        self.cache_path = Path(cache_path)
        self.cache: dict[str, list[str]] = {}
        self.first_cache: dict[str, str] = {}
        self._k = None
        self._kosha_path = kosha_path
        self.failures = 0
        if self.cache_path.exists():
            with self.cache_path.open(encoding="utf-8") as fh:
                for line in fh:
                    try:
                        r = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    self.cache[r["form"]] = r.get("lemmas", [])
                    if "first" in r:
                        self.first_cache[r["form"]] = r["first"]

    def _kosha(self):
        if self._k is None:
            from vidyut.kosha import Kosha
            self._k = Kosha(str(self._kosha_path))
        return self._k

    def _lookup(self, form: str) -> tuple[list[str], str]:
        k = self._kosha()
        for v in variants(form):
            try:
                entries = k.get(iast_to_slp1(v))
            except Exception:  # noqa: BLE001
                self.failures += 1
                entries = []
            if entries:
                lemmas = []
                for e in entries:
                    try:
                        lemmas.append(slp1_to_iast(e.lemma))
                    except Exception:  # noqa: BLE001
                        continue
                keys = sorted({key(x) for x in lemmas if key(x)})
                return keys, (lemmas[0] if lemmas else "")
        return [], ""

    def lemmas(self, form: str) -> list[str]:
        f = form.strip().lower()
        if f in self.cache:
            return self.cache[f]
        keys, first = self._lookup(f)
        self.cache[f] = keys
        self.first_cache[f] = first
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with self.cache_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"form": f, "lemmas": keys, "first": first}, ensure_ascii=False) + "\n")
        return keys

    def first(self, form: str) -> str:
        f = form.strip().lower()
        if f not in self.cache:
            self.lemmas(f)
        return self.first_cache.get(f, "")
