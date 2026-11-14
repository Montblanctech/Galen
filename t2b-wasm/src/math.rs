//! `ln` and `exp` in plain Rust (the fdlibm / musl algorithms, error < 1 ulp), so the native build and the
//! wasm build compute bit-identical scores. `f64::ln` would call the platform C library natively and a
//! different libm port on wasm32.

#[inline]
fn f(bits: u64) -> f64 {
    f64::from_bits(bits)
}

const LN2_HI: u64 = 0x3fe62e42fee00000; // 6.93147180369123816490e-01
const LN2_LO: u64 = 0x3dea39ef35793c76; // 1.90821492927058770002e-10
const LG1: u64 = 0x3FE5555555555593; // 6.666666666666735130e-01
const LG2: u64 = 0x3FD999999997FA04; // 3.999999999940941908e-01
const LG3: u64 = 0x3FD2492494229359; // 2.857142874366239149e-01
const LG4: u64 = 0x3FCC71C51D8E78AF; // 2.222219843214978396e-01
const LG5: u64 = 0x3FC7466496CB03DE; // 1.818357216161805012e-01
const LG6: u64 = 0x3FC39A09D078C69F; // 1.531383769920937332e-01
const LG7: u64 = 0x3FC2F112DF3E5244; // 1.479819860511658591e-01

/// Natural logarithm (fdlibm e_log.c as in musl).
pub fn ln(x: f64) -> f64 {
    let mut x = x;
    let mut ui = x.to_bits();
    let mut hx = (ui >> 32) as u32;
    let mut k: i32 = 0;
    if hx < 0x00100000 || (hx >> 31) != 0 {
        if ui << 1 == 0 {
            return f64::NEG_INFINITY;
        }
        if hx >> 31 != 0 {
            return f64::NAN;
        }
        // subnormal: scale up
        k -= 54;
        x *= f(0x4350000000000000); // 2^54
        ui = x.to_bits();
        hx = (ui >> 32) as u32;
    } else if hx >= 0x7ff00000 {
        return x;
    } else if hx == 0x3ff00000 && ui << 32 == 0 {
        return 0.0;
    }
    // reduce x into [sqrt(2)/2, sqrt(2)]
    hx = hx.wrapping_add(0x3ff00000 - 0x3fe6a09e);
    k += (hx >> 20) as i32 - 0x3ff;
    hx = (hx & 0x000fffff) + 0x3fe6a09e;
    ui = ((hx as u64) << 32) | (ui & 0xffffffff);
    x = f64::from_bits(ui);

    let fx = x - 1.0;
    let hfsq = 0.5 * fx * fx;
    let s = fx / (2.0 + fx);
    let z = s * s;
    let w = z * z;
    let t1 = w * (f(LG2) + w * (f(LG4) + w * f(LG6)));
    let t2 = z * (f(LG1) + w * (f(LG3) + w * (f(LG5) + w * f(LG7))));
    let r = t2 + t1;
    let dk = k as f64;
    s * (hfsq + r) + dk * f(LN2_LO) - hfsq + fx + dk * f(LN2_HI)
}

const INVLN2: u64 = 0x3ff71547652b82fe; // 1.44269504088896338700e+00
const P1: u64 = 0x3FC555555555553E; // 1.66666666666666019037e-01
const P2: u64 = 0xBF66C16C16BEBD93; // -2.77777777770155933842e-03
const P3: u64 = 0x3F11566AAF25DE2C; // 6.61375632143793436117e-05
const P4: u64 = 0xBEBBBD41C5D26BF1; // -1.65339022054652515390e-06
const P5: u64 = 0x3E66376972BEA4D0; // 4.13813679705723846039e-08

fn scalbn(mut x: f64, mut n: i32) -> f64 {
    let x1p1023 = f(0x7fe0000000000000);
    let x1p53 = f(0x4340000000000000);
    let x1p_1022 = f(0x0010000000000000);
    if n > 1023 {
        x *= x1p1023;
        n -= 1023;
        if n > 1023 {
            x *= x1p1023;
            n -= 1023;
            if n > 1023 {
                n = 1023;
            }
        }
    } else if n < -1022 {
        x *= x1p_1022 * x1p53;
        n += 1022 - 53;
        if n < -1022 {
            x *= x1p_1022 * x1p53;
            n += 1022 - 53;
            if n < -1022 {
                n = -1022;
            }
        }
    }
    x * f(((0x3ff + n) as u64) << 52)
}

