# Patagonia Reference

Use this reference only for Patagonia product pages or similar Salesforce Commerce Cloud / Demandware pages.

## Known Page Behavior

- Direct HTTP requests may return a "Hang Tight" verification page.
- Headless Chromium may be detected; use `--headed` when the page blocks automation.
- Product images are commonly served by Demandware CDN paths containing `dw/image/v2/BDJB_PRD/`.
- Direct image downloads can return 404 because the CDN expects browser context and referrer/session behavior.
- Visible HTML may contain placeholders while real images are loaded by JavaScript.

## Recommended Extraction Strategy

1. Start Playwright before making any page request.
2. Register route interception and response listeners before `page.goto()`.
3. Rewrite image width parameters from thumbnails such as `sw=512` to a stable larger size such as `sw=1400`.
4. Capture image bytes from Playwright `response` events instead of using `requests.get()`.
5. Extract text from `document.body.innerText` and parse stable labels such as `Style No.`, `Fit`, `Weight`, `Country of Origin`, and `Materials & Care Instructions`.
6. Discover color codes from `data-color`, current URL query parameters, and text patterns like `COLOR | Style No. 12345`.
7. Skip `data-color="000"`; it usually represents shared lifestyle media rather than a real color.
8. Visit each color variant URL and keep only variants that produce image responses.

## Useful Patterns

Style and color:

```regex
\b([A-Z0-9]{3,10})\s*\|\s*Style No\.\s*(\d{4,8})
```

Fit:

```regex
Fit\s+(Regular [Ff]it|Slim [Ff]it|Relaxed [Ff]it)
```

Weight:

```regex
Weight\s+(\d+)\s*g\s*\(([^)]+)\)
```

Country of origin:

```regex
Country of Origin\s+(Made in [^\n.]+)
```

## File Naming

Patagonia image filenames often follow `{style}_{color}_{type}.jpg`.

Common suffixes:

- No suffix: main flat product image
- `_GNL1` to `_GNL4`: model or general product images
- `_CDD1` to `_CDD4`: color-detail images
- `_ALTFRONT`: front view
- `_QB1` to `_QB4`: close detail
- `_HC1` or `_HC2`: hanger view
- `_STH1` or `_STH2`: studio or flat-lay detail
- `_000_LIFESTYLE1` to `_000_LIFESTYLE4`: shared lifestyle images

## Failure Modes

- `networkidle` may time out; prefer `domcontentloaded` plus explicit waits.
- `sw=1920` can fail or return no body; `sw=1400` is a safer default.
- Some discontinued colors remain in page data but produce no image response.
- Video thumbnails from `i.ytimg.com` should not be treated as product images unless the user explicitly requests video assets.
- Frontend changes can break selectors; when that happens, favor text and JSON-LD extraction over class-name selectors.
