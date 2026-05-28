---
name: product-catalog-finder
description: Fuzzy local product catalog search skill. Use when Codex needs to find product information, images, documents, or cached scrape results from local scraped_data folders based on user descriptions, category names, style numbers, color names, product names, or vague ecommerce search intent. Reads catalog_index.json when available, falls back to scanning product.json files, and returns matched product data plus local image and document paths.
---

# Product Catalog Finder

Use this skill to answer product lookup requests from local scraped product data. Do not scrape the web first. Search local catalog indexes and product folders. Only suggest or call a scraper skill when the user explicitly provides a concrete product or category URL.

## Workflow

1. Interpret the user's intent as a fuzzy product query: category, style number, product name, color, brand, material, or descriptive phrase.
2. Run `scripts/find_products.py` against likely local data roots.
3. Prefer `catalog_index.json` when present. Fall back to recursive `product.json` discovery.
4. Return the best matches with product identity, local JSON/DOCX paths, image directory, and top image paths.
5. If nothing matches locally and the user did not provide a URL, say that no cached product was found and ask the user to provide a product or category URL before scraping.
6. If nothing matches locally and the user did provide a URL, recommend using the relevant scraper skill with that exact URL.

## Common Data Roots

Try the roots explicitly provided by the user first. Otherwise check likely local folders:

- `scraped_data`
- `../scraped_data`
- `D:/python_test/scraped_data`
- `D:/python_test/scraped_data_fulltest`

## Standard Commands

Search with a natural-language query:

```bash
python scripts/find_products.py "p6 logo tee green" --root D:/python_test/scraped_data
```

Search multiple local roots:

```bash
python scripts/find_products.py "38504 POGM" --root D:/python_test/scraped_data --root D:/python_test/scraped_data_fulltest
```

Return JSON for downstream processing:

```bash
python scripts/find_products.py "mens t shirts recycled cotton" --json
```

Return Markdown with local image previews:

```bash
python scripts/find_products.py "POGM 38504" --root D:/python_test/scraped_data --markdown
```

## Output Guidance

When responding to users, include:

- Matched product name, style number, brand, price, and category when available.
- Why it matched: style number, color, keyword, product name, or category.
- Local paths to `product.json`, `product.docx`, `image_dir`, and representative image files.
- Use `--markdown` when the answer should visually show product images in Codex Desktop.
- A note if results are from cached local data and may be stale.
- Never invent, search for, or infer a URL for scraping from a category name or product description. Scraping requires a user-provided URL.

Use absolute filesystem paths in Markdown links or image tags when showing local media in Codex Desktop.
