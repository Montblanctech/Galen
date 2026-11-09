# Reference translations of *On Mixtures*: not distributed

The automated metrics of *On Mixtures* (Mix.) were computed against two published English translations,
Johnston (2020) and Singer and van der Eijk (2018). Both remain under their publishers' copyright, so this
repository does not distribute them. In `mt_eval/input/on_mixtures.txt`, and in the copy of the file
before the reference fix (`analysis/data/mixtures_pre_fix/on_mixtures.txt`), each of the 20 reference
paragraphs is replaced by the line `[reference not distributed; see mt_eval/input/REFERENCES.md]`; the
Greek and the layout of the files are unchanged. Everything computed from the English is saved in the
repository: the evaluation files in `mt_eval/output/evaluations/`, the outputs of
`analysis/02_surface_similarity.py` in `analysis/outputs/` and the token counts in `analysis/data/`.
Without the English, the scripts that need it print a line beginning `SKIPPED:` and leave the saved
outputs in place. `analysis/verify.py` checks those saved files against stored SHA-256 checksums on every
run, with or without the English.

The Comp. reference (`on_comp.txt`, by Manuela Marai) is distributed; its checksums are listed below for
completeness.

- Johnston, Ian (2020). *Galen: On Temperaments; On Non-Uniform Distemperment; The Soul's Traits Depend
  on Bodily Temperament*. Loeb Classical Library 546. Harvard University Press.
- Singer, P. N., and van der Eijk, Philip J. (2018). *Galen: Works on Human Nature, Vol. 1: Mixtures
  (De Temperamentis)*. Cambridge University Press. https://doi.org/10.1017/9781316181171

## Rebuilding the file

The locators below are those of `analysis/data/passage_locations.csv`: H. = Helmreich (1904), page,line;
K. = Kühn, vol. I (1821) for Mix.; vol. XIII (1827) for Comp., volume.page,line. Both editions of the
translations print Kühn's pagination in their margins, and Singer and van der Eijk also print
Helmreich's, so the locators find each passage in either book. The table also gives the first three and
the last three words of each translation as it was used, to mark where the passage begins and ends.

`on_mixtures.txt` is UTF-8 with LF line endings and no byte-order mark. Each passage is a line
`Chunk N`, a blank line, the Greek as one line, a blank line, reference 1 (ref1 = Johnston) as one line, a
blank line, reference 2 (ref2 = Singer and van der Eijk) as one line, and a blank line; the file ends with
one further blank line. As distributed, the file keeps this layout with the pointer line in each reference
slot, so to rebuild it, replace the pointers in order: in each passage the first pointer with Johnston's
translation of that passage and the second with Singer and van der Eijk's, each on a single line with no
line break inside it. The pre-fix copy has the same layout except that in passages 2 and 4 the two
reference lines follow each other with no blank line between them (the defect described in
`analysis/data/mixtures_pre_fix/README.md`); keep it that way when rebuilding it.

Then check the result:

```bash
python3 mt_eval/input/check_references.py path/to/rebuilt/on_mixtures.txt
python3 mt_eval/input/check_references.py --pre-fix path/to/rebuilt/pre-fix/on_mixtures.txt
```

The script checks the whole file, its layout (a reference must have its own line, with a blank line before
and after it, as above), the Greek of each passage and each translation, and prints PASS or FAIL for each.
A FAIL names the passage and the translator and, from the SHA-256 of each sentence, the sentence or
sentences that differ; it also says whether the words differ or only the typography (the text is the same
after the normalization defined below). The script ends with PASS, and exits 0, only if the whole file is
byte-identical to the file used in the evaluation. Differences in wording or punctuation, quotes and
dashes included, change the scores; differences in whitespace alone do not, because the parser collapses
whitespace, but the check still asks for a byte-identical file, so that a PASS confirms the rebuild
completely. Once the file passes, run `bash analysis/run_all.sh` and `python analysis/verify.py`: they
then recompute the surface-similarity outputs from the English and compare them with the saved files.

## Checksums

Words are counted as Python's `str.split()` counts them on the line as stored (whitespace-separated
tokens; the same as `wc -w` for these lines), and the first three and last three words are taken from the
same split. The raw SHA-256 is taken over the UTF-8 bytes of the line as stored, without its line ending.
The normalized text is made from the line, decoded from UTF-8, in this order:

1. Unicode normalization form NFKC (which, among other things, turns no-break and thin spaces into
   ordinary spaces and the ellipsis … into three full stops);
