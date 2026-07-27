#!/usr/bin/env python3
"""
mdcomputers_scraper.py

Scrapes product listing details from MDComputers.in for a given search term.

MDComputers.in runs on OpenCart, so search results live at:
    https://mdcomputers.in/?route=product/search&search=<term>&page=<n>

For each product on the results page(s), this script extracts:
    - Product name
    - Product URL
    - Current (discounted) price
    - Original (list) price, if a discount is shown
    - Discount percentage, if shown
    - Image URL

Usage:
    python mdcomputers_scraper.py "external harddrive"
    python mdcomputers_scraper.py "external harddrive" --pages 2 --out results.csv

Requirements:
    pip install requests beautifulsoup4
"""

import argparse
import csv
import re
import sys
import time
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://mdcomputers.in/"
SEARCH_ROUTE = "product/search"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch_page(session, search_term, page):
    """Fetch a single search-results page and return the HTML text."""
    params = {"route": SEARCH_ROUTE, "search": search_term}
    if page > 1:
        params["page"] = page
    url = BASE_URL + "?" + urlencode(params)

    resp = session.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


def clean_price(text):
    """Extract a numeric-friendly price string, e.g. '₹9,900' -> '9900'."""
    if not text:
        return None
    digits = re.sub(r"[^\d]", "", text)
    return digits or None


def parse_products(html):
    """Parse a search-results page and return a list of product dicts."""
    soup = BeautifulSoup(html, "html.parser")
    products = []

    # OpenCart product cards are typically wrapped in elements whose class
    # contains "product-thumb" / "product-layout". MDComputers' theme uses
    # a card-style layout; we look for the product title link (an <h4><a>
    # or <h3><a> inside a product block) as the anchor and then walk up to
    # gather the surrounding price / image info.
    candidates = soup.select(
        "div.product-thumb, div.product-layout, div.product-item, li.product"
    )

    # Fallback: if the theme uses a different wrapper, locate product links
    # directly by URL pattern (MDComputers product URLs look like
    # https://mdcomputers.in/product/<slug>) and use their closest common
    # ancestor block.
    if not candidates:
        links = soup.select('a[href*="/product/"]')
        seen_blocks = []
        for link in links:
            block = link.find_parent(["div", "li"])
            if block and block not in seen_blocks:
                seen_blocks.append(block)
        candidates = seen_blocks

    for block in candidates:
        name_tag = block.select_one("h4 a, h3 a, .caption a, a.product-title")
        if not name_tag:
            # try any link that points to a product page and has text
            name_tag = block.find("a", href=re.compile(r"/product/"))
        if not name_tag or not name_tag.get_text(strip=True):
            continue

        name = name_tag.get_text(strip=True)
        product_url = name_tag.get("href", "").strip()

        # Prices: MDComputers shows "old" (struck-through) and "new" price.
        price_new_tag = block.select_one(
            ".price-new, .special-price, span.price"
        )
        price_old_tag = block.select_one(".price-old, del")

        price_new = price_new_tag.get_text(strip=True) if price_new_tag else None
        price_old = price_old_tag.get_text(strip=True) if price_old_tag else None

        # Some themes put both prices inside one ".price" element separated
        # by whitespace, e.g. "₹9,900 ₹4,940". Split on that pattern if we
        # only matched one generic price block.
        if price_new and price_old is None:
            prices_found = re.findall(r"₹[\d,]+", price_new)
            if len(prices_found) == 2:
                price_old, price_new = prices_found[0], prices_found[1]

        # Discount badge, e.g. "-41%"
        discount_tag = block.find(string=re.compile(r"-\d+%"))
        discount = discount_tag.strip() if discount_tag else None

        img_tag = block.find("img")
        image_url = None
        if img_tag:
            image_url = img_tag.get("data-src") or img_tag.get("src")

        products.append(
            {
                "name": name,
                "url": product_url,
                "price": price_new,
                "price_numeric": clean_price(price_new),
                "original_price": price_old,
                "original_price_numeric": clean_price(price_old),
                "discount": discount,
                "image_url": image_url,
            }
        )

    return products


def scrape(search_term, max_pages=1, delay=1.0):
    session = requests.Session()
    all_products = []
    seen_urls = set()

    for page in range(1, max_pages + 1):
        print(f"Fetching page {page} for '{search_term}'...", file=sys.stderr)
        html = fetch_page(session, search_term, page)
        page_products = parse_products(html)

        if not page_products:
            print(f"No products found on page {page}; stopping.", file=sys.stderr)
            break

        new_count = 0
        for p in page_products:
            if p["url"] and p["url"] not in seen_urls:
                seen_urls.add(p["url"])
                all_products.append(p)
                new_count += 1

        if new_count == 0:
            # Likely repeated / last page
            break

        if page < max_pages:
            time.sleep(delay)

    return all_products


def save_csv(products, path):
    fieldnames = [
        "name",
        "url",
        "price",
        "price_numeric",
        "original_price",
        "original_price_numeric",
        "discount",
        "image_url",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(products)


def main():
    parser = argparse.ArgumentParser(
        description="Scrape product listings from MDComputers.in for a search term."
    )
    parser.add_argument("search_term", help='Search term, e.g. "external harddrive"')
    parser.add_argument(
        "--pages", type=int, default=1, help="Number of result pages to fetch (default: 1)"
    )
    parser.add_argument(
        "--out", default=None, help="Optional CSV output path (default: print to stdout)"
    )
    parser.add_argument(
        "--delay", type=float, default=1.0, help="Delay in seconds between page requests"
    )
    args = parser.parse_args()

    products = scrape(args.search_term, max_pages=args.pages, delay=args.delay)

    if not products:
        print("No products found. The site's HTML structure may have changed; "
              "inspect the page and adjust the CSS selectors in parse_products().",
              file=sys.stderr)
        sys.exit(1)

    if args.out:
        save_csv(products, args.out)
        print(f"Saved {len(products)} products to {args.out}", file=sys.stderr)
    else:
        for p in products:
            print(f"{p['name']}")
            print(f"  URL:      {p['url']}")
            print(f"  Price:    {p['price']}"
                  + (f" (was {p['original_price']}, {p['discount']})" if p["original_price"] else ""))
            print(f"  Image:    {p['image_url']}")
            print()
        print(f"Total products: {len(products)}", file=sys.stderr)


if __name__ == "__main__":
    main()