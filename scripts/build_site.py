#!/usr/bin/env python3
"""
Generates docs/index.html from the current digest.json.

Theme: "The Cardio Lit Review" — an editorial / science-journal aesthetic.
Warm paper background, Newsreader serif masthead, oxblood accent, numbered
entries separated by hairline rules (no generic cards).
"""

import json
from pathlib import Path
from datetime import datetime

DIGEST = Path(__file__).parent.parent / "data" / "digest.json"
OUT    = Path(__file__).parent.parent / "docs" / "index.html"
OUT.parent.mkdir(exist_ok=True)

digest = json.loads(DIGEST.read_text())
gen_dt = datetime.fromisoformat(digest["generated"])
week   = gen_dt.strftime("%d %B %Y")
summary_text = digest.get("summary_text", "")
selected     = digest.get("selected_papers", [])
total_sel    = digest["summary"].get("total_selected", len(selected))
total_cand   = digest["summary"].get("total_candidates", 0)
scoring      = digest.get("scoring", "heuristic")

# Section label + muted editorial accent colour
SECTION_META = {
    "disease_genetics": ("Disease Genetics",      "#7c2d3a"),  # oxblood
    "prs_disease":      ("PRS in Disease",        "#3f4a6b"),  # indigo ink
    "prs_methods":      ("PRS & Architecture",    "#8a5a23"),  # ochre
    "topic_watch":      ("Epigenetics & Omics",   "#46695e"),  # pine
}


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def entry(p, idx):
    section = p.get("section", "")
    label, accent = SECTION_META.get(section, ("Research", "#4a4540"))
    num = f"{idx:02d}"

    is_pre = p.get("is_preprint")
    ptype = p.get("type", "")
    # type already carries "Preprint · X"; show server name as the preprint flag
    pre_flag = (f'<span class="flag-pre">{esc(p.get("journal",""))}</span>'
                if is_pre else "")

    bullets = p.get("bullets", [])
    if bullets:
        findings = "".join(f"<li>{esc(b)}</li>" for b in bullets)
        content = f'<ul class="findings">{findings}</ul>'
    else:
        content = f'<p class="abstract">{esc(p.get("abstract",""))}</p>'

    note = p.get("relevance_note", "")
    if note:
        content += f'<p class="note">{esc(note)}</p>'

    doi_link = (f'<a class="link" href="https://doi.org/{esc(p["doi"])}" '
                f'target="_blank" rel="noopener">DOI</a>' if p.get("doi") else "")
    ris_safe = p.get("ris", "").replace(chr(10), "|").replace(chr(13), "").replace('"', "&quot;")

    delay = round(idx * 0.035, 3)
    return f"""
<article class="entry" data-section="{section}" style="animation-delay:{delay}s">
  <div class="entry-rail">
    <span class="entry-num">{num}</span>
    <span class="entry-section" style="--accent:{accent}">{esc(label)}</span>
  </div>
  <div class="entry-body">
    <div class="entry-kicker">
      <span class="ptype">{esc(ptype)}</span>{pre_flag}
    </div>
    <a class="entry-title" href="{esc(p['url'])}" target="_blank" rel="noopener">{esc(p['title']) or '(Untitled)'}</a>
    <div class="byline">{esc(p.get('authors',''))} &middot; <em>{esc(p.get('journal',''))}</em> &middot; {esc(p.get('year',''))}</div>
    {content}
    <div class="entry-links">
      <a class="link" href="{esc(p['url'])}" target="_blank" rel="noopener">PubMed</a>
      {doi_link}
      <button class="link ris" onclick="downloadRIS(this)" data-ris="{ris_safe}" data-id="{esc(p.get('pmid') or num)}">Cite ↓</button>
    </div>
  </div>
</article>"""


# ── Legend (sections present in the selection) ──
legend_html = ""
for sk, (label, accent) in SECTION_META.items():
    count = sum(1 for p in selected if p.get("section") == sk)
    if count:
        legend_html += (f'<span class="leg"><span class="leg-dot" style="background:{accent}"></span>'
                        f'{label}<span class="leg-n">{count}</span></span>')

