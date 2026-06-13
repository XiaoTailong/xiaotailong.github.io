#!/usr/bin/env python3
"""Lightweight quality checks for the academic homepage."""

from __future__ import annotations

import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
CSS = ROOT / "jemdoc.css"
NEWS = ROOT / "data" / "news.json"
PUBLICATIONS = ROOT / "data" / "publications.json"
SELECTED_DOIS = ROOT / "data" / "selected_dois.txt"


class SiteParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.section_ids: list[str] = []
        self.stylesheets: list[str] = []
        self.inline_styles = 0
        self.button_ids: list[str] = []
        self.text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        if tag == "section" and attr.get("id"):
            self.section_ids.append(attr["id"] or "")
        if tag == "link":
            rel = attr.get("rel", "") or ""
            if "stylesheet" in rel.split():
                self.stylesheets.append(attr.get("href", "") or "")
        if tag == "style":
            self.inline_styles += 1
        if tag == "button" and attr.get("id"):
            self.button_ids.append(attr["id"] or "")

    def handle_data(self, data: str) -> None:
        cleaned = " ".join(data.split())
        if cleaned:
            self.text.append(cleaned)


def expect(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def section_order_contains(actual: list[str], expected: list[str]) -> bool:
    position = 0
    for section_id in actual:
        if position < len(expected) and section_id == expected[position]:
            position += 1
    return position == len(expected)


def load_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_selected_dois(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def main() -> int:
    failures: list[str] = []

    html = INDEX.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")
    combined = f"{html}\n{css}"

    parser = SiteParser()
    parser.feed(html)
    visible_text = " ".join(parser.text)

    expected_sections = [
        "about",
        "news",
        "research",
        "selected-publications",
        "teaching",
        "service",
        "education",
    ]

    expect(any(href.split("?", 1)[0] == "jemdoc.css" for href in parser.stylesheets), "index.html should load jemdoc.css", failures)
    expect(parser.inline_styles == 0, "site styling should live in jemdoc.css, not a large inline style block", failures)
    expect(section_order_contains(parser.section_ids, expected_sections), f"sections should appear in academic order: {expected_sections}", failures)
    expect("projects" not in parser.section_ids and 'href="#projects"' not in html, "projects should be removed from the homepage navigation and sections", failures)
    expect("publications" not in parser.section_ids and 'href="#publications"' not in html, "complete publications list should be removed from the homepage", failures)
    expect('id="publicationList"' not in html and 'id="pubCount"' not in html and 'id="citationCount"' not in html, "homepage should not render complete publication metrics or list", failures)
    expect("themeBtn" not in parser.button_ids, "academic homepage should not include a theme toggle button", failures)
    expect("localStorage" not in html and "data-theme" not in html, "theme persistence code should be removed", failures)
    expect("radial-gradient" not in combined and "#9b7bff" not in combined and "#5b8cff" not in combined, "remove portfolio-style gradients and purple/blue brand colors", failures)
    expect(not re.search(r"border-radius\s*:\s*(1[0-9]|[2-9][0-9])px", css), "card radii should stay 8px or below", failures)
    expect("Open positions" in visible_text or "Prospective students" in visible_text, "hero should include a clear academic recruiting/contact signal", failures)
    expect("every spring semester" in visible_text.lower(), "teaching section should state that the course is offered every spring", failures)
    expect("data/selected_dois.txt" in html, "homepage should read representative-paper DOIs from data/selected_dois.txt instead of relying on manual edits to generated JSON", failures)
    expect("For the complete and automatically updated publication list" in visible_text and "Google Scholar" in visible_text, "Selected Publications should include a Google Scholar note for the full publication list", failures)
    expect('id="newsList"' in html and 'class="timeline feed-scroll"' in html, "news and talks should render as one compact scrollable timeline", failures)
    expect("const NEWS_TALK_LIMIT = 20" in html and ".slice(0, NEWS_TALK_LIMIT)" in html, "news and talks feeds should be limited to 20 latest items", failures)
    expect("function renderTalkSentence" in html and "I presented" in html, "talk entries should render as complete first-person sentences", failures)
    expect("Intl.DateTimeFormat('en-US'" in html, "news and talks dates should use a stable English date format", failures)
    expect("String(b.date || '').localeCompare(String(a.date || ''))" in html, "news and talks should be sorted newest first", failures)
    expect(".feed-scroll" in css and "overflow-y: auto" in css and "max-height" in css, "news and talks feeds should use compact scrollable containers", failures)
    expect(
        ".publication-list li > .paper-title" in css
        and ".publication-list li > .paper-meta" in css
        and ".publication-list li > .paper-tags" in css
        and "grid-column: 2" in css,
        "publication title, metadata, and links should stay in the wide content column",
        failures,
    )
    expect("Cited by" in html and "citations > 0" in html, "selected publications should only show positive citation counts in a compact action row", failures)

    try:
        news = load_json(NEWS)
    except Exception as exc:  # noqa: BLE001 - report JSON problems clearly
        failures.append(f"data/news.json should be valid JSON: {exc}")
        news = {}

    if isinstance(news, dict):
        news_items = news.get("items", [])
        expect(isinstance(news.get("updatedAt"), str) and bool(news.get("updatedAt")), "news should have updatedAt", failures)
        expect(isinstance(news_items, list) and len(news_items) >= 5, "news should contain at least five dated academic updates", failures)
        if isinstance(news_items, list):
            expect(
                any("Yuegang Li" in str(item.get("title", "")) and "PhD graduation" in str(item.get("title", "")) for item in news_items if isinstance(item, dict)),
                "news should include Dr. Yuegang Li's PhD graduation",
                failures,
            )
            for index, item in enumerate(news_items[:5], start=1):
                expect(isinstance(item, dict) and all(item.get(key) for key in ("date", "title", "type")), f"news item {index} should have date, title, and type", failures)

    publications = load_json(PUBLICATIONS)
    if isinstance(publications, dict):
        pub_items = publications.get("items", [])
        expect(isinstance(pub_items, list) and len(pub_items) >= 10, "publication data should contain the full publication list", failures)
        selected_dois = load_selected_dois(SELECTED_DOIS)
        expect(len(selected_dois) >= 3, "representative publications should be configured in data/selected_dois.txt, not edited directly into generated publications.json", failures)

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1

    print("Academic site checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
