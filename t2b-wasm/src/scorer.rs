//! Lexicon with the confusion channel, the bigram LM, the beam segmenter and the flags: a line-by-line port
//! of t2b_scorer.Lexicon / Segmenter and t2b_flag.flag_words. Same constants, same candidate order, same
//! stable sorts; see README "Parity" for where tie order can differ.

use crate::letters::*;
use crate::math::{exp, ln};
use crate::model::Model;
use std::collections::HashMap;

pub const BEAM: usize = 48;
pub const PER_LAST: usize = 4;
pub const CAND_TOP: usize = 8;
pub const MAX_UNK: usize = 10;
pub const FLAG_TOP: usize = 12;
pub const FLAG_MARGIN: f64 = 4.0;

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Edit {
    None,
    Sub(u32),
    /// a lost letter restored: the letter, its position in the form, and substitutions besides
    Lost { letter: u8, pos: u32, subs: u32 },
    Unknown,
}

impl Edit {
    /// the reference's edit tag: "", "sub1", "lost:Ν@3", "lost:Ν@3+sub1", "unknown"
    pub fn tag(&self) -> String {
        match *self {
            Edit::None => String::new(),
            Edit::Sub(n) => format!("sub{n}"),
            Edit::Lost { letter, pos, subs } => {
                let mut s = format!("lost:{}@{}", LETTERS[letter as usize], pos);
                if subs > 0 {
                    s.push_str(&format!("+sub{subs}"));
                }
                s
            }
            Edit::Unknown => "unknown".into(),
        }
    }
}

#[derive(Clone, Copy, Debug)]
pub struct Cand {
    pub id: u32,
    pub cost: f64,
    pub edit: Edit,
}

#[derive(Clone, Debug)]
pub struct Segment {
    pub start: usize,
    pub end: usize,
    pub form: Option<u32>,
    pub edit: Edit,
    /// LM term of this segment (0 for an unknown segment) and its channel cost
    pub lm: f64,
    pub chan: f64,
}

#[derive(Clone, Debug)]
pub struct Reading {
    pub score: f64,
    pub segments: Vec<Segment>,
}

#[derive(Clone, Debug)]
pub struct Flag {
    pub segment: usize,
    pub unattested: bool,
    pub alternative: bool,
    /// best in-channel alternative: (id, edit, score in context minus the reading as written)
    pub best: Option<(u32, Edit, f64)>,
}

impl Flag {
    pub fn kind(&self) -> &'static str {
        match (self.unattested, self.alternative) {
            (true, true) => "unattested+alt",
            (true, false) => "unattested",
            _ => "alternative",
        }
    }
}

pub struct Scorer {
    pub m: Model,
    pub log_n: f64,
    ulogp: Vec<f64>,  // math.log(uni) - logN
    pu: Vec<f64>,     // exp(ulogp)
    log_pu: Vec<f64>, // log(pu)
    b_coef_n1: Vec<f64>,
}

#[derive(Clone, Copy)]
struct Node {
    score: f64,
    last: i64,
    parent: u32,
    seg_i: u32,
    seg_j: u32,
    wid: i64,
    lm: f64,
    chan: f64,
    edit: Edit,
}

const NONE: u32 = u32::MAX;

fn sub_cost(obs: &[u8], form: &[u8]) -> (f64, u32) {
    let mut n = 0;
    let mut cost = 0.0f64;
    for (a, b) in obs.iter().zip(form.iter()) {
        if a != b {
            n += 1;
            cost += log_sub(*b);
        }
    }
    (cost, n)
}

#[derive(PartialEq, Eq, Hash, Clone)]
enum WordKey {
    Form(u32),
    Unk(Vec<u8>),
}

impl Scorer {
    pub fn new(m: Model) -> Scorer {
        let log_n = ln(m.n_tokens as f64);
        let ulogp: Vec<f64> = m.uni.iter().map(|&u| ln((u as f64).max(1e-12)) - log_n).collect();
        let pu: Vec<f64> = ulogp.iter().map(|&x| exp(x)).collect();
        let log_pu: Vec<f64> = pu.iter().map(|&x| ln(x)).collect();
        let b_coef_n1 = m.n1.iter().map(|&x| DISCOUNT * x as f64).collect();
        Scorer { m, log_n, ulogp, pu, log_pu, b_coef_n1 }
    }

