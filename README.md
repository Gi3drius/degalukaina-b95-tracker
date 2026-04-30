# B95 Fuel Price Tracker

Static GitHub Pages dashboard for B95 fuel prices scraped from degalukaina.lt.

## Files

- `scrape_degalukaina.py` - scrapes selected stations and stores B95 history in SQLite.
- `fuel_prices.db` - local SQLite history database, created by the scraper.
- `export_fuel_history.py` - exports SQLite history to static JSON.
- `docs/index.html` - GitHub Pages dashboard.
- `docs/data/fuel_prices.json` - static data consumed by the dashboard.
- `.github/workflows/update-fuel-prices.yml` - optional scheduled GitHub Actions updater.

## Run locally

Scrape default stations and save to SQLite:

```bash
python3 scrape_degalukaina.py
```

Scrape specific stations:

```bash
python3 scrape_degalukaina.py --station "Buivydiškių g. 5, Vilnius" --station "Justiniškių g. 14B, Vilnius"
```

Export JSON for the website:

```bash
python3 export_fuel_history.py
```

Serve the website locally:

```bash
python3 -m http.server 8000 --directory docs
```

Open:

```text
http://localhost:8000
```

## GitHub Pages setup

In the GitHub repository:

1. Go to Settings -> Pages.
2. Source: Deploy from a branch.
3. Branch: `main`.
4. Folder: `/docs`.
5. Save.

## Automatic daily updates

The included workflow `.github/workflows/update-fuel-prices.yml` can run daily and commit updated `fuel_prices.db` + `docs/data/fuel_prices.json`.

For the workflow to push commits, repository Actions permissions must allow write access:

Settings -> Actions -> General -> Workflow permissions -> Read and write permissions.

You can also trigger it manually from the Actions tab with `workflow_dispatch`.

## Important GitHub Pages limitation

GitHub Pages is static. It cannot run Python or write SQLite from the browser.

The Refresh button in the page reloads the latest committed JSON data. For actual price updates, run the scraper locally and push, or use the GitHub Actions workflow.
