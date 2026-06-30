#!/usr/bin/env python3
"""
Fetches new papers + preprints relevant to:
  - Disease-level genetics (CHD, DCM, SCAD)
  - PRS specifically for those diseases
  - PRS / genetic-architecture methods (oligogenic, digenic, multi-locus)
  - Epigenetic / methylation / multi-omics topics in CHD/DCM

Pipeline
--------
1. PubMed (NCBI eutils) search, dated by Entrez date (EDAT) so newly *indexed*
   papers are caught -- not just those whose stated publication date is recent.
2. Europe PMC search restricted to preprints (bioRxiv / medRxiv), same concepts.
3. Cross-week de-duplication via data/seen.json (never re-surface a paper).
4. Relevance filtering. Primary path: an LLM scores each paper 0-5 against the
   plain-English `interest_profile` in the config. Fallback (no API key): an
   improved keyword/journal heuristic. Papers scoring >= relevance_threshold are
   kept, ranked, and capped at max_papers_total.

Generates data/digest.json, consumed by build_site.py (and send_email.py if used).
"""

import json, time, re, os, sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import requests
import xml.etree.ElementTree as ET

ROOT    = Path(__file__).parent.parent
CONFIG  = ROOT / "data" / "watch_config.json"
DIGEST  = ROOT / "data" / "digest.json"
SEEN    = ROOT / "data" / "seen.json"
EUTILS  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
EPMC    = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

cfg       = json.loads(CONFIG.read_text())
SETTINGS  = cfg["settings"]
reldate   = SETTINGS.get("reldate_days", 8)
datetype  = SETTINGS.get("datetype", "edat")
max_per_q = SETTINGS.get("max_results_per_query", 40)
max_total = SETTINGS.get("max_papers_total", 25)
threshold = SETTINGS.get("relevance_threshold", 3)
incl_pre  = SETTINGS.get("include_preprints", True)
use_llm   = SETTINGS.get("use_llm", True)
llm_model = SETTINGS.get("llm_model", "claude-haiku-4-5-20251001")
PROFILE   = cfg.get("interest_profile", "")

# Optional NCBI API key (raises rate limit 3 -> 10 req/s). Set NCBI_API_KEY secret.
NCBI_KEY  = os.environ.get("NCBI_API_KEY", "").strip()

# High-impact cardiovascular/genomics journals (heuristic-fallback scoring only)
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


# ── Seen-state (cross-week de-duplication) ────────────────────────────────────

def load_seen():
    if SEEN.exists():
        try:
            data = json.loads(SEEN.read_text())
            return set(data.get("ids", []))
        except Exception:
            return set()
    return set()

def save_seen(seen):
    # Keep the most recent ~6000 ids to bound file growth.
    ids = list(seen)[-6000:]
    SEEN.write_text(json.dumps({"updated": datetime.now().isoformat(), "ids": ids}, indent=0))


# ── PubMed ────────────────────────────────────────────────────────────────────

def pubmed_search(query):
    params = {
        "db": "pubmed", "term": query,
        "retmax": max_per_q, "retmode": "json", "usehistory": "y",
        "datetype": datetype, "reldate": reldate, "sort": "date",
    }
    if NCBI_KEY:
        params["api_key"] = NCBI_KEY
    r = requests.get(f"{EUTILS}/esearch.fcgi", params=params, timeout=20)
    r.raise_for_status()
    data = r.json().get("esearchresult", {})
    return data.get("idlist", []), data.get("webenv"), data.get("querykey")


