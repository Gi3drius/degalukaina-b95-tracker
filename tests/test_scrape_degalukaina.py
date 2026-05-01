import pytest

import scrape_degalukaina as scraper


SAMPLE_HTML = """
<table>
  <tr>
    <td data-place="Vilniaus m. sav.">
      <span class="fw-semibold">Neste Lietuva</span>
      Justiniškių g. 14B, Vilnius
      <a href="https://maps.example">map</a>
    </td>
    <td>1,67</td>
    <td>1,79</td>
    <td>1,89</td>
    <td>0,77</td>
  </tr>
  <tr>
    <td data-place="Vilniaus m. sav.">
      <span class="fw-semibold">Alauša</span>
      Buivydiškių g. 5, Vilnius
    </td>
    <td>1.66</td>
    <td>–</td>
    <td>1.88</td>
    <td>-</td>
  </tr>
</table>
"""


def test_parse_rows_extracts_prices_and_station_identity():
    rows = scraper.parse_rows(SAMPLE_HTML)

    assert rows == [
        {
            "brand": "Neste Lietuva",
            "address": "Justiniškių g. 14B, Vilnius",
            "municipality": "Vilniaus m. sav.",
            "diesel": 1.67,
            "b95": 1.79,
            "b98": 1.89,
            "lpg": 0.77,
        },
        {
            "brand": "Alauša",
            "address": "Buivydiškių g. 5, Vilnius",
            "municipality": "Vilniaus m. sav.",
            "diesel": 1.66,
            "b95": None,
            "b98": 1.88,
            "lpg": None,
        },
    ]


def test_validate_results_fails_when_source_layout_breaks():
    with pytest.raises(scraper.ScrapeValidationError, match="Parsed only 0 station"):
        scraper.validate_scrape([], scraper.DEFAULT_STATIONS)


def test_validate_results_fails_when_default_station_missing():
    rows = scraper.b95_only(scraper.find_stations(scraper.parse_rows(SAMPLE_HTML), ["Justiniskiu g 14B"]))

    with pytest.raises(scraper.ScrapeValidationError, match="Missing configured station"):
        scraper.validate_scrape(rows, ["Justiniškių g. 14B, Vilnius", "Rygos g. 2, Vilnius"])


def test_validate_results_fails_when_b95_missing():
    rows = scraper.b95_only(scraper.find_stations(scraper.parse_rows(SAMPLE_HTML), ["Buivydiskiu g 5"]))

    with pytest.raises(scraper.ScrapeValidationError, match="missing B95"):
        scraper.validate_scrape(rows, ["Buivydiškių g. 5, Vilnius"])


def test_validate_results_accepts_matching_station_with_b95():
    rows = scraper.b95_only(scraper.find_stations(scraper.parse_rows(SAMPLE_HTML), ["Justiniskiu g 14B"]))

    scraper.validate_scrape(rows, ["Justiniškių g. 14B, Vilnius"])
