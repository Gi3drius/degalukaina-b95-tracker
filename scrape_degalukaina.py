#!/usr/bin/env python3
"""
Scrape fuel prices from degalukaina.lt for selected gas station addresses.

Fast/simple approach: degalukaina.lt renders the fuel-price table directly in the
homepage HTML, so this script only downloads the page and parses table rows.
No Selenium/browser/API needed.

Usage:
  python3 scrape_degalukaina.py "Buivydiškių g. 5, Vilnius"
  python3 scrape_degalukaina.py Justiniškių g. 14B, Vilnius
  python3 scrape_degalukaina.py justiniskiu
  python3 scrape_degalukaina.py --station "Buivydiškių g. 5, Vilnius" --station "Laisvės pr. 125A, Vilnius"

If no addresses are passed, it uses DEFAULT_STATIONS below.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sqlite3
import sys
import unicodedata
import urllib.request
from datetime import date, datetime
from typing import Dict, List, Optional

URL = "https://degalukaina.lt/"
DB_PATH = "fuel_prices.db"

DEFAULT_STATIONS = [
    "Buivydiškių g. 5, Vilnius",
    "Justiniškių g. 14B, Vilnius",
    "Rygos g. 2, Vilnius",
    "Geležinio Vilko g. 63, Vilnius",
    "Molėtų pl. 8, Vilnius",
    "Vilniaus g. 8, Grigiškės"
]

FUEL_COLUMNS = ["diesel", "b95", "b98", "lpg"]


def fetch_html(url: str = URL) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; fuel-price-scraper/1.0)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", "replace")


def strip_tags(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def cell_price(cell_html: str) -> Optional[float]:
    text = strip_tags(cell_html)
    if not text or text in {"–", "-"}:
        return None
    m = re.search(r"\d+(?:[.,]\d+)?", text)
    return float(m.group(0).replace(",", ".")) if m else None


def parse_rows(page_html: str) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []

    for tr in re.findall(r"<tr\b[^>]*>(.*?)</tr>", page_html, flags=re.I | re.S):
        cells = re.findall(r"<td\b([^>]*)>(.*?)</td>", tr, flags=re.I | re.S)
        if len(cells) < 5:
            continue

        first_attrs, first_html = cells[0]
        place_match = re.search(r'data-place=["\']([^"\']*)', first_attrs, flags=re.I)
        municipality = html.unescape(place_match.group(1)) if place_match else None

        brand_match = re.search(
            r'<span[^>]*class=["\'][^"\']*fw-semibold[^"\']*["\'][^>]*>(.*?)</span>',
            first_html,
            flags=re.I | re.S,
        )
        brand = strip_tags(brand_match.group(1)) if brand_match else None

        # Address is the text in the first cell after the brand, before the map link.
        first_no_links = re.sub(r"<a\b.*?</a>", " ", first_html, flags=re.I | re.S)
        first_text = strip_tags(first_no_links)
        if brand and first_text.startswith(brand):
            address = first_text[len(brand):].strip()
        else:
            address = first_text

        prices = {
            fuel: cell_price(cells[i + 1][1])
            for i, fuel in enumerate(FUEL_COLUMNS)
            if i + 1 < len(cells)
        }

        if brand and address:
            rows.append(
                {
                    "brand": brand,
                    "address": address,
                    "municipality": municipality,
                    **prices,
                }
            )

    return rows


def norm(s: str) -> str:
    """Normalize text for forgiving Lithuanian address matching.

    - case-insensitive
    - accent-insensitive: Justiniskiu matches Justiniškių
    - punctuation-insensitive: "g. 14B," and "g 14b" both match
    """
    s = unicodedata.normalize("NFKD", s.casefold())
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"[^\w]+", " ", s, flags=re.UNICODE)
    return re.sub(r"\s+", " ", s).strip()


def get_queries(positional: List[str], station_options: Optional[List[str]]) -> List[str]:
    if station_options:
        return station_options
    if not positional:
        return DEFAULT_STATIONS
    if len(positional) == 1:
        return positional

    # If the user typed an address without shell quotes, argparse receives every
    # word separately, e.g. ["Justiniškių", "g.", "14B,", "Vilnius"]. Treat that
    # as one address. For multiple stations, use repeated --station options.
    return [" ".join(positional)]


def find_stations(rows: List[Dict[str, object]], queries: List[str]) -> List[Dict[str, object]]:
    found: List[Dict[str, object]] = []
    for query in queries:
        q = norm(query)
        matches = [row for row in rows if q in norm(str(row.get("address", "")))]
        if not matches:
            # fallback: allow matching across brand + address + municipality
            matches = [
                row
                for row in rows
                if q in norm(" ".join(str(row.get(k, "")) for k in ["brand", "address", "municipality"]))
            ]
        for row in matches:
            found.append({"query": query, **row})
    return found


def print_b95_table(rows: List[Dict[str, object]]) -> None:
    headers = ["query", "brand", "address", "municipality", "b95"]
    widths = {h: len(h) for h in headers}
    formatted = []
    for row in rows:
        item = {}
        for h in headers:
            value = row.get(h)
            item[h] = "-" if value is None else str(value)
            widths[h] = max(widths[h], len(item[h]))
        formatted.append(item)

    print("  ".join(h.ljust(widths[h]) for h in headers))
    print("  ".join("-" * widths[h] for h in headers))
    for row in formatted:
        print("  ".join(row[h].ljust(widths[h]) for h in headers))


def b95_only(rows: List[Dict[str, object]]) -> List[Dict[str, object]]:
    return [
        {
            "query": row.get("query"),
            "brand": row.get("brand"),
            "address": row.get("address"),
            "municipality": row.get("municipality"),
            "b95": row.get("b95"),
        }
        for row in rows
    ]


def save_history(rows: List[Dict[str, object]], db_path: str = DB_PATH, day: Optional[str] = None) -> int:
    """Save B95 prices to SQLite history, replacing same-day rows.

    One row is unique by (day, brand, address). If the script runs again on the
    same day for the same matched station, b95 is updated to the latest scraped
    value, even if the query text is different.
    """
    day = day or date.today().isoformat()
    now = datetime.now().isoformat(timespec="seconds")

    con = sqlite3.connect(db_path)
    try:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS fuel_prices (
                day TEXT NOT NULL,
                query TEXT NOT NULL,
                brand TEXT NOT NULL,
                address TEXT NOT NULL,
                municipality TEXT,
                b95 REAL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (day, brand, address)
            )
            """
        )
        for row in rows:
            con.execute(
                """
                INSERT INTO fuel_prices (day, query, brand, address, municipality, b95, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(day, brand, address) DO UPDATE SET
                    query = excluded.query,
                    municipality = excluded.municipality,
                    b95 = excluded.b95,
                    updated_at = excluded.updated_at
                """,
                (
                    day,
                    str(row.get("query") or ""),
                    str(row.get("brand") or ""),
                    str(row.get("address") or ""),
                    row.get("municipality"),
                    row.get("b95"),
                    now,
                ),
            )
        con.commit()
        return len(rows)
    finally:
        con.close()