def pubmed_fetch(ids, webenv, querykey):
    if not ids:
        return []
    r = None
    for attempt in range(3):
        try:
            params = {
                "db": "pubmed", "webenv": webenv, "query_key": querykey,
                "rettype": "xml", "retmode": "xml", "retmax": len(ids),
            }
            if NCBI_KEY:
                params["api_key"] = NCBI_KEY
            r = requests.get(f"{EUTILS}/efetch.fcgi", params=params, timeout=30)
            if r.status_code == 429:
                time.sleep(5 * (attempt + 1)); continue
            r.raise_for_status()
            break
        except Exception:
            if attempt == 2:
                return []
            time.sleep(3)
    if r is None:
        return []
    root = ET.fromstring(r.content)
    papers = []
    for art in root.findall(".//PubmedArticle"):
        try:
            pmid = art.findtext(".//PMID", "")
            title_elem = art.find(".//ArticleTitle")
            title = "".join(title_elem.itertext()).strip() if title_elem is not None else ""
            title = re.sub(r'\s+', ' ', title)

            abs_texts = art.findall(".//AbstractText")
            abstract_parts = []
            for a in abs_texts:
                label = a.get("Label", "")
                text  = "".join(a.itertext()).strip()
                if text:
                    abstract_parts.append(f"{label}: {text}" if label else text)
            abstract = " ".join(abstract_parts).strip()

            authors = []
            for a in art.findall(".//Author")[:3]:
                ln = a.findtext("LastName", ""); fn = a.findtext("ForeName", "")
                if ln: authors.append(f"{ln} {fn[0] if fn else ''}".strip())
            if len(art.findall(".//Author")) > 3:
                authors.append("et al.")

            journal = art.findtext(".//Journal/Title", "") or art.findtext(".//ISOAbbreviation", "")
            year    = art.findtext(".//PubDate/Year", "")
            month   = art.findtext(".//PubDate/Month", "")
            doi     = ""
            for aid in art.findall(".//ArticleId"):
                if aid.get("IdType") == "doi":
                    doi = aid.text or ""

            papers.append(_paper(
                uid=f"pmid:{pmid}", pmid=pmid, title=title, abstract=abstract,
                authors=", ".join(authors), journal=journal, year=year, month=month,
                doi=doi, url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                is_preprint=False,
            ))
        except Exception:
            pass
    return papers


# ── Europe PMC (preprints: bioRxiv / medRxiv) ─────────────────────────────────

def to_epmc_query(pubmed_query):
    """Convert a PubMed field-tagged query to a Europe PMC free-text query by
    stripping the [..] field tags. The Boolean structure (AND/OR/parentheses,
    quoted phrases, * wildcards) is preserved and valid in Europe PMC."""
    q = re.sub(r'\[[^\]]*\]', '', pubmed_query)
    q = re.sub(r'\s+', ' ', q).strip()
    return q


def epmc_search_preprints(pubmed_query):
    base = to_epmc_query(pubmed_query)
    since = (datetime.now() - timedelta(days=reldate)).strftime("%Y-%m-%d")
    today = datetime.now().strftime("%Y-%m-%d")
    query = f"({base}) AND (SRC:PPR) AND (FIRST_PDATE:[{since} TO {today}])"
    try:
        r = requests.get(EPMC, params={
            "query": query, "format": "json",
            "pageSize": max_per_q, "sort": "P_PDATE_D desc", "resultType": "core",
        }, timeout=25)
        r.raise_for_status()
        results = r.json().get("resultList", {}).get("result", [])
    except Exception as e:
        print(f"  EPMC error: {e}")
        return []

    papers = []
    for it in results:
        doi   = it.get("doi", "")
        title = re.sub(r'\s+', ' ', (it.get("title", "") or "").strip()).rstrip(".")
        abstract = (it.get("abstractText", "") or "").strip()
        abstract = re.sub(r'<[^>]+>', '', abstract)  # strip any HTML tags
        author = it.get("authorString", "") or ""
        if author.count(",") > 2:
            author = ", ".join(author.split(", ")[:3]) + ", et al."
        # Friendly server label (bioRxiv / medRxiv / Research Square ...) lives in
        # bookOrReportDetails.publisher; fall back to a generic "Preprint".
        server = ((it.get("bookOrReportDetails") or {}).get("publisher")
                  or it.get("publisher") or "Preprint")
        year  = (it.get("firstPublicationDate", "") or "")[:4]
        url   = f"https://doi.org/{doi}" if doi else \
                f"https://europepmc.org/article/PPR/{it.get('id','')}"
        uid   = f"doi:{doi}" if doi else f"ppr:{it.get('id','')}"
        papers.append(_paper(
            uid=uid, pmid="", title=title, abstract=abstract, authors=author,
            journal=server, year=year, month="", doi=doi, url=url, is_preprint=True,
        ))
    return papers


# ── Paper record + light enrichment ───────────────────────────────────────────

def _paper(uid, pmid, title, abstract, authors, journal, year, month, doi, url, is_preprint):
    return {
        "uid": uid, "pmid": pmid,
        "title": title,
        "abstract": abstract[:500] + ("…" if len(abstract) > 500 else ""),
        "abstract_full": abstract,
        "bullets": summarise_abstract(abstract),
        "authors": authors, "journal": journal, "year": year, "month": month,
        "doi": doi, "url": url, "is_preprint": is_preprint,
        "ris": make_ris(pmid, title, authors, journal, year, doi, abstract, url),
        "type": classify_paper(title, abstract, is_preprint),
    }


