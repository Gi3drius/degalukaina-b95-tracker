#!/usr/bin/env python3
"""Export fuel_prices.db history to a static JSON file for GitHub Pages."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List

DEFAULT_DB = "fuel_prices.db"
DEFAULT_OUTPUT = "docs/data/fuel_prices.json"


def table_exists(con: sqlite3.Connection) -> bool:
    return con.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'fuel_prices'"
    ).fetchone() is not None


def load_rows(db_path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(db_path):
        return []

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        if not table_exists(con):
            return []
        rows = con.execute(
            """
            SELECT day, query, brand, address, municipality, b95, updated_at
            FROM fuel_prices
            ORDER BY day ASC, brand ASC, address ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        con.close()


def build_payload(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_station: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        station_key = f"{row['brand']} | {row['address']}"
        row["station_key"] = station_key
        by_station[station_key].append(row)

    latest = []
    stations = []
    for station_key, station_rows in sorted(by_station.items()):
        station_rows.sort(key=lambda r: (r["day"], r.get("updated_at") or ""))
        last = station_rows[-1]
        stations.append(
            {
                "station_key": station_key,
                "brand": last["brand"],
                "address": last["address"],
                "municipality": last.get("municipality"),
            }
        )
        latest.append(last)

    latest.sort(key=lambda r: (r.get("brand") or "", r.get("address") or ""))

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "fuel": "b95",
        "row_count": len(rows),
        "station_count": len(stations),
        "stations": stations,
        "latest": latest,
        "history": rows,
    }


def export_json(db_path: str, output_path: str) -> Dict[str, Any]:
    rows = load_rows(db_path)
    payload = build_payload(rows)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Export SQLite B95 history to static JSON")
    parser.add_argument("--db", default=DEFAULT_DB, help=f"SQLite DB path, default: {DEFAULT_DB}")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help=f"Output JSON path, default: {DEFAULT_OUTPUT}")
    args = parser.parse_args()

    payload = export_json(args.db, args.output)
    print(
        f"Exported {payload['row_count']} rows / {payload['station_count']} stations to {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
