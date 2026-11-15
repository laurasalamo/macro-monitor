// Breadth Indicators explorer: indicator list on the left, chart with range
// controls in the middle, theory / interpretation on the right.
// Uses helpers from app.js (fmtPeriod, isoMonthsBefore) and charts.js
// (referenceLines, UP_COLOR, DOWN_COLOR) at call time.

const BI_RANGES = { "1M": 1, "6M": 6, "1Y": 12, "All": null };
const BI_STORAGE_KEY = "bi-selected";
const BI_LINE_COLORS = ["#2563eb", "#d97706", "#7c3aed"];
const BI_NEUTRAL = "#78716c";
// Named colors an indicator line can ask for.
const biColor = (name) => ({ up: UP_COLOR, down: DOWN_COLOR, neutral: BI_NEUTRAL, blue: BI_LINE_COLORS[0], orange: BI_LINE_COLORS[1] }[name]);

let breadthHistoryPromise = null;

function loadBreadthHistory() {
  if (!breadthHistoryPromise) {
    breadthHistoryPromise = fetch("data/breadth_history.json", { cache: "no-store" }).then((res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    });
    breadthHistoryPromise.catch(() => { breadthHistoryPromise = null; });
  }
  return breadthHistoryPromise;
}

function biStored() {
  try { return localStorage.getItem(BI_STORAGE_KEY); } catch { return null; }
}

function biStore(key) {
  try { localStorage.setItem(BI_STORAGE_KEY, key); } catch { /* private mode */ }
}

function renderBreadthIndicatorsSection(el, section, summary) {
  if (!summary || !summary.indicators) {
    el.innerHTML = `<h2>${section.title}</h2><p>No data today (the Yahoo Finance download failed); it will be back on the next update.</p>`;
    return;
  }
  const inds = summary.indicators;
  const keys = inds.map((i) => i.key);
  let current = keys.includes(biStored()) ? biStored() : keys[0];

  el.innerHTML = `
    <div class="history-head">
      <h2>${section.title}</h2>
      <span class="month-badge">${fmtPeriod(summary.as_of, "day")}</span>
    </div>
    <p class="section-desc">${section.description}</p>
    <div class="bi-layout">
      <div class="bi-tabs" role="tablist" aria-label="Breadth indicators">
        ${inds.map((i) => `
          <button type="button" role="tab" class="bi-tab" id="bi-tab-${i.key}" data-key="${i.key}" aria-controls="bi-panel">
            <span class="bi-tab-label">${i.label}</span>
            <span class="bi-tab-value">${i.latest_text}</span>
          </button>`).join("")}
      </div>
      <div class="bi-main" id="bi-panel" role="tabpanel">
        <div class="bi-head"><h3 class="bi-title" id="bi-title"></h3><span class="month-badge bi-latest" id="bi-latest"></span></div>
        <div class="chart-controls">
          <div class="range-btns" role="group" aria-label="Time range">
            ${Object.keys(BI_RANGES).map((r) => `<button type="button" data-range="${r}">${r}</button>`).join("")}
          </div>
          <div class="date-range">
            <label for="bi-from">From</label><input type="date" id="bi-from">
            <label for="bi-to">to</label><input type="date" id="bi-to">
          </div>
        </div>
        <div class="chart-box bi-chart"><canvas id="bi-chart"></canvas></div>
        <div class="fg-legend" id="bi-legend"></div>
        <p class="chart-note" id="bi-status"></p>
      </div>
      <aside class="bi-theory" aria-live="polite">
        <div><h4>Theory</h4><p id="bi-theory"></p></div>
        <div><h4>How to read it</h4><p id="bi-interp"></p></div>
      </aside>
    </div>`;

  const tabs = [...el.querySelectorAll(".bi-tab")];
  const rangeBtns = [...el.querySelectorAll(".range-btns button")];
  const fromInput = el.querySelector("#bi-from");
  const toInput = el.querySelector("#bi-to");
  const status = el.querySelector("#bi-status");
  let history = null;
  let range = "6M";
  const hidden = {}; // indicator key -> Set of line labels switched off in the legend

  function bounds() {
    const ind = history && history.indicators.find((i) => i.key === current);
    const all = ind ? ind.lines.flatMap((l) => (l.data.length ? [l.data[0][0], l.data[l.data.length - 1][0]] : [])) : [];
    return { min: all.length ? all.reduce((a, b) => (a < b ? a : b)) : null, max: all.length ? all.reduce((a, b) => (a > b ? a : b)) : null };
  }

  function draw() {
    const meta = inds.find((i) => i.key === current);
    el.querySelector("#bi-title").textContent = meta.label;
    el.querySelector("#bi-latest").textContent = meta.latest_text;
    el.querySelector("#bi-theory").textContent = meta.theory;
    el.querySelector("#bi-interp").textContent = meta.interpretation;
    tabs.forEach((t) => {
      const on = t.dataset.key === current;
      t.setAttribute("aria-selected", String(on));
      t.tabIndex = on ? 0 : -1;
    });
    if (!history) return;
    const ind = history.indicators.find((i) => i.key === current);
    const { min, max } = bounds();
    fromInput.min = toInput.min = min || "";
    fromInput.max = toInput.max = max || "";
    if (range) {
      rangeBtns.forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.range === range)));
      const months = BI_RANGES[range];
      fromInput.value = months ? isoMonthsBefore(max, months) : min;
      toInput.value = max;
    } else {
      rangeBtns.forEach((b) => b.setAttribute("aria-pressed", "false"));
    }
    const off = hidden[current] || (hidden[current] = new Set());
    const legend = renderBreadthIndicatorChart("bi-chart", ind, fromInput.value, toInput.value, history.index_name, off);
    const legendEl = el.querySelector("#bi-legend");
    const toggles = legend.length > 1;
    legendEl.innerHTML = legend.map((l) => {
      const swatch = `<span class="legend-swatch" style="background:${l.color}${l.dash ? ";height:2px;border-radius:0" : ""}"></span>`;
      return toggles
        ? `<button type="button" class="legend-item bi-toggle" data-label="${l.label}" aria-pressed="${!off.has(l.label)}">${swatch}${l.label}</button>`
        : `<span class="legend-item">${swatch}${l.label}</span>`;
    }).join("") + (toggles ? `<span class="bi-legend-hint">Click to show or hide a line</span>` : "");
    legendEl.querySelectorAll(".bi-toggle").forEach((b) => b.addEventListener("click", () => {
      const label = b.dataset.label;
      if (off.has(label)) off.delete(label); else off.add(label);
      draw();
      legendEl.querySelector(`.bi-toggle[data-label="${CSS.escape(label)}"]`)?.focus();
    }));
  }

  function select(key, focus) {
    current = key;
    biStore(key);
    draw();
    if (focus) el.querySelector(`#bi-tab-${key}`).focus();
  }

  tabs.forEach((t, idx) => {
    t.addEventListener("click", () => select(t.dataset.key));
    t.addEventListener("keydown", (e) => {
      const step = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 }[e.key];
      if (!step) return;
      e.preventDefault();
      select(keys[(idx + step + keys.length) % keys.length], true);
    });
  });
  rangeBtns.forEach((b) => b.addEventListener("click", () => { range = b.dataset.range; draw(); }));
  [fromInput, toInput].forEach((inp) => inp.addEventListener("change", () => {
    if (fromInput.value && toInput.value && fromInput.value <= toInput.value) { range = null; draw(); }
  }));

  draw();
  status.textContent = "Loading history…";
  loadBreadthHistory().then((h) => {
    history = h;
    status.textContent = "Universe: current S&P 500 members (today's list used for the whole history).";
    requestAnimationFrame(draw);
  }).catch(() => {
    status.textContent = "Couldn't load the indicator history. Reload the page to try again.";
  });
}

