"""M2 — cross-system agreement and the disagreement worklist.

Generalises ``galen-density-map/pipeline/h3m/m2_agreement.py`` (attribution) from
"odyCy vs Stanza perseus vs Stanza proiel" to *any* set of systems that ran:

* the **audit system** is the alignment anchor; every other system's stream is
  aligned to it with the project's greedy surface aligner; a token counts only
  when **every** system aligned to it (the rest is alignment loss, reported);
* pairwise strict (accent-preserving) agreement for every unordered pair;
* all-systems agreement; audit-vs-consensus (consensus = the other systems are
  unanimous); both numbers are always reported, since vs-consensus is
  conditional on the others agreeing and therefore selects easier tokens;
* a frequency-ranked worklist of every token where the systems disagree, with
  the G2a mechanical class (encoding_artifact / accent_only / real_disagreement)
  of each other system against the audit system and a ±N-token context;
* optionally a seeded reservoir sample (Algorithm R, identical to the project's
  ``reservoir_sample_medical``: works in sorted order, tokens with surface and
  lemma) so the kit can reproduce the project's 5,000-token numbers exactly.

Honesty clause (goes in every summary): systems trained on overlapping treebanks
have correlated errors; agreement overstates accuracy and is an upper-ish bound,
never "accuracy".
"""

from __future__ import annotations

import csv
import json
import random
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any

from .align import align_surfaces
from .normalize import convention_neutral, is_greek
from .corpus import Token, Work, context_window
from .normalize import classify_lemma_disagreement, lemma_nfc, lemmas_equal_strict
from .stats import pct, rate_block

HONESTY = ("Independently implemented lemmatizers trained on the same UD treebanks (Perseus, PROIEL) have "
           "correlated errors, so agreement overstates accuracy. Report as an upper-ish bound, never as accuracy.")
ALIGN_FLAG = 0.05
CLASS_RANK = {"real_disagreement": 3, "accent_only": 2, "encoding_artifact": 1, "missing_lemma": 0}


