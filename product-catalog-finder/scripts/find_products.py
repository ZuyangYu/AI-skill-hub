#!/usr/bin/env python
"""Fuzzy-search local scraped product catalogs and return product assets."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_ROOTS = [
    Path("scraped_data"),
    Path("../scraped_data"),
    Path("D:/python_test/scraped_data"),
    Path("D:/python_test/scraped_data_fulltest"),
]


@dataclass
class ProductRecord:
    product_id: str = ""
    style_number: str = ""
    name: str = ""
    brand: str = ""
    site: str = ""
    source_url: str = ""
    category: str = ""
    price: str = ""
    currency: str = ""
    colors: list[str] = field(default_factory=list)
    color_names: dict[str, str] = field(default_factory=dict)
    keywords: list[str] = field(default_factory=list)
    json_path: str = ""
    docx_path: str = ""
    image_dir: str = ""
    image_count: int = 0
    raw: dict[str, Any] = field(default_factory=dict)


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


def tokenize(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", normalize(value))


def unique(values: list[str]) -> list[str]:
    seen = set()
    out = []
    for value in values:
        value = normalize(str(value))
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def load_records(roots: list[Path]) -> list[ProductRecord]:
    records: list[ProductRecord] = []
    seen = set()
    for root in roots:
        root = root.expanduser()
        if not root.exists():
            continue

        index_path = root / "catalog_index.json"
        if index_path.exists():
            for record in load_index(index_path):
                key = (record.site, record.product_id, record.json_path)
                if key not in seen:
                    seen.add(key)
                    records.append(record)

        for product_path in root.rglob("product.json"):
            record = load_product_json(product_path)
            if not record:
                continue
            key = (record.site, record.product_id, record.json_path)
            if key not in seen:
                seen.add(key)
                records.append(record)
    return records


def load_index(index_path: Path) -> list[ProductRecord]:
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    records = []
    for item in data.get("products", []):
        if not isinstance(item, dict):
            continue
        records.append(
            ProductRecord(
                product_id=str(item.get("product_id", "")),
                style_number=str(item.get("style_number", "")),
                name=str(item.get("name", "")),
                brand=str(item.get("brand", "")),
                site=str(item.get("site", "")),
                source_url=str(item.get("source_url", "")),
                category=str(item.get("category", "")),
                price=str(item.get("price", "")),
                currency=str(item.get("currency", "")),
                colors=list(item.get("colors") or []),
                color_names=dict(item.get("color_names") or {}),
                keywords=list(item.get("keywords") or []),
                json_path=str(item.get("json_path", "")),
                docx_path=str(item.get("docx_path", "")),
                image_dir=str(item.get("image_dir", "")),
                image_count=int(item.get("image_count") or 0),
                raw=item,
            )
        )
    return records


def load_product_json(product_path: Path) -> ProductRecord | None:
    try:
        data = json.loads(product_path.read_text(encoding="utf-8"))
    except Exception:
        return None

    product_dir = product_path.parent
    image_dir = product_dir / "images"
    docx_path = product_dir / "product.docx"
    local_images = [img for img in data.get("images", []) if img.get("filename")]
    variants = data.get("variants") or []
    colors = [v.get("color_code") for v in variants if v.get("color_code")]
    colors.extend((data.get("raw", {}) or {}).get("discovered_colors") or [])

    keywords = build_keywords_from_product(data)
    return ProductRecord(
        product_id=str(data.get("product_id", "")),
        style_number=str(data.get("style_number", "")),
        name=str(data.get("name", "")),
        brand=str(data.get("brand", "")),
        site=str(data.get("site", "")),
        source_url=str(data.get("source_url", "")),
        category=category_from_url(str(data.get("source_url", ""))),
        price=str(data.get("price", "")),
        currency=str(data.get("currency", "")),
        colors=unique(colors),
        color_names=dict(data.get("color_names") or {}),
        keywords=keywords,
        json_path=str(product_path),
        docx_path=str(docx_path) if docx_path.exists() else "",
        image_dir=str(image_dir) if image_dir.exists() else "",
        image_count=len(local_images) or count_images(image_dir),
        raw=data,
    )


def build_keywords_from_product(data: dict[str, Any]) -> list[str]:
    values = [
        data.get("product_id", ""),
        data.get("style_number", ""),
        data.get("name", ""),
        data.get("brand", ""),
        data.get("description", ""),
        category_from_url(str(data.get("source_url", ""))),
    ]
    values.extend((data.get("color_names") or {}).keys())
    values.extend((data.get("color_names") or {}).values())
    for item in data.get("features") or []:
        if isinstance(item, dict):
            values.extend([item.get("title", ""), item.get("description", "")])
        else:
            values.append(str(item))
    for item in data.get("variants") or []:
        values.extend([item.get("sku", ""), item.get("color_code", ""), item.get("color", "")])
    return unique(values)


def category_from_url(url: str) -> str:
    match = re.search(r"[?&]cgid=([^&#]+)", url)
    if match:
        return match.group(1)
    return ""


def count_images(image_dir: Path) -> int:
    if not image_dir.exists():
        return 0
    return sum(1 for path in image_dir.iterdir() if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"})


def infer_preferred_colors(query: str, record: ProductRecord) -> list[str]:
    q = normalize(query)
    preferred = []
    for code, name in record.color_names.items():
        code_norm = normalize(code)
        name_norm = normalize(name)
        if code_norm and code_norm in q:
            preferred.append(code)
        elif name_norm and any(token in q for token in tokenize(name_norm)):
            preferred.append(code)
    return unique(preferred)


def image_samples(record: ProductRecord, limit: int, query: str = "") -> list[str]:
    if not record.image_dir:
        return []
    image_dir = Path(record.image_dir)
    if not image_dir.exists():
        return []
    files = [
        path for path in image_dir.iterdir()
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    ]
    preferred = {code.upper() for code in infer_preferred_colors(query, record)}

    def sort_key(path: Path) -> tuple[int, int, str]:
        match = re.search(r"_([A-Z0-9]+)(?:_|$)", path.stem.upper())
        color = match.group(1) if match else ""
        preferred_rank = 0 if color in preferred else 1
        main_rank = 0 if re.search(r"_[A-Z0-9]+$", path.stem.upper()) else 1
        return preferred_rank, main_rank, path.name

    files.sort(key=sort_key)
    return [str(path) for path in files[:limit]]


def score_record(query: str, record: ProductRecord) -> tuple[float, list[str]]:
    q = normalize(query)
    q_tokens = tokenize(q)
    haystacks = {
        "style": [record.product_id, record.style_number],
        "name": [record.name],
        "brand": [record.brand],
        "category": [record.category],
        "colors": [*record.colors, *record.color_names.keys(), *record.color_names.values()],
        "keywords": record.keywords,
    }
    score = 0.0
    reasons: list[str] = []

    for value in haystacks["style"]:
        if value and normalize(value) == q:
            score += 100
            reasons.append(f"exact style/product id: {value}")
        elif value and normalize(value) in q:
            score += 60
            reasons.append(f"style/product id: {value}")

    weighted_fields = [
        ("name", 35),
        ("category", 24),
        ("colors", 22),
        ("brand", 12),
        ("keywords", 10),
    ]
    for field, weight in weighted_fields:
        for value in haystacks[field]:
            text = normalize(str(value))
            if not text:
                continue
            if q and q in text:
                score += weight
                reasons.append(f"{field}: {value}")
            elif text and text in q:
                score += weight * 0.8
                reasons.append(f"{field}: {value}")

    corpus = " ".join(
        normalize(str(v))
        for values in haystacks.values()
        for v in values
        if v
    )
    corpus_tokens = set(tokenize(corpus))
    matched = [token for token in q_tokens if token in corpus_tokens]
    if q_tokens:
        ratio = len(matched) / math.sqrt(len(q_tokens))
        score += ratio * 12
        if matched:
            reasons.append("token match: " + ", ".join(matched[:8]))

    return score, unique(reasons)[:8]


def search(query: str, roots: list[Path], limit: int, image_limit: int, threshold: float) -> list[dict[str, Any]]:
    records = load_records(roots)
    results = []
    for record in records:
        score, reasons = score_record(query, record)
        if score < threshold:
            continue
        results.append({
            "score": round(score, 2),
            "reasons": reasons,
            "product": record,
            "sample_images": image_samples(record, image_limit, query),
        })
    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:limit]


def result_to_dict(result: dict[str, Any]) -> dict[str, Any]:
    record: ProductRecord = result["product"]
    return {
        "score": result["score"],
        "reasons": result["reasons"],
        "product_id": record.product_id,
        "style_number": record.style_number,
        "name": record.name,
        "brand": record.brand,
        "site": record.site,
        "category": record.category,
        "price": record.price,
        "currency": record.currency,
        "colors": record.colors,
        "color_names": record.color_names,
        "json_path": record.json_path,
        "docx_path": record.docx_path,
        "image_dir": record.image_dir,
        "image_count": record.image_count,
        "sample_images": result["sample_images"],
        "source_url": record.source_url,
    }


def print_text_results(results: list[dict[str, Any]]) -> None:
    if not results:
        print("No local cached products matched the query.")
        return

    for idx, result in enumerate(results, 1):
        item = result_to_dict(result)
        print(f"{idx}. {item['name'] or item['product_id']}  score={item['score']}")
        print(f"   style: {item['style_number'] or item['product_id']}  brand: {item['brand']}  price: {item['price']} {item['currency']}".rstrip())
        if item["category"]:
            print(f"   category: {item['category']}")
        if item["reasons"]:
            print("   matched: " + "; ".join(item["reasons"]))
        print(f"   json: {item['json_path']}")
        if item["docx_path"]:
            print(f"   docx: {item['docx_path']}")
        if item["image_dir"]:
            print(f"   images: {item['image_dir']} ({item['image_count']})")
        for image in item["sample_images"]:
            print(f"   image: {image}")


def md_link(label: str, path: str) -> str:
    if not path:
        return ""
    normalized = path.replace("\\", "/")
    if " " in normalized:
        return f"[{label}](<{normalized}>)"
    return f"[{label}]({normalized})"


def md_image(alt: str, path: str) -> str:
    normalized = path.replace("\\", "/")
    if " " in normalized:
        return f"![{alt}](<{normalized}>)"
    return f"![{alt}]({normalized})"


def print_markdown_results(results: list[dict[str, Any]]) -> None:
    if not results:
        print("No local cached products matched the query.")
        return

    for idx, result in enumerate(results, 1):
        item = result_to_dict(result)
        title = item["name"] or item["product_id"] or "Product"
        print(f"### {idx}. {title}")
        print()
        facts = []
        if item["style_number"] or item["product_id"]:
            facts.append(f"Style: `{item['style_number'] or item['product_id']}`")
        if item["brand"]:
            facts.append(f"Brand: {item['brand']}")
        if item["price"]:
            facts.append(f"Price: {item['price']} {item['currency']}".rstrip())
        if item["category"]:
            facts.append(f"Category: `{item['category']}`")
        if item["image_count"]:
            facts.append(f"Images: {item['image_count']}")
        if facts:
            print("- " + "\n- ".join(facts))
        if item["reasons"]:
            print("- Matched: " + "; ".join(item["reasons"]))

        links = []
        if item["json_path"]:
            links.append(md_link("product.json", item["json_path"]))
        if item["docx_path"]:
            links.append(md_link("product.docx", item["docx_path"]))
        if item["image_dir"]:
            links.append(md_link("images", item["image_dir"]))
        if links:
            print("- Files: " + " | ".join(links))
        print()

        for image in item["sample_images"]:
            alt = Path(image).stem
            print(md_image(alt, image))
            print()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="Natural-language product query, style number, color, category, or description.")
    parser.add_argument("--root", action="append", default=[], help="Data root containing catalog_index.json or product folders. Can be repeated.")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--image-limit", type=int, default=6)
    parser.add_argument("--threshold", type=float, default=8)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--markdown", action="store_true", help="Print Markdown with local image previews and file links.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args(argv or sys.argv[1:])
    roots = [Path(root) for root in args.root] if args.root else DEFAULT_ROOTS
    results = search(args.query, roots, args.limit, args.image_limit, args.threshold)
    if args.json:
        print(json.dumps([result_to_dict(item) for item in results], ensure_ascii=False, indent=2))
    elif args.markdown:
        print_markdown_results(results)
    else:
        print_text_results(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
