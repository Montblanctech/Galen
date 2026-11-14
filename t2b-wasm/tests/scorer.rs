//! Native tests: model format, channel candidates, LM formula, segmentation, flags, JSON, and (when
//! docs/tools/autocorrect/model.bin is present) the real model against values from the Python reference.

use t2b::letters::*;
use t2b::model::{crc32, Model};
use t2b::scorer::{Edit, Scorer};

fn varint(out: &mut Vec<u8>, mut v: u64) {
    loop {
        let b = (v & 0x7f) as u8;
        v >>= 7;
        if v == 0 {
            out.push(b);
            return;
        }
        out.push(b | 0x80);
    }
}

fn codes(s: &str) -> Vec<u8> {
    string_to_letters(s).expect("Greek capitals")
}

/// A model.bin writer for tests (same layout as t2b_export_model.encode). forms: (key, count, ctx, n1);
/// bigrams: (left, right, count).
fn encode(forms: &[(&str, u32, u32, u32)], bigrams: &[(&str, &str, u32)], n_tokens: u64, bigram_min: u32) -> Vec<u8> {
    let form_min = 2u32;
    let mut alpha: Vec<usize> = (0..forms.len()).collect();
    alpha.sort_by_key(|&i| codes(forms[i].0));
    let mut rank: Vec<usize> = (0..forms.len()).collect(); // id -> form index
    rank.sort_by(|&a, &b| forms[b].1.cmp(&forms[a].1).then(codes(forms[a].0).cmp(&codes(forms[b].0))));
    let id_of = |k: &str| rank.iter().position(|&i| forms[i].0 == k).unwrap() as u32;
    let mut sec: Vec<Vec<u8>> = vec![Vec::new(); 8];
    let maxlen = forms.iter().map(|f| codes(f.0).len()).max().unwrap();
    for v in [forms.len() as u64, bigrams.len() as u64, n_tokens, form_min as u64, bigram_min as u64, maxlen as u64] {
        varint(&mut sec[0], v);
    }
    let mut prev: Vec<u8> = Vec::new();
    for &i in &alpha {
        let k = codes(forms[i].0);
        let s = prev.iter().zip(k.iter()).take_while(|(a, b)| a == b).count();
        sec[1].push(s as u8);
        sec[1].push((k.len() - s) as u8);
        sec[1].extend_from_slice(&k[s..]);
        prev = k;
        varint(&mut sec[2], (forms[i].1 - form_min) as u64);
        varint(&mut sec[3], (forms[i].1 - forms[i].2) as u64);
        varint(&mut sec[4], forms[i].3 as u64);
    }
    let mut bk: Vec<(u32, u32, u32)> = bigrams.iter().map(|&(l, r, c)| (id_of(l), id_of(r), c)).collect();
    bk.sort();
    for id in 0..forms.len() as u32 {
        let row: Vec<&(u32, u32, u32)> = bk.iter().filter(|b| b.0 == id).collect();
        varint(&mut sec[5], row.len() as u64);
        let mut last: i64 = -1;
        for b in row {
            varint(&mut sec[6], (b.1 as i64 - last - 1) as u64);
            varint(&mut sec[7], (b.2 - bigram_min) as u64);
            last = b.1 as i64;
        }
    }
    let mut body = Vec::new();
    for s in &sec {
        body.extend_from_slice(&(s.len() as u32).to_le_bytes());
        body.extend_from_slice(s);
    }
    let mut out = b"T2BM\x01\x00\x00\x00".to_vec();
    out.extend_from_slice(&body);
    out.extend_from_slice(&crc32(&body).to_le_bytes());
    out
}