class M2Accumulator:
    def __init__(
        self,
        audit: str,
        systems: list[str],
        *,
        sample_n: int = 0,
        seed: int = 20261105,
        context_width: int = 6,
        out_dir: Path,
        max_rows: int = 0,
    ) -> None:
        self.audit = audit
        self.systems = [s for s in systems if s != audit]
        self.all_systems = [audit] + self.systems
        self.sample_n = sample_n
        self.seed = seed
        self.rng = random.Random(seed)
        self.width = context_width
        self.out_dir = out_dir
        self.max_rows = max_rows
        self.pairs = list(combinations(self.all_systems, 2))
        # population counters
        self.n_works = 0
        self.works_skipped: list[dict[str, str]] = []
        self.n_anchor_tokens = 0
        self.n_eligible = 0
        self.n_aligned = 0
        self.pair_agree: Counter = Counter()
        self.pair_agree_conv: Counter = Counter()
        self.all_agree = 0
        self.cons_n = 0
        self.cons_agree = 0
        self.by_author: dict[str, Counter] = defaultdict(Counter)
        self.by_pos: dict[str, Counter] = defaultdict(Counter)
        self.align_stats: list[dict[str, Any]] = []
        self.g2a_counts: Counter = Counter()
        self.freq: Counter = Counter()  # (surface, audit lemma) over disagreement rows
        self.n_disagreements = 0
        self.disagreement_keys: set[tuple[str, int]] = set()
        # reservoir sample of records
        self.reservoir: list[dict[str, Any]] = []
        self.seen_for_sample = 0
        # streamed worklist
        out_dir.mkdir(parents=True, exist_ok=True)
        self._tmp_path = out_dir / "_disagreements.tmp.jsonl"
        self._tmp = self._tmp_path.open("w", encoding="utf-8")

    # ------------------------------------------------------------------
    def consume(self, work: Work, outputs: dict[str, list[Token]]) -> None:
        if not self.systems:
            return  # a single system has nothing to agree with; M2 is reported as skipped
        anchor = outputs.get(self.audit)
        if anchor is None:
            self.works_skipped.append({"work": work.stem, "reason": f"audit system {self.audit} produced no output"})
            return
        missing = [s for s in self.systems if s not in outputs]
        scorable = not missing
        self.n_anchor_tokens += len(anchor)
        maps: dict[str, dict[int, int]] = {}
        if scorable:
            self.n_works += 1
            a_surf = [t.surface for t in anchor]
            for s in self.systems:
                toks = outputs[s]
                # Align on Greek-letter tokens only: the project tokenizer (and so the anchor) drops
                # numerals, sigla and Latin, which a text-fed system still emits; aligning them would
                # count every such token as drop (Diophantus: 58% loss before this filter).
                keep = [k for k, t in enumerate(toks) if is_greek(t.surface)]
                pairs, stats = align_surfaces(a_surf, [toks[k].surface for k in keep])
                maps[s] = {ia: keep[ib] for ia, ib in pairs}
                stats["non_greek_tokens_dropped_before_alignment"] = len(toks) - len(keep)
                self.align_stats.append({"work": work.stem, "system": s, **stats})
        else:
            # The work stays in the population (its tokens are alignment drop and may be
            # sampled), exactly as the project's run treated works without Stanza output.
            self.works_skipped.append({"work": work.stem, "reason": f"no output from {', '.join(missing)}",
                                       "tokens_counted_as_drop": len(anchor)})
        for p, t in enumerate(anchor):
            if not t.surface or not t.lemma:
                continue
            self.n_eligible += 1
            lemmas: dict[str, str | None] = {self.audit: t.lemma}
            aligned = scorable
            for s in self.systems:
                ib = maps[s].get(p) if scorable else None
                if ib is None:
                    lemmas[s] = None
                    aligned = False
                else:
                    lemmas[s] = outputs[s][ib].lemma or None
                    if lemmas[s] is None:
                        aligned = False
            rec: dict[str, Any] | None = None
            if aligned:
                self.n_aligned += 1
                agree_all = True
                agree_all_conv = True
                for x, y in self.pairs:
                    if lemmas_equal_strict(lemmas[x], lemmas[y]):
                        self.pair_agree[(x, y)] += 1
                        self.pair_agree_conv[(x, y)] += 1
                    else:
                        agree_all = False
                        if lemmas_equal_strict(convention_neutral(lemmas[x]), convention_neutral(lemmas[y])):
                            self.pair_agree_conv[(x, y)] += 1
                        else:
                            agree_all_conv = False
                others = [lemmas[s] for s in self.systems]
                unanimous = all(lemmas_equal_strict(others[0], o) for o in others[1:])
                vs_cons: bool | None = None
                if unanimous:
                    self.cons_n += 1
                    vs_cons = lemmas_equal_strict(t.lemma, others[0])
                    if vs_cons:
                        self.cons_agree += 1
                if agree_all:
                    self.all_agree += 1
                ba = self.by_author[work.author]
                ba["aligned"] += 1
                ba["all_agree"] += int(agree_all)
                ba["all_agree_conv"] += int(agree_all_conv)
                if unanimous:
                    ba["cons_n"] += 1
                    ba["cons_agree"] += int(bool(vs_cons))
                bp = self.by_pos[t.pos]
                bp["aligned"] += 1
                bp["all_agree"] += int(agree_all)
                if not agree_all:
                    rec = self._disagreement(work, anchor, p, t, lemmas, unanimous, vs_cons)
            if self.sample_n:
                self.seen_for_sample += 1
                item = {"work_stem": work.stem, "token_index": t.i, "author": work.author, "pos": t.pos,
                        "surface": t.surface, "aligned": aligned, "lemmas": lemmas}
                if len(self.reservoir) < self.sample_n:
                    self.reservoir.append(item)
                else:
                    j = self.rng.randint(1, self.seen_for_sample)
                    if j <= self.sample_n:
                        self.reservoir[j - 1] = item

    def _disagreement(self, work: Work, anchor: list[Token], p: int, t: Token, lemmas: dict[str, str | None],
                      unanimous: bool, vs_cons: bool | None) -> dict[str, Any]:
        classes = {s: classify_lemma_disagreement(t.lemma, lemmas[s]) for s in self.systems}
        worst = max(classes.values(), key=lambda c: CLASS_RANK.get(c, 0)) if classes else "real_disagreement"
        audit_vs_others = "audit_disagrees_with_consensus" if (unanimous and vs_cons is False) else (
            "others_disagree_among_themselves" if not unanimous else "audit_agrees_with_consensus")
        self.g2a_counts[worst] += 1
        self.freq[(t.surface, t.lemma)] += 1
        self.n_disagreements += 1
        if unanimous and vs_cons is False:
            self.disagreement_keys.add((work.stem, t.i))
        row = {"work_stem": work.stem, "token_index": t.i, "author": work.author, "subcorpus": work.subcorpus,
               "pos": t.pos, "surface": t.surface,
               **{f"lemma_{s}": lemmas[s] or "" for s in self.all_systems},
               **{f"g2a_{s}": classes[s] for s in self.systems},
               "g2a_class": worst, "pattern": audit_vs_others,
               "context": context_window(anchor, p, self.width)}
        self._tmp.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row

    # ------------------------------------------------------------------
    def _summary_block(self, n_aligned: int, pair_agree: Counter, all_agree: int, cons_n: int, cons_agree: int) -> dict[str, Any]:
        return {
            "n_aligned": n_aligned,
            "pairwise": {f"{x}__{y}": rate_block(pair_agree[(x, y)], n_aligned, "agree") for x, y in self.pairs},
            "all_systems_agree": rate_block(all_agree, n_aligned, "agree"),
            f"{self.audit}_vs_consensus_of_others": {
                **rate_block(cons_agree, cons_n, "agree"),
                "n_unanimous_others": cons_n,
                "note": "conditional on the other systems agreeing (selects easier tokens); report pairwise too",
            },
        }

    def finalize(self) -> dict[str, Any]:
        self._tmp.close()
        # worklist: frequency-ranked, written as disagreements.csv
        rows: list[dict[str, Any]] = []
        with self._tmp_path.open(encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    rows.append(json.loads(line))
        self._tmp_path.unlink(missing_ok=True)
        for r in rows:
            r["pair_token_count"] = self.freq[(r["surface"], r[f"lemma_{self.audit}"])]
        rows.sort(key=lambda r: (-r["pair_token_count"], r["surface"], r["work_stem"], r["token_index"]))
        if self.max_rows:
            rows = rows[: self.max_rows]
        fields = ["pair_token_count", "g2a_class", "pattern", "author", "subcorpus", "work_stem", "token_index", "pos",
                  "surface", *[f"lemma_{s}" for s in self.all_systems], *[f"g2a_{s}" for s in self.systems], "context"]
        path = self.out_dir / "disagreements.csv"
        with path.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)

        mean_loss = (sum(s["alignment_loss_a"] for s in self.align_stats) / len(self.align_stats)) if self.align_stats else 0.0
        drop = self.n_eligible - self.n_aligned
        summary: dict[str, Any] = {
            "method": "greedy surface alignment to the audit system (resync window 8); a token counts only when every "
                      "system aligned; lemma equality is accent-preserving NFC+casefold+sigma",
            "audit_system": self.audit,
            "systems": self.all_systems,
            "status": "ok" if self.systems and self.n_works else "skipped",
            "skip_reason": ("" if self.systems and self.n_works else
                            ("only one system requested/available" if not self.systems else "no work had output from every system")),
            "n_works_scored": self.n_works,
            "works_skipped": self.works_skipped,
            "population": {
                "n_anchor_tokens": self.n_anchor_tokens,
                "n_eligible_tokens": self.n_eligible,
                "n_fully_aligned": self.n_aligned,
                "alignment_drop": drop,
                "alignment_loss_pct": pct(drop, self.n_eligible),
                "flag_alignment_loss": (drop / self.n_eligible > ALIGN_FLAG) if self.n_eligible else False,
                **self._summary_block(self.n_aligned, self.pair_agree, self.all_agree, self.cons_n, self.cons_agree),
                "pairwise_article_neutral": {f"{x}__{y}": rate_block(self.pair_agree_conv[(x, y)], self.n_aligned, "agree") for x, y in self.pairs},
                "article_neutral_note": "same tokens, lemmas compared after mapping the article convention (ἡ, τό -> ὁ); reported beside strict agreement, never instead of it",
            },
            "work_alignment_loss_mean": round(mean_loss, 4),
            "flag_work_alignment_loss": mean_loss > ALIGN_FLAG,
            "by_author": {
                a: {"n_aligned": c["aligned"],
                    "all_systems_agree": rate_block(c["all_agree"], c["aligned"], "agree"),
                    "all_systems_agree_article_neutral": rate_block(c["all_agree_conv"], c["aligned"], "agree"),
                    f"{self.audit}_vs_consensus": rate_block(c["cons_agree"], c["cons_n"], "agree")}
                for a, c in sorted(self.by_author.items(), key=lambda kv: -kv[1]["aligned"])
            },
            "by_pos": {p: {"n_aligned": c["aligned"], "all_systems_agree": rate_block(c["all_agree"], c["aligned"], "agree")}
                       for p, c in sorted(self.by_pos.items(), key=lambda kv: -kv[1]["aligned"])},
            "disagreements": {
                "n_rows": self.n_disagreements,
                "n_written": len(rows),
                "file": path.name,
                "g2a_class_counts": dict(self.g2a_counts),
                f"n_{self.audit}_disagrees_with_unanimous_others": len(self.disagreement_keys),
                "g2a_note": "encoding_artifact = equal after NFC/casefold/sigma (should be ~0; >2/20 means fix normalisation); "
                            "accent_only = equal accent-blind; real_disagreement = different headword.",
            },
            "honesty_clause": HONESTY,
        }
        if self.sample_n:
            summary["sample"] = self._sample_summary()
        return summary

    def _sample_summary(self) -> dict[str, Any]:
        recs = self.reservoir
        n = len(recs)
        aligned = [r for r in recs if r["aligned"]]
        pair_agree: Counter = Counter()
        all_agree = cons_n = cons_agree = 0
        for r in aligned:
            L = r["lemmas"]
            ok = True
            for x, y in self.pairs:
                if lemmas_equal_strict(L[x], L[y]):
                    pair_agree[(x, y)] += 1
                else:
                    ok = False
            all_agree += int(ok)
            others = [L[s] for s in self.systems]
            if all(lemmas_equal_strict(others[0], o) for o in others[1:]):
                cons_n += 1
                cons_agree += int(lemmas_equal_strict(L[self.audit], others[0]))
        drop = n - len(aligned)
        return {
            "method": "Algorithm-R reservoir sample, uniform over audit-system tokens with surface+lemma, works in sorted order",
            "seed": self.seed,
            "n_requested": self.sample_n,
            "n_emitted": n,
            "population_tokens": self.seen_for_sample,
            "n_aligned": len(aligned),
            "alignment_drop": drop,
            "alignment_loss_pct": pct(drop, n),
            "flag_alignment_loss": (drop / n > ALIGN_FLAG) if n else False,
            **self._summary_block(len(aligned), pair_agree, all_agree, cons_n, cons_agree),
        }
