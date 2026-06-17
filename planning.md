# FitFindr — planning.md

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
Loads all 40 listings from `data/listings.json` via `load_listings()` and filters them based on a text description, an optional size, and an optional max price. It scores each listing by how many of the user's description keywords appear in that listing's `title`, `description`, and `style_tags` fields, then returns the top 3 matches sorted by score (highest first).

**Input parameters:**
- `description` (str): Free-text description of what the user wants — e.g., `"vintage graphic tee"` or `"flannel shirt"`. The function tokenizes this into lowercase words and checks how many match each listing's title, description text, and style_tags list.
- `size` (str, optional): Size string to filter by, e.g., `"M"`, `"W28"`, `"S/M"`. Matched as a case-insensitive substring against the listing's `size` field. Pass `None` to skip size filtering.
- `max_price` (float, optional): The maximum price the user is willing to pay. Any listing where `price > max_price` is excluded before scoring. Pass `None` for no price limit.

**What it returns:**
A list of up to 3 listing dicts, sorted from most to least relevant. Each dict has these fields (all come directly from `listings.json`):
- `id` (str): Unique listing ID, e.g., `"lst_006"`
- `title` (str): Short item name, e.g., `"Graphic Tee — 2003 Tour Bootleg Style"`
- `description` (str): Full item description text
- `category` (str): One of `tops`, `bottoms`, `outerwear`, `shoes`, `accessories`
- `style_tags` (list[str]): Style descriptors like `["graphic tee", "vintage", "grunge"]`
- `size` (str): Size string, e.g., `"L"` or `"W30"`
- `condition` (str): One of `excellent`, `good`, `fair`
- `price` (float): Listing price in USD
- `colors` (list[str]): List of color strings
- `brand` (str or None): Brand name, or `null` if unbranded
- `platform` (str): Where it's listed — `depop`, `thredUp`, or `poshmark`

Returns an empty list `[]` if nothing passes the filters or nothing scores above 0.

**What happens if it fails or returns nothing:**
If the returned list is empty, the agent tells the user: *"I couldn't find any listings matching '[description]' with those filters. Try using broader keywords (e.g., 'graphic tee' instead of 'vintage band tee'), or remove the size/price filter and search again."* The agent stops here and does not call suggest_outfit or create_fit_card.

---

### Tool 2: suggest_outfit

**What it does:**
Given a new listing the user is considering buying and their existing wardrobe, picks the best-matching items from the wardrobe to build a complete outfit. Compatibility is scored by: (1) style tag overlap between the new item and each wardrobe piece, and (2) color compatibility (neutrals like black/white/tan pair with anything; colors match if they share a tag). It tries to return one item per complementary category — e.g., if the new item is a top, it picks the best matching bottom, shoes, and optionally an outerwear piece.

**Input parameters:**
- `new_item` (dict): A listing dict returned by `search_listings`. Must have at least `title`, `category`, `colors`, and `style_tags`. This is the thrifted piece being styled.
- `wardrobe` (dict): A wardrobe dict with a single `items` key containing a list of wardrobe item dicts. Each wardrobe item has `id`, `name`, `category`, `colors`, `style_tags`, and optional `notes`. This matches the format defined in `data/wardrobe_schema.json` and returned by `get_example_wardrobe()`.

**What it returns:**
A dict with three keys:
- `new_item` (dict): The same listing dict passed in, included so the next tool has everything in one place
- `outfit` (list[dict]): A list of 1–3 wardrobe items selected to pair with the new item. Each wardrobe item dict keeps all its original fields (`id`, `name`, `category`, `colors`, `style_tags`, `notes`).
- `styling_note` (str): A 1–2 sentence explanation of why these pieces work together, e.g., `"The faded grey tee's grunge tags match your black combat boots, and the dark wash jeans keep the palette grounded."`

