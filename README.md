# MDComputers.in Product Scraper

## Setup
```bash
pip install -r requirements.txt
```

## Usage
```bash
# Print results to the terminal
python mdcomputers_scraper.py "external harddrive"

# Fetch 2 pages of results and save to CSV
python mdcomputers_scraper.py "external harddrive" --pages 2 --out results.csv
```

## What it does
Queries `https://mdcomputers.in/?route=product/search&search=<term>` (MDComputers
runs OpenCart) and extracts, for each product on the results page:
- Name
- Product URL
- Current price / original price / discount %
- Image URL

## Note on robustness
MDComputers may change its theme/HTML structure over time, which would break
the CSS selectors in `parse_products()`. If the script returns "No products
found," inspect the page's HTML and adjust the selectors accordingly.