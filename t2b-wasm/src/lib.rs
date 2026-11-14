//! T2b transcription plausibility scorer ("ancient Greek autocorrect" for papyrus HTR output): a port of
//! galen-density-map/pipeline/t2b_scorer.py (segmenter) and t2b_flag.py (flags) that reads the compact
//! model.bin written by t2b_export_model.py. No dependencies; the wasm build exports a plain C ABI
//! (see `ffi` and docs/tools/autocorrect/glue.js).

mod continua_table;
pub mod spelling_table;
pub mod letters;
pub mod math;
pub mod model;
pub mod scorer;

use letters::{letters_to_string, LETTERS};
use scorer::{Edit, Reading, Scorer};
use spelling_table::RULES;

/// "ΟΙ written Ο before a vowel" (t2b_spelling.SpellingRules.label)
pub fn rule_label(k: u16) -> String {
    let r = &RULES[k as usize];
    let wher = match r.right {
        0 => "before a vowel",
        1 => "before a consonant",
        _ => "at the word end",
    };
    format!(
        "{} written {} {}{}",
        letters_to_string(r.reg),
        letters_to_string(r.orig),
        wher,
        if r.start { " (word start)" } else { "" }
    )
}

fn json_str(out: &mut String, s: &str) {
    out.push('"');
    for ch in s.chars() {
        match ch {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            c if (c as u32) < 0x20 => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out.push('"');
}

fn json_f64(out: &mut String, x: f64) {
    if x.is_finite() {
        // shortest representation that round-trips
        let s = format!("{x:?}");
        out.push_str(&s);
    } else {
        out.push_str("null");
    }
}

fn changes_json(out: &mut String, obs: &[u8], form: &[u8], edit: Edit) {
    out.push('[');
    let mut first = true;
    let sub = |out: &mut String, at: usize, a: u8, b: u8, first: &mut bool| {
        if !*first {
            out.push(',');
        }
        *first = false;
        out.push_str(&format!(
            "{{\"at\":{},\"from\":\"{}\",\"to\":\"{}\"}}",
            at, LETTERS[a as usize], LETTERS[b as usize]
        ));
    };
    match edit {
        Edit::Sub(_) => {
            for (p, (&a, &b)) in obs.iter().zip(form.iter()).enumerate() {
                if a != b {
                    sub(out, p, a, b, &mut first);
                }
            }
        }
        Edit::Lost { letter, pos, .. } => {
            out.push_str(&format!("{{\"at\":{},\"lost\":\"{}\"}}", pos, LETTERS[letter as usize]));
            first = false;
            let p = pos as usize;
            let red: Vec<u8> = form[..p].iter().chain(form[p + 1..].iter()).copied().collect();
            for (q, (&a, &b)) in obs.iter().zip(red.iter()).enumerate() {
                if a != b {
                    sub(out, q, a, b, &mut first);
                }
            }
        }
        Edit::Var(k) => {
            let r = &RULES[k as usize];
            let at = scorer::var_position(obs, k, form).unwrap_or(0);
            out.push_str(&format!(
                "{{\"at\":{},\"written\":\"{}\",\"spelling_of\":\"{}\"}}",
                at,
                letters_to_string(r.orig),
                letters_to_string(r.reg)
            ));
        }
        _ => {}
    }
    out.push(']');
}

/// One input -> the JSON object the page and the parity harness read:
/// {"input", "readings": [{"score", "text", "segments": [...], "flags": [...]}]}
pub fn segment_json(sc: &Scorer, text: &str, k: usize) -> String {
    let (s, readings) = sc.segment(text, k.max(1));
    readings_json(sc, &s, &readings)
}

fn readings_json(sc: &Scorer, s: &[u8], readings: &[Reading]) -> String {
    let mut out = String::with_capacity(4096);
    out.push_str("{\"input\":");
    json_str(&mut out, &letters_to_string(s));
    out.push_str(",\"readings\":[");
    for (ri, r) in readings.iter().enumerate() {
        if ri > 0 {
            out.push(',');
        }
        reading_json(sc, &mut out, s, r);
    }
    out.push_str("]}");
    out
}

fn reading_json(sc: &Scorer, out: &mut String, s: &[u8], r: &Reading) {
    let m = &sc.m;
    out.push_str("{\"score\":");
    json_f64(out, r.score);
    let text: Vec<String> = r
        .segments
        .iter()
        .map(|g| match g.form {
            Some(id) => letters_to_string(m.key(id)),
            None => format!("?{}?", letters_to_string(&s[g.start..g.end])),
        })
        .collect();
    out.push_str(",\"text\":");
    json_str(out, &text.join(" "));
    out.push_str(",\"segments\":[");
    for (gi, g) in r.segments.iter().enumerate() {
        if gi > 0 {
            out.push(',');
        }
        let obs = &s[g.start..g.end];
        out.push_str(&format!("{{\"start\":{},\"end\":{},\"observed\":", g.start, g.end));
        json_str(out, &letters_to_string(obs));
        out.push_str(",\"form\":");
        match g.form {
            Some(id) => json_str(out, &letters_to_string(m.key(id))),
            None => out.push_str("null"),
        }
        out.push_str(",\"edit\":");
        json_str(out, &g.edit.tag());
        let corrected = matches!(g.edit, Edit::Sub(_) | Edit::Lost { .. });
        if let Edit::Var(k) = g.edit {
            out.push_str(",\"spelling\":");
            json_str(out, &rule_label(k));
        }
        out.push_str(&format!(
            ",\"corrected\":{},\"unknown\":{},\"count\":{},\"lm\":",
            corrected,
            g.form.is_none(),
            g.form.map_or(0, |id| m.uni[id as usize])
        ));
        json_f64(out, g.lm);
        out.push_str(",\"chan\":");
        json_f64(out, g.chan);
        out.push_str(",\"score\":");
        json_f64(out, g.lm + g.chan);
        out.push_str(",\"changes\":");
        match g.form {
            Some(id) => changes_json(out, obs, m.key(id), g.edit),
            None => out.push_str("[]"),
        }
        out.push('}');
    }
    let (flags, spellings) = sc.flags_and_spellings(s, r);
    out.push_str("],\"spellings\":[");
    for (i, x) in spellings.iter().enumerate() {
        if i > 0 {
            out.push(',');
        }
        let g = &r.segments[x.segment];
        out.push_str(&format!("{{\"segment\":{},\"observed\":", x.segment));
        json_str(out, &letters_to_string(&s[g.start..g.end]));
        out.push_str(",\"regularized\":");
        json_str(out, &letters_to_string(m.key(x.id)));
        out.push_str(&format!(",\"rule\":{},\"label\":", x.rule));
        json_str(out, &rule_label(x.rule));
        out.push_str(&format!(",\"accepted\":{},\"count\":{}}}", x.accepted, m.uni[x.id as usize]));
    }
    out.push_str("],\"flags\":[");
    for (fi, f) in flags.iter().enumerate() {
        if fi > 0 {
            out.push(',');
        }
        let g = &r.segments[f.segment];
        let obs = &s[g.start..g.end];
        out.push_str(&format!("{{\"segment\":{},\"observed\":", f.segment));
        json_str(out, &letters_to_string(obs));
        out.push_str(",\"kind\":");
        json_str(out, f.kind());
        out.push_str(&format!(",\"count\":{}", m.exact(obs).map_or(0, |id| m.uni[id as usize])));
        let notes = sc.flag_notes(obs, f);
        out.push_str(",\"alt_spelling\":");
        match notes.alt_spelling {
            Some(k) => json_str(out, &rule_label(k)),
            None => out.push_str("null"),
        }
        out.push_str(&format!(",\"stem_attested\":{}", notes.stem_attested));
        match f.best {
            Some((id, edit, margin)) => {
                out.push_str(",\"alternative\":");
                json_str(out, &letters_to_string(m.key(id)));
                out.push_str(",\"alt_edit\":");
                json_str(out, &edit.tag());
                out.push_str(&format!(",\"alt_count\":{},\"margin\":", m.uni[id as usize]));
                json_f64(out, margin);
                out.push_str(",\"alt_changes\":");
                changes_json(out, obs, m.key(id), edit);
            }
            None => out.push_str(",\"alternative\":null,\"alt_edit\":\"\",\"alt_count\":0,\"margin\":null,\"alt_changes\":[]"),
        }
        out.push('}');
    }
    out.push_str("]}");
}

/// A whole text, one input per non-empty line, with the writer's habits: pass 1 with the table's rule costs;
/// a rule the best readings use at least HABIT_MIN times gets the text's own rate (t2b_spelling.adapt_costs)
/// and every line is read again. {"lines": [segment_json objects], "habits": [...]}. The scorer's costs are
/// restored before returning.
pub fn segment_text_json(sc: &mut Scorer, text: &str, k: usize) -> String {
    let lines: Vec<&str> = text.lines().filter(|l| !l.trim().is_empty()).collect();
    let mut uses: std::collections::BTreeMap<u16, u32> = std::collections::BTreeMap::new();
    let mut forms: Vec<Vec<u8>> = Vec::new();
    let mut first: Vec<String> = Vec::with_capacity(lines.len());
    for l in &lines {
        // the k readings of pass 1; the best one does not depend on k, so these are the output when no habit
        // changes a cost (the reference reads every line twice; the results are the same)
        let (s, rs) = sc.segment(l, k.max(1));
        first.push(readings_json(sc, &s, &rs));
        if let Some(r) = rs.first() {
            for g in &r.segments {
                if let Edit::Var(q) = g.edit {
                    *uses.entry(q).or_insert(0) += 1;
                }
                if let Some(id) = g.form {
                    forms.push(sc.m.key(id).to_vec());
                }
            }
        }
    }
    let opps = scorer::opportunities(&forms);
    let adapted = scorer::adapt_costs(&uses, &opps);
    let mut habits = String::from("[");
    if let Some(c) = &adapted {
        let mut first = true;
        let mut order: Vec<(&u16, &u32)> = uses.iter().collect();
        order.sort_by(|a, b| b.1.cmp(a.1).then(a.0.cmp(b.0)));
        for (&q, &u) in order {
            if c[q as usize] == RULES[q as usize].cost {
                continue;
            }
            if !first {
                habits.push(',');
            }
            first = false;
            habits.push_str(&format!("{{\"rule\":{q},\"label\":"));
            json_str(&mut habits, &rule_label(q));
            habits.push_str(&format!(",\"uses\":{u},\"opportunities\":{},\"corpus_rate\":", opps.get(&q).copied().unwrap_or(0)));
            json_f64(&mut habits, RULES[q as usize].rate);
            habits.push_str(",\"text_rate\":");
            json_f64(&mut habits, math::exp(c[q as usize]));
            habits.push('}');
        }
    }
    habits.push(']');
    let reread = adapted.is_some();
    if reread {
        sc.set_spelling_costs(adapted);
    }
    let mut out = String::from("{\"lines\":[");
    for (i, l) in lines.iter().enumerate() {
        if i > 0 {
            out.push(',');
        }
        if reread {
            out.push_str(&segment_json(sc, l, k));
        } else {
            out.push_str(&first[i]);
        }
    }
    out.push_str("],\"habits\":");
    out.push_str(&habits);
    out.push('}');
    sc.set_spelling_costs(None);
    out
}

pub fn info_json(sc: &Scorer) -> String {
    let m = &sc.m;
    format!(
        "{{\"forms\":{},\"bigrams\":{},\"tokens\":{},\"form_min\":{},\"bigram_min\":{},\"max_len\":{},\"spelling_rules\":{}}}",
        m.n,
        m.n_bigrams(),
        m.n_tokens,
        m.form_min,
        m.bigram_min,
        m.max_len,
        RULES.len()
    )
}

/// The C ABI for the wasm build: JS allocates a buffer with t2b_alloc, writes UTF-8 (or the model bytes)
/// into it, calls t2b_init / t2b_segment, then reads t2b_out_len() bytes of JSON at t2b_out_ptr().
pub mod ffi {
    use super::*;
    use std::sync::Mutex;

    static STATE: Mutex<Option<Scorer>> = Mutex::new(None);
    static OUT: Mutex<Vec<u8>> = Mutex::new(Vec::new());

    fn set_out(s: String) -> i32 {
        let mut o = OUT.lock().unwrap();
        *o = s.into_bytes();
        o.len() as i32
    }

    #[unsafe(no_mangle)]
    pub extern "C" fn t2b_alloc(len: usize) -> *mut u8 {
        let mut v: Vec<u8> = Vec::with_capacity(len.max(1));
        let p = v.as_mut_ptr();
        std::mem::forget(v);
        p
    }

    /// # Safety
    /// `ptr` must come from t2b_alloc(len).
    #[unsafe(no_mangle)]
    pub unsafe extern "C" fn t2b_free(ptr: *mut u8, len: usize) {
        unsafe { drop(Vec::from_raw_parts(ptr, 0, len.max(1))) }
    }

    /// Load model.bin. 0 = ok; -1 = error (message in the out buffer).
    /// # Safety
    /// `ptr` must point to `len` readable bytes.
    #[unsafe(no_mangle)]
    pub unsafe extern "C" fn t2b_init(ptr: *const u8, len: usize) -> i32 {
        let data = unsafe { std::slice::from_raw_parts(ptr, len) };
        match model::Model::from_bytes(data) {
            Ok(m) => {
                let sc = Scorer::new(m);
                set_out(info_json(&sc));
                *STATE.lock().unwrap() = Some(sc);
                0
            }
            Err(e) => {
                set_out(e);
                -1
            }
        }
    }

    /// Segment one line (UTF-8 at ptr/len) into the k best readings; returns the JSON length (or -1).
    /// # Safety
    /// `ptr` must point to `len` readable bytes.
    #[unsafe(no_mangle)]
    pub unsafe extern "C" fn t2b_segment(ptr: *const u8, len: usize, k: u32) -> i32 {
        let bytes = unsafe { std::slice::from_raw_parts(ptr, len) };
        let text = String::from_utf8_lossy(bytes);
        let st = STATE.lock().unwrap();
        match st.as_ref() {
            Some(sc) => {
                let j = segment_json(sc, &text, k as usize);
                drop(st);
                set_out(j)
            }
            None => {
                drop(st);
                set_out("model not loaded".into());
                -1
            }
        }
    }

    /// Segment a whole text (lines), with the writer's habits (segment_text_json); returns the JSON length.
    /// # Safety
    /// `ptr` must point to `len` readable bytes.
    #[unsafe(no_mangle)]
    pub unsafe extern "C" fn t2b_segment_text(ptr: *const u8, len: usize, k: u32) -> i32 {
        let bytes = unsafe { std::slice::from_raw_parts(ptr, len) };
        let text = String::from_utf8_lossy(bytes);
        let mut st = STATE.lock().unwrap();
        match st.as_mut() {
            Some(sc) => {
                let j = segment_text_json(sc, &text, k as usize);
                drop(st);
                set_out(j)
            }
            None => {
                drop(st);
                set_out("model not loaded".into());
                -1
            }
        }
    }

    #[unsafe(no_mangle)]
    pub extern "C" fn t2b_out_ptr() -> *const u8 {
        OUT.lock().unwrap().as_ptr()
    }

    #[unsafe(no_mangle)]
    pub extern "C" fn t2b_out_len() -> usize {
        OUT.lock().unwrap().len()
    }
}
