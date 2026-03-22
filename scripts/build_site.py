#!/usr/bin/env python3
"""
Generates docs/index.html from the current digest.json.
Theme: slate blue background, white cards, teal accent — matching the
Epigenetic Clock Selector site style.
"""

import json
from pathlib import Path
from datetime import datetime

DIGEST = Path(__file__).parent.parent / "data" / "digest.json"
OUT    = Path(__file__).parent.parent / "docs" / "index.html"
OUT.parent.mkdir(exist_ok=True)

digest = json.loads(DIGEST.read_text())
week   = datetime.fromisoformat(digest["generated"]).strftime("%d %B %Y")
summary_text = digest.get("summary_text", "")
selected     = digest.get("selected_papers", [])
total_sel    = digest["summary"].get("total_selected", len(selected))
total_cand   = digest["summary"].get("total_candidates", 0)

SECTION_META = {
    "disease_genetics": ("CHD / DCM / SCAD Genetics",  "#0d9488"),
    "prs_disease":      ("PRS in CHD · DCM · SCAD",    "#6366f1"),
    "prs_methods":      ("PRS & Oligogenic Methods",    "#f59e0b"),
    "topic_watch":      ("Epigenetics & Methylation",   "#64748b"),
}


def paper_card(p):
    section = p.get("section", "")
    _, accent = SECTION_META.get(section, ("Other", "#64748b"))
    doi_link = f'<a class="ext" href="https://doi.org/{p["doi"]}" target="_blank">DOI ↗</a>' if p.get("doi") else ""
    ris_safe = p["ris"].replace(chr(10), "|").replace(chr(13), "").replace('"', "&quot;")
    topic_badge = f'<span class="badge topic" style="background:{accent}20;color:{accent}">{p.get("topic","").replace("_"," ")}</span>'
    type_badge  = f'<span class="badge btype">{p.get("type","")}</span>'

    bullets = p.get("bullets", [])
    if bullets:
        bullet_items = "".join(f"<li>{b}</li>" for b in bullets)
        content_html = f'<ul class="card-bullets">{bullet_items}</ul>'
    else:
        # Fallback to plain abstract if no bullets
        content_html = f'<p class="card-abstract">{p.get("abstract","")}</p>'

    return f"""
<div class="card" data-section="{section}">
  <div class="card-accent" style="background:{accent}"></div>
  <div class="card-body">
    <div class="card-meta">{type_badge}{topic_badge}</div>
    <a class="card-title" href="{p['url']}" target="_blank">{p['title'] or '(No title)'}</a>
    <div class="card-authors">{p.get('authors','')} &mdash; <em>{p.get('journal','')}</em> {p.get('year','')}</div>
    {content_html}
    <div class="card-links">
      <a class="ext" href="{p['url']}" target="_blank">PubMed ↗</a>
      {doi_link}
      <button class="ris-btn" onclick="downloadRIS(this)" data-ris="{ris_safe}" data-title="{p['pmid']}">⬇ RIS</button>
    </div>
  </div>
</div>"""


# Build section legend items
legend_html = ""
for sk, (label, accent) in SECTION_META.items():
    count = sum(1 for p in selected if p.get("section") == sk)
    if count > 0:
        legend_html += f'<span class="legend-item"><span class="legend-dot" style="background:{accent}"></span>{label} ({count})</span>'

# Build summary lines for display
summary_lines = [ln for ln in summary_text.split("\n") if ln.strip()]
summary_header = summary_lines[0] if summary_lines else ""
summary_bullets = summary_lines[1:] if len(summary_lines) > 1 else []
highlight = next((ln for ln in summary_bullets if ln.strip().startswith("Highlight")), "")
bullets   = [ln for ln in summary_bullets if not ln.strip().startswith("Highlight")]

bullets_html = "".join(f"<li>{b.strip().lstrip('• ')}</li>" for b in bullets if b.strip())
highlight_html = f'<div class="highlight-line">{highlight.strip()}</div>' if highlight else ""