# ── Standfirst (parse the summary text) ──
summary_lines  = [ln.strip() for ln in summary_text.split("\n") if ln.strip()]
summary_header = summary_lines[0] if summary_lines else f"{total_sel} papers this week"
highlight      = next((ln for ln in summary_lines if ln.startswith("Highlight")), "")
bullets        = [ln.lstrip("• ").strip() for ln in summary_lines[1:]
                  if ln and not ln.startswith("Highlight")]
stand_bullets  = "".join(f"<li>{esc(b)}</li>" for b in bullets)
highlight_html = (f'<p class="highlight"><span>Editor’s pick</span>{esc(highlight.replace("Highlight:", "").strip())}</p>'
                  if highlight else "")

entries_html = "".join(entry(p, i + 1) for i, p in enumerate(selected))
if not selected:
    entries_html = ('<div class="empty"><em>No new papers matched your focus areas this period.</em>'
                    '<br>The press rests until next Monday.</div>')

scoring_label = "AI-ranked" if scoring == "llm" else "keyword-screened"

OUT.write_text(f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>The Cardio Lit Review · {week}</title>
  <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' fill='%23faf7f2'/%3E%3Ctext x='16' y='23' font-family='Georgia,serif' font-size='22' font-style='italic' text-anchor='middle' fill='%237c2d3a'%3ER%3C/text%3E%3C/svg%3E">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Newsreader:ital,wght@0,400;0,500;0,600;1,400;1,500&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {{
      --paper:#faf7f2; --paper-warm:#f3ede1; --ink:#1c1a17; --ink-soft:#4a4540;
      --ink-faint:#8a8175; --hairline:#e3dacd; --hairline-soft:#ece4d6;
      --oxblood:#7c2d3a; --oxblood-deep:#5e1f29;
    }}
    *,*::before,*::after {{ box-sizing:border-box; margin:0; padding:0; }}

    html {{ scroll-behavior:smooth; }}
    body {{
      background:
        radial-gradient(120% 80% at 50% -10%, #fffdf9 0%, var(--paper) 55%) fixed,
        var(--paper);
      color:var(--ink);
      font-family:'IBM Plex Sans', system-ui, sans-serif;
      line-height:1.6;
      -webkit-font-smoothing:antialiased;
      padding:0 22px;
    }}
    /* subtle paper grain */
    body::before {{
      content:""; position:fixed; inset:0; pointer-events:none; z-index:0;
      opacity:0.035;
      background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='2'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
    }}
    .wrap {{ max-width:780px; margin:0 auto; position:relative; z-index:1; }}

    /* ── Masthead ── */
    .masthead {{ text-align:center; padding:54px 0 26px; }}
    .eyebrow {{
      font-family:'IBM Plex Mono', monospace; font-size:0.66rem; letter-spacing:0.32em;
      text-transform:uppercase; color:var(--oxblood); margin-bottom:18px;
    }}
    .masthead h1 {{
      font-family:'Newsreader', serif; font-weight:500; font-size:clamp(2.6rem,7vw,4rem);
      letter-spacing:-0.015em; line-height:0.98; color:var(--ink);
    }}
    .masthead h1 em {{ font-style:italic; color:var(--oxblood); }}
    .rule {{ border:none; border-top:1.5px solid var(--ink); margin:22px 0 5px; }}
    .rule.thin {{ border-top:0.5px solid var(--ink); margin:0 0 0; }}
    .dateline {{
      display:flex; justify-content:space-between; align-items:center;
      font-family:'IBM Plex Mono', monospace; font-size:0.7rem; letter-spacing:0.08em;
      text-transform:uppercase; color:var(--ink-soft); padding:9px 2px 0;
    }}
    .dateline .mid {{ color:var(--ink-faint); }}

    /* ── Standfirst ── */
    .standfirst {{
      margin:34px 0 10px; padding:4px 0 4px 22px; border-left:2px solid var(--oxblood);
    }}
    .standfirst h2 {{
      font-family:'Newsreader', serif; font-weight:500; font-size:1.32rem;
      line-height:1.35; color:var(--ink); margin-bottom:12px;
    }}
    .standfirst ul {{ list-style:none; display:flex; flex-wrap:wrap; gap:6px 20px; }}
    .standfirst li {{
      font-size:0.86rem; color:var(--ink-soft); position:relative; padding-left:14px;
    }}
    .standfirst li::before {{ content:"—"; position:absolute; left:0; color:var(--oxblood); }}
    .highlight {{
      margin-top:16px; font-family:'Newsreader', serif; font-style:italic;
      font-size:0.98rem; color:var(--ink-soft); line-height:1.5;
    }}
    .highlight span {{
      display:inline-block; font-family:'IBM Plex Mono', monospace; font-style:normal;
      font-size:0.6rem; letter-spacing:0.18em; text-transform:uppercase;
      color:var(--oxblood); margin-right:9px; vertical-align:middle;
    }}

    /* ── Controls / legend ── */
    .meta-bar {{
      display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between;
      gap:14px; margin:30px 0 8px; padding-bottom:14px;
      border-bottom:0.5px solid var(--ink);
    }}
    .legend {{ display:flex; flex-wrap:wrap; gap:5px 16px; }}
    .leg {{
      display:inline-flex; align-items:center; gap:7px;
      font-size:0.74rem; color:var(--ink-soft);
    }}
    .leg-dot {{ width:8px; height:8px; border-radius:50%; }}
    .leg-n {{ font-family:'IBM Plex Mono', monospace; font-size:0.66rem; color:var(--ink-faint); }}
    .search-wrap {{ position:relative; }}
    #search {{
      font-family:'IBM Plex Sans', sans-serif; font-size:0.8rem; color:var(--ink);
      background:transparent; border:none; border-bottom:1px solid var(--hairline);
      padding:5px 4px 5px 20px; width:170px; transition:border-color .2s, width .2s;
    }}
    #search:focus {{ outline:none; border-color:var(--oxblood); width:210px; }}
    #search::placeholder {{ color:var(--ink-faint); }}
    .search-wrap::before {{
      content:"⌕"; position:absolute; left:0; top:3px; color:var(--ink-faint); font-size:1rem;
    }}

    /* ── Entries ── */
    .entries {{ margin:8px 0 0; }}
    .entry {{
      display:grid; grid-template-columns:108px 1fr; gap:24px;
      padding:30px 0; border-bottom:0.5px solid var(--hairline);
      opacity:0; transform:translateY(14px);
      animation:rise .6s cubic-bezier(.2,.7,.2,1) forwards;
    }}
    @keyframes rise {{ to {{ opacity:1; transform:none; }} }}
    .entry-rail {{ text-align:right; padding-top:3px; }}
    .entry-num {{
      display:block; font-family:'Newsreader', serif; font-size:1.6rem;
      color:var(--ink-faint); line-height:1; font-weight:400;
    }}
    .entry-section {{
      display:inline-block; margin-top:10px;
      font-family:'IBM Plex Mono', monospace; font-size:0.6rem; letter-spacing:0.13em;
      text-transform:uppercase; color:var(--accent);
      border-top:2px solid var(--accent); padding-top:6px;
    }}
    .entry-kicker {{
      display:flex; flex-wrap:wrap; align-items:center; gap:10px; margin-bottom:9px;
      font-family:'IBM Plex Mono', monospace; font-size:0.62rem; letter-spacing:0.1em;
      text-transform:uppercase; color:var(--ink-faint);
    }}
    .flag-pre {{
      color:var(--oxblood); border:0.5px solid var(--oxblood); border-radius:2px;
      padding:1px 6px; letter-spacing:0.08em;
    }}
    .entry-title {{
      display:block; font-family:'Newsreader', serif; font-weight:500;
      font-size:1.42rem; line-height:1.24; color:var(--ink); text-decoration:none;
      letter-spacing:-0.01em; transition:color .15s;
    }}
    .entry-title:hover {{ color:var(--oxblood); }}
    .byline {{
      font-size:0.78rem; color:var(--ink-faint); margin:8px 0 12px; font-style:normal;
    }}
    .byline em {{ color:var(--ink-soft); font-style:italic; }}
    .findings {{ list-style:none; margin-bottom:13px; }}
    .findings li {{
      font-size:0.9rem; color:var(--ink-soft); line-height:1.62;
      padding:2px 0 2px 18px; position:relative;
    }}
    .findings li::before {{
      content:""; position:absolute; left:0; top:12px; width:7px; height:1px;
      background:var(--oxblood);
    }}
    .abstract {{ font-size:0.88rem; color:var(--ink-soft); margin-bottom:13px; }}
    .note {{
      font-family:'Newsreader', serif; font-style:italic; font-size:0.85rem;
      color:var(--ink-faint); margin-bottom:13px;
    }}
    .entry-links {{ display:flex; gap:18px; align-items:center; }}
    .link {{
      font-family:'IBM Plex Mono', monospace; font-size:0.68rem; letter-spacing:0.05em;
      text-transform:uppercase; color:var(--ink-soft); text-decoration:none;
      background:none; border:none; cursor:pointer; padding:0; position:relative;
    }}
    .link::after {{
      content:""; position:absolute; left:0; bottom:-3px; width:100%; height:1px;
      background:var(--oxblood); transform:scaleX(0); transform-origin:left;
      transition:transform .22s;
    }}
    .link:hover {{ color:var(--oxblood); }}
    .link:hover::after {{ transform:scaleX(1); }}

    .empty {{
      text-align:center; padding:70px 20px; color:var(--ink-faint);
      font-family:'Newsreader', serif; font-size:1.1rem; line-height:1.8;
    }}
    .hidden {{ display:none !important; }}

    /* ── Footer ── */
    footer {{
      margin:30px 0 60px; padding-top:20px; border-top:1.5px solid var(--ink);
      text-align:center;
      font-family:'IBM Plex Mono', monospace; font-size:0.66rem; letter-spacing:0.08em;
      text-transform:uppercase; color:var(--ink-faint); line-height:2;
    }}
    footer a {{ color:var(--oxblood); text-decoration:none; }}
    footer a:hover {{ text-decoration:underline; }}

    @media (max-width:560px) {{
      .entry {{ grid-template-columns:1fr; gap:10px; }}
      .entry-rail {{ text-align:left; display:flex; align-items:baseline; gap:14px; }}
      .entry-section {{ margin-top:0; border-top:none; padding-top:0; }}
      .dateline {{ font-size:0.6rem; }}
    }}
  </style>
