#!/usr/bin/env python3
import argparse, os, json, datetime as dt

from semanticscholar import SemanticScholar

FIELDS = [
  "title","year","authors","venue","publicationTypes","publicationDate",
  "citationCount","externalIds","url","paperId"
]

def norm_doi(s: str) -> str:
    if not s: return ""
    s = s.strip()
    s = s.replace("https://doi.org/", "").replace("http://doi.org/", "")
    if s.lower().startswith("doi:"):
        s = s[4:].strip()
    return s

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--author-id", required=True)
    ap.add_argument("--out", default="data/publications.json")
    ap.add_argument("--selected-dois", default="data/selected_dois.txt")
    ap.add_argument("--limit", type=int, default=1000)
    args = ap.parse_args()

    api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
    sch = SemanticScholar(api_key=api_key)

    # One call returns paginated results; iterate to collect up to limit
    papers = []
    for p in sch.get_author_papers(args.author_id, fields=FIELDS, limit=args.limit):
        if p:
            papers.append(p)

    selected = set()
    if os.path.exists(args.selected_dois):
        with open(args.selected_dois, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                selected.add(norm_doi(line))

    items = []
    for p in papers:
        ext = p.get("externalIds") or {}
        doi = norm_doi(ext.get("DOI") or "")
        authors = p.get("authors") or []
        authors_str = ", ".join([a.get("name","").strip() for a in authors if a.get("name")])

        items.append({
            "doi": doi,
            "title": p.get("title") or "",
            "authors": authors_str,
            "venue": p.get("venue") or "",
            "year": p.get("year") or "",
            "url": p.get("url") or (("https://www.semanticscholar.org/paper/" + p.get("paperId")) if p.get("paperId") else ""),
            "citationCount": p.get("citationCount"),
            "publicationDate": p.get("publicationDate") or "",
            "publicationTypes": p.get("publicationTypes") or [],
            "selected": (doi in selected) if doi else False,
        })

    # Sort newest first, then by citations
    def key(it):
        y = int(it["year"] or 0)
        c = int(it["citationCount"] or 0) if it["citationCount"] is not None else 0
        return (-y, -c, (it["title"] or "").lower())

    items.sort(key=key)

    out = {
        "updatedAt": dt.datetime.utcnow().date().isoformat(),
        "source": {"name": "Semantic Scholar", "via": f"author:{args.author_id}"},
        "counts": {"total": len(items)},
        "items": items
    }

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"Wrote {args.out}: {len(items)} item(s).")

if __name__ == "__main__":
    main()