// Draws one indicator; returns legend entries [{label, color, dash}].
function renderBreadthIndicatorChart(canvasId, ind, from, to, indexName, off = new Set()) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return [];
  const existing = Chart.getChart(canvas);
  if (existing) existing.destroy();
  const css = getComputedStyle(document.documentElement);
  const get = (n) => css.getPropertyValue(n).trim();
  const muted = get("--text-muted");
  const border = get("--border");
  const indexFill = get("--bi-index-fill");
  const indexLine = get("--bi-index-line");

  const inRange = (data) => data.filter(([d]) => d >= from && d <= to).map(([d, v]) => ({ x: d, y: v }));
  const legend = [];
  let lineIdx = 0;
  const datasets = ind.lines.map((line) => {
    const data = inRange(line.data);
    if (line.type === "area" && line.color) {
      // Filled from zero; later areas are drawn on top of earlier ones.
      const c = biColor(line.color);
      legend.push({ label: line.label, color: c });
      return {
        type: "line", label: line.label, data, yAxisID: "y", order: 2, hidden: off.has(line.label),
        borderColor: c, borderWidth: 1, backgroundColor: c + "b3",
        fill: "origin", pointRadius: 0, pointHoverRadius: 3, tension: 0,
      };
    }
    if (line.type === "area") {
      legend.push({ label: line.label, color: indexLine });
      return {
        type: "line", label: line.label, data, yAxisID: "y2", order: 3, hidden: off.has(line.label),
        borderColor: indexLine, borderWidth: 1, backgroundColor: indexFill,
        fill: "start", pointRadius: 0, pointHoverRadius: 3, tension: 0,
      };
    }
    if (line.type === "bar") {
      let colors;
      if (line.sign_colors) {
        colors = data.map((p) => (p.y >= 0 ? UP_COLOR : DOWN_COLOR) + "b3");
        legend.push({ label: `${line.label} (green up / red down)`, color: UP_COLOR });
      } else if (line.extreme) {
        const [lo, hi] = line.extreme;
        colors = data.map((p) => (p.y >= hi ? UP_COLOR : p.y <= lo ? DOWN_COLOR : muted) + (p.y >= hi || p.y <= lo ? "e6" : "80"));
        legend.push({ label: `${line.label} (green ≥ ${hi}%, red ≤ ${lo}%)`, color: muted });
      } else {
        const c = line.color === "up" ? UP_COLOR : line.color === "down" ? DOWN_COLOR : muted;
        colors = c + "cc";
        legend.push({ label: line.label, color: c });
      }
      return {
        type: "bar", label: line.label, data, yAxisID: "y", order: 2, hidden: off.has(line.label),
        backgroundColor: colors, borderWidth: 0, barPercentage: 1, categoryPercentage: 1, grouped: false,
      };
    }
    const dashed = !!line.dash;
    const color = line.color ? biColor(line.color) : dashed ? muted : BI_LINE_COLORS[lineIdx++ % BI_LINE_COLORS.length];
    legend.push({ label: line.label, color, dash: dashed });
    return {
      type: "line", label: line.label, data, yAxisID: "y", order: 1, hidden: off.has(line.label),
      borderColor: color, borderWidth: dashed ? 1.25 : line.color ? 2 : 1.75, borderDash: dashed ? [5, 4] : [],
      pointRadius: 0, pointHoverRadius: 4, tension: 0.1, fill: false,
    };
  });

  const hasY2 = ind.lines.some((l) => l.axis === "y2");
  const refs = (ind.refs || []).map((r) => (typeof r === "object"
    // Labelled level: dashed line in its tone with a value pill.
    ? { value: r.value, color: r.tone === "neutral" ? "#a8a29e" : biColor(r.tone), dash: [5, 4], label: `${r.value}${ind.unit === "%" ? "%" : ""}` }
    : { value: r, color: r === 0 || r === 50 ? muted : border, dash: r === 0 ? [] : [4, 4] }));
  const yScale = { position: "left", ticks: { color: muted }, grid: { color: border } };
  if (ind.range) { yScale.min = ind.range[0]; yScale.max = ind.range[1]; }
  if (ind.unit === "%") yScale.ticks.callback = (v) => `${v}%`;
  const spanDays = (new Date(to) - new Date(from)) / 864e5;
  const unit = spanDays <= 70 ? "week" : spanDays <= 800 ? "month" : "year";
  // Tick values are local-midnight timestamps (the date adapter parses
  // "YYYY-MM-DD" as local time), so use local getters.
  const periodKey = (v) => {
    const d = new Date(v);
    if (unit === "year") return d.getFullYear();
    if (unit === "month") return d.getFullYear() * 12 + d.getMonth();
    const day = Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()) / 864e5;
    return Math.floor((day + 3) / 7); // weeks starting Monday
  };
  const periodLabel = (v, first) => {
    const d = new Date(v);
    if (unit === "year") return String(d.getFullYear());
    if (unit === "week") return d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
    const withYear = first || d.getMonth() === 0;
    return d.toLocaleDateString("en-GB", { month: "short", ...(withYear ? { year: "numeric" } : {}) });
  };
  const fmt = (v) => (Number.isInteger(v) || Math.abs(v) >= 1000 ? v.toLocaleString(undefined, { maximumFractionDigits: 0 }) : v.toFixed(Math.abs(v) < 10 ? 2 : 1));

  new Chart(canvas.getContext("2d"), {
    data: { datasets },
    plugins: [referenceLines],
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      scales: {
        x: {
          type: "timeseries", offset: ind.lines.some((l) => l.type === "bar"),
          // One tick per trading day; label only the first day of each period.
          ticks: {
            source: "data", autoSkip: false, maxRotation: 0, color: muted,
            callback: (value, i, ticks) => {
              if (i && periodKey(ticks[i - 1].value) === periodKey(value)) return "";
              if (i === 0) {
                // Skip the first label if the next period starts too close to it.
                const next = ticks.findIndex((t) => periodKey(t.value) !== periodKey(value));
                if (next !== -1 && next < ticks.length * 0.08) return "";
              }
              return periodLabel(value, i === 0);
            },
          },
          grid: { color: (c) => (c.tick && c.tick.label ? border : "transparent") },
        },
        y: yScale,
        ...(hasY2 ? { y2: { position: "right", grid: { display: false }, ticks: { color: muted }, title: { display: true, text: indexName, color: muted } } } : {}),
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (c) => `${c.dataset.label}: ${fmt(c.parsed.y)}${ind.unit === "%" ? "%" : ""}`,
          },
        },
        referenceLines: { lines: refs },
      },
      interaction: { mode: "index", intersect: false },
    },
  });
  return legend;
}
