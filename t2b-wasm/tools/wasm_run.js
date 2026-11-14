// Run docs/tools/autocorrect/t2b.wasm under Node over stdin lines, through the page's own glue.js:
//   node t2b-wasm/tools/wasm_run.js WASM MODEL [-k 5] < lines.txt > out.jsonl
// Timing (load, per line) goes to stderr. Used by tools/wasm_vs_native.py.
'use strict';
const fs = require('fs');
const path = require('path');
const glue = require(path.join(__dirname, '..', '..', 'docs', 'tools', 'autocorrect', 'glue.js'));

const args = process.argv.slice(2);
let k = 5;
const kIdx = args.indexOf('-k');
if (kIdx >= 0) { k = +args[kIdx + 1]; args.splice(kIdx, 2); }
const [wasmPath, modelPath] = args;
const lines = fs.readFileSync(0, 'utf8').split('\n');
if (lines.length && lines[lines.length - 1] === '') lines.pop();

(async () => {
  const wasm = fs.readFileSync(wasmPath);
  const imports = WebAssembly.Module.imports(new WebAssembly.Module(wasm));
  const t0 = performance.now();
  const sc = await glue.create(wasm, fs.readFileSync(modelPath));
  const load = performance.now() - t0;
  const times = [];
  const out = [];
  for (const line of lines) {
    const t = performance.now();
    out.push(sc.segmentJSON(line, k));
    times.push(performance.now() - t);
  }
  fs.writeFileSync(1, out.join('\n') + '\n');
  times.sort((a, b) => a - b);
  const mean = times.reduce((a, b) => a + b, 0) / Math.max(times.length, 1);
  process.stderr.write(JSON.stringify({
    imports: imports.length, load_ms: +load.toFixed(1), lines: times.length, mean_ms: +mean.toFixed(2),
    median_ms: +(times[times.length >> 1] || 0).toFixed(2), p95_ms: +(times[Math.floor(times.length * 0.95)] || 0).toFixed(2),
    max_ms: +(times[times.length - 1] || 0).toFixed(2), info: sc.info,
  }) + '\n');
})().catch((e) => { console.error(e); process.exit(1); });
