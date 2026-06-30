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
4. **Relevance filtering** — an LLM (Anthropic) scores every candidate 0–5 against
   the plain-English `interest_profile` in the config and keeps those at or above
   `relevance_threshold`. Without an `ANTHROPIC_API_KEY` it falls back to a keyword
   heuristic, so the workflow always succeeds.

Output is a static dashboard (GitHub Pages). No email — check or refresh the site
whenever you want.

## What it monitors
- **Disease genetics** — CHD, DCM, SCAD gene discovery / rare & de novo variants / sequencing
- **PRS in disease** — polygenic risk scores in CHD, DCM, SCAD
- **PRS & methods** — oligogenic / digenic / multi-locus architecture, rare+common integration
- **Topics** — DNA methylation, episignatures, multi-omics in CHD / DCM

## Tuning
Edit `data/watch_config.json`:
- **`interest_profile`** (plain English) — the main precision knob. Describe what
  you want and don't want; the LLM filters against it.
- **`queries`** — recall knob. PubMed field-tagged Boolean per topic.
- **`settings`** — `reldate_days`, `relevance_threshold`, `max_papers_total`,
  `include_preprints`, `use_llm`, `llm_model`.

## Schedule
Runs every Monday 07:00 Sydney time (GitHub Actions), and on manual dispatch.

## Secrets (GitHub → Settings → Secrets → Actions)
- `ANTHROPIC_API_KEY` — enables LLM relevance scoring (recommended).
- `NCBI_API_KEY` — optional; raises the NCBI rate limit.