cards_html = "".join(paper_card(p) for p in selected)
if not selected:
    cards_html = '<div class="no-papers">No new papers matched your focus areas this week. Check back next Monday.</div>'

OUT.write_text(f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Cardio Lit Monitor</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #1e2d3e;
      color: #334155;
      min-height: 100vh;
    }}

    /* ── Header ── */
    .site-header {{
      background: #162333;
      border-bottom: 3px solid #0d9488;
      padding: 28px 24px 20px;
      text-align: center;
    }}
    .site-header h1 {{
      font-size: 1.7rem;
      font-weight: 700;
      color: #ffffff;
      letter-spacing: -0.02em;
      margin-bottom: 4px;
    }}
    .site-header .subtitle {{
      font-size: 0.85rem;
      color: #94a3b8;
    }}
    .site-header a {{ color: #0d9488; text-decoration: none; }}
    .site-header a:hover {{ text-decoration: underline; }}

    /* ── Summary card ── */
    .summary-wrap {{
      max-width: 820px;
      margin: 28px auto 0;
      padding: 0 20px;
    }}
    .summary-card {{
      background: #ffffff;
      border-radius: 12px;
      padding: 20px 24px;
      box-shadow: 0 2px 12px rgba(0,0,0,0.18);
      border-top: 4px solid #0d9488;
    }}
    .summary-card h2 {{
      font-size: 0.95rem;
      font-weight: 700;
      color: #0d9488;
      margin-bottom: 10px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    .summary-header {{
      font-size: 0.95rem;
      font-weight: 600;
      color: #1e293b;
      margin-bottom: 8px;
    }}
    .summary-card ul {{
      list-style: none;
      margin-bottom: 10px;
    }}
    .summary-card ul li {{
      font-size: 0.85rem;
      color: #475569;
      padding: 3px 0;
    }}
    .summary-card ul li::before {{
      content: "→ ";
      color: #0d9488;
    }}
    .highlight-line {{
      font-size: 0.82rem;
      color: #64748b;
      border-top: 1px solid #e2e8f0;
      padding-top: 10px;
      margin-top: 6px;
      font-style: italic;
    }}
    .legend {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 14px;
      padding-top: 14px;
      border-top: 1px solid #e2e8f0;
    }}
    .legend-item {{
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 0.78rem;
      color: #475569;
    }}
    .legend-dot {{
      width: 10px;
      height: 10px;
      border-radius: 50%;
      flex-shrink: 0;
    }}

    /* ── Controls ── */
    .controls {{
      max-width: 820px;
      margin: 16px auto 0;
      padding: 0 20px;
      display: flex;
      gap: 10px;
      align-items: center;
    }}
    #search {{
      flex: 1;
      max-width: 320px;
      background: #ffffff;
      border: 1px solid #cbd5e1;
      border-radius: 8px;
      padding: 8px 14px;
      font-size: 0.85rem;
      color: #1e293b;
    }}
    #search:focus {{ outline: none; border-color: #0d9488; box-shadow: 0 0 0 2px #0d948820; }}
    #search::placeholder {{ color: #94a3b8; }}
    .count-badge {{
      font-size: 0.8rem;
      color: #94a3b8;
    }}

    /* ── Cards ── */
    .cards-wrap {{
      max-width: 820px;
      margin: 16px auto 40px;
      padding: 0 20px;
      display: flex;
      flex-direction: column;
      gap: 14px;
    }}
    .card {{
      background: #ffffff;
      border-radius: 10px;
      box-shadow: 0 1px 8px rgba(0,0,0,0.12);
      display: flex;
      overflow: hidden;
      transition: box-shadow 0.15s;
    }}
    .card:hover {{ box-shadow: 0 4px 16px rgba(0,0,0,0.18); }}
    .card-accent {{
      width: 5px;
      flex-shrink: 0;
    }}
    .card-body {{
      padding: 16px 18px;
      flex: 1;
      min-width: 0;
    }}
    .card-meta {{
      margin-bottom: 7px;
      display: flex;
      flex-wrap: wrap;
      gap: 5px;
    }}
    .badge {{
      display: inline-block;
      padding: 2px 9px;
      border-radius: 20px;
      font-size: 0.68rem;
      font-weight: 600;
      letter-spacing: 0.02em;
    }}
    .btype {{
      background: #f1f5f9;
      color: #64748b;
    }}
    .topic {{
      /* colour injected inline */
    }}
    .card-title {{
      font-size: 0.92rem;
      font-weight: 600;
      color: #0f172a;
      text-decoration: none;
      line-height: 1.45;
      display: block;
      margin-bottom: 5px;
    }}
    .card-title:hover {{ color: #0d9488; }}
    .card-authors {{
      font-size: 0.75rem;
      color: #64748b;
      margin-bottom: 8px;
    }}
    .card-abstract {{
      font-size: 0.8rem;
      color: #475569;
      line-height: 1.6;
      margin-bottom: 10px;
    }}
    .card-bullets {{
      list-style: none;
      margin: 0 0 10px;
      padding: 0;
    }}
    .card-bullets li {{
      font-size: 0.8rem;
      color: #334155;
      line-height: 1.55;
      padding: 3px 0 3px 14px;
      position: relative;
    }}
    .card-bullets li::before {{
      content: "▸";
      position: absolute;
      left: 0;
      color: #0d9488;
      font-size: 0.7rem;
      top: 4px;
    }}
    .card-links {{
      display: flex;
      gap: 12px;
      align-items: center;
      font-size: 0.75rem;
    }}
    .ext {{
      color: #0d9488;
      text-decoration: none;
      font-weight: 500;
    }}
    .ext:hover {{ text-decoration: underline; }}
    .ris-btn {{
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      color: #475569;
      padding: 3px 9px;
      border-radius: 4px;
      font-size: 0.7rem;
      cursor: pointer;
      font-weight: 500;
    }}
    .ris-btn:hover {{ background: #e2e8f0; }}

    .no-papers {{
      background: #ffffff;
      border-radius: 10px;
      padding: 28px 24px;
      text-align: center;
      color: #64748b;
      font-size: 0.9rem;
    }}
    .hidden {{ display: none !important; }}
  </style>
</head>
<body>

<header class="site-header">
  <h1>🫀 Cardio Lit Monitor</h1>
  <p class="subtitle">Weekly digest &middot; {week} &middot;
    <a href="https://github.com/jlmthompson/cardio-lit-monitor" target="_blank">GitHub ↗</a>
  </p>
</header>

<div class="summary-wrap">
  <div class="summary-card">
    <h2>This Week</h2>
    <p class="summary-header">{summary_header}</p>
    <ul>{bullets_html}</ul>
    {highlight_html}
    <div class="legend">{legend_html}</div>
  </div>
</div>

<div class="controls">
  <input id="search" type="text" placeholder="Filter papers…" oninput="filterCards(this.value)">
  <span class="count-badge" id="count-label">{total_sel} of {total_cand} candidate papers selected</span>
</div>

<div class="cards-wrap" id="cards">
{cards_html}
</div>

<script>
function filterCards(q) {{
  q = q.toLowerCase();
  let shown = 0;
  document.querySelectorAll('.card').forEach(c => {{
    const hide = q.length > 1 && !c.textContent.toLowerCase().includes(q);
    c.classList.toggle('hidden', hide);
    if (!hide) shown++;
  }});
  const total = document.querySelectorAll('.card').length;
  document.getElementById('count-label').textContent =
    q.length > 1 ? `${{shown}} of ${{total}} papers shown` : `{total_sel} of {total_cand} candidate papers selected`;
}}
function downloadRIS(btn) {{
  const ris   = btn.dataset.ris.replace(/\\|/g, '\\n');
  const fname = 'paper_' + btn.dataset.title + '.ris';
  const blob  = new Blob([ris], {{type: 'application/x-research-info-systems'}});
  const a     = Object.assign(document.createElement('a'), {{
    href: URL.createObjectURL(blob), download: fname
  }});
  a.click();
}}
</script>

</body>
</html>""")

print(f"Site built → {OUT}")
