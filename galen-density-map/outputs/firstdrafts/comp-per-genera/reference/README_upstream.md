# AI Translation Evaluation of Ancient Greek Medical Texts

Code and data for evaluating LLM translations of passages from two works of Galen: automated metrics scored against reference translations, and expert MQM evaluation of each translation without references.

## Source Texts

Ten passages from each of two works by Galen of Pergamum (c. 129–216 CE):

- **De compositione medicamentorum per genera** (*On the Composition of Drugs According to Kinds*): 10 passages, 1 reference translation (prepared for this study)
- **De temperamentis** (*On Mixtures*): 10 passages, 2 published reference translations (Johnston 2020; Singer and van der Eijk 2018), not distributed: see `mt_eval/input/REFERENCES.md`

## Models

| Model | API Identifier | Snapshot Date | Settings (see `mt_eval/src/translator.py`) |
|-------|---------------|---------------|----------|
| GPT-5 | `gpt-5-2025-08-07` | August 7, 2025 | Responses API; reasoning effort "high"; verbosity "medium"; max output 16,000 tokens; no temperature parameter |
| Claude Sonnet 4.5 | `claude-sonnet-4-5-20250929` | September 29, 2025 | Messages API; temperature 0.3; max 8,000 tokens; extended thinking off |
| Gemini 2.5 Pro | `gemini-2.5-pro` | June 17, 2025 (GA stable) | temperature 0.3; max output 16,000 tokens; default (built-in) thinking |

All 60 translations were generated on 29 October 2025: one generation per passage per model, each on the first attempt. No call enabled any tool (no web search, no search grounding).

## Repository Structure

```
galen_project/
├── mt_eval/                       # Translation + automated evaluation pipeline
│   ├── src/                       # Core modules (parser, translator, evaluator, reporter)
│   ├── input/                     # Greek source texts; the Comp. reference translation; REFERENCES.md for the Mix. ones
│   ├── output/
│   │   ├── translations/          # Raw and blinded translation JSONs
│   │   └── evaluations/           # Per-chunk metric scores
│   ├── config/env.example         # API key template
│   ├── pipeline.py                # Main workflow entry point
│   └── requirements.txt
│
├── mqm/                           # MQM human evaluation: summary sheets (errors by severity and type, TQS, ratings)
│
├── analysis/                      # From the data to the tables and figure of the paper; see its README
│   ├── 01_...py - 11_...py        # The analyses, one per question
│   ├── 20_...py - 37_...py        # One script per table or figure
│   ├── data/                      # Frozen inputs (Stanza output, Diorisis form index, hand checks, rescored metrics)
│   ├── outputs/                   # All results; INDEX.md says which script writes each file
│   └── verify.py                  # Reruns everything and checks it matches outputs/
│
├── corpus_metrics/                # The original rarity measure (superseded by analysis/07; see below)
│   ├── rebuild_difficulty_audit.py  # The original measure's script
│   ├── download_diorisis.sh       # Downloads the Diorisis Ancient Greek Corpus
│   ├── comp.txt                   # De Compositione passage chunks (Greek; chunk 1 is the preface, see below)
│   ├── mix.txt                    # De Temperamentis passage chunks (Greek)
│   ├── diorisis_frequencies.json  # Cached lemma frequency dictionary
│   └── passage_difficulty_zipf.csv  # The original measure's values
│
├── LICENSE
└── README.md
```

## Evaluation Metrics

Seven metric families spanning lexical and neural approaches:

| Metric | Type | Multi-Reference Strategy |
|--------|------|--------------------------|
| BLEU-4 | Lexical (n-gram precision) | n-gram matches pooled over both references (sacreBLEU) |
| chrF++ | Lexical (character n-gram F-score) | Library multi-reference (sacreBLEU): the higher single-reference score |
| METEOR | Lexical (stems + synonyms) | Library multi-reference (NLTK): the higher single-reference score |
| ROUGE-L | Lexical (longest common subsequence) | Max across references |
| BERTScore | Neural (contextual embeddings) | Max F1 across references |
| COMET | Neural (trained on human judgments) | Max across references |
| BLEURT | Neural (learned evaluation) | Max across references |

The evaluation files also store each Mix. translation's score against each of its two references. The
tables in `analysis/` score Mix. as the mean of its two single-reference scores, so that Mix. and Comp.
(one reference) are scored alike; the multi-reference scores above are kept for comparison.

## Reproduction

### Prerequisites

- Python 3.8+
- API keys for OpenAI, Anthropic, and Google AI (only needed to regenerate translations)

### Translation Pipeline