**What happens if it fails or returns nothing:**
If `wardrobe["items"]` is an empty list, the agent responds: *"Your wardrobe is empty, so I can't suggest a full outfit yet. Based on this item's style tags ([style_tags]), it would pair well with dark denim, chunky sneakers, or layered outerwear. Add some items to your wardrobe for real pairings next time."* The agent still continues to `create_fit_card` but passes an outfit with an empty `outfit` list so the fit card only covers the new item.

---

### Tool 3: create_fit_card

**What it does:**
Takes the complete outfit suggestion from `suggest_outfit` and generates a formatted, social-media-ready fit card. It combines the thrifted item's details (price, platform, condition) with the wardrobe pairings into a short caption and a structured outfit list. This is the final output the user actually sees.

**Input parameters:**
- `outfit` (dict): The dict returned by `suggest_outfit`. Must have:
  - `new_item` (dict): The listing being styled, with at least `title`, `price`, `condition`, `platform`, `style_tags`
  - `outfit` (list[dict]): The wardrobe items to pair with it (can be empty if wardrobe was empty)
  - `styling_note` (str): The styling explanation from suggest_outfit

**What it returns:**
A dict with three keys:
- `caption` (str): A 2–3 sentence social-style caption describing the full look. Example: *"Thrifted this 2003 Tour Bootleg tee off Depop for $24 — good condition, barely worn-in. Styled it with my dark wash baggy jeans and black combat boots for a classic grunge fit. Thrift smarter, not harder."*
- `item_details` (str): A one-liner summary of the thrifted item: `"[title] — $[price], [condition] condition, via [platform]"`
- `full_outfit_list` (list[str]): Every item in the look as a formatted string. The new thrifted item is marked with `★` at the front, wardrobe items are prefixed with `·`. Example: `["★ Graphic Tee — 2003 Tour Bootleg Style ($24, Depop)", "· Baggy straight-leg jeans, dark wash", "· Black combat boots"]`

**What happens if it fails or returns nothing:**
If the `outfit` dict is missing the `new_item` key or `new_item` is `None`, the agent says: *"Something went wrong building the fit card — the item data is incomplete. Here's what I found: try searching again or check that the listing is still available."* If `outfit["outfit"]` is empty (empty wardrobe case), the function still runs and just produces a fit card with only the new item listed.

---

### Additional Tools (if any)

None for Milestone 3/4. Potential stretch: a `save_to_wardrobe` tool that appends a purchased listing to the user's wardrobe dict so future outfit suggestions improve over time.

---

## Planning Loop

**How does your agent decide which tool to call next?**

The planning loop runs once per user message. Here's the exact conditional logic it follows:

**Step 1 — Parse user input.**
Extract three things from the message: a description string (required), a size string (optional, default `None`), and a max_price float (optional, default `None`). If no description is found, return: *"I need a description of what you're looking for — try something like 'vintage denim jacket' or 'graphic tee under $30'."*

**Step 2 — Call search_listings.**
Call `search_listings(description, size, max_price)`. Check the return value:
- If `results == []` (empty list): set error message to *"No listings matched '[description]'..."* (full message in Error Handling section), return early, done.
- If `len(results) >= 1`: set `session_state["last_search_results"] = results`, set `session_state["selected_item"] = results[0]`, continue to Step 3.

**Step 3 — Call suggest_outfit.**
Call `suggest_outfit(new_item=session_state["selected_item"], wardrobe=session_state["wardrobe"])`.
- If `wardrobe["items"] == []` (empty wardrobe): suggest_outfit still returns a valid dict but with `outfit=[]`. Set `session_state["outfit_suggestion"] = result`. Log a note that wardrobe was empty. Continue to Step 4 anyway.
- If `wardrobe["items"]` is non-empty and suggest_outfit returns a dict with `outfit` containing at least 1 item: set `session_state["outfit_suggestion"] = result`. Continue to Step 4.

**Step 4 — Call create_fit_card.**
Call `create_fit_card(outfit=session_state["outfit_suggestion"])`.
- If `create_fit_card` raises an exception or returns `None`: return partial result — show the listing title, price, platform, and the styling_note from session_state["outfit_suggestion"]. Done.
- If it succeeds: set `session_state["fit_card"] = result`. Continue to Step 5.

