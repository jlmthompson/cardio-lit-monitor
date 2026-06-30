# The Cardiovascular Genomics Review

Automated weekly literature monitor for **cardiovascular genomics**, across three
streams: the genetics/genomics of **congenital heart disease (CHD) and dilated
cardiomyopathy (DCM)**; **genomic-study methods** (rare-variant/burden testing,
PRS/PGS, GWAS, MTAG, fine-mapping, …); and **AI/ML** applied to genomics and
cardiovascular disease.

**Live dashboard:** https://jlmthompson.github.io/cardio-lit-monitor/

## How it works
1. **Search** — PubMed (NCBI eutils) using field-tagged Boolean queries, dated by
   **Entrez date (EDAT)** so newly *indexed* papers are caught, not just those
   with a recent stated publication date.
2. **Preprints** — Europe PMC, restricted to preprint servers (bioRxiv / medRxiv /
   Research Square …), using the same concepts.
3. **De-duplication** — `data/seen.json` records everything already surfaced, so a
   paper never appears twice across weeks.
4. **Relevance filtering** — a transparent keyword heuristic scores every candidate
   0–5 across the three streams (cardiac anchor, genomic-methods terms, AI-tied-to-
   genomics) with off-topic guards, and keeps those at or above `relevance_threshold`.
   Titles matching `exclude_terms` are dropped outright. No API key, no secrets — the
   workflow runs entirely on public APIs.

Output is a static dashboard (GitHub Pages). No email — check or refresh the site
whenever you want.

## What it monitors
- **Cardiovascular Genomics** — CHD & DCM gene discovery, rare/de novo variants, sequencing, omics
- **Genomic Methods** — rare-variant & burden testing, PRS/PGS, GWAS, MTAG, fine-mapping, genetic correlation
- **AI & Machine Learning** — deep learning for variant effect/pathogenicity, foundation/LLMs for genomics, ML genomic prediction

## Tuning
Edit `data/watch_config.json`:
- **`queries`** — recall knob. PubMed field-tagged Boolean per stream; broaden or
  narrow to change what gets pulled.
- **`relevance_threshold`** — precision knob. Raise to 4 for a tighter, smaller
  digest; lower to 2 to cast wider.
- **`exclude_terms`** — kill recurring noise: any paper whose **title** contains one
  of these is dropped (e.g. add `"cardiac surgery"` or `"pulmonary hypertension"` if
  those keep slipping in).
- **`settings`** — `reldate_days`, `max_papers_total`, `include_preprints`.

## Schedule
Runs every Monday 07:00 Sydney time (GitHub Actions), and on manual dispatch.
