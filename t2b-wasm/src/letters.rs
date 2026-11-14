//! Alphabet, confusion classes and scriptio-continua normalisation (t2b_scorer.LETTERS, CONFUSION_CLASSES,
//! FOLD, FOLD_ALPHABET, to_continua).

use crate::continua_table::CONTINUA;

/// Letter codes 0..23 in t2b_scorer.LETTERS order; code 24 is U+03A2, an unassigned code point that
/// to_continua keeps (it is inside the Α-Ω range) and that no attested form contains.
pub const LETTERS: [char; 25] = [
    'Α', 'Β', 'Γ', 'Δ', 'Ε', 'Ζ', 'Η', 'Θ', 'Ι', 'Κ', 'Λ', 'Μ', 'Ν', 'Ξ', 'Ο', 'Π', 'Ρ', 'Σ', 'Τ', 'Υ', 'Φ',
    'Χ', 'Ψ', 'Ω', '\u{03A2}',
];

/// fold: each letter -> the first letter of its confusion class (ΑΛΔ, ΕΘΟΣ, ΗΝ, ΙΤ)
pub const FOLD: [u8; 25] = [0, 1, 2, 0, 4, 5, 6, 4, 8, 9, 0, 11, 6, 13, 4, 15, 16, 4, 8, 19, 20, 21, 22, 23, 24];

/// size of the confusion class of a letter (t2b_scorer.CLASS_SIZE, default 2)
pub const CLASS_SIZE: [u8; 25] = [3, 2, 2, 3, 4, 2, 2, 4, 2, 2, 3, 2, 2, 2, 4, 2, 2, 4, 2, 2, 2, 2, 2, 2, 2];

/// sorted({fold(c) for c in LETTERS})
pub const FOLD_ALPHABET: [u8; 17] = [0, 1, 2, 4, 5, 6, 8, 9, 11, 13, 15, 16, 19, 20, 21, 22, 23];

/// The constants of t2b_scorer, with the logs taken as Python's math.log computes them (bit patterns), so the
/// channel costs are bit-identical to the reference.
pub const EPS_SUB: f64 = 0.03;
pub const EPS_DEL: f64 = 0.01;
pub const DISCOUNT: f64 = 0.75;
pub const P_UNK: f64 = 1e-4;
pub const MIN_COUNT: u32 = 2;
/// math.log(EPS_SUB / (size - 1) / (1 - EPS_SUB)) for class size 2, 3, 4
pub const LOG_SUB_2: f64 = f64::from_bits(0xc00bcf0cd474166b);
pub const LOG_SUB_3: f64 = f64::from_bits(0xc010ad4eca195273);
pub const LOG_SUB_4: f64 = f64::from_bits(0xc0124c8108e54bf8);
/// math.log(EPS_DEL)
pub const LOG_DEL: f64 = f64::from_bits(0xc0126bb1bbb55515);
/// math.log(P_UNK)
pub const LOG_P_UNK: f64 = f64::from_bits(0xc0226bb1bbb55515);
/// math.log(1 / 24)
pub const LOG_UNK_LETTER: f64 = f64::from_bits(0xc0096ca77c922cf9);

#[inline]
pub fn log_sub(form_letter: u8) -> f64 {
    match CLASS_SIZE[form_letter as usize] {
        3 => LOG_SUB_3,
        4 => LOG_SUB_4,
        _ => LOG_SUB_2,
    }
}

/// Any Greek text -> scriptio-continua letter codes (t2b_scorer.to_continua: NFD, combining marks dropped,
/// uppercase, ς / ϲ / C -> Σ, everything that is not a letter dropped). to_continua works per code point, so a
/// generated table (tools/gen_continua.py) reproduces it exactly.
pub fn to_continua(text: &str) -> Vec<u8> {
    let mut out = Vec::with_capacity(text.len() / 2);
    for ch in text.chars() {
        let cp = ch as u32;
        if let Ok(p) = CONTINUA.binary_search_by_key(&cp, |e| e.0) {
            out.push(CONTINUA[p].1);
        }
    }
    out
}

pub fn letters_to_string(codes: &[u8]) -> String {
    codes.iter().map(|&c| LETTERS[c as usize]).collect()
}

pub fn string_to_letters(s: &str) -> Option<Vec<u8>> {
    s.chars().map(|c| LETTERS.iter().position(|&l| l == c).map(|p| p as u8)).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fold_and_classes_follow_the_reference() {
        let classes = ["ΑΛΔ", "ΕΘΟΣ", "ΗΝ", "ΙΤ"];
        for (code, &c) in LETTERS.iter().enumerate() {
            let cls = classes.iter().find(|k| k.contains(c));
            let head = cls.map(|k| k.chars().next().unwrap()).unwrap_or(c);
            assert_eq!(LETTERS[FOLD[code] as usize], head);
            assert_eq!(CLASS_SIZE[code] as usize, cls.map(|k| k.chars().count()).unwrap_or(2));
        }
        let mut fa: Vec<u8> = (0..24).map(|c| FOLD[c]).collect();
        fa.sort();
        fa.dedup();
        assert_eq!(fa, FOLD_ALPHABET.to_vec());
    }

    #[test]
    fn constants_match_their_definitions() {
        let close = |a: f64, b: f64| (a - b).abs() < 1e-15 * b.abs();
        assert!(close(LOG_SUB_2, (EPS_SUB / 1.0 / (1.0 - EPS_SUB)).ln()));
        assert!(close(LOG_SUB_3, (EPS_SUB / 2.0 / (1.0 - EPS_SUB)).ln()));
        assert!(close(LOG_SUB_4, (EPS_SUB / 3.0 / (1.0 - EPS_SUB)).ln()));
        assert!(close(LOG_DEL, EPS_DEL.ln()));
        assert!(close(LOG_P_UNK, P_UNK.ln()));
        assert!(close(LOG_UNK_LETTER, (1.0f64 / 24.0).ln()));
    }

    #[test]
    fn continua_like_python() {
        let s = |t: &str| letters_to_string(&to_continua(t));
        assert_eq!(s("καὶ τὸν λόγον"), "ΚΑΙΤΟΝΛΟΓΟΝ");
        assert_eq!(s("ᾠδῇ, ἧς"), "ΩΔΗΗΣ");
        assert_eq!(s("ϲοφίαϲ"), "ΣΟΦΙΑΣ");
        assert_eq!(s("CΟΦΙΑC"), "ΣΟΦΙΑΣ");
        assert_eq!(s("[ἀ]νθρώ<πο>υ 12 abc"), "ΑΝΘΡΩΠΟΥΣ"); // Latin c -> C -> Σ, as in to_continua
        assert_eq!(s("Ϊ ΐ ϐ ϑ µ"), "ΙΙΒΘΜ");
        assert_eq!(s(""), "");
    }
}
