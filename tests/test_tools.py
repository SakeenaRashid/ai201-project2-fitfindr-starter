"""
tests/test_tools.py

Unit tests for search_listings, suggest_outfit, and create_fit_card.
The search tests run against the real listings.json and need no API key.
The LLM guard tests exercise the early-exit paths and also need no API key.
"""

import sys
import os

# Make sure imports work when running pytest from the project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools import search_listings, suggest_outfit, create_fit_card


# ── search_listings tests ─────────────────────────────────────────────────────

def test_search_returns_results():
    """A broad query with a generous price ceiling should return at least one listing."""
    results = search_listings("vintage graphic tee", None, 50)
    assert len(results) > 0


def test_search_empty_results():
    """A nonsense query with a tiny price and rare size should return nothing."""
    results = search_listings("designer ballgown", "XXS", 5)
    assert results == []


def test_search_price_filter():
    """Every result returned must have a price at or below the max_price."""
    results = search_listings("jacket", None, 10)
    for listing in results:
        assert listing["price"] <= 10


# ── suggest_outfit tests ──────────────────────────────────────────────────────

def test_suggest_outfit_empty_wardrobe():
    """Empty wardrobe should return immediately with outfit=[] and no LLM call."""
    new_item = {
        "id": "lst_006",
        "title": "Graphic Tee — 2003 Tour Bootleg Style",
        "category": "tops",
        "colors": ["black"],
        "style_tags": ["graphic tee", "vintage", "grunge", "streetwear"],
        "size": "L",
        "condition": "good",
        "price": 24.0,
        "platform": "depop",
    }
    empty_wardrobe = {"items": []}

    result = suggest_outfit(new_item, empty_wardrobe)

    assert isinstance(result, dict)
    assert result["outfit"] == []
    assert result["new_item"] == new_item


# ── create_fit_card tests ─────────────────────────────────────────────────────

def test_create_fit_card_missing_input():
    """new_item=None should return an error string without raising an exception."""
    outfit = {"outfit": [], "styling_note": "some note"}

    result = create_fit_card(outfit, None)

    assert isinstance(result, str)
    assert len(result) > 0