fn toy() -> Scorer {
    let forms = [
        ("ΚΑΙ", 500, 480, 40),
        ("ΤΟΝ", 300, 290, 30),
        ("ΛΟΓΟΝ", 120, 110, 20),
        ("ΤΗΝ", 200, 190, 25),
        ("ΤΗ", 60, 55, 10),
        ("ΤΟ", 400, 380, 50),
        ("ΛΟΓΟΣ", 90, 85, 15),
        ("ΓΟΝ", 3, 3, 2),
        ("ΛΟ", 2, 2, 1),
    ];
    let bigrams = [("ΚΑΙ", "ΤΟΝ", 40), ("ΤΟΝ", "ΛΟΓΟΝ", 30), ("ΚΑΙ", "ΤΗΝ", 20), ("ΚΑΙ", "ΤΟ", 9), ("ΤΟ", "ΛΟΓΟΣ", 5)];
    Scorer::new(Model::from_bytes(&encode(&forms, &bigrams, 10_000, 2)).unwrap())
}

fn key(sc: &Scorer, id: u32) -> String {
    letters_to_string(sc.m.key(id))
}

#[test]
fn model_ids_lookup_and_rows() {
    let sc = toy();
    let m = &sc.m;
    assert_eq!(m.n, 9);
    assert_eq!(m.max_len, 5);
    // ids are ranks by (count desc, key asc)
    let ks: Vec<String> = (0..m.n as u32).map(|i| key(&sc, i)).collect();
    assert_eq!(ks, ["ΚΑΙ", "ΤΟ", "ΤΟΝ", "ΤΗΝ", "ΛΟΓΟΝ", "ΛΟΓΟΣ", "ΤΗ", "ΓΟΝ", "ΛΟ"]);
    let id = |s: &str| m.exact(&codes(s)).unwrap();
    assert_eq!(m.exact(&codes("ΤΟΙ")), None);
    assert_eq!(m.bigram(id("ΚΑΙ"), id("ΤΟΝ")), 40);
    assert_eq!(m.bigram(id("ΚΑΙ"), id("ΤΟ")), 9);
    assert_eq!(m.bigram(id("ΤΟΝ"), id("ΚΑΙ")), 0);
    assert_eq!((m.uni[id("ΤΟΝ") as usize], m.ctx[id("ΤΟΝ") as usize], m.n1[id("ΤΟΝ") as usize]), (300, 290, 30));
    // ΤΟΝ and ΤΗΝ do not share a fold (Ο folds to Ε, Η to Η); ΛΟΓΟΝ and ΛΟΓΟΣ do not either (Ν vs Σ)
    let fo: Vec<u8> = codes("ΤΟΝ").iter().map(|&c| FOLD[c as usize]).collect();
    assert_eq!(m.fold_range(&fo).iter().map(|&i| key(&sc, i)).collect::<Vec<_>>(), ["ΤΟΝ"]);
}

#[test]
fn model_rejects_damage() {
    let forms = [("ΚΑΙ", 5, 5, 1), ("ΤΟ", 4, 4, 1)];
    let mut b = encode(&forms, &[("ΚΑΙ", "ΤΟ", 3)], 100, 2);
    assert!(Model::from_bytes(&b).is_ok());
    let last = b.len() - 6;
    b[last] ^= 1;
    assert!(Model::from_bytes(&b).err().unwrap().contains("checksum"));
    assert!(Model::from_bytes(b"nope").is_err());
    assert!(Model::from_bytes(&b[..b.len() / 2]).is_err());
}

#[test]
fn lm_is_interpolated_absolute_discounting() {
    let sc = toy();
    let m = &sc.m;
    let id = |s: &str| m.exact(&codes(s)).unwrap();
    let n = 10_000f64;
    let pu = |c: f64| c / n;
    // seen bigram: (c - d) / ctx + d * n1 / ctx * P(w)
    let want = ((40.0 - 0.75) / 480.0 + 0.75 * 40.0 / 480.0 * pu(300.0)).ln();
    assert!((sc.lm(id("ΚΑΙ") as i64, id("ΤΟΝ")) - want).abs() < 1e-12);
    // unseen: only the back-off mass
    let want = (0.75 * 40.0 / 480.0 * pu(120.0)).ln();
    assert!((sc.lm(id("ΚΑΙ") as i64, id("ΛΟΓΟΝ")) - want).abs() < 1e-12);
    // no context: unigram
    assert!((sc.lm(-1, id("ΛΟΓΟΝ")) - pu(120.0).ln()).abs() < 1e-12);
}

