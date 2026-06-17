# FitFindr

FitFindr is an AI-powered thrift shopping assistant. You describe what you're looking for, and it searches a mock secondhand listings dataset, suggests an outfit using your existing wardrobe, and generates a shareable fit card caption — all in one flow.

Built with Python, Groq (llama-3.3-70b-versatile), and Gradio.

## Setup

```bash
pip install -r requirements.txt
```

Add your Groq API key to a `.env` file in the project root (free key at [console.groq.com](https://console.groq.com)):
```
GROQ_API_KEY=your_key_here
```

Run the app:
```bash
python app.py
```

Or test the agent directly from the terminal:
```bash
python agent.py
```

---

## 🛠️ Tool Inventory

### Tool 1: `search_listings`

**Purpose:** Searches the mock listings dataset (`data/listings.json`) for items matching the user's description with optional size and price filters. No LLM involved — pure keyword scoring.

**Parameters:**
- `description` (str) — free-text keywords describing what the user wants, e.g. `"vintage graphic tee"`
- `size` (str | None) — size string to filter by, e.g. `"M"`, `"W28"`, `"S/M"`. Case-insensitive substring match against the listing's size field. Pass `None` to skip.
- `max_price` (float | None) — maximum price in USD, inclusive. Pass `None` for no limit.

**Output:** A list of up to 3 listing dicts sorted by relevance score (highest first). Each dict has `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`. Returns `[]` if nothing matches — never raises.

**Scoring:** Each keyword from the description is checked against the listing's `title` (+2), `style_tags` (+2), and `description` text (+1). Listings that score 0 are dropped before sorting.

---

### Tool 2: `suggest_outfit`

**Purpose:** Given a new thrifted item and the user's wardrobe, calls the Groq LLM to pick 1–3 complementary wardrobe pieces and write a short styling note. Skips the LLM entirely if the wardrobe is empty.

**Parameters:**
- `new_item` (dict) — a listing dict from `search_listings`, must have at least `title`, `category`, `colors`, `style_tags`
- `wardrobe` (dict) — a wardrobe dict with an `items` key containing a list of wardrobe item dicts (each with `id`, `name`, `category`, `colors`, `style_tags`)

**Output:** A dict with three keys:
- `new_item` (dict) — the original listing, passed through so the next tool has everything in one place
- `outfit` (list[dict]) — wardrobe items chosen by the LLM; empty list if wardrobe was empty
- `styling_note` (str) — 1–2 sentence explanation of why the pieces work together

---

### Tool 3: `create_fit_card`

**Purpose:** Calls the Groq LLM at `temperature=0.9` to generate a casual OOTD caption, then combines it with a formatted item details line and a ★/· outfit list into one final string.

**Parameters:**
- `outfit` (dict) — the dict returned by `suggest_outfit`, needs `styling_note` and `outfit` keys
- `new_item` (dict) — the listing dict for the thrifted item

**Output:** A formatted string with three parts:
1. A 2–3 sentence social-style caption (LLM-generated)
2. `[title] — $[price], [condition] condition, via [platform]`
3. A full outfit list — new item prefixed with `★`, wardrobe items with `·`

Returns a descriptive error string if `outfit` is falsy or `new_item` is `None` — never raises.

---

## 🔁 How the Planning Loop Works

The planning loop lives in `run_agent()` in `agent.py`. It runs once per query and follows this exact conditional logic:

**Step 1 — Parse the query with regex, no LLM**

`_parse_query()` extracts three things from the raw query string:
- `max_price` — matches `"under $30"`, `"below $40"`, `"max $50"`, `"less than $25"`
- `size` — matches `"size M"`, `"size W28"`, etc.
- `description` — what's left after stripping those phrases and cleaning up whitespace

If `description` is empty after stripping, `session["error"]` is set and `run_agent()` returns immediately. No tools are called.

**Step 2 — Call `search_listings`, hard stop if empty**

`search_listings(description, size, max_price)` runs and the result is stored in `session["search_results"]`. If the list is empty, `session["error"]` is set with a message that fills in the actual query, size, and price, and the loop returns early. This is a hard stop — `suggest_outfit` and `create_fit_card` are never called when there are no results.

**Step 3 — Pick the top result, call `suggest_outfit`**

`session["selected_item"]` is set to `results[0]`. Then `suggest_outfit` is called with the selected item and the user's wardrobe. If the wardrobe is empty, `suggest_outfit` returns `outfit=[]` immediately without making any API call. The loop does not stop here — it continues to step 4 regardless.

**Step 4 — Call `create_fit_card`**

`create_fit_card` is called with `session["outfit_suggestion"]` and `session["selected_item"]`. If the inputs are invalid, it returns an error string instead of raising. Either way the result is stored in `session["fit_card"]` and the loop continues to step 5.

**Step 5 — Return the completed session**

The full session dict is returned. `handle_query()` in `app.py` reads the keys and populates the three Gradio output panels.

---

## 🗂️ State Management

All state lives in a single `session` dict initialized by `_new_session()` at the start of each `run_agent()` call. Tools do not pass data directly to each other, everything flows through the session.

| Key | Type | Set when | Used by |
|---|---|---|---|
| `session["query"]` | str | Session start | Reference only |
| `session["parsed"]` | dict | After `_parse_query()` | Unpacked into `description`, `size`, `max_price` for tool calls |
| `session["wardrobe"]` | dict | Session start, passed in from `app.py` | Read by `suggest_outfit` |
| `session["search_results"]` | list[dict] | After `search_listings` returns | `[0]` → `selected_item`; `[1:]` shown as "Also found" in the UI |
| `session["selected_item"]` | dict | Set to `results[0]` after a successful search | Passed as `new_item` to `suggest_outfit` and `create_fit_card` |
| `session["outfit_suggestion"]` | dict | After `suggest_outfit` returns | Passed as `outfit` to `create_fit_card`; formatted for UI panel 2 |
| `session["fit_card"]` | str | After `create_fit_card` returns | Shown in UI panel 3 |
| `session["error"]` | str or None | Set at any early-exit branch | Checked first in `handle_query()`; if set, shown in panel 1 and panels 2–3 are empty |

---

## ⚠️ Error Handling

**`search_listings` — no results match the query**

If the filtered and scored list is empty, `run_agent()` sets `session["error"]` and returns without calling any LLM tool.

Tested with:
```python
search_listings("designer ballgown", size="XXS", max_price=5)
# → []
```
Agent response: *"I couldn't find any listings matching 'designer ballgown' in size XXS under $5. Try broader keywords — for example, 'graphic tee' instead of 'vintage band tee' — or remove the size or price filter and try again."*

---

**`suggest_outfit` — wardrobe is empty**

If `wardrobe["items"]` is empty, `suggest_outfit` short-circuits before any API call and returns a dict with `outfit=[]`.

Tested with:
```python
suggest_outfit(results[0], get_empty_wardrobe())
# → {'new_item': {...}, 'outfit': [], 'styling_note': 'Wardrobe is empty.'}
```
The loop continues to `create_fit_card` so the user still gets a fit card — just without any wardrobe pairings listed.

---

**`create_fit_card` — outfit is missing or incomplete**

If the `outfit` argument is falsy or `new_item` is `None`, `create_fit_card` returns an error string instead of crashing.

Tested with:
```python
create_fit_card("", results[0])
# → "Error: outfit data is incomplete — try running the search again."
```
This string gets stored in `session["fit_card"]` and displayed in the UI's fit card panel.

---

## 🪞 Spec Reflection

**One way planning.md helped:**

The Planning Loop section was specific enough that it translated almost directly into code. Writing out "if results == [], set error and return early, do NOT proceed to suggest_outfit" before implementation meant I didn't have to make that architectural decision while coding. The five-step structure in planning.md maps one-to-one to the five comment blocks in `run_agent()`.

**One way the implementation diverged from the spec:**

Planning.md named the session key `"last_search_results"`, but the actual stub in `agent.py` defined the key as `"search_results"`. I went with `"search_results"` to match the stub. The spec also described `suggest_outfit` as returning a `str`, but it needed to return a structured dict so that `create_fit_card` could build the ★/· outfit list deterministically without having to parse free text. The type annotations in the original stubs were placeholders — the task description was more specific about the return format, so I followed that instead.

---

## 🤖 AI Usage

**Instance 1 — Implementing `search_listings`**

I gave Claude the Tool 1 spec from planning.md (description, parameter table, return value, failure mode) and the `load_listings()` docstring from `utils/data_loader.py`. I asked it to implement keyword scoring across `title`, `description`, and `style_tags`.

What it produced: a working implementation, but with equal weights (+1) for all three fields. I revised the scoring to give `style_tags` and `title` +2 points and `description` text only +1, because style_tags are the most intentional signal in the dataset — a listing tagged `"graphic tee"` is much stronger evidence than one that just happens to use the word "tee" in a sentence. I verified by running `search_listings("vintage graphic tee", None, 50)` and confirming that lst_006 (the bootleg tee) ranked first.

**Instance 2 — Implementing `suggest_outfit`**

I gave Claude the Tool 2 spec from planning.md, the wardrobe schema from `data/wardrobe_schema.json`, and the requirement that the empty wardrobe case must return immediately without an API call.

What it produced: the core Groq API call with a prompt asking for a JSON object with `outfit_item_ids` and `styling_note`. I added the markdown fence stripping step (`re.sub(r"```(?:json)?\n?", ...)`) after testing revealed that `llama-3.3-70b-versatile` sometimes wraps its JSON in ` ```json ` blocks even when the prompt explicitly says not to. I also added the `except (json.JSONDecodeError, KeyError)` fallback that keeps the raw LLM text as `styling_note` rather than crashing, so the tool degrades gracefully on a malformed response.
