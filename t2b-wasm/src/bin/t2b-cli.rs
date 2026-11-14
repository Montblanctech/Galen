//! Native CLI for the parity harness and for timing:
//!   t2b-cli MODEL.bin [-k 5] [--time] < lines.txt > out.jsonl
//! One input line (any Greek text) per stdin line; one JSON object per output line.

use std::io::{BufRead, Write};
use std::time::Instant;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let mut model = None;
    let mut k = 5usize;
    let mut time = false;
    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "-k" => {
                k = args.get(i + 1).and_then(|x| x.parse().ok()).expect("-k N");
                i += 1;
            }
            "--time" => time = true,
            a => model = Some(a.to_string()),
        }
        i += 1;
    }
    let model = model.expect("usage: t2b-cli MODEL.bin [-k 5] [--time] < lines");
    let t0 = Instant::now();
    let data = std::fs::read(&model).expect("read model");
    let m = t2b::model::Model::from_bytes(&data).expect("decode model");
    let sc = t2b::scorer::Scorer::new(m);
    if time {
        eprintln!("load {:.1} ms; {}", t0.elapsed().as_secs_f64() * 1e3, t2b::info_json(&sc));
    }
    let stdin = std::io::stdin();
    let stdout = std::io::stdout();
    let mut out = std::io::BufWriter::new(stdout.lock());
    let mut times = Vec::new();
    for line in stdin.lock().lines() {
        let line = line.expect("read stdin");
        let t = Instant::now();
        let j = t2b::segment_json(&sc, &line, k);
        times.push(t.elapsed().as_secs_f64() * 1e3);
        writeln!(out, "{j}").unwrap();
    }
    out.flush().unwrap();
    if time && !times.is_empty() {
        let mut s = times.clone();
        s.sort_by(|a, b| a.partial_cmp(b).unwrap());
        let mean = s.iter().sum::<f64>() / s.len() as f64;
        eprintln!(
            "{} lines: mean {:.2} ms, median {:.2} ms, p95 {:.2} ms, max {:.2} ms",
            s.len(),
            mean,
            s[s.len() / 2],
            s[(s.len() * 95 / 100).min(s.len() - 1)],
            s[s.len() - 1]
        );
    }
}