#[test]
fn channel_candidates() {
    let sc = toy();
    // Η/Ν confusion: ΤΟΗ is read as ΤΟΝ with one substitution
    let c = sc.candidates(&codes("ΤΟΗ"), 8);
    let got: Vec<(String, String)> = c.iter().map(|x| (key(&sc, x.id), x.edit.tag())).collect();
    assert!(got.contains(&("ΤΟΝ".into(), "sub1".into())), "{got:?}");
    let ton = c.iter().find(|x| key(&sc, x.id) == "ΤΟΝ").unwrap();
    assert_eq!(ton.cost, LOG_SUB_2);
    // a lost letter: ΤΟ + lost Ν (and ΤΟ itself, exact)
    let c = sc.candidates(&codes("ΤΟ"), 8);
    let got: Vec<(String, String)> = c.iter().map(|x| (key(&sc, x.id), x.edit.tag())).collect();
    assert_eq!(got[0], ("ΤΟ".into(), "".into()));
    assert!(got.contains(&("ΤΟΝ".into(), "lost:Ν@2".into())), "{got:?}");
    let ton = c.iter().find(|x| key(&sc, x.id) == "ΤΟΝ").unwrap();
    assert_eq!(ton.cost, LOG_DEL);
    // ranked by unigram + channel, best first
    let s: Vec<f64> = c.iter().map(|x| sc.unigram_logp(x.id) + x.cost).collect();
    assert!(s.windows(2).all(|w| w[0] >= w[1]));
    // no deletions for one-letter observations; top truncates
    assert!(sc.candidates(&codes("Τ"), 8).iter().all(|x| !matches!(x.edit, Edit::Lost { .. })));
    assert!(sc.candidates(&codes("ΤΟ"), 1).len() == 1);
}

#[test]
fn segments_toy_lines() {
    let sc = toy();
    let (s, r) = sc.segment("καὶ τὸν λόγον", 3);
    assert_eq!(letters_to_string(&s), "ΚΑΙΤΟΝΛΟΓΟΝ");
    let words = |r: &t2b::scorer::Reading| -> Vec<String> {
        r.segments.iter().map(|g| g.form.map(|i| key(&sc, i)).unwrap_or_else(|| "?".into())).collect()
    };
    assert_eq!(words(&r[0]), ["ΚΑΙ", "ΤΟΝ", "ΛΟΓΟΝ"]);
    assert!(r.windows(2).all(|w| w[0].score >= w[1].score));
    // the score is the sum of the segment terms
    let sum: f64 = r[0].segments.iter().map(|g| g.lm + g.chan).sum();
    assert!((sum - r[0].score).abs() < 1e-9);
    // a confusion is undone
    let (_, r) = sc.segment("ΚΑΙΤΟΗΛΟΓΟΝ", 2);
    assert_eq!(words(&r[0]), ["ΚΑΙ", "ΤΟΝ", "ΛΟΓΟΝ"]);
    assert_eq!(r[0].segments[1].edit, Edit::Sub(1));
    // letters no form explains become an unknown segment
    let (s, r) = sc.segment("ΚΑΙΞΨΞΤΟΝ", 1);
    let g = r[0].segments.iter().find(|g| g.form.is_none()).expect("unknown segment");
    assert_eq!(letters_to_string(&s[g.start..g.end]), "ΞΨΞ");
    assert_eq!(g.edit, Edit::Unknown);
    assert_eq!(g.chan, LOG_P_UNK + 3.0 * LOG_UNK_LETTER);
    // empty input
    let (_, r) = sc.segment("12, ...", 5);
    assert_eq!(r.len(), 1);
    assert!(r[0].segments.is_empty());
}

