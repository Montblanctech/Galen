//! model.bin reader (format: MODEL_FORMAT.md; writer: galen-density-map/pipeline/t2b_export_model.py).

use crate::letters::FOLD;

pub struct Model {
    pub n: usize,
    pub n_tokens: u64,
    pub form_min: u32,
    pub bigram_min: u32,
    pub max_len: usize,
    key_off: Vec<u32>, // id -> offset into keys / fkeys (n + 1 entries)
    keys: Vec<u8>,     // letter codes, id order
    fkeys: Vec<u8>,    // folded letter codes, id order
    pub uni: Vec<u32>,
    pub ctx: Vec<u32>,
    pub n1: Vec<u32>,
    row_off: Vec<u32>, // left id -> range in right / bcount
    right: Vec<u32>,
    bcount: Vec<u32>,
    by_key: Vec<u32>,  // ids in key order
    by_fold: Vec<u32>, // ids in (folded key, id) order
}

struct Reader<'a> {
    b: &'a [u8],
    o: usize,
}

impl<'a> Reader<'a> {
    fn varint(&mut self) -> Result<u64, String> {
        let mut v: u64 = 0;
        let mut shift = 0;
        loop {
            let x = *self.b.get(self.o).ok_or("model: truncated varint")?;
            self.o += 1;
            v |= ((x & 0x7f) as u64) << shift;
            if x < 0x80 {
                return Ok(v);
            }
            shift += 7;
            if shift > 63 {
                return Err("model: bad varint".into());
            }
        }
    }
    fn varints(&mut self, n: usize) -> Result<Vec<u64>, String> {
        let mut out = Vec::with_capacity(n);
        for _ in 0..n {
            out.push(self.varint()?);
        }
        if self.o != self.b.len() {
            return Err("model: section has trailing bytes".into());
        }
        Ok(out)
    }
}

pub fn crc32(data: &[u8]) -> u32 {
    let mut table = [0u32; 256];
    for i in 0..256u32 {
        let mut c = i;
        for _ in 0..8 {
            c = if c & 1 != 0 { 0xEDB88320 ^ (c >> 1) } else { c >> 1 };
        }
        table[i as usize] = c;
    }
    let mut crc = 0xFFFFFFFFu32;
    for &b in data {
        crc = table[((crc ^ b as u32) & 0xff) as usize] ^ (crc >> 8);
    }
    crc ^ 0xFFFFFFFF
}

fn u32_of(x: u64, what: &str) -> Result<u32, String> {
    u32::try_from(x).map_err(|_| format!("model: {what} out of range"))
}

impl Model {
    pub fn from_bytes(data: &[u8]) -> Result<Model, String> {
        if data.len() < 12 || &data[..4] != b"T2BM" || data[4] != 1 {
            return Err("not a T2BM v1 model".into());
        }
        let body = &data[8..data.len() - 4];
        let want = u32::from_le_bytes(data[data.len() - 4..].try_into().unwrap());
        if crc32(body) != want {
            return Err("model checksum mismatch (truncated download?)".into());
        }
        let mut secs: Vec<&[u8]> = Vec::new();
        let mut o = 0;
        while o < body.len() {
            if o + 4 > body.len() {
                return Err("model: bad section header".into());
            }
            let ln = u32::from_le_bytes(body[o..o + 4].try_into().unwrap()) as usize;
            if o + 4 + ln > body.len() {
                return Err("model: section overruns".into());
            }
            secs.push(&body[o + 4..o + 4 + ln]);
            o += 4 + ln;
        }
        if secs.len() != 8 {
            return Err("model: expected 8 sections".into());
        }
        let h = Reader { b: secs[0], o: 0 }.varints(6)?;
        let n = h[0] as usize;
        let nb = h[1] as usize;
        let n_tokens = h[2];
        let form_min = u32_of(h[3], "form_min")?;
        let bigram_min = u32_of(h[4], "bigram_min")?;
        let max_len = h[5] as usize;
        if n >= (1 << 23) {
            return Err("model: too many forms".into());
        }

        // keys, front-coded in key order
        let kb = secs[1];
        let mut akeys: Vec<u8> = Vec::with_capacity(kb.len() * 3);
        let mut aoff: Vec<u32> = Vec::with_capacity(n + 1);
        aoff.push(0);
        let mut prev_start = 0usize;
        let mut o = 0usize;
        for _ in 0..n {
            if o + 2 > kb.len() {
                return Err("model: keys truncated".into());
            }
            let s = kb[o] as usize;
            let ln = kb[o + 1] as usize;
            let prev_len = akeys.len() - prev_start;
            if s > prev_len || o + 2 + ln > kb.len() {
                return Err("model: bad front coding".into());
            }
            let start = akeys.len();
            for t in 0..s {
                let c = akeys[prev_start + t];
                akeys.push(c);
            }
            for &c in &kb[o + 2..o + 2 + ln] {
                if c >= 24 {
                    return Err("model: letter code out of range".into());
                }
                akeys.push(c);
            }
            o += 2 + ln;
            prev_start = start;
            aoff.push(akeys.len() as u32);
        }
        if o != kb.len() {
            return Err("model: keys section has trailing bytes".into());
        }
        let auni = Reader { b: secs[2], o: 0 }.varints(n)?;
        let adctx = Reader { b: secs[3], o: 0 }.varints(n)?;
        let an1 = Reader { b: secs[4], o: 0 }.varints(n)?;

        // ids: rank by (count desc, key asc); alpha position a -> id
        let auni32: Vec<u32> = auni
            .iter()
            .map(|&u| u32_of(u + form_min as u64, "count"))
            .collect::<Result<_, _>>()?;
        let mut order: Vec<u32> = (0..n as u32).collect(); // id -> alpha position
        order.sort_by(|&a, &b| auni32[b as usize].cmp(&auni32[a as usize]).then(a.cmp(&b)));
        let mut by_key = vec![0u32; n]; // alpha position -> id
        for (id, &a) in order.iter().enumerate() {
            by_key[a as usize] = id as u32;
        }
        let mut key_off = Vec::with_capacity(n + 1);
        let mut keys = Vec::with_capacity(akeys.len());
        let mut uni = Vec::with_capacity(n);
        let mut ctx = Vec::with_capacity(n);
        let mut n1 = Vec::with_capacity(n);
        key_off.push(0u32);
        for &a in &order {
            let a = a as usize;
            keys.extend_from_slice(&akeys[aoff[a] as usize..aoff[a + 1] as usize]);
            key_off.push(keys.len() as u32);
            let u = auni32[a];
            let d = adctx[a];
            if d > u as u64 || an1[a] > u as u64 - d {
                return Err("model: count invariant broken".into());
            }
            uni.push(u);
            ctx.push(u - d as u32);
            n1.push(an1[a] as u32);
        }
        drop(akeys);
        let fkeys: Vec<u8> = keys.iter().map(|&c| FOLD[c as usize]).collect();

        // bigram rows in id order
        let rowlen = Reader { b: secs[5], o: 0 }.varints(n)?;
        let delta = Reader { b: secs[6], o: 0 }.varints(nb)?;
        let bc = Reader { b: secs[7], o: 0 }.varints(nb)?;
        let mut row_off = Vec::with_capacity(n + 1);
        let mut right = Vec::with_capacity(nb);
        let mut bcount = Vec::with_capacity(nb);
        row_off.push(0u32);
        let mut p = 0usize;
        for &rl in &rowlen {
            let mut r: i64 = -1;
            for _ in 0..rl {
                if p >= nb {
                    return Err("model: bigram rows overrun".into());
                }
                r += delta[p] as i64 + 1;
                if r as usize >= n {
                    return Err("model: bigram right id out of range".into());
                }
                right.push(r as u32);
                bcount.push(u32_of(bc[p] + bigram_min as u64, "bigram count")?);
                p += 1;
            }
            row_off.push(p as u32);
        }
        if p != nb {
            return Err("model: bigram count mismatch".into());
        }

        let mut m = Model {
            n,
            n_tokens,
            form_min,
            bigram_min,
            max_len,
            key_off,
            keys,
            fkeys,
            uni,
            ctx,
            n1,
            row_off,
            right,
            bcount,
            by_key,
            by_fold: Vec::new(),
        };
        let mut by_fold: Vec<u32> = (0..n as u32).collect();
        by_fold.sort_by(|&a, &b| m.fkey(a).cmp(m.fkey(b)).then(a.cmp(&b)));
        m.by_fold = by_fold;
        Ok(m)
    }

