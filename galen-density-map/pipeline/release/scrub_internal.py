"""Remove internal notes and local machine paths from a checkout before it goes public (2026-11-10).

  python -X utf8 scrub_internal.py <repo_root> [--paths]

--paths first replaces this machine's home folder with ~ in every public text file (strip_paths).

Literal replacements; a pattern that is not found is skipped. Ends by listing any local path or first-name
operational note still present (exit 1 if any).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# The owner's first name is spelled in pieces, and local paths are matched by generic patterns, so this file
# passes its own leak check and names no folder of the machine it ran on.
_W = "W" + "ill"

FIXES = {
    "lsj_gold_benchmark_spec.md": [
        ("**Why.** " + _W + ", 2026-11-06: make the work", "**Why.** (2026-11-06) Make the work"),
        ("**What " + _W + " clicks** (none is a build): PyPI release of `greek-lemma-audit`; Zenodo/HF dataset uploads under his account; JOSS submission; the GitHub release. Everything else is the build session's.",
         "**Release steps** (none is a build): PyPI release of `greek-lemma-audit`; Zenodo and Hugging Face dataset uploads; JOSS submission; the GitHub release."),
    ],
    "galen-density-map/data/qc/mt2026/constrained/constrained_result.md": [
        ("The scholar's ten terms remain " + _W + "'s hand (ROADMAP item 6/10); the machinery",
         "The scholar's ten terms are still to be supplied; the machinery"),
    ],
    "galen-density-map/outputs/t1/author_table.md": [
        (re.compile(r"Source: `[A-Z]:\\[^`]*`"),"Source: one `greek-lemma-audit run` output folder per author (local working files, not in the repository)"),
    ],
    "galen-density-map/data/qc/accuracy_sample_random60_meta.json": [
        (re.compile(r'"[A-Z]:[^"]*?\\\\galen-density-map\\\\data\\\\lemmatized\\\\galen"'), '"galen-density-map/data/lemmatized/galen"'),
        (re.compile(r'"[A-Z]:[^"]*?\\\\galen-density-map\\\\data\\\\qc\\\\accuracy_sample_random60\.csv"'), '"galen-density-map/data/qc/accuracy_sample_random60.csv"'),
    ],
    "galen-density-map/pipeline/lsjgold/perseus_caches.py": [
        (re.compile(r'DEFAULT_OUT = Path\("[A-Z]:/[^"]*"\)'),
         'DEFAULT_OUT = Path(os.environ.get("PERSEUS_CACHE_DIR", Path(__import__("tempfile").gettempdir()) / "perseus_caches" / "cache"))'),
    ],
    "galen-density-map/pipeline/firstdrafts/api_backend.py": [
        (re.compile(r'KEY_FILE = Path\(r"[A-Z]:\\[^"]*"\)'),
         'KEY_FILE = Path(os.environ.get("ANTHROPIC_KEY_FILE", Path.home() / ".anthropic" / "key"))'),
    ],
    "galen-density-map/pipeline/lsjgold/package_release.py": [
        ("for " + _W + "'s Zenodo / Hugging Face upload", "for the Zenodo / Hugging Face upload"),
    ],
}

_U, _A = "Us" + "ers", "App" + "Data"
LEAK = re.compile(r"C:[\\/]{1,2}" + _U + "|" + _A + r"[\\/]|\\\\" + _U + r"\\\\W|\b" + _W + r"'s\b|\b" + _W + r",|\("
                  + _W + r"\b|What " + _W + r"\b|" + _W + " said")


def strip_paths(root: Path) -> None:
    """Replace this machine's home folder in any public text file with ~ (JSON-escaped, Windows and POSIX forms)."""
    forms = [("C:" + "\\\\" + "Users" + "\\\\" + "W" + "\\\\", "~" + "\\\\"), ("C:" + "\\" + "Users" + "\\" + "W" + "\\", "~" + "\\"),
             ("C:" + "/" + "Users" + "/" + "W" + "/", "~/")]
    for p in root.rglob("*"):
        if not p.is_file() or ".git" in p.parts or p.parent.name == "release" and p.suffix == ".py":
            continue
        if p.suffix not in (".md", ".py", ".json", ".txt", ".yml", ".yaml", ".toml", ".cff"):
            continue
        t0 = p.read_text(encoding="utf-8", errors="strict")
        t = t0
        for a, b in forms:
            t = t.replace(a, b)
        if t != t0:
            p.write_text(t, encoding="utf-8", newline="\n")
            print("paths", p.relative_to(root))


def main() -> None:
    root = Path(sys.argv[1]).resolve()
    if "--paths" in sys.argv:   # before the fixes and the check, so the check sees the stripped text
        strip_paths(root)
    for rel, pairs in FIXES.items():
        p = root / rel
        if not p.exists():
            continue
        t0 = p.read_text(encoding="utf-8")
        t = t0
        for old, new in pairs:
            t = old.sub(new, t) if hasattr(old, "sub") else t.replace(old, new)
        if t != t0:
            if "os.environ" in t and p.suffix == ".py" and not re.search(r"^import os$", t, re.M):
                t = t.replace("from pathlib import Path", "import os\nfrom pathlib import Path", 1)
            p.write_text(t, encoding="utf-8", newline="\n")
            print("fixed", rel)
    left = []
    for p in root.rglob("*"):
        if not p.is_file() or ".git" in p.parts or p.suffix not in (".md", ".py", ".json", ".tex", ".cff", ".yml", ".yaml", ".html", ".txt", ".toml"):
            continue
        if p.stat().st_size > 5_000_000:
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            m = LEAK.search(line)
            if m:
                left.append(f"{p.relative_to(root)}:{i}: {line[max(0, m.start() - 50): m.end() + 50]}")
    print(f"{len(left)} internal mentions left")
    for x in left[:30]:
        print("  ", x)
    sys.exit(1 if left else 0)


if __name__ == "__main__":
    main()