#[test]
fn flags_follow_t2b_flag() {
    let sc = toy();
    let (s, r) = sc.segment("ΚΑΙΤΟΗΛΟΓΟΝ", 1);
    let f = sc.flags(&s, &r[0]);
    // the observed ΤΟΗ is unattested; its best in-channel reading is ΤΟΝ
    assert_eq!(f.len(), 1);
    assert_eq!(f[0].segment, 1);
    assert!(f[0].unattested);
    let (id, edit, _) = f[0].best.unwrap();
    assert_eq!(key(&sc, id), "ΤΟΝ");
    assert_eq!(edit, Edit::Sub(1));
    let (s, r) = sc.segment("ΚΑΙΤΟΝΛΟΓΟΝ", 1);
    assert!(sc.flags(&s, &r[0]).is_empty());
}

#[test]
fn json_shape() {
    let sc = toy();
    let j = t2b::segment_json(&sc, "ΚΑΙΤΟΗΛΟΓΟΝ", 2);
    assert!(j.starts_with("{\"input\":\"ΚΑΙΤΟΗΛΟΓΟΝ\",\"readings\":[{\"score\":"));
    assert!(j.contains("\"text\":\"ΚΑΙ ΤΟΝ ΛΟΓΟΝ\""));
    assert!(j.contains("\"edit\":\"sub1\",\"corrected\":true"));
    assert!(j.contains("\"changes\":[{\"at\":2,\"from\":\"Η\",\"to\":\"Ν\"}]"));
    assert!(j.contains("\"kind\":\"unattested\""));
    let opens = j.matches('{').count();
    assert_eq!(opens, j.matches('}').count());
    assert_eq!(j.matches('[').count(), j.matches(']').count());
}

// --- the real model ---------------------------------------------------------------------------------

fn real() -> Option<Scorer> {
    let p = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../docs/tools/autocorrect/model.bin");
    let b = std::fs::read(p).ok()?;
    Some(Scorer::new(Model::from_bytes(&b).expect("model.bin decodes")))
}

#[test]
fn real_model_matches_python_reference() {
    let Some(sc) = real() else {
        eprintln!("model.bin not found; skipped");
        return;
    };
    // values from t2b_scorer.Segmenter on t2b_export_model.read_model(model.bin)
    let cases: [(&str, &[(&str, f64)]); 3] = [
        ("ΟΥΝΕΙΩΘΕΝΗΦΥΣΙΣΕΙΣΤΗΤΩΝΑΚΥΡΩΤΕΡΩΝ", &[
            ("ΟΥΝ ΕΙΩΘΕΝ Η ΦΥΣΙΣ ΕΙΣ ΤΗΝ ΤΩΝ ΑΚΥΡΩΤΕΡΩΝ", -50.67405235001402),
            ("ΟΥΝ ΕΙΩΘΕΝ Η ΦΥΣΙΣ ΕΙΣ ΤΗ ΤΩΝ ΑΚΥΡΩΤΕΡΩΝ", -51.594925108765295),
            ("ΟΥΝ ΕΙΩΘΕΝ Η ΦΥΣΙΣ ΕΙΣ ΤΗΣ ΤΩΝ ΑΚΥΡΩΤΕΡΩΝ", -55.20162748407931),
        ]),
        ("ΡΩΜΗΝΕΑΝΓΑΡΑΜΛΠΑΝΙΑΣΥΝΕΛΘΟΤΤΔΕΙΡΗΜΕΝΑ", &[
            ("ΡΩΜΗΝ ΕΑΝ ΓΑΡ ΑΜΑ ΠΑΝΤΑ ΣΥΝΕΛΘΟΙ ΤΑ ΕΙΡΗΜΕΝΑ", -75.02655621723777),
            ("ΡΩΜΗΝ ΕΑΝ ΓΑΡ ΑΜΑ ΠΑΝΤΑ ΣΥΝΕΛΘΕΙΝ ΤΑ ΕΙΡΗΜΕΝΑ", -80.73994381803647),
            ("ΡΩΜΗΝ ΕΑΝ ΓΑΡ ΑΜΑ ΠΑΝΤΑΣ ΣΥΝΕΛΘΟΙ ΤΑ ΕΙΡΗΜΕΝΑ", -80.88015358618989),
        ]),
        ("οὖν εἴωθεν ἡ φύσις", &[
            ("ΟΥΝ ΕΙΩΘΕΝ Η ΦΥΣΙΣ", -23.266312603897994),
            ("ΓΟΥΝ ΕΙΩΘΕΝ Η ΦΥΣΙΣ", -32.461138047848024),
            ("ΣΥΝ ΕΙΩΘΕΝ Η ΦΥΣΙΣ", -32.87825543382161),
        ]),
    ];
    for (text, want) in cases {
        let (s, r) = sc.segment(text, 3);
        for (rd, (w, score)) in r.iter().zip(want.iter()) {
            let got: Vec<String> = rd
                .segments
                .iter()
                .map(|g| g.form.map(|i| key(&sc, i)).unwrap_or_else(|| format!("?{}?", letters_to_string(&s[g.start..g.end]))))
                .collect();
            assert_eq!(got.join(" "), *w);
            assert!((rd.score - score).abs() < 1e-9, "{} vs {}", rd.score, score);
        }
    }
}

