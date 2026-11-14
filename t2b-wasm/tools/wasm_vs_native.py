"""The shipped t2b.wasm (run under Node through the page's glue.js) against the native t2b-cli: the JSON for
every parity input must be byte-identical (both builds use the crate's own ln/exp, so no float can differ).

  python -I -X utf8 t2b-wasm/tools/wasm_vs_native.py [--limit N]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import parity as P  # noqa: E402

DOCS = P.REPO / "docs" / "tools" / "autocorrect"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args(argv)
    rows = P.inputs(a.limit)
    with tempfile.TemporaryDirectory() as td:
        inp = Path(td) / "in.txt"
        inp.write_text("\n".join(r["text"] for r in rows) + "\n", encoding="utf-8")
        with open(inp, encoding="utf-8") as fh:
            nat = subprocess.run([str(P.CLI), str(DOCS / "model.bin"), "-k", "5", "--time"], stdin=fh,
                                 capture_output=True, check=True)
        with open(inp, encoding="utf-8") as fh:
            was = subprocess.run(["node", str(HERE / "wasm_run.js"), str(DOCS / "t2b.wasm"), str(DOCS / "model.bin"),
                                  "-k", "5"], stdin=fh, capture_output=True, check=True)
    n_lines = nat.stdout.decode("utf-8").splitlines()
    w_lines = was.stdout.decode("utf-8").splitlines()
    same = sum(x == y for x, y in zip(n_lines, w_lines))
    wt = json.loads(was.stderr.decode("utf-8").strip().splitlines()[-1])
    report = {"inputs": len(rows), "identical": same, "native_lines": len(n_lines), "wasm_lines": len(w_lines),
              "native_timing": nat.stderr.decode("utf-8").strip().splitlines(), "wasm_node_timing": wt,
              "wasm_bytes": (DOCS / "t2b.wasm").stat().st_size, "model_bytes": (DOCS / "model.bin").stat().st_size}
    if not a.limit:
        (P.OUT / "wasm_vs_native.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=1))
    if same != len(rows) or len(w_lines) != len(rows):
        raise SystemExit("wasm and native outputs differ")


if __name__ == "__main__":
    main()