    /// log P(w | prev) under the interpolated absolute-discounting bigram LM (Segmenter.lm_grid); prev < 0 =
    /// no context
    #[inline]
    pub fn lm(&self, prev: i64, w: u32) -> f64 {
        if prev < 0 {
            return self.log_pu[w as usize];
        }
        let pv = prev as usize;
        let cv = self.m.ctx[pv];
        if cv == 0 {
            return self.log_pu[w as usize];
        }
        let cvw = self.m.bigram(pv as u32, w) as f64;
        let cvs = cv as f64;
        let a = cvw - DISCOUNT;
        let a = if a > 0.0 { a } else { 0.0 };
        let p = a / cvs + self.b_coef_n1[pv] / cvs * self.pu[w as usize];
        ln(if p > 1e-300 { p } else { 1e-300 })
    }

    pub fn unigram_logp(&self, id: u32) -> f64 {
        self.ulogp[id as usize]
    }

    /// Forms that could have produced `obs` (Lexicon._candidates): best `top` by unigram + channel.
    pub fn candidates(&self, obs: &[u8], top: usize) -> Vec<Cand> {
        let mut out: Vec<Cand> = Vec::new();
        let mut pos: HashMap<u32, usize> = HashMap::new();
        let mut put = |out: &mut Vec<Cand>, c: Cand| match pos.get(&c.id) {
            None => {
                pos.insert(c.id, out.len());
                out.push(c);
            }
            Some(&p) => {
                if c.cost > out[p].cost {
                    out[p].cost = c.cost;
                    out[p].edit = c.edit;
                }
            }
        };
        let fo: Vec<u8> = obs.iter().map(|&c| FOLD[c as usize]).collect();
        for &i in self.m.fold_range(&fo) {
            let (cost, n) = sub_cost(obs, self.m.key(i));
            put(&mut out, Cand { id: i, cost, edit: if n > 0 { Edit::Sub(n) } else { Edit::None } });
        }
        if obs.len() >= 2 && obs.len() < self.m.max_len {
            // the reference looks up fo[:p] + ch + fo[p:] for every slot p and letter ch; the same lookups are
            // done here by narrowing a sorted range letter by letter, which skips the (many) empty ones early
            // and yields the same ids in the same order
            let mut red: Vec<u8> = Vec::with_capacity(obs.len());
            let (mut plo, mut phi) = (0usize, self.m.n); // keys sharing fo[..p]
            for p in 0..=fo.len() {
                if plo == phi {
                    break; // no key starts with fo[..p], so none with any longer prefix of it
                }
                for &ch in FOLD_ALPHABET.iter() {
                    let (mut lo, mut hi) = self.m.fold_narrow(plo, phi, p, ch);
                    for (d, &c) in fo[p..].iter().enumerate() {
                        if lo == hi {
                            break;
                        }
                        (lo, hi) = self.m.fold_narrow(lo, hi, p + 1 + d, c);
                    }
                    if lo == hi {
                        continue;
                    }
                    for &i in self.m.fold_exact_in(lo, hi, fo.len() + 1) {
                        let form = self.m.key(i);
                        red.clear();
                        red.extend_from_slice(&form[..p]);
                        red.extend_from_slice(&form[p + 1..]);
                        let (cost, n) = sub_cost(obs, &red);
                        let cost = cost + LOG_DEL;
                        put(&mut out, Cand { id: i, cost, edit: Edit::Lost { letter: form[p], pos: p as u32, subs: n } });
                    }
                }
                if p < fo.len() {
                    (plo, phi) = self.m.fold_narrow(plo, phi, p, fo[p]);
                }
            }
        }
        // sorted(out.items(), key=lambda kv: -(unigram_logp + cost))[:top] -- a stable sort on the key
        let keyf = |c: &Cand| -(self.ulogp[c.id as usize] + c.cost);
        out.sort_by(|a, b| keyf(a).partial_cmp(&keyf(b)).unwrap());
        out.truncate(top);
        out
    }

