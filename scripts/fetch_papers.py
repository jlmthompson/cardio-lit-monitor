#!/usr/bin/env python3
"""
Fetches new papers from PubMed and PGS Catalog.
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
PGSC    = "https://www.pgscatalog.org/rest"

cfg      = json.loads(CONFIG.read_text())
lookback = cfg["settings"]["lookback_days"]
cutoff   = (datetime.now() - timedelta(days=lookback)).strftime("%Y/%m/%d")


# ── PubMed helpers ────────────────────────────────────────────────────────────

def pubmed_search(query, max_results=20):
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
    r = requests.get(f"{EUTILS}/efetch.fcgi", params={
        "db": "pubmed", "webenv": webenv, "query_key": querykey,
        "rettype": "xml", "retmode": "xml", "retmax": len(ids)
    }, timeout=30)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    papers = []
    for art in root.findall(".//PubmedArticle"):
        try:
            pmid  = art.findtext(".//PMID", "")
            title = art.findtext(".//ArticleTitle", "").strip()
            # Remove XML tags from title
            title = re.sub(r'<[^>]+>', '', title)
            # Abstract
            abs_texts = art.findall(".//AbstractText")
            abstract  = " ".join(a.text or "" for a in abs_texts if a.text).strip()
            # Authors
            authors = []
            for a in art.findall(".//Author")[:3]:
                ln = a.findtext("LastName","")
                fn = a.findtext("ForeName","")
                if ln: authors.append(f"{ln} {fn[0] if fn else ''}".strip())
            if len(art.findall(".//Author")) > 3:
                authors.append("et al.")
            # Journal & date
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
                "abstract": abstract[:400] + ("…" if len(abstract) > 400 else ""),
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
    """Classify paper type from title/abstract."""
    text = (title + " " + abstract).lower()
    if any(w in text for w in ["review", "meta-analysis", "systematic review"]):
        return "Review"
    if any(w in text for w in ["genome-wide association", "gwas"]):
        return "GWAS"
    if any(w in text for w in ["polygenic risk", "polygenic score", "prs", "pgs"]):
        return "PRS"
    if any(w in text for w in ["case report", "case series", "proband"]):
        return "Case report"
    if any(w in text for w in ["mouse", "zebrafish", "cell line", "in vitro", "functional"]):
        return "Functional study"
    if any(w in text for w in ["methylation", "epigenetic", "histone"]):
        return "Epigenetics"
    if any(w in text for w in ["variant", "mutation", "pathogenic", "sequence"]):
        return "Variant report"
    return "Research article"


# ── PGS Catalog ──────────────────────────────────────────────────────────────

def fetch_new_pgs_scores():
    """Check PGS Catalog for recently added scores in cardiac/NDD traits."""
    traits = ["congenital heart disease", "cardiomyopathy", "dilated cardiomyopathy",
              "atrial fibrillation", "coronary artery disease", "ADHD", "autism"]
    new_scores = []
    for trait in traits:
        try:
            r = requests.get(f"{PGSC}/score/search/", params={"trait_name": trait, "limit": 5}, timeout=15)
            if r.status_code != 200:
                continue
            for s in r.json().get("results", []):
                pub_date = s.get("date_released","")
                if pub_date and pub_date >= (datetime.now() - timedelta(days=lookback*4)).strftime("%Y-%m-%d"):
                    new_scores.append({
                        "pgs_id":      s.get("id",""),
                        "name":        s.get("name",""),
                        "trait":       trait,
                        "variants":    s.get("variants_number",0),
                        "date":        pub_date,
                        "url":         f"https://www.pgscatalog.org/score/{s.get('id','')}/"
                    })
            time.sleep(0.5)
        except Exception:
            pass
    return new_scores


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    digest = {
        "generated": datetime.now().isoformat(),
        "lookback_days": lookback,
        "cutoff_date": cutoff,
        "sections": {}
    }

    seen_pmids = set()

    # ── Gene Watch ──
    print("Fetching Gene Watch papers...")
    gene_section = {}
    for list_name, gl in cfg["gene_lists"].items():
        list_results = defaultdict(list)
        genes = gl["genes"]
        for gene in genes:
            query = f"{gene}[Gene] AND (cardiac OR heart OR neurodevelopmental OR congenital OR NDD OR autism OR ADHD)"
            try:
                ids, wh, qk = pubmed_search(query, max_results=5)
                ids = [i for i in ids if i not in seen_pmids]
                if ids:
                    papers = pubmed_fetch(ids, wh, qk)
                    for p in papers:
                        p["gene"]  = gene
                        p["type"]  = classify_paper(p["title"], p["abstract"])
                        seen_pmids.add(p["pmid"])
                    list_results[gene].extend(papers)
                time.sleep(0.35)
            except Exception as e:
                print(f"  Error fetching {gene}: {e}")
        gene_section[list_name] = {
            "description": gl["description"],
            "results": dict(list_results),
            "total": sum(len(v) for v in list_results.values())
        }
    digest["sections"]["gene_watch"] = gene_section

    # ── PRS Topics ──
    print("Fetching PRS Watch papers...")
    prs_section = {}
    for topic_name, topic in cfg["prs_topics"].items():
        topic_papers = []
        for query in topic["queries"]:
            try:
                ids, wh, qk = pubmed_search(query, max_results=10)
                ids = [i for i in ids if i not in seen_pmids]
                if ids:
                    papers = pubmed_fetch(ids, wh, qk)
                    for p in papers:
                        p["query"] = query
                        p["type"]  = classify_paper(p["title"], p["abstract"])
                        seen_pmids.add(p["pmid"])
                    topic_papers.extend(papers)
                time.sleep(0.35)
            except Exception as e:
                print(f"  Error on '{query}': {e}")
        # Deduplicate within topic
        seen_in_topic = set()
        unique_papers = []
        for p in topic_papers:
            if p["pmid"] not in seen_in_topic:
                unique_papers.append(p)
                seen_in_topic.add(p["pmid"])
        prs_section[topic_name] = {
            "description": topic["description"],
            "papers": unique_papers,
            "total": len(unique_papers)
        }
    digest["sections"]["prs_watch"] = prs_section

    # ── Topic Watch ──
    print("Fetching Topic Watch papers...")
    topic_section = {}
    for topic_name, topic in cfg["topic_watch"].items():
        topic_papers = []
        for query in topic["queries"]:
            try:
                ids, wh, qk = pubmed_search(query, max_results=10)
                ids = [i for i in ids if i not in seen_pmids]
                if ids:
                    papers = pubmed_fetch(ids, wh, qk)
                    for p in papers:
                        p["query"] = query
                        p["type"]  = classify_paper(p["title"], p["abstract"])
                        seen_pmids.add(p["pmid"])
                    topic_papers.extend(papers)
                time.sleep(0.35)
            except Exception as e:
                print(f"  Error on '{query}': {e}")
        seen_in_topic = set()
        unique = []
        for p in topic_papers:
            if p["pmid"] not in seen_in_topic:
                unique.append(p)
                seen_in_topic.add(p["pmid"])
        topic_section[topic_name] = {
            "description": topic.get("description", topic_name),
            "papers": unique,
            "total": len(unique)
        }
    digest["sections"]["topic_watch"] = topic_section

    # ── PGS Catalog ──
    print("Checking PGS Catalog for new scores...")
    digest["sections"]["pgs_new_scores"] = fetch_new_pgs_scores()

    # ── Summary ──
    total = sum(
        sum(gl["total"] for gl in digest["sections"]["gene_watch"].values()),
        # prs
    )
    gene_total  = sum(s["total"] for s in digest["sections"]["gene_watch"].values())
    prs_total   = sum(s["total"] for s in digest["sections"]["prs_watch"].values())
    topic_total = sum(s["total"] for s in digest["sections"]["topic_watch"].values())
    digest["summary"] = {
        "gene_papers":  gene_total,
        "prs_papers":   prs_total,
        "topic_papers": topic_total,
        "new_pgs":      len(digest["sections"]["pgs_new_scores"]),
        "total":        gene_total + prs_total + topic_total,
    }

    DIGEST.write_text(json.dumps(digest, indent=2))
    print(f"\nDone. {digest['summary']['total']} papers found.")
    print(f"Saved → {DIGEST}")


if __name__ == "__main__":
    main()
