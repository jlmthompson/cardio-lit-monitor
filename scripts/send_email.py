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

week = datetime.now().strftime("%d %B %Y")


def section_html(title, icon, colour, papers, key_field="title"):
    if not papers:
        return ""
    html = f"""
    <div style="margin-bottom:28px;">
      <h2 style="font-size:16px;font-weight:700;color:{colour};
                 border-bottom:2px solid {colour};padding-bottom:6px;margin-bottom:14px;">
        {icon} {title}
      </h2>"""
    for p in papers[:8]:
        ptype = p.get("type","")
        html += f"""
      <div style="margin-bottom:14px;padding:12px;background:#f9f9f9;
                  border-left:3px solid {colour};border-radius:4px;">
        <div style="margin-bottom:4px;">
          <span style="font-size:11px;background:#e8e8e8;padding:2px 7px;
                       border-radius:10px;color:#555;">{ptype}</span>
          {"<span style='font-size:11px;background:#ffeaa7;padding:2px 7px;border-radius:10px;color:#555;margin-left:4px;'>" + p.get('gene','') + "</span>" if p.get('gene') else ""}
        </div>
        <a href="{p['url']}" style="font-size:14px;font-weight:600;color:#1a1a2e;
                                    text-decoration:none;line-height:1.4;">
          {p['title']}
        </a>
        <div style="font-size:12px;color:#666;margin-top:4px;">
          {p.get('authors','')} · <em>{p.get('journal','')}</em> {p.get('year','')}
        </div>
        <div style="font-size:12px;color:#444;margin-top:6px;line-height:1.5;">
          {p.get('abstract','')}
        </div>
        <div style="margin-top:6px;">
          <a href="{p['url']}" style="font-size:12px;color:#3498db;">PubMed ↗</a>
          {"&nbsp;·&nbsp;<a href='https://doi.org/" + p['doi'] + "' style='font-size:12px;color:#3498db;'>DOI ↗</a>" if p.get('doi') else ""}
        </div>
      </div>"""
    if len(papers) > 8:
        html += f"<p style='font-size:12px;color:#888;'>+ {len(papers)-8} more — <a href='{SITE_URL}'>view all on site</a></p>"
    html += "</div>"
    return html


# ── Build HTML email ──────────────────────────────────────────────────────────
html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
             max-width:680px;margin:0 auto;padding:20px;color:#1a1a2e;">

  <div style="background:linear-gradient(135deg,#1a1d2e,#2d3154);
              padding:24px;border-radius:8px;margin-bottom:24px;text-align:center;">
    <h1 style="color:#fff;font-size:20px;margin:0 0 6px;">
      🫀 Cardio Lit Monitor
    </h1>
    <p style="color:#8892b0;font-size:13px;margin:0;">
      Weekly digest · {week}
    </p>
  </div>

  <!-- Summary strip -->
  <div style="display:flex;gap:12px;margin-bottom:24px;text-align:center;">
    {"".join(f'''<div style="flex:1;background:#f0f4ff;border-radius:6px;padding:12px;">
      <div style="font-size:22px;font-weight:700;color:#3d4266;">{n}</div>
      <div style="font-size:11px;color:#666;">{label}</div>
    </div>''' for n, label in [
        (s['gene_papers'], 'Gene papers'),
        (s['prs_papers'],  'PRS papers'),
        (s['topic_papers'],'Topic papers'),
        (s['new_pgs'],     'New PGS scores'),
    ])}
  </div>

  <p style="font-size:13px;color:#666;margin-bottom:24px;">
    Papers published in the last {digest['lookback_days']} days.
    <a href="{SITE_URL}" style="color:#3498db;">View full digest online ↗</a>
  </p>
"""

# Gene watch — flatten to a single list sorted by gene
gene_papers = []
for list_name, gl in digest["sections"]["gene_watch"].items():
    for gene, papers in gl["results"].items():
        gene_papers.extend(papers)
html += section_html("Gene Watch", "🔴", "#e74c3c", gene_papers)

# PRS watch — per topic
prs_colours = {
    "CHD_PRS": "#e74c3c", "DCM_PRS": "#e67e22",
    "Cardiovascular_PRS": "#e74c3c", "NDD_PRS": "#3498db", "Cardiometabolic_PRS": "#e67e22"
}
prs_all = []
for topic, data in digest["sections"]["prs_watch"].items():
    prs_all.extend(data["papers"])
html += section_html("PRS Watch", "💙", "#3498db", prs_all)

# Topic watch
topic_all = []
for topic, data in digest["sections"]["topic_watch"].items():
    topic_all.extend(data["papers"])
html += section_html("Topic Watch", "🟢", "#27ae60", topic_all)

# PGS Catalog new scores
pgs = digest["sections"].get("pgs_new_scores", [])
if pgs:
    html += """<div style="margin-bottom:28px;">
      <h2 style="font-size:16px;font-weight:700;color:#9b59b6;
                 border-bottom:2px solid #9b59b6;padding-bottom:6px;margin-bottom:14px;">
        🆕 New PGS Catalog Scores
      </h2>"""
    for sc in pgs:
        html += f"""
      <div style="margin-bottom:10px;padding:10px;background:#f9f0ff;
                  border-left:3px solid #9b59b6;border-radius:4px;">
        <a href="{sc['url']}" style="font-size:13px;font-weight:600;color:#1a1a2e;">{sc['pgs_id']}: {sc['name']}</a>
        <div style="font-size:12px;color:#666;">Trait: {sc['trait']} · {sc['variants']:,} variants · Added {sc['date']}</div>
      </div>"""
    html += "</div>"

html += f"""
  <hr style="border:none;border-top:1px solid #eee;margin:24px 0;">
  <p style="font-size:11px;color:#aaa;text-align:center;">
    <a href="{SITE_URL}" style="color:#3498db;">View online</a> ·
    Sent to {TO_EMAIL} · Generated by
    <a href="https://github.com/jlmthompson/cardio-lit-monitor" style="color:#3498db;">cardio-lit-monitor</a>
  </p>
</body>
</html>
"""

# ── Send ──────────────────────────────────────────────────────────────────────
msg = MIMEMultipart("alternative")
msg["Subject"] = f"🫀 Cardio Lit Monitor — {s['total']} new papers ({week})"
msg["From"]    = f"Cardio Lit Monitor <{GMAIL_ADDRESS}>"
msg["To"]      = TO_EMAIL
msg.attach(MIMEText(html, "html"))

with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
    server.login(GMAIL_ADDRESS, GMAIL_PASSWORD)
    server.sendmail(GMAIL_ADDRESS, TO_EMAIL, msg.as_string())

print(f"Email sent to {TO_EMAIL}")
