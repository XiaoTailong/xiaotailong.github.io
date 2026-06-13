#!/usr/bin/env python3
"""Regression checks for the Semantic Scholar publications generator."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import types
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "tools" / "s2_author_to_publications_json.py"


class FakeSemanticScholar:
    def __init__(self, api_key=None):
        self.api_key = api_key

    def get_author_papers(self, author_id, fields=None, limit=None):
        return [
            {
                "externalIds": {"DOI": "https://doi.org/10.1234/SELECTED"},
                "title": "Selected paper",
                "authors": [{"name": "Tailong Xiao"}, {"name": "A. Collaborator"}],
                "venue": "Test Journal",
                "year": 2025,
                "url": "https://example.test/selected",
                "citationCount": 7,
                "publicationDate": "2025-01-01",
                "publicationTypes": ["JournalArticle"],
                "paperId": "paper-selected",
            },
            {
                "externalIds": {"DOI": "10.5678/OTHER"},
                "title": "Other paper",
                "authors": [{"name": "A. Collaborator"}, {"name": "Tailong Xiao"}],
                "venue": "Another Journal",
                "year": 2024,
                "url": "https://example.test/other",
                "citationCount": 3,
                "publicationDate": "2024-01-01",
                "publicationTypes": ["JournalArticle"],
                "paperId": "paper-other",
            },
        ]


def load_generator():
    fake_module = types.ModuleType("semanticscholar")
    fake_module.SemanticScholar = FakeSemanticScholar

    with mock.patch.dict(sys.modules, {"semanticscholar": fake_module}):
        spec = importlib.util.spec_from_file_location("s2_generator_under_test", GENERATOR)
        if spec is None or spec.loader is None:
            raise RuntimeError("Could not load publications generator")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


def run_generator(module, out_path: Path, selected_path: Path) -> dict:
    argv = [
        "s2_author_to_publications_json.py",
        "--author-id",
        "test-author",
        "--out",
        str(out_path),
        "--selected-dois",
        str(selected_path),
    ]

    with mock.patch.object(sys, "argv", argv):
        module.main()

    return json.loads(out_path.read_text(encoding="utf-8"))


def test_selected_dois_are_applied() -> None:
    module = load_generator()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        selected_path = tmp_path / "selected_dois.txt"
        selected_path.write_text("# comments are ignored\n10.1234/selected\n", encoding="utf-8")

        data = run_generator(module, tmp_path / "publications.json", selected_path)

    selected = [item for item in data["items"] if item["selected"]]
    assert len(data["items"]) == 2
    assert [item["title"] for item in selected] == ["Selected paper"]
    assert data["source"] == {"name": "Semantic Scholar", "via": "author:test-author"}


def test_missing_selected_dois_file_is_nonfatal() -> None:
    module = load_generator()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        data = run_generator(module, tmp_path / "publications.json", tmp_path / "missing.txt")

    assert len(data["items"]) == 2
    assert all(item["selected"] is False for item in data["items"])


def main() -> int:
    test_selected_dois_are_applied()
    test_missing_selected_dois_file_is_nonfatal()
    print("Publication generator regression checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