/// The range-narrowing lookup in Scorer::candidates must find exactly what the reference's plain
/// "fold_range(fo[:p] + ch + fo[p:])" loop finds, in the same order.
#[test]
fn deletion_lookup_equals_the_plain_loop() {
    let Some(sc) = real() else {
        return;
    };
    let m = &sc.m;
    let mut rng: u64 = 12345;
    let mut next = || {
        rng ^= rng << 13;
        rng ^= rng >> 7;
        rng ^= rng << 17;
        rng
    };
    let mut checked = 0;
    for _ in 0..3000 {
        // substrings of real forms, sometimes with a letter dropped or changed
        let id = (next() % m.n as u64) as u32;
        let k = m.key(id).to_vec();
        let a = (next() % k.len() as u64) as usize;
        let b = a + 1 + (next() % (k.len() - a) as u64) as usize;
        let mut obs = k[a..b].to_vec();
        if obs.len() > 2 && next() % 2 == 0 {
            obs.remove((next() % obs.len() as u64) as usize);
        }
        if obs.len() < 2 || obs.len() >= m.max_len {
            continue;
        }
        let fo: Vec<u8> = obs.iter().map(|&c| FOLD[c as usize]).collect();
        let mut plain: Vec<(u32, u32)> = Vec::new();
        for p in 0..=fo.len() {
            for &ch in FOLD_ALPHABET.iter() {
                let mut key = fo[..p].to_vec();
                key.push(ch);
                key.extend_from_slice(&fo[p..]);
                for &i in m.fold_range(&key) {
                    if !plain.iter().any(|x| x.0 == i) && m.fold_range(&fo).iter().all(|&j| j != i) {
                        plain.push((i, p as u32));
                    }
                }
            }
        }
        let got: Vec<(u32, u32)> = sc
            .candidates(&obs, usize::MAX)
            .iter()
            .filter_map(|c| match c.edit {
                Edit::Lost { pos, .. } => Some((c.id, pos)),
                _ => None,
            })
            .collect();
        let mut a1: Vec<u32> = plain.iter().map(|x| x.0).collect();
        let mut a2: Vec<u32> = got.iter().map(|x| x.0).collect();
        a1.sort();
        a2.sort();
        assert_eq!(a1, a2, "obs {}", letters_to_string(&obs));
        checked += 1;
    }
    assert!(checked > 1000);
}