/// e^x (fdlibm e_exp.c as in musl).
pub fn exp(x: f64) -> f64 {
    if x.is_nan() {
        return x;
    }
    let hfull = (x.to_bits() >> 32) as u32;
    let sign = (hfull >> 31) as i32;
    let hx = hfull & 0x7fffffff;
    if hx >= 0x4086232b {
        if x > 709.782712893383973096 {
            return f64::INFINITY;
        }
        if x < -745.13321910194110842 {
            return 0.0;
        }
    }
    let mut x = x;
    let (hi, lo, k): (f64, f64, i32);
    if hx > 0x3fd62e42 {
        // |x| > 0.5 ln2
        let kk = if hx >= 0x3ff0a2b2 {
            (f(INVLN2) * x + if sign == 0 { 0.5 } else { -0.5 }) as i32
        } else {
            1 - sign - sign
        };
        k = kk;
        hi = x - kk as f64 * f(LN2_HI);
        lo = kk as f64 * f(LN2_LO);
        x = hi - lo;
    } else if hx > 0x3e300000 {
        k = 0;
        hi = x;
        lo = 0.0;
    } else {
        return 1.0 + x;
    }
    let xx = x * x;
    let c = x - xx * (f(P1) + xx * (f(P2) + xx * (f(P3) + xx * (f(P4) + xx * f(P5)))));
    let y = 1.0 + (x * c / (2.0 - c) - lo + hi);
    if k == 0 { y } else { scalbn(y, k) }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ulps(a: f64, b: f64) -> u64 {
        (a.to_bits() as i64 - b.to_bits() as i64).unsigned_abs()
    }

    #[test]
    fn constants_match_their_decimal_values() {
        assert_eq!(f(LN2_HI), 6.93147180369123816490e-01);
        assert_eq!(f(LN2_LO), 1.90821492927058770002e-10);
        assert_eq!(f(LG1), 6.666666666666735130e-01);
        assert_eq!(f(LG2), 3.999999999940941908e-01);
        assert_eq!(f(LG3), 2.857142874366239149e-01);
        assert_eq!(f(LG4), 2.222219843214978396e-01);
        assert_eq!(f(LG5), 1.818357216161805012e-01);
        assert_eq!(f(LG6), 1.531383769920937332e-01);
        assert_eq!(f(LG7), 1.479819860511658591e-01);
        assert_eq!(f(INVLN2), 1.44269504088896338700e+00);
        assert_eq!(f(P1), 1.66666666666666019037e-01);
        assert_eq!(f(P2), -2.77777777770155933842e-03);
        assert_eq!(f(P3), 6.61375632143793436117e-05);
        assert_eq!(f(P4), -1.65339022054652515390e-06);
        assert_eq!(f(P5), 4.13813679705723846039e-08);
    }

    #[test]
    fn ln_and_exp_within_one_ulp_of_std() {
        let mut s: u64 = 0x9E3779B97F4A7C15;
        let mut worst = (0u64, 0u64);
        for _ in 0..200_000 {
            s ^= s << 13;
            s ^= s >> 7;
            s ^= s << 17;
            let u = (s >> 11) as f64 / (1u64 << 53) as f64;
            let x = (u * 40.0 - 20.0).exp(); // 2e-9 .. 5e8
            worst.0 = worst.0.max(ulps(ln(x), x.ln()));
            let y = u * 60.0 - 50.0;
            worst.1 = worst.1.max(ulps(exp(y), y.exp()));
        }
        assert!(worst.0 <= 1 && worst.1 <= 1, "worst ulps ln {} exp {}", worst.0, worst.1);
        assert_eq!(ln(1.0), 0.0);
        assert_eq!(exp(0.0), 1.0);
        assert_eq!(ln(0.0), f64::NEG_INFINITY);
        assert!(ln(-1.0).is_nan());
        assert!(ulps(ln(1e-300), (1e-300f64).ln()) <= 1);
        assert!(ulps(ln(5e-324), (5e-324f64).ln()) <= 1);
    }
}