def make_ris(pmid, title, authors, journal, year, doi, abstract, url):
    lines = ["TY  - JOUR"]
    for a in [a for a in authors.split(", ") if a and a != "et al."]:
        lines.append(f"AU  - {a}")
    lines += [
        f"TI  - {title}", f"JO  - {journal}", f"PY  - {year}",
        f"DO  - {doi}", f"AB  - {abstract[:300]}", f"UR  - {url}", "ER  - ",
    ]
    return "\n".join(lines)


def classify_paper(title, abstract, is_preprint=False):
    text = (title + " " + abstract).lower()
    if any(w in text for w in ["review", "meta-analysis", "systematic review"]):
        base = "Review"
    elif any(w in text for w in ["genome-wide association", "gwas"]):
        base = "GWAS"
    elif any(w in text for w in ["polygenic risk", "polygenic score", "prs", "pgs"]):
        base = "PRS"
    elif any(w in text for w in ["whole exome", "whole genome sequencing", "wgs", "wes"]):
        base = "Sequencing study"
    elif any(w in text for w in ["oligogenic", "digenic", "multilocus", "multi-locus"]):
        base = "Methods"
    elif any(w in text for w in ["methylation", "epigenetic", "histone", "chromatin"]):
        base = "Epigenetics"
    elif any(w in text for w in ["case report", "case series"]):
        base = "Case report"
    elif any(w in text for w in ["mouse", "zebrafish", "cell line", "in vitro", "functional"]):
        base = "Functional study"
    else:
        base = "Research article"
    return f"Preprint · {base}" if is_preprint else base


def summarise_abstract(abstract):
    if not abstract:
        return []
    PRIORITY_LABELS = re.compile(
        r'(RESULTS?|CONCLUSIONS?|FINDINGS?|KEY FINDINGS?|MAIN RESULTS?'
        r'|INTERPRETATION|SIGNIFICANCE|TAKE-?AWAY)\s*:\s*', re.IGNORECASE)
    labelled_text = []
    for m in PRIORITY_LABELS.finditer(abstract):
        start = m.end()
        nxt = PRIORITY_LABELS.search(abstract, start)
        end = nxt.start() if nxt else len(abstract)
        chunk = abstract[start:end].strip()
        if chunk:
            labelled_text.append(chunk)
    source = " ".join(labelled_text) if labelled_text else abstract

    SUB_HEADER = re.compile(r'(?<=[.!\?])\s+[A-Z][A-Za-z /\-]{3,40}:\s+')
    sub_parts = SUB_HEADER.split(source)
    if len(sub_parts) > 3:
        source = " ".join(sub_parts)

    raw = re.split(r'(?<=[.!?])\s+(?=[A-Z\(])', source.strip())
    sentences = [s.strip() for s in raw if len(s.strip()) > 25]
    if not sentences:
        return []

    RESULTS_SIGNALS = [
        "we found", "we identified", "we show", "we demonstrate", "we report",
        "we observed", "we detected", "our results", "our findings",
        "results show", "results indicate", "results suggest",
        "findings suggest", "findings indicate", "analysis revealed",
        "associated with", "significantly", "were associated", "was associated",
        "increased risk", "decreased risk", "higher risk", "lower risk",
        "identified", "revealed", "demonstrated", "confirmed", "established",
        "pathogenic variant", "de novo", "rare variant", "loss-of-function",
        "odds ratio", "hazard ratio", "p <", "p=", "95% ci",
        "genome-wide", "exome", "whole genome", "gwas",
        "in conclusion", "collectively", "together, these",
    ]
    SKIP_SIGNALS = [
        "background:", "introduction:", "methods:", "aim of", "aims to",
        "we sought to", "we aimed to", "the purpose of",
        "to investigate", "to determine", "to assess", "to evaluate",
        "is a common", "is a rare", "remains unclear", "remain poorly",
        "little is known", "registration:", "identifier:", "prospero",
        "http", "clinicaltrials",
    ]
    scored = []
    for i, sent in enumerate(sentences):
        low = sent.lower(); score = 0
        if labelled_text:
            score = 5
        else:
            for sig in RESULTS_SIGNALS:
                if sig in low: score += 2
            score += i * 0.3
        for sig in SKIP_SIGNALS:
            if sig in low: score -= 4
        if len(sent) > 350: score -= 1
        if len(sent) < 40: score -= 2
        scored.append((score, i, sent))
    scored.sort(key=lambda x: (-x[0], x[1]))
    top = sorted(scored[:3], key=lambda x: x[1])
    bullets = [s for _, _, s in top if s]

    MAX_BULLET = 220
    cleaned = []
    for b in bullets:
        b = b.rstrip("…").strip()
        b = PRIORITY_LABELS.sub("", b).strip()
        b = SUB_HEADER.sub(" ", b).strip()
        if len(b) > MAX_BULLET:
            cut = b[:MAX_BULLET].rfind(".")
            b = b[:cut + 1] if cut > MAX_BULLET // 2 else b[:MAX_BULLET].rsplit(" ", 1)[0] + "…"
        if b and not b.endswith((".", "!", "?", "…")):
            b += "."
        if b and len(b) > 20:
            cleaned.append(b)
    return cleaned[:3]


