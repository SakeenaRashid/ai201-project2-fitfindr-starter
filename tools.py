"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → dict
    create_fit_card(outfit, new_item)               → str
"""

import json
import os
import re

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform
    """
    listings = load_listings()

    # Apply hard filters before scoring
    if max_price is not None:
        listings = [l for l in listings if l["price"] <= max_price]

    if size is not None:
        size_lower = size.lower()
        listings = [l for l in listings if size_lower in l["size"].lower()]

    # Tokenize the description into lowercase words
    keywords = re.findall(r'[a-z]+', description.lower())
    if not keywords:
        return []

    scored = []
    for listing in listings:
        title_words = set(re.findall(r'[a-z]+', listing["title"].lower()))
        desc_words = set(re.findall(r'[a-z]+', listing["description"].lower()))
        tag_words = set()
        for tag in listing["style_tags"]:
            tag_words.update(re.findall(r'[a-z]+', tag.lower()))

        score = 0
        for kw in keywords:
            if kw in tag_words:
                score += 2  # style tags are the most specific signal
            if kw in title_words:
                score += 2  # title is also a strong match
            if kw in desc_words:
                score += 1  # description is a weaker match

        if score > 0:
            scored.append((score, listing))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [listing for _, listing in scored[:3]]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> dict:
    """
    Given a thrifted item and the user's wardrobe, suggest complementary pieces
    to build a complete outfit.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A dict with keys:
            new_item     – the original listing dict
            outfit       – list of wardrobe item dicts chosen by the LLM (may be empty)
            styling_note – 1-2 sentence explanation of the pairing
        If the wardrobe is empty, returns immediately without calling the LLM.
    """
    if not wardrobe.get("items"):
        return {"new_item": new_item, "outfit": [], "styling_note": "Wardrobe is empty."}

    client = _get_groq_client()

    wardrobe_lines = "\n".join(
        f"- id: {item['id']}, name: {item['name']}, "
        f"colors: {', '.join(item['colors'])}, tags: {', '.join(item['style_tags'])}"
        for item in wardrobe["items"]
    )

    prompt = f"""You are a thrift fashion stylist helping someone build an outfit.

New thrifted item:
- Title: {new_item['title']}
- Category: {new_item['category']}
- Colors: {', '.join(new_item['colors'])}
- Style tags: {', '.join(new_item['style_tags'])}

User's wardrobe:
{wardrobe_lines}

Choose 1-3 wardrobe items that pair well with the new item to make a complete outfit.
Return ONLY a JSON object — no markdown fences, no explanation before or after:
{{
  "outfit_item_ids": ["id of chosen item", "another id if needed"],
  "styling_note": "1-2 sentences explaining why these pieces work together."
}}"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )

    content = response.choices[0].message.content.strip()

    # Strip markdown code fences if the LLM adds them anyway
    if content.startswith("```"):
        content = re.sub(r"```(?:json)?\n?", "", content).strip().rstrip("`").strip()

    try:
        parsed = json.loads(content)
        id_set = set(parsed.get("outfit_item_ids", []))
        selected = [item for item in wardrobe["items"] if item["id"] in id_set]
        styling_note = parsed.get("styling_note", content)
    except (json.JSONDecodeError, KeyError):
        # If JSON parsing fails, keep the raw text as the styling note
        selected = []
        styling_note = content

    return {"new_item": new_item, "outfit": selected, "styling_note": styling_note}


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: dict, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The dict returned by suggest_outfit (has 'outfit' and 'styling_note').
        new_item: The listing dict for the thrifted item.

    Returns:
        A formatted string with:
          - A 2-3 sentence social-style caption (from the LLM at temperature=0.9)
          - An item details one-liner (title, price, condition, platform)
          - A full outfit list (new item prefixed with ★, wardrobe items with ·)
        If outfit is missing or new_item is None, returns a descriptive error
        string — does NOT raise an exception.
    """
    if not outfit or new_item is None:
        return "Error: outfit data is incomplete — try running the search again."

    styling_note = outfit.get("styling_note", "") if isinstance(outfit, dict) else str(outfit)
    wardrobe_items = outfit.get("outfit", []) if isinstance(outfit, dict) else []

    client = _get_groq_client()

    item_details = (
        f"{new_item['title']} — ${new_item['price']}, "
        f"{new_item['condition']} condition, via {new_item['platform']}"
    )

    prompt = f"""Write a 2-3 sentence OOTD (outfit of the day) caption for a thrift fashion post.

Thrifted item: {item_details}
Outfit notes: {styling_note}

Requirements:
- Sound casual and authentic — like a real person posting, not a brand
- Mention the item name, price, and platform naturally (once each)
- Capture the specific vibe of the outfit
- No hashtags
Write only the caption, nothing else."""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9,
    )

    caption = response.choices[0].message.content.strip()

    full_outfit_list = [
        f"★ {new_item['title']} (${new_item['price']}, {new_item['platform']})"
    ]
    for item in wardrobe_items:
        full_outfit_list.append(f"· {item['name']}")

    outfit_str = "\n".join(full_outfit_list)

    return f"{caption}\n\n{item_details}\n\n{outfit_str}"
