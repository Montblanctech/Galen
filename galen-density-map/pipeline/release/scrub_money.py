"""Remove every mention of money and API token usage from a checkout before it goes public (rule of 2026-11-10:
"There shouldn't be anything about money or tokens"). Greek word/token counts of the texts stay: they describe the
text, not usage.

  python -X utf8 scrub_money.py <repo_root> [--public]

Text rules apply to CHANGELOG.md and outputs/firstdrafts/*/README.md. With --public it also deletes the usage and
cost files and strips usage keys from every JSON/JSONL under outputs/firstdrafts/ and docs/first-drafts/.
Ends with a check that lists anything still matching; exit code 1 if something is left.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

DROP_FILES = ("usage.jsonl", "cost_estimate.json", "cost_projection.json")
DROP_KEYS = {"usd", "cum_usd", "usage", "input_tokens", "output_tokens", "cache_creation_input_tokens",
             "cache_read_input_tokens", "n_words_for_cost", "usd_batch", "total_usd_direct", "total_usd_batch"}

# (pattern, replacement, flags); applied in order
RULES = [
    (r" Cycle 3 spend \$[\d.,]+ \(`usage\.jsonl` per work\); programme total \$[\d.,]+\.", "", 0),
    (r"; \$[\d.,]+(?= ·)", "", 0),
    (r"; \$[\d.,]+\.", ".", 0),
    (r" Pre-run estimate \$[\d.,]+ direct / \$[\d.,]+ batch under a \$[\d,]+ cap\.", "", 0),
    (r" \(\$[\d.,]+\)", "", 0),
    (r"per-call usage and USD to `usage\.jsonl`; `--budget` stop; ", "", 0),
    (r"stopped on a credit refusal with", "stopped with", 0),
    (r"^- Cost \(`usage\.jsonl`, list prices\):.*\n", "", re.M),
    (r"^## Cost \(`cost_estimate\.json`, before the run\)\n.*?\n\n", "", re.M | re.S),
    (r"^\*\*Spend: .*?\n\n", "", re.M | re.S),
    (r"cost rule, ", "", 0),
    (r"resume, pricing and parsers", "resume and parsers", 0),
    (r" The run paused once at [0-9:]+ when the API account's prepaid balance ran out \((.*?)\) and resumed from its files at [0-9:]+ after the account was funded;",
     r" The run paused once (\1) and resumed from its files;", 0),
    (r"`checks\.json`, `usage\.jsonl`\)", "`checks.json`)", 0),
    (r"`cost_estimate\.json`, ", "", 0),
    (r", `usage\.jsonl`", "", 0),
    (r"`usage\.jsonl`, ", "", 0),
    (r", prompt SHA-256 and usage on every row", ", prompt SHA-256 on every row", 0),
    (r"by W" r"ill's rule \(2026-11-09\) no script calls the paid Claude API; `translate\.py` had an API backend for the case where a key existed, it was never used \(no key is configured on this machine\) and was removed\.",
     "no script called the Claude API for this work.", 0),
    (r" The API-equivalent cost estimated before the run was \$[\d.,]+ \(`cost_estimate\.json`\); the actual charge is subscription usage\.", "", 0),
    (r"; about [\d.]+M subagent tokens as reported by the Agent tool", "", 0),
]

CHECK = re.compile(r"\$\s?\d|\busd\b|usage\.jsonl|cost_estimate|cost_projection|\bbudget\b|\bspen[dt]\b|credit refusal|prepaid|"
                   r"subscription|list prices?|funded|input_tokens|output_tokens|\bM tokens\b|subagent tokens|thinking allowance", re.I)


def text_files(root: Path) -> list[Path]:
    fd = root / "galen-density-map" / "outputs" / "firstdrafts"
    return [root / "CHANGELOG.md"] + sorted(fd.glob("*/README.md"))


def strip(o):
    if isinstance(o, dict):
        return {k: strip(v) for k, v in o.items() if k not in DROP_KEYS}
    if isinstance(o, list):
        return [strip(v) for v in o]
    return o


def main() -> None:
    root = Path(sys.argv[1]).resolve()
    public = "--public" in sys.argv
    for p in text_files(root):
        if not p.exists():
            continue
        t0 = p.read_text(encoding="utf-8")
        t = t0
        for pat, rep, fl in RULES:
            t = re.sub(pat, rep, t, flags=fl)
        if t != t0:
            p.write_text(t, encoding="utf-8", newline="\n")
            print("edited", p.relative_to(root))
    data_dirs = [root / "galen-density-map" / "outputs" / "firstdrafts", root / "docs" / "first-drafts"]
    if public:
        for d in data_dirs:
            for name in DROP_FILES:
                for p in d.rglob(name):
                    p.unlink()
                    print("deleted", p.relative_to(root))
            for p in list(d.rglob("*.jsonl")) + list(d.rglob("*.json")):
                raw = p.read_text(encoding="utf-8")
                if not re.search(r'"(' + "|".join(DROP_KEYS) + r')"\s*:', raw):
                    continue
                if p.suffix == ".jsonl":
                    out = "".join(json.dumps(strip(json.loads(line)), ensure_ascii=False) + "\n" for line in raw.splitlines() if line.strip())
                else:
                    out = json.dumps(strip(json.loads(raw)), ensure_ascii=False, indent=1 if "\n " in raw[:200] else None)
                p.write_text(out, encoding="utf-8", newline="\n")
                print("stripped", p.relative_to(root))
    left = []
    scan = text_files(root) + ([f for d in data_dirs for f in list(d.rglob("*.json")) + list(d.rglob("*.jsonl"))] if public else [])
    for p in scan:
        if not p.exists():
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if p.suffix in (".json", ".jsonl"):
                hit = re.search(r'"(' + "|".join(DROP_KEYS) + r')"\s*:', line)
            else:
                hit = CHECK.search(line)
            if hit:
                left.append(f"{p.relative_to(root)}:{i}: {line[max(0, hit.start() - 60): hit.end() + 60]}")
    print(f"{len(left)} mentions left")
    for x in left[:40]:
        print("  ", x)
    sys.exit(1 if left else 0)


if __name__ == "__main__":
    main()