# ── Relevance: LLM primary, heuristic fallback ────────────────────────────────

def heuristic_score(paper):
    """Fallback 0-5 score when no LLM is available."""
    text = (paper["title"] + " " + paper.get("abstract_full", "")).lower()
    title_lower = paper["title"].lower()
    score = 0
    if any(j in paper.get("journal", "").lower() for j in HIGH_IMPACT):
        score += 3
    if any(kw in title_lower for kw in DISEASE_KEYWORDS):
        score += 3
    elif any(kw in text for kw in DISEASE_KEYWORDS):
        score += 1
    if any(kw in text for kw in METHODS_KEYWORDS):
        score += 1
    if any(w in text for w in ["patients", "cohort", "participants", "individuals", "proband", "families"]):
        score += 1
    if any(w in text for w in ["mouse model", "zebrafish", "in vitro", "cell line"]) and \
       not any(w in text for w in ["patients", "cohort", "participants"]):
        score -= 3
    # Map heuristic onto the 0-5 LLM scale (clamp)
    return max(0, min(5, round(score / 2)))


def llm_score(papers):
    """Score papers 0-5 for relevance to PROFILE using Anthropic. Mutates papers
    in place with 'score' and 'relevance_note'. Returns True on success."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return False
    try:
        import anthropic
    except ImportError:
        print("  anthropic package not installed; using heuristic fallback.")
        return False

    client = anthropic.Anthropic(api_key=api_key)
    by_uid = {p["uid"]: p for p in papers}
    BATCH = 15
    uids = list(by_uid.keys())
    ok = False
    for i in range(0, len(uids), BATCH):
        chunk = uids[i:i + BATCH]
        items = []
        for uid in chunk:
            p = by_uid[uid]
            ab = (p.get("abstract_full") or "")[:1200]
            items.append({"id": uid, "title": p["title"],
                          "journal": p.get("journal", ""), "abstract": ab})
        prompt = (
            "You are triaging new papers for a researcher. Score each paper's "
            "relevance to THIS researcher's interests on a 0-5 integer scale:\n"
            "5 = squarely on-target, must read.\n"
            "3-4 = clearly relevant.\n"
            "1-2 = tangential / only loosely related.\n"
            "0 = off-topic (e.g. no genetics, animal-only with no human relevance, "
            "surgical/clinical-outcome only, drug trial, imaging only).\n\n"
            f"RESEARCHER'S INTEREST PROFILE:\n{PROFILE}\n\n"
            "PAPERS (JSON):\n" + json.dumps(items, ensure_ascii=False) + "\n\n"
            "Respond with ONLY a JSON array, one object per paper, in the same "
            'order: [{"id": "<id>", "score": <int 0-5>, "reason": "<<=12 words>"}]. '
            "No prose, no markdown fences."
        )
        try:
            resp = client.messages.create(
                model=llm_model, max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
            )
            txt = resp.content[0].text.strip()
            txt = re.sub(r'^```(?:json)?|```$', '', txt.strip(), flags=re.MULTILINE).strip()
            results = json.loads(txt)
            for res in results:
                p = by_uid.get(res.get("id"))
                if p is not None:
                    p["score"] = int(res.get("score", 0))
                    p["relevance_note"] = res.get("reason", "")
            ok = True
        except Exception as e:
            print(f"  LLM scoring error on batch {i // BATCH}: {e}")
            for uid in chunk:
                by_uid[uid].setdefault("score", heuristic_score(by_uid[uid]))
        time.sleep(0.3)
    return ok


# ── Fetch orchestration ───────────────────────────────────────────────────────

def fetch_all(seen):
    """Run every query across PubMed (+ preprints), de-dup against seen, and
    return a flat list of candidate papers tagged with section/topic."""
    section_groups = [
        ("disease_genetics", cfg.get("disease_genetics", {})),
        ("prs_disease",      cfg.get("prs_disease", {})),
        ("prs_methods",      cfg.get("prs_methods", {})),
        ("topic_watch",      cfg.get("topic_watch", {})),
    ]
    candidates = {}  # uid -> paper (first section wins)
    for section_key, section_cfg in section_groups:
        if not section_cfg:
            continue
        print(f"Fetching {section_key}...")
        for topic_name, topic in section_cfg.items():
            for query in topic["queries"]:
                # PubMed
                try:
                    ids, wh, qk = pubmed_search(query)
                    ids = [i for i in ids if f"pmid:{i}" not in seen]
                    for p in pubmed_fetch(ids, wh, qk):
                        if p["uid"] in seen or p["uid"] in candidates:
                            continue
                        p["section"] = section_key; p["topic"] = topic_name
                        candidates[p["uid"]] = p
                    time.sleep(0.35)
                except Exception as e:
                    print(f"  PubMed error on '{query[:50]}...': {e}")
                # Preprints
                if incl_pre:
                    try:
                        for p in epmc_search_preprints(query):
                            if p["uid"] in seen or p["uid"] in candidates:
                                continue
                            p["section"] = section_key; p["topic"] = topic_name
                            candidates[p["uid"]] = p
                        time.sleep(0.35)
                    except Exception as e:
                        print(f"  EPMC error on '{query[:50]}...': {e}")
        n = sum(1 for p in candidates.values() if p["section"] == section_key)
        print(f"  → {n} candidates so far in {section_key}")
    return list(candidates.values())


def generate_summary(selected, section_counts):
    if not selected:
        return "No new papers matching your focus areas this period."
    n = len(selected)
    n_pre = sum(1 for p in selected if p.get("is_preprint"))
    lines = [f"{n} paper{'s' if n != 1 else ''} selected this period"
             + (f" ({n_pre} preprint{'s' if n_pre != 1 else ''})" if n_pre else "") + ":"]
    label_map = {
        "disease_genetics": "disease genetics (CHD / DCM / SCAD)",
        "prs_disease": "PRS in CHD/DCM/SCAD",
        "prs_methods": "PRS & oligogenic methods",
        "topic_watch": "epigenetics / methylation / omics",
    }
    for section, count in section_counts.items():
        if count > 0:
            lines.append(f"  • {count} × {label_map.get(section, section)}")
    top = selected[0]
    lines.append(f"\nHighlight: {top['title']} ({top['journal']}, {top['year']})")
    return "\n".join(lines)


def main():
    seen = load_seen()
    print(f"Loaded {len(seen)} previously-seen ids.")

    candidates = fetch_all(seen)
    print(f"\n{len(candidates)} new candidate papers fetched.")

    # ── Relevance scoring ──
    scored_by_llm = False
    if use_llm and candidates:
        scored_by_llm = llm_score(candidates)
    if not scored_by_llm:
        print("  Using heuristic relevance scoring.")
        for p in candidates:
            if "score" not in p:
                p["score"] = heuristic_score(p)

    # ── Select: threshold + global cap; ties broken by section priority ──
    section_priority = {"disease_genetics": 4, "prs_disease": 3, "prs_methods": 3, "topic_watch": 2}
    kept = [p for p in candidates if p.get("score", 0) >= threshold]
    kept.sort(key=lambda p: (p.get("score", 0), section_priority.get(p["section"], 1)), reverse=True)
    selected = kept[:max_total]

    section_counts = defaultdict(int)
    for p in selected:
        section_counts[p["section"]] += 1

    # Per-section breakdown (full candidate sets) for the site
    sections = defaultdict(list)
    for p in candidates:
        sections[p["section"]].append(p)
    digest = {
        "generated": datetime.now().isoformat(),
        "lookback_days": reldate,
        "datetype": datetype,
        "scoring": "llm" if scored_by_llm else "heuristic",
        "sections": {k: {"papers": sorted(v, key=lambda x: x.get("score", 0), reverse=True),
                         "total": len(v)} for k, v in sections.items()},
        "selected_papers": selected,
        "summary_text": generate_summary(selected, dict(section_counts)),
        "summary": {
            "total_selected": len(selected),
            "total_candidates": len(candidates),
            "section_counts": dict(section_counts),
        },
    }
    DIGEST.write_text(json.dumps(digest, indent=2))

    # ── Persist seen (all fetched candidates, so we never re-process them) ──
    for p in candidates:
        seen.add(p["uid"])
    save_seen(seen)

    print(f"\nDone. {len(selected)} selected from {len(candidates)} candidates "
          f"(scoring: {'LLM' if scored_by_llm else 'heuristic'}).")
    print(f"Saved → {DIGEST}\n")
    print(digest["summary_text"])


if __name__ == "__main__":
    main()
