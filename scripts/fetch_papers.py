#!/usr/bin/env python3
"""
Fetches new papers from PubMed focused on:
  - Disease-level genetics (CHD, DCM, SCAD)
  - PRS specifically for those diseases
  - PRS/genetic architecture methods (oligogenic, digenic, multi-locus)
  - Epigenetic/methylation topics in CHD/DCM

Ranks by relevance and caps at max_papers_total (default 10).
Generates data/digest.json consumed by the website and email sender.
"""

import json, time, re, os
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import requests
import xml.etree.ElementTree as ET

CONFIG  = Path(__file__).parent.parent / "data" / "watch_config.json"
DIGEST  = Path(__file__).parent.parent / "data" / "digest.json"
EUTILS  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

cfg      = json.loads(CONFIG.read_text())
lookback = cfg["settings"]["lookback_days"]
max_total = cfg["settings"].get("max_papers_total", 10)
cutoff   = (datetime.now() - timedelta(days=lookback)).strftime("%Y/%m/%d")

# High-impact cardiovascular/genomics journals (bonus scoring)
HIGH_IMPACT = {
    "nature", "science", "cell", "nejm", "new england journal of medicine",
    "lancet", "jama", "nature genetics", "nature medicine", "nature communications",
    "nature cardiovascular research", "circulation", "circulation research",
    "european heart journal", "journal of the american college of cardiology",
    "american journal of human genetics", "genome research", "genome biology",
    "cell genomics", "nature human behaviour", "plos genetics",
    "human molecular genetics", "genetics in medicine", "npj genomic medicine",
    "european journal of human genetics"
}

# Keywords that boost relevance score
DISEASE_KEYWORDS = [
    "congenital heart disease", "congenital heart defect", "chd", "hlhs",
    "dilated cardiomyopathy", "dcm",
    "spontaneous coronary artery dissection", "scad"
]
METHODS_KEYWORDS = [
    "oligogenic", "digenic", "multilocus", "multi-locus",
    "genetic architecture", "polygenic", "rare variant burden",
    "whole exome sequencing", "whole genome sequencing", "gwas",
    "genome-wide association"
]


# ── PubMed helpers ────────────────────────────────────────────────────────────

def pubmed_search(query, max_results=15):
    full_query = f"({query}) AND (\"{cutoff}\"[PDAT]:\"3000\"[PDAT])"
    r = requests.get(f"{EUTILS}/esearch.fcgi", params={
        "db": "pubmed", "term": full_query,
        "retmax": max_results, "retmode": "json", "usehistory": "y"
    }, timeout=20)
    r.raise_for_status()
    data = r.json().get("esearchresult", {})
    return data.get("idlist", []), data.get("webenv"), data.get("querykey")


def pubmed_fetch(ids, webenv, querykey):
    if not ids:
        return []
    for attempt in range(3):
        try:
            r = requests.get(f"{EUTILS}/efetch.fcgi", params={
                "db": "pubmed", "webenv": webenv, "query_key": querykey,
                "rettype": "xml", "retmode": "xml", "retmax": len(ids)
            }, timeout=30)
            if r.status_code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            r.raise_for_status()
            break
        except Exception:
            if attempt == 2: return []
            time.sleep(3)
    root = ET.fromstring(r.content)
    papers = []
    for art in root.findall(".//PubmedArticle"):
        try:
            pmid  = art.findtext(".//PMID", "")
            title = art.findtext(".//ArticleTitle", "").strip()
            title = re.sub(r'<[^>]+>', '', title)
            abs_texts = art.findall(".//AbstractText")
            abstract  = " ".join(a.text or "" for a in abs_texts if a.text).strip()
            authors = []
            for a in art.findall(".//Author")[:3]:
                ln = a.findtext("LastName","")
                fn = a.findtext("ForeName","")
                if ln: authors.append(f"{ln} {fn[0] if fn else ''}".strip())
            if len(art.findall(".//Author")) > 3:
                authors.append("et al.")
            journal = art.findtext(".//Journal/Title","") or art.findtext(".//ISOAbbreviation","")
            year    = art.findtext(".//PubDate/Year","")
            month   = art.findtext(".//PubDate/Month","")
            doi     = ""
            for aid in art.findall(".//ArticleId"):
                if aid.get("IdType") == "doi":
                    doi = aid.text or ""
            papers.append({
                "pmid":     pmid,
                "title":    title,
                "abstract": abstract[:500] + ("…" if len(abstract) > 500 else ""),
                "abstract_full": abstract,
                "authors":  ", ".join(authors),
                "journal":  journal,
                "year":     year,
                "month":    month,
                "doi":      doi,
                "url":      f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "ris":      make_ris(pmid, title, authors, journal, year, doi, abstract),
            })
        except Exception:
            pass
    return papers


