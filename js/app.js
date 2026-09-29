// Fetches data/data.json and renders every section generically from
// js/config.js. No build step, no framework.

function getPath(data, path) {
  return path.split(".").reduce((obj, key) => (obj ? obj[key] : undefined), data);
}

function fmt(value, unit) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const rounded = Math.abs(value) >= 100 ? value.toFixed(0) : value.toFixed(2);
  if (!unit) return rounded;
  return unit === "%" || unit === "pp" ? `${rounded}${unit}` : `${rounded} ${unit}`;
}

function deltaClass(delta) {
  if (delta === null || delta === undefined) return "";
  return delta > 0 ? "up" : delta < 0 ? "down" : "";
}

function statCardHTML(card, data) {
  const m = getPath(data, card.path);
  if (!m || m.latest === null || m.latest === undefined) {
    return `<div class="card"><div class="card-label">${card.label}</div><div class="card-value">—</div></div>`;
  }
  const dClass = deltaClass(m.delta);
  const staleBadge = m.stale ? `<span class="badge stale">Stale ${m.days_since}d</span>` : "";
  const arrow = m.delta > 0 ? "↑" : m.delta < 0 ? "↓" : "→";
  const deltaStr =
    m.delta !== null && m.delta !== undefined
      ? `<span class="delta ${dClass}">${arrow} ${Math.abs(m.delta).toFixed(2)}${card.unit && card.unit !== "$" ? card.unit : ""}</span>`
      : "";
  return `
    <div class="card">
      <div class="card-label">${card.label} ${staleBadge}</div>
      <div class="card-value">${fmt(m.latest, card.unit)}</div>
      <div class="card-meta">${deltaStr} <span class="as-of">${m.as_of || ""}</span></div>
    </div>`;
}

function renderRegimeSection(regime) {
  if (!regime) return "<h2>Regime Dashboard</h2><p>No data.</p>";

  const cards = regime.snapshot_cards || {};
  const cardDefs = [
    { key: "gdp_growth", label: "GDP Growth", unit: "%" },
    { key: "cpi_yoy", label: "Inflation (CPI)", unit: "%" },
    { key: "unemployment", label: "Unemployment", unit: "%" },
    { key: "payrolls_mom", label: "Payrolls MoM", unit: "K" },
    { key: "spread_10y2y", label: "10Y-2Y Spread", unit: "pp" },
    { key: "spread_2y3m", label: "2Y-3M Spread", unit: "pp" },
  ];
  const cardHTML = cardDefs
    .map((cd) => {
      const m = cards[cd.key];
      return `<div class="card">
        <div class="card-label">${cd.label}</div>
        <div class="card-value">${m ? fmt(m.latest, cd.unit) : "—"}</div>
        <div class="card-meta">${m && m.as_of ? m.as_of : ""}</div>
      </div>`;
    })
    .join("");

  const counts = regime.trailing_36mo_counts || {};
  const total = Object.values(counts).reduce((a, b) => a + b, 0) || 1;
  const slug = (s) => s.replace(/\s+/g, "").toLowerCase();
  const barHTML = Object.entries(counts)
    .map(([label, n]) => {
      const pct = ((n / total) * 100).toFixed(1);
      return `<div class="regime-seg regime-${slug(label)}" style="width:${pct}%" title="${label}: ${n}mo"></div>`;
    })
    .join("");
  const legendHTML = Object.entries(counts)
    .map(
      ([label, n]) =>
        `<span class="legend-item"><span class="legend-swatch regime-${slug(label)}"></span>${label} (${n}mo)</span>`
    )
    .join("");

  return `
    <h2>Regime Dashboard</h2>
    <div class="regime-box regime-${slug(regime.current_label || "neutral")}">
      <div class="regime-label">CURRENT REGIME</div>
      <div class="regime-value">${regime.current_label || "—"}</div>
      <div class="regime-score">${regime.bullish_count} / ${regime.bullish_total} bullish</div>
    </div>
    <div class="card-grid">${cardHTML}</div>
    <h3>Regime History (trailing 36mo)</h3>
    <div class="regime-bar">${barHTML}</div>
    <div class="regime-legend">${legendHTML}</div>
  `;
}

