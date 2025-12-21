#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from typing import Any, Dict, Iterable, List, Optional

from semanticscholar import SemanticScholar

FIELDS = [
    "title","year","authors","venue","publicationTypes","publicationDate",
    "citationCount","externalIds","url","paperId",
]

def norm_doi(s: str) -> str:
    if not s:
        return ""
    s = s.strip()
    s = s.replace("https://doi.org/", "").replace("http://doi.org/", "")
    if s.lower().startswith("doi:"):
        s = s[4:].strip()
    return s

def safe_get(p: Any, key: str, default: Any = None) -> Any:
    if p is None:
        return default
    if isinstance(p, dict):
        return p.get(key, default)
    return getattr(p, key, default)

def external_ids(p: Any) -> Dict[str, Any]:
    ext = safe_get(p, "externalIds", None)
    if isinstance(ext, dict):
        return ext
    ext2 = safe_get(p, "external_ids", None)
    return ext2 if isinstance(ext2, dict) else {}

def authors_to_str(authors: Any) -> str:
    if not authors:
        return ""
    names: List[str] = []
    for a in authors:
        if a is None:
            continue
        if isinstance(a, dict):
            n = (a.get("name") or "").strip()
        elif isinstance(a, str):
            n = a.strip()
        else:
            n = (getattr(a, "name", "") or "").strip()
        if n:
            names.append(n)
    return ", ".join(names)

def load_selected_dois(path: Optional[str]) -> set[str]:
    if not path or not os.path.exists(path):
        return set()
    out: set[str] = set()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            out.add(norm_doi(line))
    return out

def iter_author_papers(client: SemanticScholar, author_id: str, limit: int) -> Iterable[Any]:
    try:
        yield from client.get_author_papers(author_id, fields=FIELDS, limit=limit)
        return
    except TypeError:
        pass
    papers = client.get_author_papers(author_id)
    for i, p in enumerate(papers):
        if i >= limit:
            break
        yield p

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--author-id", required=True)
    ap.add_argument("--out", default="data/publications.json")
    ap.add_argument("--selected-dois", default="data/selected_dois.txt")
    ap.add_argument("--limit", type=int, default=2000)
    args = ap.parse_args()

    api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY") or None
    client = SemanticScholar(api_key=api_key) if api_key else SemanticScholar()

    selected = load_selected_dois(args.selected_dois)

    items: List[Dict[str, Any]] = []
    for p in iter_author_papers(client, args.author_id, args.limit):
        if not p:
            continue
        ext = external_ids(p)
        doi = norm_doi(ext.get("DOI") or "")

        authors = safe_get(p, "authors", None) or []
        authors_str = authors_to_str(authors)

        paper_id = safe_get(p, "paperId", "") or safe_get(p, "paper_id", "") or ""
        url = safe_get(p, "url", "") or (f"https://www.semanticscholar.org/paper/{paper_id}" if paper_id else "")

        items.append({
            "doi": doi,
            "title": safe_get(p, "title", "") or "",
            "authors": authors_str,
            "venue": safe_get(p, "venue", "") or "",
            "year": safe_get(p, "year", "") or "",
            "url": url,
            "citationCount": safe_get(p, "citationCount", None),
            "publicationDate": safe_get(p, "publicationDate", "") or "",
            "publicationTypes": safe_get(p, "publicationTypes", None) or [],
            "selected": (doi in selected) if doi else False,
        })

    def y(x):
        try: return int(x.get("year") or 0)
        except: return 0
    def c(x):
        try: return int(x.get("citationCount") or 0)
        except: return 0

    items.sort(key=lambda x: (y(x), c(x), (x.get("title") or "").lower()), reverse=True)

    out = {
        "updatedAt": dt.datetime.utcnow().date().isoformat(),
        "source": {"name": "Semantic Scholar", "via": f"author:{args.author_id}"},
        "counts": {"total": len(items)},
        "items": items,
    }

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"Wrote {args.out}: {len(items)} item(s).")

if __name__ == "__main__":
    main()