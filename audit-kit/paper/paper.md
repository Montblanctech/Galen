---
title: 'greek-lemma-audit: bounded accuracy ranges and blind reviewer sheets for Ancient Greek lemmatizers, author by author'
tags:
  - Python
  - Ancient Greek
  - lemmatization
  - evaluation
  - digital classics
authors:
  - name: William Pepperman
    affiliation: 1
affiliations:
  - name: Montblanc Tech LLC, independent researcher, United States
    index: 1
date: 6 November 2026
bibliography: paper.bib
---

# Summary

Lemmatizers for Ancient Greek are evaluated on treebank test splits that under-represent the vocabulary scholars actually look up: rare, technical, author-specific words. `greek-lemma-audit` is a command-line kit that audits any lemmatizer's output over any Greek corpus, author by author, without a human reader, and emits a *bounded* accuracy range rather than a single score: an error floor from the Morpheus morphological analyzer (a lemma the analyzer cannot derive from the surface is a near-certain error), an upper bound from agreement among independently trained systems, a point estimate on the dictionary-cited stratum (LSJ citations relocated to tokens), and a blind, salted reviewer sheet with a scorer for human or model adjudication. Every number carries its N, its 95% Wilson interval and its seed; the corpus is never modified.

Adapters are provided for odyCy [@odycy], Stanza [@stanza] (Perseus and PROIEL models), Open Greek's Dilemma lemmatizer, and the Stoicheia tagger-parser [@stoicheia]; a system that cannot run reports why instead of being dropped. Convention differences between systems (the article as ὁ against gender-specific forms, adverbs under their adjective) are mapped by a documented table and reported *beside* the strict figure, never instead of it. A `batches` command splits any sheet into blind, parallel reader tasks for any model or person; `score` merges the answers and replays the control gate. An `lsjgold` command scores any system's per-work token caches on the LSJ-Gold benchmark (57,278 LSJ citations relocated into First1KGreek and Perseus editions over 17 authors); the gold file ships inside the package under CC BY 4.0, so a new system gets its leaderboard row without touching the project's pipeline.

# Statement of need

The kit grew out of the Galen Density Project [@galen-density], which found that a state-of-the-art neural lemmatizer agreed with a dictionary's headword on only 62% of Galen's LSJ-cited vocabulary while scoring over 90% on treebank-style text. Reported accuracy on common words says little about a corpus whose interest lies in its rare ones. Researchers building restoration models, term maps or translation aids for an author need to know how a lemmatizer fails *on that author*, and lexicon-first and neural systems fail differently: across the fifty largest First1KGreek authors the kit found a lexicon-first system's Morpheus floor flat at 94--97% while the neural system's floor dipped exactly on the medical authors. The kit makes that measurement a one-command, reproducible, citable table, and the accompanying LSJ-Gold loci make the dictionary-cited stratum a standing benchmark that new systems can be scored on.

# Acknowledgements

Morpheus is served by the Perseids Project; LSJ XML by the Perseus Digital Library; texts by the Open Greek and Latin First1KGreek project; Dilemma and the Open Greek corpus by the Open Greek project; Stoicheia by Cullhed and Thörn Cleland.

# References