    fn prune(nodes: &[Node], h: &[u32]) -> Vec<u32> {
        let mut v: Vec<u32> = h.to_vec();
        v.sort_by(|&a, &b| (-nodes[a as usize].score).partial_cmp(&(-nodes[b as usize].score)).unwrap());
        let mut out = Vec::with_capacity(BEAM.min(v.len()));
        let mut per: HashMap<i64, usize> = HashMap::new();
        for x in v {
            let c = per.entry(nodes[x as usize].last).or_insert(0);
            if *c >= PER_LAST {
                continue;
            }
            *c += 1;
            out.push(x);
            if out.len() >= BEAM {
                break;
            }
        }
        out
    }

    /// k best readings of a scriptio-continua string (letter codes), Segmenter.segment
    pub fn segment_codes(&self, s: &[u8], k: usize) -> Vec<Reading> {
        let n = s.len();
        if n == 0 {
            return vec![Reading { score: 0.0, segments: vec![] }];
        }
        // candidates per start: (end, id or -1, channel cost, edit); built by length ascending
        let mut cache: HashMap<&[u8], Vec<Cand>> = HashMap::new();
        let mut cands: Vec<Vec<(usize, i64, f64, Edit)>> = vec![Vec::new(); n];
        for i in 0..n {
            // range(1, min(max_len + 1, n - i) + 1) as in the reference (length max_len + 1 yields nothing)
            for l in 1..=(self.m.max_len + 1).min(n - i) {
                let obs = &s[i..i + l];
                let cs = cache.entry(obs).or_insert_with(|| self.candidates(obs, CAND_TOP));
                for c in cs.iter() {
                    cands[i].push((i + l, c.id as i64, c.cost, c.edit));
                }
                if l <= MAX_UNK {
                    cands[i].push((i + l, -1, LOG_P_UNK + l as f64 * LOG_UNK_LETTER, Edit::Unknown));
                }
            }
        }
        let mut nodes: Vec<Node> = vec![Node {
            score: 0.0,
            last: -1,
            parent: NONE,
            seg_i: 0,
            seg_j: 0,
            wid: -1,
            lm: 0.0,
            chan: 0.0,
            edit: Edit::None,
        }];
        let mut hyps: Vec<Vec<u32>> = vec![Vec::new(); n + 1];
        hyps[0].push(0);
        let mut tot: Vec<f64> = Vec::new();
        let mut lmv: Vec<f64> = Vec::new();
        let mut flat: Vec<(f64, usize)> = Vec::new();
        for i in 0..n {
            let h = Self::prune(&nodes, &hyps[i]);
            hyps[i] = h.clone();
            let c = &cands[i];
            if h.is_empty() || c.is_empty() {
                continue;
            }
            let nc = c.len();
            tot.clear();
            lmv.clear();
            for &hid in &h {
                let hn = nodes[hid as usize];
                for &(_, cid, chan, _) in c.iter() {
                    let lm = if cid < 0 { 0.0 } else { self.lm(hn.last, cid as u32) };
                    lmv.push(lm);
                    tot.push(hn.score + lm + chan);
                }
            }
            // group the columns by end position (contiguous, ascending: candidates are built by length)
            let mut a = 0;
            while a < nc {
                let j = c[a].0;
                let mut b = a;
                while b < nc && c[b].0 == j {
                    b += 1;
                }
                let ncols = b - a;
                flat.clear();
                for (hi, _) in h.iter().enumerate() {
                    for ci in 0..ncols {
                        flat.push((tot[hi * nc + a + ci], hi * ncols + ci));
                    }
                }
                let m = BEAM.min(flat.len());
                // top m by score; equal scores keep flat order (numpy's argpartition order is unspecified)
                flat.sort_by(|x, y| y.0.partial_cmp(&x.0).unwrap().then(x.1.cmp(&y.1)));
                for &(score, t) in flat[..m].iter() {
                    let (hi, ci) = (t / ncols, t % ncols);
                    let col = a + ci;
                    let (jj, cid, chan, edit) = c[col];
                    nodes.push(Node {
                        score,
                        last: cid,
                        parent: h[hi],
                        seg_i: i as u32,
                        seg_j: jj as u32,
                        wid: cid,
                        lm: lmv[hi * nc + col],
                        chan,
                        edit,
                    });
                    hyps[j].push((nodes.len() - 1) as u32);
                }
                a = b;
            }
        }
        let mut fin = hyps[n].clone();
        fin.sort_by(|&a, &b| (-nodes[a as usize].score).partial_cmp(&(-nodes[b as usize].score)).unwrap());
        let mut out = Vec::new();
        let mut seen: std::collections::HashSet<Vec<WordKey>> = std::collections::HashSet::new();
        for hid in fin {
            let mut segs = Vec::new();
            let mut x = hid;
            while x != NONE && nodes[x as usize].parent != NONE {
                let nd = nodes[x as usize];
                segs.push(Segment {
                    start: nd.seg_i as usize,
                    end: nd.seg_j as usize,
                    form: if nd.wid >= 0 { Some(nd.wid as u32) } else { None },
                    edit: nd.edit,
                    lm: nd.lm,
                    chan: nd.chan,
                });
                x = nd.parent;
            }
            segs.reverse();
            let key: Vec<WordKey> = segs
                .iter()
                .map(|g| match g.form {
                    Some(id) => WordKey::Form(id),
                    None => WordKey::Unk(s[g.start..g.end].to_vec()),
                })
                .collect();
            if !seen.insert(key) {
                continue;
            }
            out.push(Reading { score: nodes[hid as usize].score, segments: segs });
            if out.len() >= k {
                break;
            }
        }
        out
    }