**Step 5 — Return final output.**
Format and return the fit card to the user: `caption`, `item_details`, and `full_outfit_list`. Include all other search results (results[1] and results[2]) as *"also found:"* at the bottom. Done.

---

## State Management

**How does information from one tool get passed to the next?**

The agent maintains a single `session_state` dict for the duration of a conversation session. It is initialized at the start of the session and updated in-place after each tool call. Here's exactly what's stored and when:

| Variable | Type | Set when | Used by |
|---|---|---|---|
| `session_state["wardrobe"]` | dict (wardrobe format from wardrobe_schema.json) | Session start — initialized with `get_example_wardrobe()` or `get_empty_wardrobe()` | suggest_outfit reads this every call |
| `session_state["last_search_results"]` | list[dict] | After search_listings returns a non-empty list | Displayed to user as "also found" items; could be used by future stretch tools |
| `session_state["selected_item"]` | dict (listing) | After search_listings — set to `results[0]` | Passed as `new_item` to suggest_outfit |
| `session_state["outfit_suggestion"]` | dict (with new_item, outfit, styling_note keys) | After suggest_outfit returns | Passed as `outfit` to create_fit_card |
| `session_state["fit_card"]` | dict (with caption, item_details, full_outfit_list keys) | After create_fit_card returns | Returned to user as final output |

Tools do not pass data directly to each other — they only read from and write to `session_state`. This means if the user asks a follow-up question (e.g., "show me the second result instead"), the agent can pull `session_state["last_search_results"][1]` and re-run from Step 3 without calling search_listings again.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | "I couldn't find any listings matching '[description]'[and those filters]. Try broader keywords — for example, 'graphic tee' instead of 'vintage distressed band tee' — or remove the size or price filter and try again." |
| suggest_outfit | Wardrobe is empty | "Your wardrobe is empty, so I can't pair this with anything you own yet. Based on its style tags ([style_tags from new_item]), this piece would work well with dark denim, chunky sneakers, or a classic layer on top. Add some wardrobe items and I can give you real outfit pairings." |
| create_fit_card | Outfit input is missing or incomplete (new_item is None or missing required keys) | "I hit a snag generating the fit card — the outfit data looks incomplete. Here's what I have: [title] — $[price], [condition] condition, via [platform]. [styling_note from outfit_suggestion]. Try running the search again to get a fresh result." |

---

## Architecture

```
User message
     │
     ▼
┌─────────────────────────────────────────────────────────────────┐
│                        PLANNING LOOP                            │
│                                                                 │
│  1. Parse description, size, max_price from user message        │
│     │                                                           │
│     ├── no description found ──────────────────────────────►  "Tell me what you're looking for"  STOP
│     │                                                           │
│     ▼                                                           │
│  2. call search_listings(description, size, max_price)          │
│     │                                                           │
│     ├── results == [] ─────────────────────────────────────►  "No listings matched..." STOP
│     │                                                           │
│     ▼  results[0] → session_state["selected_item"]             │
│                                                                 │
│  3. call suggest_outfit(selected_item, wardrobe)                │
│     │                                                           │
│     ├── wardrobe.items == [] ──► outfit={} but CONTINUE        │
│     │                             (note empty wardrobe)        │
│     ▼  result → session_state["outfit_suggestion"]             │
│                                                                 │
│  4. call create_fit_card(outfit_suggestion)                     │
│     │                                                           │
│     ├── exception / None ──────────────────────────────────►  partial result (listing + styling note)  STOP
│     │                                                           │
│     ▼  result → session_state["fit_card"]                      │
│                                                                 │
│  5. Return fit_card to user (caption, item_details,             │
│     full_outfit_list) + "also found:" for results[1..2]        │
└─────────────────────────────────────────────────────────────────┘
         ▲           │           │            │
         │           │           │            │
         │    search_listings  suggest_outfit  create_fit_card
         │           │           │            │
         └───────────┴─────session_state──────┘
                           (wardrobe,
                            last_search_results,
                            selected_item,
                            outfit_suggestion,
                            fit_card)
```