    #[inline]
    pub fn key(&self, id: u32) -> &[u8] {
        &self.keys[self.key_off[id as usize] as usize..self.key_off[id as usize + 1] as usize]
    }

    #[inline]
    pub fn fkey(&self, id: u32) -> &[u8] {
        &self.fkeys[self.key_off[id as usize] as usize..self.key_off[id as usize + 1] as usize]
    }

    /// id of an attested form, by its exact key
    pub fn exact(&self, key: &[u8]) -> Option<u32> {
        let v = &self.by_key;
        let (mut lo, mut hi) = (0usize, v.len());
        while lo < hi {
            let mid = (lo + hi) / 2;
            match self.key(v[mid]).cmp(key) {
                std::cmp::Ordering::Less => lo = mid + 1,
                std::cmp::Ordering::Greater => hi = mid,
                std::cmp::Ordering::Equal => return Some(v[mid]),
            }
        }
        None
    }

    /// ids whose folded key equals `fkey`, in ascending id order
    pub fn fold_range(&self, fkey: &[u8]) -> &[u32] {
        let v = &self.by_fold;
        let lo = v.partition_point(|&id| self.fkey(id) < fkey);
        let hi = lo + v[lo..].partition_point(|&id| self.fkey(id) == fkey);
        &v[lo..hi]
    }

    /// bigram count c(left, right), 0 if absent (or pruned)
    #[inline]
    pub fn bigram(&self, left: u32, right: u32) -> u32 {
        let a = self.row_off[left as usize] as usize;
        let b = self.row_off[left as usize + 1] as usize;
        match self.right[a..b].binary_search(&right) {
            Ok(p) => self.bcount[a + p],
            Err(_) => 0,
        }
    }

    /// Range of `by_fold` (as positions) whose folded keys share a prefix of length depth + 1 ending in `ch`,
    /// given the range [lo, hi) of keys that share the first `depth` letters. Keys of length == depth sort first.
    #[inline]
    pub fn fold_narrow(&self, lo: usize, hi: usize, depth: usize, ch: u8) -> (usize, usize) {
        let v = &self.by_fold[lo..hi];
        let at = |id: u32| -> i16 {
            let k = self.fkey(id);
            if k.len() > depth { k[depth] as i16 } else { -1 }
        };
        let a = v.partition_point(|&id| at(id) < ch as i16);
        let b = a + v[a..].partition_point(|&id| at(id) == ch as i16);
        (lo + a, lo + b)
    }

    /// ids in by_fold[lo..hi] (a range sharing a prefix of length `len`) whose folded key is exactly that
    /// prefix: they sort first, in ascending id order
    #[inline]
    pub fn fold_exact_in(&self, lo: usize, hi: usize, len: usize) -> &[u32] {
        let v = &self.by_fold[lo..hi];
        let e = v.partition_point(|&id| self.fkey(id).len() == len);
        &v[..e]
    }

    pub fn n_bigrams(&self) -> usize {
        self.right.len()
    }
}
