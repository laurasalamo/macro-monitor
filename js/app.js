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

const STATE_WORDS = { bullish: "Bullish", neutral: "Neutral", bearish: "Bearish" };
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function fmtIndicator(value, cardDef, decimals) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const sign = cardDef.signed && value > 0 ? "+" : "";
  return `${sign}${value.toFixed(decimals)}${cardDef.suffix}`;
}

// "Q2 2026", "Sep 2026" or "Oct 2, 2026" depending on the release frequency.
function fmtPeriod(isoDate, period) {
  if (!isoDate) return "";
  const [y, m, d] = isoDate.split("-").map(Number);
  if (period === "quarter") return `Q${Math.floor((m - 1) / 3) + 1} ${y}`;
  if (period === "month") return `${MONTHS[m - 1]} ${y}`;
  return `${MONTHS[m - 1]} ${d}, ${y}`;
}

function indicatorCardHTML(cd, m) {
  const state = (m && m.state) || "none";
  const value = m ? fmtIndicator(m.latest, cd, m.decimals) : "—";
  const stateWord = STATE_WORDS[state] || "No data";
  const staleBadge = m && m.stale ? `<span class="badge stale">Stale ${m.days_since}d</span>` : "";
  return `
    <button type="button" class="ind-card state-${state}" data-key="${cd.key}" aria-haspopup="dialog"
            title="${stateWord}. Click to see the history.">
      <span class="ind-label"><span class="ind-dot" aria-hidden="true"></span>${cd.label}</span>
      <span class="ind-value">${value}<span class="sr-only"> — ${stateWord}</span></span>
      <span class="ind-meta">${m ? fmtPeriod(m.as_of, cd.period) : ""} ${staleBadge}</span>
    </button>`;
}

function renderRegimeSection(regime) {
  if (!regime) return "<h2>Regime Dashboard</h2><p>No data.</p>";

  const cards = regime.snapshot_cards || {};
  const counts = regime.counts || { bullish: 0, neutral: 0, bearish: 0 };
  const total = regime.total || REGIME_CARDS.length;
  const label = regime.current_label || "Neutral";

  const scoreBar = ["bullish", "neutral", "bearish"]
    .filter((s) => counts[s] > 0)
    .map((s) => `<div class="score-seg state-${s}" style="flex:${counts[s]}" title="${counts[s]} ${s}"></div>`)
    .join("");
  const unscored = total - counts.bullish - counts.neutral - counts.bearish;
  const unscoredSeg = unscored > 0 ? `<div class="score-seg state-none" style="flex:${unscored}" title="${unscored} no data"></div>` : "";

  const history = regime.trailing_36mo_counts || {};
  const monthly = regime.monthly || [];
  const latestMonth = monthly.length ? monthly[monthly.length - 1].month : "";
  const historyLegend = Object.entries(history)
    .map(([l, n]) => `<span class="legend-item"><span class="legend-swatch state-${l.toLowerCase()}"></span>${l} <span class="legend-count">(${n}mo)</span></span>`)
    .join("");

  return `
    <h2>Regime Dashboard</h2>
    <div class="regime-panel state-${label.toLowerCase()}">
      <div class="regime-panel-top">
        <div>
          <div class="regime-label">Current regime</div>
          <div class="regime-value">${label}</div>
          <div class="regime-breakdown">${counts.bullish} bullish · ${counts.neutral} neutral · ${counts.bearish} bearish</div>
        </div>
        <div class="regime-tally" aria-label="${counts.bullish} of ${total} indicators bullish">
          <span class="tally-n">${counts.bullish}</span><span class="tally-sep">/</span><span class="tally-total">${total}</span>
          <span class="tally-word">bullish</span>
        </div>
      </div>
      <div class="score-bar">${scoreBar}${unscoredSeg}</div>
    </div>
    <div class="ind-grid">${REGIME_CARDS.map((cd) => indicatorCardHTML(cd, cards[cd.key])).join("")}</div>
    <p class="ind-hint">Net score (bullish − bearish) of +3 or more = Bullish, −3 or less = Bearish. Click any indicator for its full history.</p>
    <div class="history-head">
      <h3>Regime History</h3>
      ${latestMonth ? `<span class="month-badge">${latestMonth}</span>` : ""}
    </div>
    <p class="section-desc">Monthly regime from the 7 indicators above, last ${monthly.length} months. Bar height is the net score (bullish − bearish); the dashed line marks the +3 Bullish cutoff. Hover a bar for its breakdown.</p>
    <div class="regime-legend">${historyLegend}</div>
    <div class="history-chart"><canvas id="regime-history-chart"></canvas></div>
  `;
}

// ---------------------------------------------------------------- indicator pop-up

let regimeHistoryPromise = null;

function loadRegimeHistory() {
  if (!regimeHistoryPromise) {
    regimeHistoryPromise = fetch("data/regime_history.json", { cache: "no-store" }).then((res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    });
    regimeHistoryPromise.catch(() => { regimeHistoryPromise = null; }); // allow a retry
  }
  return regimeHistoryPromise;
}