</head>
<body>
<div class="wrap">

  <header class="masthead">
    <div class="eyebrow">Cardiovascular Genomics — Weekly Surveillance</div>
    <h1>The Cardio Lit <em>Review</em></h1>
    <hr class="rule">
    <hr class="rule thin">
    <div class="dateline">
      <span>{week}</span>
      <span class="mid">Curated from PubMed &amp; preprints</span>
      <span>{total_sel} of {total_cand} screened</span>
    </div>
  </header>

  <section class="standfirst">
    <h2>{esc(summary_header)}</h2>
    <ul>{stand_bullets}</ul>
    {highlight_html}
  </section>

  <div class="meta-bar">
    <div class="legend">{legend_html}</div>
    <div class="search-wrap">
      <input id="search" type="text" placeholder="Search the issue…" oninput="filterEntries(this.value)">
    </div>
  </div>

  <main class="entries" id="entries">
    {entries_html}
  </main>

  <footer>
    The Cardio Lit Review · {scoring_label} · Refreshed every Monday<br>
    <a href="https://github.com/jlmthompson/cardio-lit-monitor" target="_blank" rel="noopener">Source on GitHub</a>
  </footer>

</div>

<script>
function filterEntries(q) {{
  q = q.toLowerCase().trim();
  document.querySelectorAll('.entry').forEach(e => {{
    const hide = q.length > 1 && !e.textContent.toLowerCase().includes(q);
    e.classList.toggle('hidden', hide);
  }});
}}
function downloadRIS(btn) {{
  const ris   = btn.dataset.ris.replace(/\\|/g, '\\n');
  const fname = 'cardio_lit_' + btn.dataset.id + '.ris';
  const blob  = new Blob([ris], {{type:'application/x-research-info-systems'}});
  const a = Object.assign(document.createElement('a'), {{
    href:URL.createObjectURL(blob), download:fname
  }});
  a.click();
}}
</script>
</body>
</html>""")

print(f"Site built → {OUT}")