```bash
cd mt_eval
./setup.sh                        # Creates venv and installs dependencies
cp config/env.example .env        # Add your API keys

source venv/bin/activate

# Full pipeline (translate + evaluate + report) with all seven metrics; BLEURT needs the
# BLEURT-20 checkpoint (set BLEURT_CHECKPOINT, or place it in mt_eval/models/BLEURT-20)
python3 pipeline.py input/on_mixtures.txt --metrics bleu chrf meteor rouge bertscore comet bleurt

# Select specific models
python3 pipeline.py input/on_comp.txt --models openai claude

# Use only fast metrics (no neural)
python3 pipeline.py input/on_comp.txt --metrics bleu rouge chrf

# Enable GPU for neural metrics
python3 pipeline.py input/on_mixtures.txt --gpu
```

### The original rarity measure (superseded)

```bash
cd corpus_metrics
./download_diorisis.sh            # Downloads Diorisis corpus (~185 MB)
pip install -r requirements.txt
python3 rebuild_difficulty_audit.py
```

`rebuild_difficulty_audit.py` is the original rarity measure, kept for the record: Zipf-based rarity scores for each passage chunk against the Diorisis Ancient Greek Corpus (820 texts, ~10M tokens). The measure used now is computed in `analysis/`.

`passage_difficulty_zipf.csv` holds the values of this original measure. `analysis/07_rarity_measure.py` reproduces them from Stanza's output and then corrects the measure in documented steps (numerals and symbols removed, weight abbreviations expanded, words that Stanza split at ῤῥ re-joined; a Stanza lemma that matches nothing in Diorisis replaced with the same lemma with normalized accents or case, or else with Diorisis's own lemma for the word form; disagreements between the two about rare and common decided by hand). It also measures the right first passage of Comp.: chunk 1 of `comp.txt` is Galen's preface to Book I, not the passage translated and evaluated (I.2, chunk 1 of `mt_eval/input/on_comp.txt`).

## Analyses

`analysis/` computes every table and figure of the paper from the data above (the evaluation files, the MQM sheets, the texts) and a few frozen inputs of its own. Inputs are frozen, seeds are fixed and outputs are committed (Python 3.10 or later):

```bash
pip install -r analysis/requirements.txt
bash analysis/run_all.sh      # regenerate outputs
python analysis/verify.py     # confirm they match the committed outputs
```

`analysis/outputs/INDEX.md` lists, for each table, the script that computes it.

## External Data

The [Diorisis Ancient Greek Corpus](https://doi.org/10.6084/m9.figshare.6187256.v1) (Vatri & McGillivray, 2018) is needed only to rerun the original measure in `corpus_metrics/`; `analysis/` uses the frequency dictionary and the form index derived from it, which are included. The corpus is downloaded by `corpus_metrics/download_diorisis.sh` and is not included in this repository because of its size (2.3 GB uncompressed). The corpus is distributed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

> Vatri, A., & McGillivray, B. (2018). The Diorisis Ancient Greek Corpus: Linguistics and Literature. *Research Data Journal for the Humanities and Social Sciences*, 3(1). https://doi.org/10.1163/24523666-01000013. Corpus: https://doi.org/10.6084/m9.figshare.6187256.v1

## License

Code: [MIT License](LICENSE)

Data:

- The Greek text of Galen is in the public domain. The passages of *On Mixtures* are from Helmreich's edition, those of *On the Composition of Drugs According to Kinds* from Kühn's, and the locators also give Kühn's pages for *On Mixtures*: Helmreich, Georg (1904), *Galeni De Temperamentis Libri III* (Leipzig: Teubner); Kühn, Karl Gottlob, *Claudii Galeni Opera Omnia*, vol. 1 (1821) and vol. 13 (1827) (Leipzig: Knobloch).
- The two published English translations of *On Mixtures* used as references, Johnston (2020; Loeb Classical Library 546, Harvard University Press) and Singer and van der Eijk (2018; Cambridge University Press), remain under their publishers' copyright and are not distributed. [`mt_eval/input/REFERENCES.md`](mt_eval/input/REFERENCES.md) gives the locator, word count and checksums of each passage, so that anyone with the books can rebuild `mt_eval/input/on_mixtures.txt` and check the result.
- The English reference translation of *On the Composition of Drugs According to Kinds* in `mt_eval/input/on_comp.txt` was made for this study: © Manuela Marai, released under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- The model translations and the annotation data are released under the MIT License with the code.

## Repository history

The history of this repository was rewritten on 2026-10-27 to remove the copyrighted reference translations, so commit hashes differ from those of earlier clones. The `submitted` tag still marks the state of the code at submission.