2. the soft hyphen U+00AD and the zero-width characters U+200B, U+200C, U+200D and U+FEFF are deleted;
3. the dashes U+2010 to U+2015 and the minus sign U+2212 become "-" (U+002D); the ellipsis U+2026
   becomes "..."; the quotes ‘ ’ ‚ ‛ (U+2018 to U+201B), the modifier letter apostrophe ʼ (U+02BC) and
   the prime ′ (U+2032) become "'" (U+0027); the quotes “ ” „ ‟ (U+201C to U+201F) become '"' (U+0022);
4. the text is split at whitespace as Python's `str.split()` splits it and joined with single spaces,
   which also removes leading and trailing whitespace.

Case is not changed. Its SHA-256 is taken over its UTF-8 bytes. For the per-sentence checksums, which
`check_references.py` holds (319 sentences), the normalized text is split at every space that follows
".", "?" or "!", and the line as stored, stripped of leading and trailing whitespace, at every run of
whitespace that follows ".", "?" or "!"; each sentence's SHA-256 is taken over its UTF-8 bytes.
`check_references.py` holds the same values as this table.

| Passage | Chapter | Helmreich (H.) | Kühn (K.) | Slot | Translator | Words | Begins | Ends | SHA-256 of the normalized text | SHA-256 of the line as stored |
|---|---|---|---|---|---|---|---|---|---|---|
| Mix. 1 | I.1 | 1,1–2,3 H. | I.509,1–510,15 K. | ref1 | Johnston | 263 | That the bodies … | … of the terms. | `14499c620239db7bd3d7692af487d2abc22f82787bac866823ac3867f69f5278` | `52ce78ab0cddf5ace889f538f5a999cbffc863efdd88f962c77cb800d201320b` |
| Mix. 1 | I.1 | 1,1–2,3 H. | I.509,1–510,15 K. | ref2 | Singer & van der Eijk | 294 | That the bodies … | … terms are used. | `c6e1a049cb61141069639063a2c4e569b71ffad9431c023b671a6e6459eefa62` | `c6e1a049cb61141069639063a2c4e569b71ffad9431c023b671a6e6459eefa62` |
| Mix. 2 | I.4 | 12,13–13,10 H. | I.527,13–529,2 K. | ref1 | Johnston | 264 | And this, the … | … wet and hot. | `23f0f1f8b0ad47b306a66569693d57c26be0978da509bb3309af54328510fe9e` | `23f0f1f8b0ad47b306a66569693d57c26be0978da509bb3309af54328510fe9e` |
| Mix. 2 | I.4 | 12,13–13,10 H. | I.527,13–529,2 K. | ref2 | Singer & van der Eijk | 263 | And it is … | … wet and hot. | `6d44b3359a5bb5758c48834042ceb6e17ce2656d61575e74fdc9fb0aaa268bf8` | `6d44b3359a5bb5758c48834042ceb6e17ce2656d61575e74fdc9fb0aaa268bf8` |
| Mix. 3 | I.6 | 23,16–24,10 H. | I.545,14–547,4 K. | ref1 | Johnston | 258 | In these, the … | … it functions best. | `fef33c3fec4a1c3a856eb76c85b9bd834038ec6b3d11d17d61da4bb945ca70cb` | `c19e19ed6bb09f269982f1c8288522362d15e8d69680a92ea55764a21089e2eb` |
| Mix. 3 | I.6 | 23,16–24,10 H. | I.545,14–547,4 K. | ref2 | Singer & van der Eijk | 305 | Of these, the … | … its activities optimally. | `d54aa040a80a6b0a09ddb3dc468393ba8f1d8706b492efd5f8f2e00e7ad1ebac` | `79f20e25143249fe38d496a0da71057c3f7bdcff4445eb9f04ed9d25a8aaf902` |
| Mix. 4 | I.9 | 35,3–28 H. | I.564,7–565,14 K. | ref1 | Johnston | 256 | Therefore, those parts … | … appropriate to each. | `ad8a2a79551cf12469584b156654a368f1a86ace8f8959ed0f88e9b6a1103aad` | `67931bef001c198b7f5a0493e025aafef23d8203c547e53e69e4885cede90ca4` |
| Mix. 4 | I.9 | 35,3–28 H. | I.564,7–565,14 K. | ref2 | Singer & van der Eijk | 311 | Now, those parts … | … appropriate to each. | `5f0a503432475742d2d3e374a2d0e8833f65fa49e6fa2e7e1815a6307e3d8dea` | `5f0a503432475742d2d3e374a2d0e8833f65fa49e6fa2e7e1815a6307e3d8dea` |
| Mix. 5 | II.2 | 47,22–48,16 H. | I.584,3–585,10 K. | ref1 | Johnston | 302 | In turn, from … | … in their prime. | `6a48e78336a53c39c0c58083f7608381a4124019f0750f7c2a746037a98941be` | `ab4680e3a356440f2d2c15247fbd0c7dff16eb1ef97b5976b6e4fc5e38e24a9b` |
| Mix. 5 | II.2 | 47,22–48,16 H. | I.584,3–585,10 K. | ref2 | Singer & van der Eijk | 302 | Again, on the … | … in the prime. | `5bd722613230c7d49d3354c4ea047724dac1adf0f20e0064fecb75ba7583ddb5` | `f177e3c672df0bcb7a52583261882dbbb2aa6d88b8cad8cfd8da3790ccc42eb6` |
| Mix. 6 | II.3 | 59,6–60,4 H. | I.602,11–604,1 K. | ref1 | Johnston | 265 | All membranes are … | … become like this. | `3c496b90f9b3323a9def49ae7ac381f256e5c9f3d778fceff4d2281c918a57b1` | `af8011db136e97ac2d828d709886e18b7cdba9ecbbf9c709dde4e69645a9ea91` |
| Mix. 6 | II.3 | 59,6–60,4 H. | I.602,11–604,1 K. | ref2 | Singer & van der Eijk | 290 | All membranes, certainly, … | … has become so. | `97a96ab92e17fc2eabc0107a5bac43047ad05b283b517a8e539c2539b257af04` | `d3e6916a6deacbdb16415e7a103661e52e51d48962a6629b9b9aa5f6639df7d9` |
| Mix. 7 | II.5–6 | 70,6–71,5 H. | I.620,13–622,5 K. | ref1 | Johnston | 294 | For it was … | … the whole body. | `1c92b903b7e6156180875d80a59b1c558e231807c99221597ee71c56e8bd98c8` | `1c92b903b7e6156180875d80a59b1c558e231807c99221597ee71c56e8bd98c8` |
| Mix. 7 | II.5–6 | 70,6–71,5 H. | I.620,13–622,5 K. | ref2 | Singer & van der Eijk | 303 | (For it was … | … as a whole. | `b0b0fd945fe0dd0e05a1857c2c89db7e6e263e9374e506620652c9da01115270` | `096ec4f556d47dd1d33761ec460802c1de34fa140d51ed284b819e785e7d05b1` |
| Mix. 8 | II.6 | 81,10–82,3 H. | I.638,11–639,16 K. | ref1 | Johnston | 274 | And those in … | … krasis is wet. | `dec56a5e9c0d8757a020762edc8843420a3e2177bb7b218c8a3ecb01eef37f3e` | `dec56a5e9c0d8757a020762edc8843420a3e2177bb7b218c8a3ecb01eef37f3e` |
| Mix. 8 | II.6 | 81,10–82,3 H. | I.638,11–639,16 K. | ref2 | Singer & van der Eijk | 277 | Then, too, a … | … wet overall mixture. | `65f1fdac45c30bab70d10448d6993d5086f21f069a2f7aed44645813a468a1d2` | `c589b8c0548e999e70691535ddedb01c7c47bd09ccd1f6c7cef769282c23bc57` |
| Mix. 9 | III.2 | 93,21–94,21 H. | I.658,5–659,13 K. | ref1 | Johnston | 303 | And the medication … | … leading to extinction. | `09b293a1a16c0ec0162b77a31a13225f5cf7c7f91d15149e597f87e9d8f941f4` | `6fdeb6bbd4fc65deadf7dd779c5994a78ad0a227c80a2f7a30a6d714b481cabd` |
| Mix. 9 | III.2 | 93,21–94,21 H. | I.658,5–659,13 K. | ref2 | Singer & van der Eijk | 304 | Medea’s drug was … | … risk destroying it. | `d2286e366d699f05adf9faea24000475273b0e50ad81382b3937317c33ce393d` | `f7c7bbd13b87a37673fbeab51a1197b73239bd44d7cf66c4c3d14d84fdd1160a` |
| Mix. 10 | III.4 | 105,2–27 H. | I.676,17–678,9 K. | ref1 | Johnston | 310 | For in this … | … of green wood. | `9eefd105ee098a059aa940508d71b6a481360c7a0b377cb83585713d1b82374b` | `0205d13988fcd740e92d433de522ba4e93fe8ce0f3f936f12ecea2050eb4aec5` |
| Mix. 10 | III.4 | 105,2–27 H. | I.676,17–678,9 K. | ref2 | Singer & van der Eijk | 303 | For if we … | … of green wood. | `67fb2bcb611729753885e270a7cc3f786ef6b5edb29612909537b5534aded3ed` | `67fb2bcb611729753885e270a7cc3f786ef6b5edb29612909537b5534aded3ed` |
| Comp. 1 | I.2 | – | XIII.367,10–369,1 K. | ref1 | Marai | 292 | Regarding the properties … | … point of burning. | `83e1e68f1ff89e1ac6f4a5d948bbd82a7a262b6276fe108f7355e032fbd5d7f6` | `2858cdb243a3f77e9b0d19a99045724149282fe23ba063dec1afc11f53b14b68` |
| Comp. 2 | I.15–16 | – | XIII.431,4–432,13 K. | ref1 | Marai | 315 | However, nobody would … | … marrow, 2 unciae. | `7d28e5effa5a16ebea46208edd614b7f23a5159e4a2376301277c079922ab391` | `8521640e88ae08cd59972daa9ae2bb38c326e1f427dad3b0b889c0be73c95613` |
| Comp. 3 | II.4–5 | – | XIII.499,5–500,15 K. | ref1 | Marai | 335 | But I will … | … with a cerate. | `707183a03b658a9e25ff120849e094d18c6f6b8fba18203688bbd09806009206` | `8243400418f5b4fe076bd2474bec3b9ca5966ec69dd27e8f43f56f48251c2fb7` |
| Comp. 4 | III.2 | – | XIII.569,10–570,17 K. | ref1 | Marai | 310 | Among the substances … | … windows facing south. | `c0ddd86ed25198d19a58d45b76e270b04eab49dc376e2948e39c20312078dd36` | `25e093764617b5bb3a3257e732245527ac6f769c0572b250907d53366e74ff11` |
| Comp. 5 | III.7–8 | – | XIII.635,6–636,14 K. | ref1 | Marai | 314 | A thick composition … | … could cure all. | `910a8f16090459e575385eb5bbaafc51f9b503a46aee7fa3e98507a8089b9089` | `c6a27020e165a909aa9f49caac6f604a29fa90d2e9fb17fcc60da8a3498e45b4` |
| Comp. 6 | IV.5 | – | XIII.703,8–704,13 K. | ref1 | Marai | 240 | The thickness of … | … hard-to-heal chronic wounds. | `e8d111f66f5c0c854e578637316a22965796a5a151f910fba5699760f45caf35` | `ca318413bf8bb53eb34ed535f6d660568dc9b99ea55bc7ee390d4616da280dc3` |
| Comp. 7 | V.2 | – | XIII.771,18–773,9 K. | ref1 | Marai | 280 | Ampelitis [i.e unidentified … | … to the remedy. | `c4d33dc7f6ea39e95922373ddc57e4061a60fd37f83b69fe5b4a1fec80568573` | `465bf3f34dd51bc52d95461cf885fcf53db4a640c72848ee405e9504e0e8f152` |
| Comp. 8 | V.13 | – | XIII.840,10–842,1 K. | ref1 | Marai | 308 | Sitz bath for … | … with rose oil. | `acd49bda3380e73da9824ccdf31a3c248f8b912999e35459ac692666b64b67a9` | `aa6c1a0cc6f7aa32a0e6bbf99db4d76ac370524596becda6d398f907ebf2fa9b` |
| Comp. 9 | VI.10 | – | XIII.909,17–911,7 K. | ref1 | Marai | 245 | Terebinth resin, 48 … | … to 8 drachmai. | `eb576e8d86275495af3d36b73b218233c889ecc53b1102b520d20b4590fcc3ee` | `d711b33d3dbfea92139f990ef9242123cdcd9bb990e7afe1ae8273529ddc5eb6` |
| Comp. 10 | VII.7 | – | XIII.983,3–984,8 K. | ref1 | Marai | 275 | [ingredient] 10 [drachmai]; … | … drachmai each; frankincense. | `91d92ca4ffe5ec33f030967b9a30e8a5eb4fd6432b15178725c12a113b31e645` | `7f240de02effcd9d2bea0488635f116eed8d021fd1a7186cc28f5ca54f9107e5` |

Whole files, with the English (SHA-256):

```
5e6c7c7a02ae3d8761ea0236bc45b4f1789dafe13a9c066e299b0ed27c642076  mt_eval/input/on_mixtures.txt (57,608 bytes; the file evaluated after the reference fix)
07af3ce679e91a3f5244dd02d4dfb796b0f9fba5fae7a4ad8019d9e0881bd98a  analysis/data/mixtures_pre_fix/on_mixtures.txt (57,606 bytes; before the fix)
92850bd0d99c05e11afc391c502e6d53885717817aea547b692e1204370a459a  mt_eval/input/on_comp.txt (45,621 bytes; distributed as is)
```

The first is also the `input_file.sha256` recorded in `mt_eval/output/evaluations/on_mixtures_evaluation.json`.
