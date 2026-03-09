#!/usr/bin/env python3
"""Generates docs/index.html from the current digest.json."""

import json
from pathlib import Path
from datetime import datetime

DIGEST = Path(__file__).parent.parent / "data" / "digest.json"
OUT    = Path(__file__).parent.parent / "docs" / "index.html"
OUT.parent.mkdir(exist_ok=True)

digest = json.loads(DIGEST.read_text())
s      = digest["summary"]
week   = datetime.fromisoformat(digest["generated"]).strftime("%d %B %Y")
SITE   = "https://jlmthompson.github.io/cardio-lit-monitor/"


def paper_card(p, accent):
    gene_badge = f'<span class="badge gene">{p["gene"]}</span>' if p.get("gene") else ""
    doi_link   = f'<a class="ext" href="https://doi.org/{p["doi"]}" target="_blank">DOI ↗</a>' if p.get("doi") else ""
    ris_btn    = f'<button class="ris-btn" onclick="downloadRIS(this)" data-ris="{p["ris"].replace(chr(10),"|").replace(chr(13),"")}" data-title="{p["pmid"]}">⬇ RIS</button>'
    return f"""
<div class="card" style="border-left-color:{accent}">
  <div class="card-meta">
    <span class="badge type">{p.get("type","")}</span>{gene_badge}
  </div>
  <a class="card-title" href="{p["url"]}" target="_blank">{p["title"]}</a>
  <div class="card-authors">{p.get("authors","")} · <em>{p.get("journal","")}</em> {p.get("year","")}</div>
  <div class="card-abstract">{p.get("abstract","")}</div>
  <div class="card-links">
    <a class="ext" href="{p["url"]}" target="_blank">PubMed ↗</a>
    {doi_link}
    {ris_btn}
  </div>
</div>"""


def section_block(title, icon, accent, papers, max_show=50):
    if not papers:
        return f'<div class="section"><div class="section-header" style="border-color:{accent}">{icon} {title}</div><p class="empty">No new papers this week.</p></div>'
    cards = "".join(paper_card(p, accent) for p in papers[:max_show])
    extra = f'<p class="more">Showing {min(len(papers),max_show)} of {len(papers)} papers.</p>' if len(papers) > max_show else ""
    return f"""
<div class="section">
  <div class="section-header" style="border-color:{accent};color:{accent}">{icon} {title}
    <span class="section-count">{len(papers)}</span>
  </div>
  {cards}{extra}
</div>"""


# Flatten paper lists
gene_papers  = [p for gl in digest["sections"]["gene_watch"].values()
                  for papers in gl["results"].values() for p in papers]
prs_papers   = [p for data in digest["sections"]["prs_watch"].values()  for p in data["papers"]]
topic_papers = [p for data in digest["sections"]["topic_watch"].values() for p in data["papers"]]
pgs_scores   = digest["sections"].get("pgs_new_scores", [])

gene_html  = section_block("Gene Watch",  "🔴", "#e74c3c", gene_papers)
prs_html   = section_block("PRS Watch",   "💙", "#3498db", prs_papers)
topic_html = section_block("Topic Watch", "🟢", "#27ae60", topic_papers)

pgs_html = ""
if pgs_scores:
    cards = "".join(f"""
<div class="card" style="border-left-color:#9b59b6">
  <a class="card-title" href="{sc['url']}" target="_blank">{sc['pgs_id']}: {sc['name']}</a>
  <div class="card-authors">Trait: {sc['trait']} · {sc['variants']:,} variants · Added {sc['date']}</div>
</div>""" for sc in pgs_scores)
    pgs_html = f'<div class="section"><div class="section-header" style="border-color:#9b59b6;color:#9b59b6">🆕 New PGS Catalog Scores <span class="section-count">{len(pgs_scores)}</span></div>{cards}</div>'