def make_ris(pmid, title, authors, journal, year, doi, abstract):
    lines = ["TY  - JOUR"]
    for a in (a for a in authors if a != "et al."):
        lines.append(f"AU  - {a}")
    lines += [
        f"TI  - {title}",
        f"JO  - {journal}",
        f"PY  - {year}",
        f"DO  - {doi}",
        f"AB  - {abstract[:300]}",
        f"UR  - https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        "ER  - "
    ]
    return "\n".join(lines)


def classify_paper(title, abstract):
    text = (title + " " + abstract).lower()
    if any(w in text for w in ["review", "meta-analysis", "systematic review"]):
        return "Review"
    if any(w in text for w in ["genome-wide association", "gwas"]):
        return "GWAS"
    if any(w in text for w in ["polygenic risk", "polygenic score", "prs", "pgs"]):
        return "PRS"
    if any(w in text for w in ["whole exome", "whole genome sequencing", "wgs", "wes"]):
        return "Sequencing study"
    if any(w in text for w in ["oligogenic", "digenic", "multilocus", "multi-locus"]):
        return "Methods"
    if any(w in text for w in ["methylation", "epigenetic", "histone", "chromatin"]):
        return "Epigenetics"
    if any(w in text for w in ["case report", "case series"]):
        return "Case report"
    if any(w in text for w in ["mouse", "zebrafish", "cell line", "in vitro", "functional"]):
        return "Functional study"
    return "Research article"


def relevance_score(paper, section_key):
    """Score 0-10: higher = more relevant to keep."""
    text = (paper["title"] + " " + paper.get("abstract_full", "")).lower()
    score = 0
    # Journal impact
    journal_lower = paper.get("journal", "").lower()
    if any(j in journal_lower for j in HIGH_IMPACT):
        score += 3
    # Disease keyword match in title (strong signal)
    title_lower = paper["title"].lower()
    for kw in DISEASE_KEYWORDS:
        if kw in title_lower:
            score += 2
            break
    # Disease keyword in abstract
    for kw in DISEASE_KEYWORDS:
        if kw in text:
            score += 1
            break
    # Methods keywords (especially for prs_methods section)
    if "prs_methods" in section_key or "oligogenic" in section_key.lower():
        for kw in METHODS_KEYWORDS:
            if kw in text:
                score += 2
                break
    # Human study bonus (penalise pure animal studies)
    if any(w in text for w in ["patients", "cohort", "participants", "individuals", "proband", "families"]):
        score += 1
    if any(w in text for w in ["mouse model", "zebrafish", "in vitro", "cell line"]) and \
       not any(w in text for w in ["patients", "cohort", "participants"]):
        score -= 2
    return score


# ── Main ──────────────────────────────────────────────────────────────────────

def fetch_section(section_name, section_cfg, seen_pmids):
    """Fetch papers for a named section group. Returns flat list with section tag."""
    all_papers = []
    for topic_name, topic in section_cfg.items():
        for query in topic["queries"]:
            try:
                ids, wh, qk = pubmed_search(query)
                ids = [i for i in ids if i not in seen_pmids]
                if ids:
                    papers = pubmed_fetch(ids, wh, qk)
                    for p in papers:
                        p["section"] = section_name
                        p["topic"]   = topic_name
                        p["type"]    = classify_paper(p["title"], p.get("abstract_full",""))
                        p["score"]   = relevance_score(p, f"{section_name}_{topic_name}")
                        seen_pmids.add(p["pmid"])
                    all_papers.extend(papers)
                time.sleep(0.35)
            except Exception as e:
                print(f"  Error on '{query}': {e}")
    # Deduplicate within section by PMID
    seen = set()
    unique = []
    for p in all_papers:
        if p["pmid"] not in seen:
            unique.append(p)
            seen.add(p["pmid"])
    # Sort by score desc
    unique.sort(key=lambda x: x["score"], reverse=True)
    return unique


