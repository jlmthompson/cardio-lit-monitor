#!/usr/bin/env python3
"""
Sends the weekly digest as a formatted HTML email via Gmail SMTP.
Credentials passed via environment variables (GitHub Actions secrets).
"""

import json, os, smtplib
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

DIGEST = Path(__file__).parent.parent / "data" / "digest.json"
CONFIG = Path(__file__).parent.parent / "data" / "watch_config.json"

cfg    = json.loads(CONFIG.read_text())
digest = json.loads(DIGEST.read_text())
s      = digest["summary"]

GMAIL_ADDRESS  = os.environ["GMAIL_ADDRESS"]
GMAIL_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
TO_EMAIL       = cfg["settings"]["email_to"]
SITE_URL       = "https://jlmthompson.github.io/cardio-lit-monitor/"

week         = datetime.now().strftime("%d %B %Y")
selected     = digest.get("selected_papers", [])
summary_text = digest.get("summary_text", "")
total_sel    = s.get("total_selected", len(selected))

SECTION_META = {
    "disease_genetics": ("CHD / DCM / SCAD Genetics",  "#0d9488"),
    "prs_disease":      ("PRS in CHD · DCM · SCAD",    "#6366f1"),
    "prs_methods":      ("PRS & Oligogenic Methods",    "#f59e0b"),
    "topic_watch":      ("Epigenetics & Methylation",   "#64748b"),
}


def paper_row(p):
    label, colour = SECTION_META.get(p.get("section",""), ("Other", "#64748b"))
    topic = p.get("topic","").replace("_"," ")
    doi_link = f' &nbsp;·&nbsp; <a href="https://doi.org/{p["doi"]}" style="color:{colour};">DOI ↗</a>' if p.get("doi") else ""
    return f"""
  <div style="margin-bottom:16px;padding:14px;background:#f8fafc;
              border-left:4px solid {colour};border-radius:6px;">
    <div style="margin-bottom:6px;">
      <span style="font-size:11px;background:#e2e8f0;padding:2px 8px;border-radius:12px;color:#475569;">{p.get("type","")}</span>
      <span style="font-size:11px;padding:2px 8px;border-radius:12px;margin-left:4px;background:{colour}20;color:{colour};">{topic}</span>
    </div>
    <a href="{p['url']}" style="font-size:14px;font-weight:600;color:#0f172a;text-decoration:none;line-height:1.45;display:block;margin-bottom:5px;">
      {p['title'] or '(No title)'}
    </a>
    <div style="font-size:12px;color:#64748b;margin-bottom:7px;">
      {p.get('authors','')} &mdash; <em>{p.get('journal','')}</em> {p.get('year','')}
    </div>
    <div style="font-size:12px;color:#475569;line-height:1.55;margin-bottom:8px;">
      {p.get('abstract','')}
    </div>
    <a href="{p['url']}" style="font-size:12px;color:{colour};font-weight:500;">PubMed ↗</a>{doi_link}
  </div>"""


# Summary bullets for email
summary_lines = [ln.strip() for ln in summary_text.split("\n") if ln.strip()]
summary_header = summary_lines[0] if summary_lines else f"{total_sel} new papers this week"
bullets = [ln.lstrip("• ").lstrip("→ ") for ln in summary_lines[1:]
           if ln.strip() and not ln.strip().startswith("Highlight")]
highlight = next((ln for ln in summary_lines if "Highlight" in ln), "")

bullets_html = "".join(
    f'<li style="font-size:13px;color:#475569;padding:3px 0;">{b}</li>'
    for b in bullets
)

section_counts = s.get("section_counts", {})
count_items = "".join(
    f'<div style="flex:1;background:#f0fdf9;border-radius:8px;padding:12px 10px;text-align:center;">'
    f'<div style="font-size:22px;font-weight:700;color:#0d9488;">{section_counts.get(sk,0)}</div>'
    f'<div style="font-size:10px;color:#64748b;margin-top:2px;">{label.split("(")[0].strip()}</div>'
    f'</div>'
    for sk, (label, _) in SECTION_META.items()
    if section_counts.get(sk, 0) > 0
)

papers_html = "".join(paper_row(p) for p in selected)

html = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
             max-width:680px;margin:0 auto;padding:20px;color:#0f172a;background:#ffffff;">

  <!-- Header -->
  <div style="background:#162333;border-bottom:4px solid #0d9488;
              padding:24px;border-radius:10px 10px 0 0;margin-bottom:0;text-align:center;">
    <h1 style="color:#ffffff;font-size:1.5rem;margin:0 0 4px;">🫀 Cardio Lit Monitor</h1>
    <p style="color:#94a3b8;font-size:13px;margin:0;">Weekly digest &middot; {week}</p>
  </div>

  <!-- Summary -->
  <div style="background:#ffffff;border:1px solid #e2e8f0;border-top:none;
              padding:20px 24px;border-radius:0 0 10px 10px;margin-bottom:20px;">
    <h2 style="font-size:13px;font-weight:700;color:#0d9488;text-transform:uppercase;
               letter-spacing:0.04em;margin-bottom:10px;">This Week</h2>
    <p style="font-size:14px;font-weight:600;color:#1e293b;margin-bottom:8px;">{summary_header}</p>
    <ul style="list-style:none;margin-bottom:12px;">{bullets_html}</ul>
    {"<p style='font-size:12px;color:#64748b;font-style:italic;border-top:1px solid #e2e8f0;padding-top:10px;'>" + highlight + "</p>" if highlight else ""}

    <!-- Section counts -->
    <div style="display:flex;gap:10px;margin-top:14px;">{count_items}</div>

    <p style="font-size:12px;color:#94a3b8;margin-top:14px;">
      <a href="{SITE_URL}" style="color:#0d9488;font-weight:500;">View full digest online ↗</a>
      &nbsp;&middot;&nbsp; Papers from the last {digest['lookback_days']} days
    </p>
  </div>

  <!-- Papers -->
  {papers_html}

  <!-- Footer -->
  <hr style="border:none;border-top:1px solid #e2e8f0;margin:24px 0;">
  <p style="font-size:11px;color:#94a3b8;text-align:center;">
    <a href="{SITE_URL}" style="color:#0d9488;">View online</a> &middot;
    Sent to {TO_EMAIL} &middot;
    <a href="https://github.com/jlmthompson/cardio-lit-monitor" style="color:#0d9488;">cardio-lit-monitor on GitHub</a>
  </p>
</body>
</html>"""

# ── Send ──────────────────────────────────────────────────────────────────────
msg = MIMEMultipart("alternative")
msg["Subject"] = f"🫀 Cardio Lit Monitor — {total_sel} selected papers ({week})"
msg["From"]    = f"Cardio Lit Monitor <{GMAIL_ADDRESS}>"
msg["To"]      = TO_EMAIL
msg.attach(MIMEText(html, "html"))

with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
    server.login(GMAIL_ADDRESS, GMAIL_PASSWORD)
    server.sendmail(GMAIL_ADDRESS, TO_EMAIL, msg.as_string())

print(f"Email sent to {TO_EMAIL}")
