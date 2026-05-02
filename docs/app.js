const DATA_URL = "data/fuel_prices.json";

let payload = null;
let chart = null;

const el = (id) => document.getElementById(id);

function fmtPrice(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  return Number(value).toFixed(2);
}

function fmtDateTime(value) {
  if (!value) return "-";
  return String(value).replace("T", " ");
}

function stationLabel(row) {
  return `${row.brand} — ${row.address}`;
}

async function loadData(cacheBust = false) {
  const url = cacheBust ? `${DATA_URL}?t=${Date.now()}` : DATA_URL;
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`Could not load ${DATA_URL}: HTTP ${response.status}`);
  payload = await response.json();
  render();
}

function render() {
  const history = payload.history || [];
  const latest = payload.latest || [];

  el("stationCount").textContent = payload.station_count ?? 0;
  el("rowCount").textContent = payload.row_count ?? history.length;
  el("generatedAt").textContent = fmtDateTime(payload.generated_at);
  el("lastScrapeAt").textContent = fmtDateTime(payload.last_successful_scrape_at);
  if (payload.source_url) {
    el("sourceUrl").href = payload.source_url;
    el("sourceUrl").textContent = payload.source_url.replace(/^https?:\/\//, "").replace(/\/$/, "");
  }

  renderHeroMetrics(latest, history);
  renderStationSelect(payload.stations || []);
  renderTable();
  renderLatestCards(filteredLatest());
  renderChart();
}

function renderHeroMetrics(latest, history) {
  const priced = latest
    .filter((row) => row.b95 !== null && row.b95 !== undefined && !Number.isNaN(Number(row.b95)))
    .sort((a, b) => Number(a.b95) - Number(b.b95));

  if (!priced.length) {
    el("cheapestPrice").textContent = "-";
    el("cheapestStation").textContent = "No latest B95 price available";
    el("priceRange").textContent = "-";
    el("latestDay").textContent = "-";
    el("trendSummary").textContent = "Waiting for data";
    return;
  }

  const cheapest = priced[0];
  const highest = priced[priced.length - 1];
  const days = [...new Set(latest.map((row) => row.day).filter(Boolean))].sort();

  el("cheapestPrice").textContent = `${fmtPrice(cheapest.b95)} €/L`;
  el("cheapestStation").textContent = stationLabel(cheapest);
  el("priceRange").textContent = `${fmtPrice(cheapest.b95)}–${fmtPrice(highest.b95)} €`;
  el("latestDay").textContent = days.at(-1) || "-";
  el("trendSummary").textContent = trendSummary(history);
}

function trendSummary(history) {
  const days = [...new Set(history.map((row) => row.day).filter(Boolean))].sort();
  if (days.length < 2) return "Need more history";

  const latestDay = days.at(-1);
  const previousDay = days.at(-2);
  const avgForDay = (day) => {
    const values = history
      .filter((row) => row.day === day && row.b95 !== null && row.b95 !== undefined)
      .map((row) => Number(row.b95))
      .filter((value) => !Number.isNaN(value));
    if (!values.length) return null;
    return values.reduce((sum, value) => sum + value, 0) / values.length;
  };

  const latestAvg = avgForDay(latestDay);
  const previousAvg = avgForDay(previousDay);
  if (latestAvg === null || previousAvg === null) return "Need more history";

  const diff = latestAvg - previousAvg;
  if (Math.abs(diff) < 0.005) return `Flat at ${fmtPrice(latestAvg)} €/L avg`;
  return `${diff > 0 ? "Up" : "Down"} ${Math.abs(diff).toFixed(2)} €/L to ${fmtPrice(latestAvg)} €/L avg`;
}

function renderStationSelect(stations) {
  const select = el("stationSelect");
  const current = select.value;
  select.innerHTML = "";

  const all = document.createElement("option");
  all.value = "__all__";
  all.textContent = "All stations";
  select.appendChild(all);

  for (const station of stations) {
    const option = document.createElement("option");
    option.value = station.station_key;
    option.textContent = `${station.brand} — ${station.address}`;
    select.appendChild(option);
  }

  if ([...select.options].some((option) => option.value === current)) {
    select.value = current;
  }
}

function filteredLatest() {
  const latest = payload.latest || [];
  const selected = el("stationSelect").value;
  const needle = el("searchInput").value.trim().toLowerCase();

  return latest.filter((row) => {
    const stationOk = selected === "__all__" || row.station_key === selected;
    const searchOk = !needle || [row.brand, row.address, row.municipality, row.day]
      .filter(Boolean)
      .join(" ")
      .toLowerCase()
      .includes(needle);
    return stationOk && searchOk;
  });
}

function renderTable() {
  const rows = filteredLatest();
  const body = el("latestBody");
  body.innerHTML = "";

  for (const row of rows) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(row.brand)}</td>
      <td>${escapeHtml(row.address)}</td>
      <td>${escapeHtml(row.municipality || "-")}</td>
      <td class="price">${fmtPrice(row.b95)} €/L</td>
      <td>${escapeHtml(row.day || "-")}</td>
      <td>${escapeHtml(fmtDateTime(row.updated_at))}</td>
    `;
    body.appendChild(tr);
  }

  el("tableHint").textContent = `${rows.length} row(s)`;
}

function renderLatestCards(rows) {
  const wrap = el("latestCards");
  wrap.innerHTML = "";

  const sorted = [...rows].sort((a, b) => Number(a.b95 ?? Infinity) - Number(b.b95 ?? Infinity));
  for (const row of sorted) {
    const card = document.createElement("article");
    card.className = "stationCard";
    card.innerHTML = `
      <strong>${escapeHtml(row.brand)}</strong>
      <span class="cardPrice">${fmtPrice(row.b95)} €</span>
      <small>${escapeHtml(row.address)}<br>${escapeHtml(row.municipality || "-")}</small>
    `;
    wrap.appendChild(card);
  }

  if (!sorted.length) {
    wrap.innerHTML = `<article class="stationCard"><strong>No matches</strong><small>Try clearing filters.</small></article>`;
  }
}

function renderChart() {
  const history = payload.history || [];
  const selected = el("stationSelect").value;
  const selectedRows = selected === "__all__"
    ? history
    : history.filter((row) => row.station_key === selected);

  const stationKeys = [...new Set(selectedRows.map((row) => row.station_key))].sort();
  const labels = [...new Set(selectedRows.map((row) => row.day))].sort();

  const datasets = stationKeys.map((key, idx) => {
    const rowsByDay = new Map(
      selectedRows
        .filter((row) => row.station_key === key)
        .map((row) => [row.day, row.b95])
    );
    return {
      label: key,
      data: labels.map((day) => rowsByDay.has(day) ? rowsByDay.get(day) : null),
      borderColor: colorFor(idx),
      backgroundColor: colorFor(idx, 0.16),
      pointRadius: selected === "__all__" ? 2 : 4,
      pointHoverRadius: 6,
      borderWidth: selected === "__all__" ? 2 : 3,
      tension: 0.32,
      spanGaps: true,
    };
  });

  el("chartHint").textContent = `${labels.length} day(s), ${stationKeys.length} station(s)`;

  const ctx = el("priceChart");
  if (chart) chart.destroy();
  chart = new Chart(ctx, {
    type: "line",
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: {
          position: "bottom",
          labels: { color: "#d0d6e0", boxWidth: 10, boxHeight: 10, usePointStyle: true },
        },
        tooltip: {
          backgroundColor: "rgba(15, 16, 17, .96)",
          borderColor: "rgba(255,255,255,.12)",
          borderWidth: 1,
          titleColor: "#f7f8f8",
          bodyColor: "#d0d6e0",
          callbacks: { label: (ctx) => `${ctx.dataset.label}: ${fmtPrice(ctx.parsed.y)} €/L` },
        },
      },
      scales: {
        x: { ticks: { color: "#8a8f98" }, grid: { color: "rgba(255, 255, 255, .06)" } },
        y: {
          ticks: { color: "#8a8f98", callback: (value) => `${Number(value).toFixed(2)} €` },
          grid: { color: "rgba(255, 255, 255, .06)" },
        },
      },
    },
  });
}

function colorFor(index, alpha = 1) {
  const colors = [
    [113, 112, 255],
    [16, 185, 129],
    [245, 158, 11],
    [248, 113, 113],
    [56, 189, 248],
    [217, 70, 239],
    [163, 230, 53],
  ];
  const c = colors[index % colors.length];
  return `rgba(${c[0]}, ${c[1]}, ${c[2]}, ${alpha})`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

el("refreshBtn").addEventListener("click", async () => {
  const btn = el("refreshBtn");
  btn.disabled = true;
  btn.textContent = "Reloading...";
  try {
    await loadData(true);
  } catch (err) {
    alert(err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "Reload latest data";
  }
});

el("stationSelect").addEventListener("change", () => {
  renderTable();
  renderLatestCards(filteredLatest());
  renderChart();
});

el("searchInput").addEventListener("input", () => {
  renderTable();
  renderLatestCards(filteredLatest());
});

loadData().catch((err) => {
  console.error(err);
  document.body.innerHTML = `<main class="page"><section class="panel"><h1>Could not load data</h1><p>${escapeHtml(err.message)}</p></section></main>`;
});
