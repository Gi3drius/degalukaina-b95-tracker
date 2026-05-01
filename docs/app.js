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

  renderStationSelect(payload.stations || []);
  renderTable(latest);
  renderChart();
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
      <td class="price">${fmtPrice(row.b95)}</td>
      <td>${escapeHtml(row.day || "-")}</td>
      <td>${escapeHtml(fmtDateTime(row.updated_at))}</td>
    `;
    body.appendChild(tr);
  }

  el("tableHint").textContent = `${rows.length} row(s)`;
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
      tension: 0.25,
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
        legend: { labels: { color: "#e6edf3" } },
        tooltip: { callbacks: { label: (ctx) => `${ctx.dataset.label}: ${fmtPrice(ctx.parsed.y)} €/L` } },
      },
      scales: {
        x: { ticks: { color: "#8b949e" }, grid: { color: "rgba(139, 148, 158, .15)" } },
        y: {
          ticks: { color: "#8b949e", callback: (value) => `${Number(value).toFixed(2)} €` },
          grid: { color: "rgba(139, 148, 158, .15)" },
        },
      },
    },
  });
}

function colorFor(index, alpha = 1) {
  const colors = [
    [88, 166, 255],
    [63, 185, 80],
    [210, 153, 34],
    [248, 81, 73],
    [188, 140, 255],
    [57, 211, 215],
    [255, 166, 87],
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
  renderChart();
});

el("searchInput").addEventListener("input", renderTable);

loadData().catch((err) => {
  console.error(err);
  document.body.innerHTML = `<main class="page"><section class="panel"><h1>Could not load data</h1><p>${escapeHtml(err.message)}</p></section></main>`;
});
