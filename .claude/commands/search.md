Run a full literature search and push results to Notion.

Arguments: $ARGUMENTS

---

**Parse $ARGUMENTS** (all optional except query):
- First quoted string or the full input = **query**
- `classic` / `frontier` / `balanced` = **mode** (default: balanced)
- A known perspective key = **perspective** (default: none)
- Any other single word that looks like a discipline or theory = **unknown perspective** → see below
- `snowball` = set do_snowball=true
- A number (e.g. `30`) = **max_results** (default: 20)

If $ARGUMENTS is empty, ask the user for a query before proceeding.

---

**Auto-add unknown perspectives**

Before searching, call `mcp__lit_search__list_perspectives_tool` to get the current list.

If the user specified a perspective that is NOT in that list:
1. Use your knowledge to generate appropriate `theorists`, `core_concepts` (6-10 items), and `seed_terms` (6-10 database-friendly phrases) for that perspective.
2. Call `mcp__lit_search__add_perspective` to save it permanently.
3. Confirm to the user: "Added new perspective: [label]" — then continue with the search.

---

**Step 1 — Search**

Call `mcp__lit_search__search_literature` with the parsed parameters.
When done, report:
- Total papers found and after dedup
- Source breakdown (by_source from stats)
- Top 5 paper titles with year and citation count

**Step 2 — Export to Notion**

Immediately call `mcp__lit_search__export_to_notion` with:
- papers = the full papers list from Step 1
- query, mode, perspective = same values used in Step 1
- stats = the stats dict from Step 1

Report the Notion page URL when done.

**Step 3 — Summary**

Print a concise markdown summary:
- Query and parameters used
- Paper count (raw → dedup'd)
- Notion page link
- Top 10 papers as a numbered list: Title (Year) — first author — N citations

Do not ask for confirmation between steps — run all automatically.
