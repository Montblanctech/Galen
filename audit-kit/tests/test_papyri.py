from greek_lemma_audit.papyri import normalize_token, scan_tokens


def test_supplement_boundary_and_restored_letters():
    r = normalize_token("κα[ὶς")
    assert r.form == "καὶς" and "supplement_boundary" in r.flags
    r = normalize_token("δ[εῖ]σθαι")
    assert r.form == "δεῖσθαι" and "restored_letters" in r.flags


def test_insertion_breaks_unread_and_adscript():
    assert normalize_token("θε〈ῖ〉σιν").form == "θεῖσιν"
    r = normalize_token("σω]‖τηρίαν")
    assert r.form == "σωτηρίαν" and "line_or_column_break" in r.flags
    r = normalize_token(".ἀ[λλ᾿")
    assert r.form.startswith("ἀλλ") and any(f.startswith("unread_letters") for f in r.flags)
    r = normalize_token("τῶι")
    assert r.form == "τῷ" and "iota_adscript" in r.flags
    assert normalize_token("καί").form == "καί"  # αι is a diphthong, untouched


def test_quotes_elision_and_footnote_digit():
    assert normalize_token("δ’").form == "δ’"
    assert normalize_token("ῥητορικήν“.").form == "ῥητορικήν"
    assert normalize_token("ποιητικήν.1").form == "ποιητικήν"
    assert normalize_token("φάρμακον").changed is False


def test_scan_counts():
    rep = scan_tokens(["κα[ὶς", "καί", "τῶι", "θε〈ῖ〉σιν", "λόγος"])
    assert rep["tokens"] == 5 and rep["touched"] == 3
    assert rep["by_flag"]["iota_adscript"] == 1
