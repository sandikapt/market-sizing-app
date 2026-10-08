TEXT = """
**What it does**

Takes a topline revenue number per product per year and breaks it down into granular combinations of segment, region, industry (and optionally company) using percentage weights you define in the input Excel.

**Input sheets**

| Sheet | Purpose |
|---|---|
| `topline` | Revenue per product per year — this is the number that gets locked and distributed |
| `yearref` | Maps column codes (y1, y2…) to actual years |
| `gs_segment_input` | Weight per segment per product (must sum to 100%) |
| `gs_region_input` | Weight per region per product (must sum to 100%) |
| `gs_industry_input` | Weight per industry per product (must sum to 100%) |
| `gs_company_input` | Weight per company per product (optional, must sum to 100%) |
| `block_list` | Combinations to exclude (empty column = match all) |

**How distribution works**

1. All valid segment x region x industry (x company) combinations are built per product
2. Blocklist removes impossible combinations (e.g. Government + specific company)
3. Combined weight = segment% x region% x industry% (x company%)
4. Each combination gets: topline x (its weight / sum of all weights for that product-year)
5. Because weights are normalized per product-year, topline per product is always preserved exactly

**Why effective share is not equal to input weight**

If some combinations are blocked, the blocked share gets redistributed proportionally to the remaining combinations. So a region weight of 14.0% might show as 14.05% effective share — that is the blocklist effect, not a bug.

**Editing weights**

When you edit a weight below, only that product is affected. The difference is redistributed within the same product-year. Other products stay untouched.
"""
