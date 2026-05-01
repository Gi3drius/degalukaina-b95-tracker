import json
import sqlite3

import pytest

import export_fuel_history as exporter


def make_db(path):
    con = sqlite3.connect(path)
    con.execute(
        """
        CREATE TABLE fuel_prices (
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
    con.execute(
        """
        INSERT INTO fuel_prices VALUES
        ('2026-05-01', 'Station A', 'Brand', 'Station A', 'City', 1.70, '2026-05-01T06:00:00')
        """
    )
    con.commit()
    con.close()


def test_export_includes_source_and_success_metadata(tmp_path):
    db = tmp_path / "fuel_prices.db"
    output = tmp_path / "fuel_prices.json"
    make_db(db)

    payload = exporter.export_json(str(db), str(output), source_url="https://example.test/")

    assert payload["source_url"] == "https://example.test/"
    assert payload["last_successful_scrape_at"] == "2026-05-01T06:00:00"
    assert payload["row_count"] == 1
    assert json.loads(output.read_text(encoding="utf-8"))["source_url"] == "https://example.test/"


def test_validate_payload_rejects_empty_history():
    payload = exporter.build_payload([])

    with pytest.raises(exporter.ExportValidationError, match="No history rows"):
        exporter.validate_payload(payload)


def test_validate_payload_rejects_latest_rows_without_b95():
    payload = exporter.build_payload([
        {
            "day": "2026-05-01",
            "query": "Station A",
            "brand": "Brand",
            "address": "Station A",
            "municipality": "City",
            "b95": None,
            "updated_at": "2026-05-01T06:00:00",
        }
    ])

    with pytest.raises(exporter.ExportValidationError, match="missing B95"):
        exporter.validate_payload(payload)