    /// k best readings of any Greek text (normalised with to_continua first)
    pub fn segment(&self, text: &str, k: usize) -> (Vec<u8>, Vec<Reading>) {
        let s = to_continua(text);
        let r = self.segment_codes(&s, k);
        (s, r)
    }

    fn flag_lp(&self, prev: i64, wid: i64) -> f64 {
        if wid < 0 {
            LOG_P_UNK + 3.0 * LOG_UNK_LETTER // unknown, length-neutral
        } else {
            self.lm(prev, wid as u32)
        }
    }

    /// t2b_flag.flag_words applied to the observed words of a reading's segmentation: a word is flagged if
    /// it is unattested as written, or if a form reachable through the channel scores more than 4 nats
    /// better in context (P(w | prev) + channel + P(next | w)).
    pub fn flags(&self, s: &[u8], r: &Reading) -> Vec<Flag> {
        let words: Vec<&[u8]> = r.segments.iter().map(|g| &s[g.start..g.end]).collect();
        let ids: Vec<i64> = words.iter().map(|w| self.m.exact(w).map(|x| x as i64).unwrap_or(-1)).collect();
        let mut out = Vec::new();
        for (i, w) in words.iter().enumerate() {
            let prev = if i > 0 { ids[i - 1] } else { -1 };
            let nxt = ids.get(i + 1).copied();
            let wid = ids[i];
            let next_term = |id: i64| match nxt {
                Some(nx) if nx >= 0 => self.flag_lp(id, nx),
                _ => 0.0,
            };
            let base = self.flag_lp(prev, wid) + next_term(wid);
            let mut best: Option<(f64, u32, Edit)> = None;
            for c in self.candidates(w, FLAG_TOP) {
                if c.id as i64 == wid {
                    continue;
                }
                let sc = self.flag_lp(prev, c.id as i64) + c.cost + next_term(c.id as i64);
                if best.map_or(true, |b| sc > b.0) {
                    best = Some((sc, c.id, c.edit));
                }
            }
            let unatt = wid < 0;
            let alt = best.is_some_and(|b| b.0 - base > FLAG_MARGIN);
            if unatt || alt {
                out.push(Flag {
                    segment: i,
                    unattested: unatt,
                    alternative: alt,
                    best: best.map(|b| (b.1, b.2, b.0 - base)),
                });
            }
        }
        out
    }
}