function isoYearsBefore(isoDate, years) {
  const [y, m, d] = isoDate.split("-");
  return `${Number(y) - years}-${m}-${d}`;
}

function isoMonthsBefore(isoDate, months) {
  const [y, m, d] = isoDate.split("-").map(Number);
  const target = new Date(y, m - 1 - months, 1);
  // Clamp the day so e.g. May 31 minus 3 months lands on Feb 28, not Mar 3.
  const lastDay = new Date(target.getFullYear(), target.getMonth() + 1, 0).getDate();
  target.setDate(Math.min(d, lastDay));
  const pad = (n) => String(n).padStart(2, "0");
  return `${target.getFullYear()}-${pad(target.getMonth() + 1)}-${pad(target.getDate())}`;
}

function fredUrl(fred) {
  return fred.includes(",")
    ? `https://fred.stlouisfed.org/graph/?id=${fred}`
    : `https://fred.stlouisfed.org/series/${fred}`;
}

function setupIndicatorModal(regime) {
  const dialog = document.getElementById("ind-modal");
  const fromInput = document.getElementById("ind-from");
  const toInput = document.getElementById("ind-to");
  const rangeButtons = [...dialog.querySelectorAll(".range-btns button")];
  let active = null; // { cardDef, lines, firstDate, lastDate, recessions }
  let lastRange = "10Y";

  function draw(from, to) {
    fromInput.value = from;
    toInput.value = to;
    renderIndicatorChart("ind-chart", active.lines, active.recessions, from, to);
  }

  function applyRange(range) {
    lastRange = range;
    rangeButtons.forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.range === range)));
    const years = { "1Y": 1, "5Y": 5, "10Y": 10 }[range];
    const from = years ? isoYearsBefore(active.lastDate, years) : active.firstDate;
    draw(from < active.firstDate ? active.firstDate : from, active.lastDate);
  }

  function applyCustomRange() {
    if (!fromInput.value || !toInput.value || fromInput.value >= toInput.value) return;
    rangeButtons.forEach((b) => b.setAttribute("aria-pressed", "false"));
    draw(fromInput.value, toInput.value);
  }

  async function open(key) {
    const cd = REGIME_CARDS.find((c) => c.key === key);
    const m = (regime.snapshot_cards || {})[key];
    document.getElementById("ind-modal-title").textContent = cd.title;
    document.getElementById("ind-modal-rule").textContent = m && m.rule ? m.rule : "";
    const link = document.getElementById("ind-fred-link");
    link.href = fredUrl(cd.fred);
    link.textContent = `View ${cd.fred.replace(",", " & ")} on FRED ↗`;
    const note = document.getElementById("ind-modal-note");
    note.textContent = "Loading history…";
    if (!dialog.open) dialog.showModal();

    let hist;
    try {
      hist = await loadRegimeHistory();
    } catch (e) {
      note.textContent = `Could not load data/regime_history.json (${e.message}).`;
      return;
    }
    const series = hist.series || {};
    const lines = [{ label: cd.lineLabel || cd.label, data: series[key] || [], unit: cd.unit }];
    (cd.extra || []).forEach((x) => lines.push({ label: x.label, data: series[x.key] || [], unit: cd.unit, secondary: true }));
    const main = lines[0].data;
    if (!main.length) {
      note.textContent = "No history available for this indicator.";
      return;
    }
    active = { cardDef: cd, lines, recessions: hist.recessions || [], firstDate: main[0][0], lastDate: main[main.length - 1][0] };
    fromInput.min = toInput.min = active.firstDate;
    fromInput.max = toInput.max = active.lastDate;
    note.textContent = "Shaded areas indicate U.S. recessions (NBER). Source: FRED, Federal Reserve Bank of St. Louis.";
    applyRange(lastRange);
  }

  rangeButtons.forEach((b) => b.addEventListener("click", () => active && applyRange(b.dataset.range)));
  fromInput.addEventListener("change", applyCustomRange);
  toInput.addEventListener("change", applyCustomRange);
  dialog.querySelector(".ind-modal-close").addEventListener("click", () => dialog.close());
  // A click on the backdrop lands on the <dialog> itself, not its inner wrapper.
  dialog.addEventListener("click", (e) => { if (e.target === dialog) dialog.close(); });

  document.getElementById("regime").addEventListener("click", (e) => {
    const card = e.target.closest(".ind-card");
    if (card) open(card.dataset.key);
  });
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

// ---------------------------------------------------------------- section chart controls

const RANGE_MONTHS = { "3M": 3, "6M": 6, "1Y": 12, "2Y": 24, "5Y": 60, "10Y": 120 };

