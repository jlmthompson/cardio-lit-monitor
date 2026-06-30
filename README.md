# Cardio Lit Monitor 🫀

Automated weekly literature monitor for the **genetics / genomics of structural
and inherited heart disease** (CHD, DCM, SCAD), PRS & genetic-architecture
methods, and CHD/DCM epigenetics & multi-omics.

**Live dashboard:** https://jlmthompson.github.io/cardio-lit-monitor/

## How it works
1. **Search** — PubMed (NCBI eutils) using field-tagged Boolean queries, dated by
   **Entrez date (EDAT)** so newly *indexed* papers are caught, not just those
   with a recent stated publication date.
2. **Preprints** — Europe PMC, restricted to preprint servers (bioRxiv / medRxiv /
   Research Square …), using the same concepts.
3. **De-duplication** — `data/seen.json` records everything already surfaced, so a
   paper never appears twice across weeks.
4. **Relevance filtering** — a transparent keyword/journal heuristic scores every
   candidate 0–5 (cardiac anchor + genetics/methods gating, with off-topic guards)
   and keeps those at or above `relevance_threshold`. No API key, no secrets — the
   workflow runs entirely on public APIs.

> Optional: an LLM relevance pass (scoring abstracts against the plain-English
> `interest_profile`) is wired in but **off by default**. Set `use_llm: true` and
> provide an `ANTHROPIC_API_KEY` only if you want it. It's not needed.

Output is a static dashboard (GitHub Pages). No email — check or refresh the site
whenever you want.

## What it monitors
- **Disease genetics** — CHD, DCM, SCAD gene discovery / rare & de novo variants / sequencing
- **PRS in disease** — polygenic risk scores in CHD, DCM, SCAD
- **PRS & methods** — oligogenic / digenic / multi-locus architecture, rare+common integration
- **Topics** — DNA methylation, episignatures, multi-omics in CHD / DCM

## Tuning
Edit `data/watch_config.json`:
- **`queries`** — recall knob. PubMed field-tagged Boolean per topic; broaden or
  narrow to change what gets pulled.
- **`relevance_threshold`** — precision knob. Raise to 4 for a tighter, smaller
  digest; lower to 2 to cast wider.
- **`settings`** — `reldate_days`, `max_papers_total`, `include_preprints`.
- **`interest_profile`** — only used if you opt into the LLM pass (`use_llm: true`).

## Schedule
Runs every Monday 07:00 Sydney time (GitHub Actions), and on manual dispatch.
No secrets required.
