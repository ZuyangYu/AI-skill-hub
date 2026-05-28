---
name: patagonia-scraper
description: General product-page scraping and documentation skill with a Patagonia adapter. Use when Codex needs to extract product data, images, color variants, pricing, materials, care details, or generate JSON/DOCX deliverables from Patagonia product URLs or similar ecommerce product pages. Supports Playwright-based browser scraping, image capture, structured output, and reusable troubleshooting for anti-bot or lazy-loaded product media.
---

# Product Page Scraping

Use this skill to turn ecommerce product pages into structured product data, downloaded images, and optional Word documents. Prefer the bundled script for repeatable work, then adapt only when the target site needs special handling.

## Workflow

1. Confirm the input URL and desired outputs: JSON, images, DOCX, or all.
2. Use `scripts/scrape_product.py` as the first implementation path.
3. For Patagonia URLs, use `--site patagonia` so the script enables Demandware image capture and color-variant handling.
4. Save outputs under `scraped_data/{product_id}/`.
5. If the script misses fields, inspect the page with Playwright and patch the smallest site-specific extractor.
6. Keep fragile site behavior in `references/`, not in this file.

## Bundled Resources

- `scripts/scrape_product.py`: CLI scraper for product pages. It extracts JSON-LD, common product metadata, visible text fields, images, and can generate DOCX output.
- `scripts/requirements.txt`: Python dependencies for the bundled script.
- `references/patagonia.md`: Patagonia-specific notes for Demandware/Salesforce Commerce Cloud pages, CDN image behavior, color variants, and failure modes.

## Standard Commands

Install dependencies when needed:

```bash
pip install -r scripts/requirements.txt
python -m playwright install chromium
```

Run a general product-page scrape:

```bash
python scripts/scrape_product.py "https://example.com/product" --site generic --outputs json images docx
```

Run a Patagonia scrape:

```bash
python scripts/scrape_product.py "https://www.patagonia.com/..." --site patagonia --outputs json images docx
```

Use a visible browser if the site blocks headless mode:

```bash
python scripts/scrape_product.py "https://www.patagonia.com/..." --site patagonia --headed
```

## Output Contract

Store one product per folder:

```text
scraped_data/
└── {product_id}/
    ├── images/
    ├── product.json
    └── product.docx
```

`product.json` should include these stable top-level keys when available:

- `source_url`
- `site`
- `product_id`
- `name`
- `brand`
- `price`
- `currency`
- `style_number`
- `color_code`
- `color_names`
- `description`
- `features`
- `materials`
- `care_instructions`
- `certifications`
- `images`
- `raw`

## Adaptation Rules

- Prefer structured sources first: JSON-LD, embedded product state, meta tags, then visible text.
- Use Playwright when content is rendered, lazy-loaded, protected by cookies, or image URLs are session-dependent.
- Capture image bytes from browser responses when direct HTTP downloads return 403/404.
- Keep browser routing and response listeners registered before `page.goto()`.
- Do not scatter output files in the skill folder. Use the current task workspace and `scraped_data/`.
- If a target site's terms, robots policy, login wall, or anti-bot flow makes scraping inappropriate, stop and explain the limitation.

## Patagonia Notes

Read `references/patagonia.md` when any of these are true:

- The URL is on `patagonia.com`.
- The page shows "Hang Tight" or similar browser verification.
- Product images load as Demandware CDN URLs.
- The user asks for all colors or high-resolution Patagonia images.