**Error paths** branch off at steps 2, 3, and 4 as shown above. Each error path returns a user-facing message and stops — it does not fall through to the next tool.

---

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**

I'll use **Claude** (via Claude Code / claude-sonnet-4-6) to implement each of the three tools separately.

For `search_listings`: I'll paste in the Tool 1 spec from this file (description, parameter table, return value, failure mode) plus the `load_listings()` docstring from `utils/data_loader.py`. I'll ask Claude to implement `search_listings(description, size, max_price)` that calls `load_listings()`, scores each listing by keyword overlap between the description and the listing's title/description/style_tags fields, filters by size and price, and returns the top 3 as a list. I'll verify it by running 3 manual test cases: (1) `"graphic tee", None, 30.0` — should return lst_006 ($24) and lst_002 ($18); (2) `"flannel shirt", None, None` — should return lst_003; (3) `"dragon wizard cape", None, None` — should return `[]`.

For `suggest_outfit`: I'll paste in the Tool 2 spec plus the wardrobe schema from `data/wardrobe_schema.json` and the `get_example_wardrobe()` docstring. I'll ask Claude to implement `suggest_outfit(new_item, wardrobe)` that scores wardrobe items by style tag overlap with the new item, picks one complementary item per category, and returns the `{new_item, outfit, styling_note}` dict. I'll verify by calling it with lst_006 (graphic tee, category=tops, style_tags=["graphic tee","vintage","grunge","streetwear","band tee"]) and the example wardrobe — expected result: outfit should include the dark wash baggy jeans and black combat boots (both have grunge/streetwear tags). I'll also verify the empty wardrobe case returns `outfit=[]` without crashing.

For `create_fit_card`: I'll paste in the Tool 3 spec. I'll ask Claude to implement `create_fit_card(outfit)` that formats the caption, item_details string, and full_outfit_list from the suggest_outfit output. I'll verify by passing in a hardcoded suggest_outfit result and checking that the `★` prefix appears on the new item, `·` prefixes appear on wardrobe items, and the caption contains the price and platform name.

**Milestone 4 — Planning loop and state management:**

I'll use **Claude** (via Claude Code) to implement the planning loop.

I'll paste in the Planning Loop section and State Management table from this file — specifically the 5-step conditional logic and the session_state variable table. I'll ask Claude to implement a `run_agent(user_message, session_state)` function that parses the user message for description/size/max_price, calls the three tools in order, updates session_state after each call, and handles the three error branches (no description, empty results, empty wardrobe, failed fit card).

I'll verify by running the full example query from "A Complete Interaction" below and checking that: (1) search returns the graphic tee listing, (2) suggest_outfit returns baggy jeans + combat boots from the example wardrobe, (3) create_fit_card returns a caption with "$24" and "depop" in it. I'll also run two edge cases: the empty wardrobe path (swap in `get_empty_wardrobe()`) and the no-results path (query `"dragon wizard cape", None, None`).

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
First, the agent calls `search_listings("vintage graphic tee", size=None, max_price=30.0)`. It filters listings by description match and price, returning up to 3 results sorted by relevance. If no results are found, the agent tells the user to try different search terms and stops here.

**Step 2:**
Next, `search_listings` is returned as the top result: "Faded Band Tee — $22, Depop, Good condition." The agent calls `suggest_outfit(new_item=<band tee>, wardrobe=<user's wardrobe>)`, which uses the user's existing items (baggy jeans, chunky sneakers) to generate a styled outfit recommendation.

**Step 3:**
The agent calls `create_fit_card(outfit=<suggestion>, new_item=<band tee>)`, which generates a shareable social-style caption describing the full look and how the new item was thrifted.

**Final output to user:**
At the end, the user sees the top listing match, an outfit suggestion pairing the tee with their existing wardrobe, and a ready-to-share fit card caption.
