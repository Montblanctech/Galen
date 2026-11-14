//! Native CLI for the parity harness and for timing:
//!   t2b-cli MODEL.bin [-k 5] [--time] [--no-spelling] < lines.txt > out.jsonl
//! One input line (any Greek text) per stdin line; one JSON object per output line.
//!   t2b-cli MODEL.bin --text [-k 5] < text.txt > out.json
//! The whole of stdin as one text, read with the writer's habits (segment_text_json); one JSON object.

use std::io::{BufRead, Write};
use std::time::Instant;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let mut model = None;
    let mut k = 5usize;
    let mut time = false;
    let mut text_mode = false;
    let mut spelling = true;
    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "-k" => {
                k = args.get(i + 1).and_then(|x| x.parse().ok()).expect("-k N");
                i += 1;
            }
            "--time" => time = true,
            "--text" => text_mode = true,
            "--no-spelling" => spelling = false,
            a => model = Some(a.to_string()),
        }
        i += 1;
    }
    let model = model.expect("usage: t2b-cli MODEL.bin [-k 5] [--time] < lines");
    let t0 = Instant::now();
    let data = std::fs::read(&model).expect("read model");
    let m = t2b::model::Model::from_bytes(&data).expect("decode model");
    let mut sc = t2b::scorer::Scorer::new(m);
    sc.spelling = spelling;
    if time {
        eprintln!("load {:.1} ms; {}", t0.elapsed().as_secs_f64() * 1e3, t2b::info_json(&sc));
    }
    let stdin = std::io::stdin();
    if text_mode {
        let mut all = String::new();
        std::io::Read::read_to_string(&mut stdin.lock(), &mut all).expect("read stdin");
        println!("{}", t2b::segment_text_json(&mut sc, &all, k));
        return;
    }
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