OUT.write_text(f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Cardio Lit Monitor</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
         background:#0f1117;color:#e8eaf6;min-height:100vh}}
    header{{background:#1a1d2e;padding:20px 32px;border-bottom:1px solid #2d3154}}
    header h1{{font-size:1.3rem;color:#fff;margin-bottom:4px}}
    header p{{font-size:0.8rem;color:#8892b0}}
    .stats-bar{{display:flex;gap:16px;padding:16px 32px;background:#151824;
               border-bottom:1px solid #2d3154;flex-wrap:wrap}}
    .stat{{background:#1a1d2e;padding:10px 18px;border-radius:8px;text-align:center}}
    .stat-n{{font-size:1.5rem;font-weight:700;color:#fff}}
    .stat-l{{font-size:0.72rem;color:#8892b0;margin-top:2px}}
    .controls{{padding:12px 32px;background:#1a1d2e;border-bottom:1px solid #2d3154;
              display:flex;gap:10px;flex-wrap:wrap;align-items:center}}
    #search{{background:#252840;border:1px solid #3d4266;color:#e8eaf6;
            padding:6px 12px;border-radius:6px;width:260px;font-size:0.85rem}}
    #search:focus{{outline:none;border-color:#7c83d3}}
    .main{{max-width:860px;margin:0 auto;padding:24px 32px}}
    .section{{margin-bottom:36px}}
    .section-header{{font-size:1rem;font-weight:700;border-bottom:2px solid;
                    padding-bottom:8px;margin-bottom:16px;display:flex;
                    align-items:center;justify-content:space-between}}
    .section-count{{background:#252840;color:#e8eaf6;font-size:0.75rem;
                   padding:2px 10px;border-radius:10px;font-weight:400}}
    .card{{background:#1a1d2e;border-left:3px solid #3d4266;border-radius:6px;
          padding:14px 16px;margin-bottom:12px}}
    .card-meta{{margin-bottom:6px}}
    .badge{{display:inline-block;padding:2px 8px;border-radius:10px;
            font-size:0.7rem;font-weight:600;margin-right:4px}}
    .badge.type{{background:#252840;color:#8892b0}}
    .badge.gene{{background:#2d1a0a;color:#f39c12}}
    .card-title{{font-size:0.9rem;font-weight:600;color:#c8d6f8;
                text-decoration:none;line-height:1.4;display:block;margin-bottom:4px}}
    .card-title:hover{{color:#fff}}
    .card-authors{{font-size:0.75rem;color:#8892b0;margin-bottom:6px}}
    .card-abstract{{font-size:0.8rem;color:#a0a8c0;line-height:1.55;margin-bottom:8px}}
    .card-links{{font-size:0.75rem;display:flex;gap:10px;align-items:center}}
    .ext{{color:#7c83d3;text-decoration:none}}
    .ext:hover{{text-decoration:underline}}
    .ris-btn{{background:#252840;border:1px solid #3d4266;color:#8892b0;
             padding:2px 8px;border-radius:4px;font-size:0.72rem;cursor:pointer}}
    .ris-btn:hover{{background:#3d4266}}
    .empty{{color:#4a5080;font-size:0.85rem;padding:12px 0}}
    .more{{font-size:0.78rem;color:#4a5080;margin-top:8px}}
    .hidden{{display:none}}
  </style>
</head>
<body>
<header>
  <h1>🫀 Cardio Lit Monitor</h1>
  <p>Weekly digest · {week} · <a class="ext" href="https://github.com/jlmthompson/cardio-lit-monitor" target="_blank">GitHub ↗</a></p>
</header>

<div class="stats-bar">
  <div class="stat"><div class="stat-n">{s['gene_papers']}</div><div class="stat-l">Gene papers</div></div>
  <div class="stat"><div class="stat-n">{s['prs_papers']}</div><div class="stat-l">PRS papers</div></div>
  <div class="stat"><div class="stat-n">{s['topic_papers']}</div><div class="stat-l">Topic papers</div></div>
  <div class="stat"><div class="stat-n">{s['new_pgs']}</div><div class="stat-l">New PGS scores</div></div>
  <div class="stat"><div class="stat-n">{s['total']}</div><div class="stat-l">Total new papers</div></div>
</div>

<div class="controls">
  <input id="search" type="text" placeholder="Filter papers…" oninput="filterCards(this.value)">
</div>

<div class="main" id="main-content">
  {gene_html}
  {prs_html}
  {topic_html}
  {pgs_html}
</div>

<script>
function filterCards(q) {{
  q = q.toLowerCase();
  document.querySelectorAll('.card').forEach(c => {{
    const text = c.textContent.toLowerCase();
    c.classList.toggle('hidden', q.length > 1 && !text.includes(q));
  }});
}}
function downloadRIS(btn) {{
  const ris   = btn.dataset.ris.replace(/\|/g, '\\n');
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
