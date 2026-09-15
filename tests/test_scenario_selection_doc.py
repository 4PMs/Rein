"""Smoke test for docs/scenario-selection.md: required policy statements present."""

from pathlib import Path

ROOT = Path(__file__).parents[1]
DOC_PATH = ROOT / "docs" / "scenario-selection.md"


def _text() -> str:
    return DOC_PATH.read_text(encoding="utf-8")


def test_doc_exists():
    assert DOC_PATH.is_file()


def test_doc_names_the_source_writeup():
    text = _text()
    assert "Whyiest/Juice-Shop-Write-up" in text


def test_doc_declares_difficulty_based_ids():
    text = _text()
    for prefix in ("JS-D1-", "JS-D2-", "JS-D3-", "JS-D4-", "JS-D5-", "JS-D6-"):
        assert prefix in text


def test_doc_states_the_suitability_filter():
    text = _text()
    for keyword in (
        "Deterministic evidence", "Gateway-observable", "Narrow RoE scope",
        "Repeatability", "broad solver", "destructive",
    ):
        assert keyword in text


def test_doc_defers_browser_and_destructive_categories():
    text = _text()
    assert "Browser/DOM-only" in text or "browser_dom_executor" in text
    assert "DoS" in text or "destructive" in text.lower()


def test_doc_requires_fixtures_for_state_changing_scenarios():
    text = _text()
    assert "fixtures:" in text
    assert "tempera.fixtures" in text