function fmtPct(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(1)}%`;
}

function scoreClass(score) {
  if (score >= 75) return "score-high";
  if (score >= 50) return "score-mid";
  return "score-low";
}

function pctClass(value) {
  if (value === null || value === undefined) return "";
  return value > 0 ? "up" : value < 0 ? "down" : "";
}

function renderMomentumSection(section, momentum) {
  let html = `<h2>${section.title}</h2>`;
  if (section.description) html += `<p class="section-desc">${section.description}</p>`;

  if (!momentum || !momentum.rows || !momentum.rows.length) {
    return html + "<p>No data.</p>";
  }

  const rows = momentum.rows
    .map(
      (r) => `
      <tr>
        <td class="mom-rank">${r.rank}</td>
        <td class="mom-etf"><strong>${r.ticker}</strong><span class="mom-label">${r.label}</span></td>
        <td><span class="mom-score ${scoreClass(r.score)}">${r.score}</span></td>
        <td class="mom-sub">${r.tend}</td>
        <td class="mom-sub">${r.acel}</td>
        <td class="mom-sub">${r.max}</td>
        <td class="mom-sub">${r.vol}</td>
        <td class="${pctClass(r.ret_1m)}">${fmtPct(r.ret_1m)}</td>
        <td class="${pctClass(r.ret_3m)}">${fmtPct(r.ret_3m)}</td>
        <td class="${pctClass(r.ret_6m)}">${fmtPct(r.ret_6m)}</td>
        <td class="${pctClass(r.ret_12m)}">${fmtPct(r.ret_12m)}</td>
        <td class="${pctClass(r.from_high)}">${fmtPct(r.from_high)}</td>
        <td>${r.rvol !== null && r.rvol !== undefined ? r.rvol.toFixed(1) + "×" : "—"}</td>
      </tr>`
    )
    .join("");

  html += `
    <p class="card-meta">As of ${momentum.as_of || "—"}</p>
    <div class="mom-table-wrap">
      <table class="mom-table">
        <thead>
          <tr>
            <th>#</th><th>ETF</th><th>Score</th><th>Tend</th><th>Acel</th><th>Max</th><th>Vol</th>
            <th>1M</th><th>3M</th><th>6M</th><th>12M</th><th>vs 52w High</th><th>RVOL</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
  return html;
}

function renderSection(section, data) {
  const el = document.createElement("section");
  el.id = section.id;
  el.className = "section";

  if (section.kind === "regime") {
    el.innerHTML = renderRegimeSection(data.regime);
    return el;
  }

  if (section.kind === "curve") {
    el.innerHTML = `<h2>${section.title}</h2><div class="chart-box"><canvas id="chart-${section.id}"></canvas></div>`;
    requestAnimationFrame(() => renderYieldCurveChart(`chart-${section.id}`, data.yield_curve));
    return el;
  }

  if (section.kind === "momentum") {
    el.innerHTML = renderMomentumSection(section, data.momentum);
    return el;
  }

  let html = `<h2>${section.title}</h2>`;
  if (section.description) html += `<p class="section-desc">${section.description}</p>`;
  if (section.cards) {
    html += `<div class="card-grid">${section.cards.map((c) => statCardHTML(c, data)).join("")}</div>`;
  }
  if (section.chart) {
    html += `<div class="chart-box"><h3>${section.chart.title}</h3><canvas id="chart-${section.id}"></canvas></div>`;
  }
  if (section.barChart) {
    html += `<div class="chart-box"><h3>${section.barChart.title}</h3><canvas id="bar-${section.id}"></canvas></div>`;
  }
  el.innerHTML = html;

  if (section.chart) {
    requestAnimationFrame(() => renderLineChart(`chart-${section.id}`, section.chart.series, data));
  }
  if (section.barChart) {
    requestAnimationFrame(() => renderBarChart(`bar-${section.id}`, getPath(data, section.barChart.path)));
  }
  return el;
}

async function main() {
  const nav = document.getElementById("nav");
  nav.innerHTML = SECTIONS.map((s) => `<a href="#${s.id}">${s.title}</a>`).join("");

  let data;
  try {
    const res = await fetch("data/data.json", { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    data = await res.json();
  } catch (e) {
    document.getElementById("sections").innerHTML =
      `<p class="error">Could not load data/data.json (${e.message}). Run scripts/fetch_data.py first.</p>`;
    return;
  }

  document.getElementById("generated-at").textContent =
    "Data generated " + new Date(data.generated_at_utc).toLocaleString();

  const container = document.getElementById("sections");
  container.innerHTML = "";
  for (const section of SECTIONS) {
    container.appendChild(renderSection(section, data));
  }
}

main();