def generate_summary(selected_papers, section_counts):
    """Generate a plain-English top-line summary."""
    lines = []
    total = len(selected_papers)
    if total == 0:
        return "No new papers matching your focus areas this week."
    lines.append(f"{total} paper{'s' if total != 1 else ''} selected from this week's literature:")
    for section, count in section_counts.items():
        if count > 0:
            label = {
                "disease_genetics": "disease genetics (CHD / DCM / SCAD)",
                "prs_disease": "PRS in CHD/DCM/SCAD",
                "prs_methods": "PRS & oligogenic methods",
                "topic_watch": "epigenetics / methylation"
            }.get(section, section)
            lines.append(f"  • {count} × {label}")
    if selected_papers:
        top = selected_papers[0]
        lines.append(f"\nHighlight: {top['title']} ({top['journal']}, {top['year']})")
    return "\n".join(lines)


def main():
    digest = {
        "generated": datetime.now().isoformat(),
        "lookback_days": lookback,
        "cutoff_date": cutoff,
        "sections": {}
    }

    seen_pmids = set()
    all_candidates = []   # (section_key, paper)

    section_groups = [
        ("disease_genetics", cfg.get("disease_genetics", {})),
        ("prs_disease",      cfg.get("prs_disease", {})),
        ("prs_methods",      cfg.get("prs_methods", {})),
        ("topic_watch",      cfg.get("topic_watch", {})),
    ]

    for section_key, section_cfg in section_groups:
        if not section_cfg:
            continue
        print(f"Fetching {section_key}...")
        papers = fetch_section(section_key, section_cfg, seen_pmids)
        digest["sections"][section_key] = {
            "papers": papers,
            "total": len(papers)
        }
        for p in papers:
            all_candidates.append((section_key, p))
        print(f"  → {len(papers)} unique papers found")

    # ── Global ranking: pick top max_total papers across all sections ──
    # Sort all candidates by score desc; break ties by section priority
    section_priority = {
        "disease_genetics": 4,
        "prs_disease":      3,
        "prs_methods":      3,
        "topic_watch":      2,
    }
    all_candidates.sort(
        key=lambda x: (x[1]["score"], section_priority.get(x[0], 1)),
        reverse=True
    )
    # Ensure we don't exceed max_total; also try to have at least 1 from each section
    selected = []
    seen_selected = set()
    # First pass: one from each section
    section_done = set()
    for sk, p in all_candidates:
        if sk not in section_done and p["pmid"] not in seen_selected:
            selected.append(p)
            seen_selected.add(p["pmid"])
            section_done.add(sk)
    # Second pass: fill up to max_total by score
    for sk, p in all_candidates:
        if len(selected) >= max_total:
            break
        if p["pmid"] not in seen_selected:
            selected.append(p)
            seen_selected.add(p["pmid"])
    # Final sort by score
    selected.sort(key=lambda x: x["score"], reverse=True)

    # Count per section
    section_counts = defaultdict(int)
    for p in selected:
        section_counts[p["section"]] += 1

    summary_text = generate_summary(selected, dict(section_counts))
    digest["selected_papers"] = selected
    digest["summary_text"] = summary_text
    digest["summary"] = {
        "total_selected": len(selected),
        "total_candidates": len(all_candidates),
        "section_counts": dict(section_counts),
    }

    DIGEST.write_text(json.dumps(digest, indent=2))
    print(f"\nDone. {len(selected)} papers selected (from {len(all_candidates)} candidates).")
    print(f"Saved → {DIGEST}")
    print(f"\nSummary:\n{summary_text}")


if __name__ == "__main__":
    main()