function chartControlsHTML(section) {
  const { id, chart } = section;
  let html = "";
  if (chart.toggles) {
    html += `
    <div class="series-toggles" role="group" aria-label="Lines shown">
      ${chart.series.map((s, i) => `
        <button type="button" class="series-toggle" data-index="${i}" aria-pressed="true">
          <span class="swatch" style="--swatch:${s.color}"></span>${s.label}
        </button>`).join("")}
    </div>`;
  }
  if (chart.ranges) {
    html += `
    <div class="chart-controls">
      <div class="range-btns" role="group" aria-label="Time range">
        ${chart.ranges.map((r) => `<button type="button" data-range="${r}">${r}</button>`).join("")}
      </div>
      <div class="date-range">
        <label for="${id}-from">From</label><input type="date" id="${id}-from">
        <label for="${id}-to">to</label><input type="date" id="${id}-to">
      </div>
    </div>`;
  }
  return html;
}

// Wires a section's range buttons, date inputs and line toggles to its chart.
// Preset ranges are measured over the lines currently shown, so "Max" starts
// where the longest visible series starts.
function setupChartControls(el, section, data) {
  const { chart } = section;
  const canvasId = `chart-${section.id}`;
  const fromInput = el.querySelector(`#${section.id}-from`);
  const toInput = el.querySelector(`#${section.id}-to`);
  const rangeButtons = [...el.querySelectorAll(".range-btns button")];
  const toggleButtons = [...el.querySelectorAll(".series-toggle")];
  const shown = new Set(chart.series.map((_, i) => i));
  const historyOf = (s) => (getPath(data, s.path) || {}).history || [];
  const span = (series) => {
    const dates = series.flatMap((s) => historyOf(s).map(([d]) => d)).sort();
    return dates.length ? [dates[0], dates[dates.length - 1]] : [null, null];
  };
  const [allFirst, allLast] = span(chart.series);
  let from = null;
  let to = null;
  let activeRange = null; // null while a custom date range is showing

  function draw() {
    if (fromInput) {
      fromInput.value = from || "";
      toInput.value = to || "";
    }
    const visible = chart.series.filter((_, i) => shown.has(i));
    renderLineChart(canvasId, visible, data, from, to, Boolean(chart.toggles));
  }

  function applyRange(range) {
    activeRange = range;
    rangeButtons.forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.range === range)));
    let [firstDate, lastDate] = span(chart.series.filter((_, i) => shown.has(i)));
    if (!firstDate) [firstDate, lastDate] = [allFirst, allLast];
    const months = RANGE_MONTHS[range];
    const start = months ? isoMonthsBefore(lastDate, months) : firstDate;
    from = start < firstDate ? firstDate : start;
    to = lastDate;
    draw();
  }

  function applyCustomRange() {
    if (!fromInput.value || !toInput.value || fromInput.value >= toInput.value) return;
    activeRange = null;
    rangeButtons.forEach((b) => b.setAttribute("aria-pressed", "false"));
    from = fromInput.value;
    to = toInput.value;
    draw();
  }

  toggleButtons.forEach((b) => b.addEventListener("click", () => {
    const i = Number(b.dataset.index);
    if (shown.has(i)) shown.delete(i); else shown.add(i);
    b.setAttribute("aria-pressed", String(shown.has(i)));
    if (activeRange) applyRange(activeRange); else draw();
  }));

  if (chart.ranges && allFirst) {
    fromInput.min = toInput.min = allFirst;
    fromInput.max = toInput.max = allLast;
    rangeButtons.forEach((b) => b.addEventListener("click", () => applyRange(b.dataset.range)));
    fromInput.addEventListener("change", applyCustomRange);
    toInput.addEventListener("change", applyCustomRange);
    applyRange(chart.defaultRange || chart.ranges[chart.ranges.length - 1]);
  } else {
    draw();
  }
}

function renderSection(section, data) {
  const el = document.createElement("section");
  el.id = section.id;
  el.className = "section";

  if (section.kind === "regime") {
    el.innerHTML = renderRegimeSection(data.regime);
    if (data.regime && data.regime.monthly) {
      requestAnimationFrame(() => renderRegimeHistoryChart("regime-history-chart", data.regime.monthly, data.regime.total));
    }
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
    const cols = section.cardColumns ? ` style="--card-cols:${section.cardColumns}"` : "";
    html += `<div class="card-grid"${cols}>${section.cards.map((c) => statCardHTML(c, data)).join("")}</div>`;
  }
  if (section.chart && (section.chart.ranges || section.chart.toggles)) {
    html += `<h3 class="chart-title">${section.chart.title}</h3>${chartControlsHTML(section)}`;
    html += `<div class="chart-box"><canvas id="chart-${section.id}"></canvas></div>`;
    if (section.chart.note) html += `<p class="chart-note">${section.chart.note}</p>`;
  } else if (section.chart) {
    html += `<div class="chart-box"><h3>${section.chart.title}</h3><canvas id="chart-${section.id}"></canvas></div>`;
  }
  if (section.barChart) {
    html += `<div class="chart-box"><h3>${section.barChart.title}</h3><canvas id="bar-${section.id}"></canvas></div>`;
  }
  el.innerHTML = html;

  if (section.chart && (section.chart.ranges || section.chart.toggles)) {
    requestAnimationFrame(() => setupChartControls(el, section, data));
  } else if (section.chart) {
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
  if (data.regime) setupIndicatorModal(data.regime);
}

main();
