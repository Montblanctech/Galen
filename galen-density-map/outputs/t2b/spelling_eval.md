# Spelling rules on held-out papyri

Rules: 253, learned on the train documents. Test: papyri.info DDbDP + DCLP test documents (1 in 10 by a seeded hash), not used to learn the rules.

## Words (written form unattested, regularized form attested)

| pairs asked | best reading = editor's form, spelling rules | same, HTR channel only | accepted as a spelling |
|---|---|---|---|
| 4,183 | 0.558 | 0.230 | 0.395 |

Of 9,775 test pairs, 3,396 have a written form that is itself attested (read as written) and 2,196 a regularized form not in the counts (names, documentary words).

## Scribal slips (sic / corr)

545 slips; 89 unattested as written; 11 would be excused as a spelling (12.4%).

## Lines (five words as written, run together)

| system | windows | boundary F1 | misspelled words | read as the editor's form |
|---|---|---|---|---|
| without spelling rules | 600 | 0.805 | 703 | 0.102 |
| with spelling rules | 600 | 0.833 | 703 | 0.243 |
