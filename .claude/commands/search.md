Run a full literature search using WebFetch and push results to Notion.

Arguments: $ARGUMENTS

---

## Parse $ARGUMENTS

All optional except query:
- First quoted string or the full input (up to any keyword below) = **query**
- `classic` / `frontier` / `balanced` = **mode** (default: `balanced`)
- A perspective key (see list below) or any theoretical/disciplinary word = **perspective** (default: none)
- `snowball` = enable citation snowballing (fetch references of top 5 papers)
- A number (e.g. `30`) = **max_results** per source (default: 20)

If $ARGUMENTS is empty, ask the user for a query before proceeding.

---

## Known Perspectives (seed terms embedded)

Use these seed terms to enrich the search query. If the user provides a perspective key listed here, append its seed terms to the search. If the user provides an unknown perspective name, use your knowledge to generate 4–6 relevant seed phrases for it — no API call needed.

- **profession**: professional work, jurisdiction, expertise, occupational closure, professionalization, Freidson professionalism
- **organization**: institutional theory, organizational isomorphism, DiMaggio Powell institutional, organizational legitimacy, neo-institutionalism
- **symbolic**: symbolic interactionism, Goffman presentation self, identity construction, framing theory, meaning-making sociology
- **stratification**: social stratification Bourdieu, cultural capital habitus, class analysis sociology, social reproduction inequality
- **network**: social network analysis, Granovetter weak ties, structural holes Burt, network embeddedness, social capital networks
- **knowledge**: sociology of knowledge Berger Luckmann, social construction reality, epistemic community, Latour actor-network theory
- **feminist**: feminist theory, intersectionality Crenshaw, Butler gender performativity, care ethics gender, gender inequality labor
- **governance**: governance policy, Foucault power discourse, Habermas public sphere, bureaucracy state, regulatory governance
- **political_economy**: political economy, Polanyi embeddedness market, varieties of capitalism, labor market institutions, financialization
- **psychology**: social identity theory Tajfel, self-efficacy Bandura, cognitive bias decision-making, burnout work stress, psychological safety
- **postcolonial**: postcolonial theory Said Orientalism, Spivak subaltern, decolonial theory Quijano, coloniality of power, Global South knowledge
- **historical**: path dependency historical institutionalism, Thelen institutional change, critical juncture, comparative historical analysis
- **sts**: social construction technology SCOT, Jasanoff sociotechnical imaginaries, algorithmic accountability, AI ethics governance
- **time_allocation**: time use diary, Becker household production, work-family balance, time poverty, life course transitions, Hochschild second shift

---

## Step 1 — Build Search Terms

1. Extract 3–5 core keywords from the query (strip stop words, keep meaningful nouns/phrases).
2. If a perspective was given (known or unknown), append 3–4 of its seed phrases.
3. For `frontier` mode: append `"recent" OR "emerging" OR "new"` to the boolean string.
4. Construct a URL-encoded search string: join keywords with `+`.

---

## Step 2 — Fetch Papers via WebFetch

Run **all three** source fetches. Use max_results as the per_page value (cap at 50).

**OpenAlex** (highest priority — broadest coverage):
```
https://api.openalex.org/works?search={SEARCH_STRING}&per_page={max_results}&sort=cited_by_count:desc&select=id,title,publication_year,authorships,doi,cited_by_count,primary_location,open_access
```
For `frontier` mode, add `&filter=publication_year:>{CURRENT_YEAR-2}` and sort by `publication_date:desc`.

**Semantic Scholar** (citation graph):
```
https://api.semanticscholar.org/graph/v1/paper/search?query={SEARCH_STRING}&limit={max_results}&fields=title,year,authors,citationCount,externalIds,openAccessPdf
```

**CrossRef** (DOI metadata):
```
https://api.crossref.org/works?query={SEARCH_STRING}&rows={max_results}&sort=is-referenced-by-count&order=desc&select=title,author,published,DOI,is-referenced-by-count,URL
```

Parse results into a unified paper list. Each paper should have:
- `title`, `year`, `authors` (list of name strings), `doi`, `url`, `citation_count`, `source` (openalex/s2/crossref)

---

## Step 3 — Deduplicate

1. Group papers by DOI (exact match) — keep the copy with the highest citation_count.
2. For papers without DOI, compare titles: if two titles share >85% of words, keep one.
3. Count: raw_total (sum across sources), after_dedup.

---

## Step 4 — Optional Snowballing

If `snowball` was requested and there are ranked results:
- Take the top 3 papers with a DOI.
- For each, fetch S2 references:
  ```
  https://api.semanticscholar.org/graph/v1/paper/{DOI}/references?fields=title,year,authors,citationCount,externalIds&limit=20
  ```
- Filter new papers: keep only those whose title contains at least one of the original query keywords.
- Add surviving papers to the pool and re-deduplicate.

---

## Step 5 — Rank

- `classic`: sort by citation_count descending.
- `frontier`: sort by year descending, then citation_count.
- `balanced`: sort by `citation_count * 0.6 + (year - 2000) * 2` descending.

Take top 50.

---

## Step 6 — Export to Notion

Call `mcp__c2c9a715-7d5a-478f-ac15-9b58511e27e3__notion-create-pages` with:

```json
{
  "parent": {"database_id": "32f87c1298c2804bbf70d96984ed8e05"},
  "properties": {
    "Name": {"title": [{"text": {"content": "Search: {QUERY} [{MODE}]"}}]},
    "Tags": {"multi_select": [{"name": "{MODE}"}, {"name": "{PERSPECTIVE or 'general'}"}]}
  },
  "children": [
    {
      "object": "block",
      "type": "callout",
      "callout": {
        "rich_text": [{"type": "text", "text": {"content": "Query: {QUERY}\nMode: {MODE} | Perspective: {PERSPECTIVE}\nDate: {TODAY}"}}],
        "icon": {"emoji": "🔍"},
        "color": "blue_background"
      }
    },
    {
      "object": "block",
      "type": "paragraph",
      "paragraph": {
        "rich_text": [{"type": "text", "text": {"content": "Sources: OpenAlex + Semantic Scholar + CrossRef | Raw: {RAW_TOTAL} → Dedup'd: {AFTER_DEDUP}"}}]
      }
    },
    {
      "object": "block",
      "type": "divider",
      "divider": {}
    },
    {
      "object": "block",
      "type": "heading_2",
      "heading_2": {"rich_text": [{"type": "text", "text": {"content": "Top Papers"}}]}
    }
  ]
}
```

Then append numbered list items for up to 50 papers. For each paper, format as:
`{N}. {Title} ({Year}) — {First Author} — {citation_count} citations — DOI: {doi}`

If the Notion create-pages call has a 100-block limit, split into two calls: first call creates the page with header blocks + first ~45 papers; second call appends remaining papers using `mcp__c2c9a715-7d5a-478f-ac15-9b58511e27e3__notion-update-page` or a second create with the page ID as parent.

---

## Step 7 — Summary

Print a concise markdown summary:

```
## Search Results: {QUERY}

**Parameters:** mode={MODE} | perspective={PERSPECTIVE} | sources=OpenAlex,S2,CrossRef
**Papers:** {RAW_TOTAL} raw → {AFTER_DEDUP} after dedup
**Notion:** {PAGE_URL}

### Top 10 Papers
1. Title (Year) — First Author — N citations
...
```

Do not ask for confirmation between steps — run all steps automatically.