def print_history(db_path: str = DB_PATH) -> int:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        table_exists = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'fuel_prices'"
        ).fetchone()
        if not table_exists:
            print("No history found.")
            return 0
        rows = con.execute(
            """
            SELECT day, query, brand, address, municipality, b95, updated_at
            FROM fuel_prices
            ORDER BY day DESC, query, brand, address
            """
        ).fetchall()
    finally:
        con.close()

    if not rows:
        print("No history found.")
        return 0

    headers = ["day", "query", "brand", "address", "municipality", "b95", "updated_at"]
    dict_rows = [dict(row) for row in rows]
    widths = {h: len(h) for h in headers}
    for row in dict_rows:
        for h in headers:
            widths[h] = max(widths[h], len("-" if row.get(h) is None else str(row.get(h))))
    print("  ".join(h.ljust(widths[h]) for h in headers))
    print("  ".join("-" * widths[h] for h in headers))
    for row in dict_rows:
        print("  ".join(("-" if row.get(h) is None else str(row.get(h))).ljust(widths[h]) for h in headers))
    return len(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape B95 fuel prices from degalukaina.lt")
    parser.add_argument("stations", nargs="*", help="Station address words or one quoted station address")
    parser.add_argument("-s", "--station", action="append", help="Station address/query. Repeat for multiple stations.")
    parser.add_argument("--db", default=DB_PATH, help=f"SQLite history DB path, default: {DB_PATH}")
    parser.add_argument("--no-save", action="store_true", help="Only print current B95 prices; do not save history")
    parser.add_argument("--history", action="store_true", help="Print saved B95 price history from the DB and exit")
    parser.add_argument("--date", help="Override history date as YYYY-MM-DD, mostly useful for testing/backfills")
    parser.add_argument("--json", action="store_true", help="Output current B95 results as JSON")
    parser.add_argument("--csv", action="store_true", help="Output current B95 results as CSV")
    args = parser.parse_args()

    if args.history:
        print_history(args.db)
        return 0

    queries = get_queries(args.stations, args.station)
    page = fetch_html()
    rows = parse_rows(page)
    results = b95_only(find_stations(rows, queries))

    if not args.no_save and results:
        saved = save_history(results, db_path=args.db, day=args.date)
        print(f"Saved {saved} B95 row(s) to {args.db}", file=sys.stderr)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    elif args.csv:
        headers = ["query", "brand", "address", "municipality", "b95"]
        writer = csv.DictWriter(sys.stdout, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    else:
        if results:
            print_b95_table(results)
        else:
            print("No matching stations found.", file=sys.stderr)
            print(f"Parsed {len(rows)} stations from {URL}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
