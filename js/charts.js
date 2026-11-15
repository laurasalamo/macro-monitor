// Chart.js render helpers. One generic line-chart renderer serves every
// section because every metric in data.json shares the same leaf shape.

const CHART_COLORS = ["#2563eb", "#dc2626", "#d97706", "#16a34a", "#7c3aed", "#0891b2"];

const UP_COLOR = "#16a34a";
const DOWN_COLOR = "#dc2626";

// Options (all optional): `from`/`to` (ISO dates) limit the chart to a window;
// only points inside it are plotted so the y-axis fits the visible range.
// `hideLegend` is for charts whose toggle chips or title already name the
// lines. `unit` suffixes the y-axis and tooltip values. `bars` draws bars,
// green above zero and red below. `timeUnit: "quarter"` labels ticks Q2'26 on windows up to 3 years.
// Re-rendering the same canvas replaces its chart.
function renderLineChart(canvasId, seriesDefs, data, opts = {}) {
  const { from, to, hideLegend, unit = "", bars, timeUnit } = opts;
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const existing = Chart.getChart(canvas);
  if (existing) existing.destroy();
  const inWindow = ([d]) => (!from || d >= from) && (!to || d <= to);
  const num = (v) => v.toLocaleString(undefined, { maximumFractionDigits: 2 });

  const datasets = seriesDefs.map((s, i) => {
    const m = getPath(data, s.path);
    const points = ((m && m.history) || []).filter(inWindow).map(([d, v]) => ({ x: d, y: v }));
    const color = s.color || CHART_COLORS[i % CHART_COLORS.length];
    return bars
      ? { label: s.label, data: points, backgroundColor: points.map((p) => (p.y < 0 ? DOWN_COLOR : UP_COLOR)), borderRadius: 3 }
      : { label: s.label, data: points, borderColor: color, backgroundColor: "transparent", borderWidth: 1.5, pointRadius: 0, tension: 0.15 };
  });

  // Quarter labels only on short windows; longer ones get automatic (year) ticks.
  const shortWindow = from && to && localDate(to) - localDate(from) <= 3 * 365.25 * 864e5;
  const time = timeUnit === "quarter" && shortWindow
    ? { unit: "quarter", displayFormats: { quarter: "QQQ''yy" }, tooltipFormat: "QQQ yyyy" }
    : from || to ? {} : { unit: "month" };
  // Bars sit between ticks, so pad the window by half a period on each side.
  const x = { type: "time", time, offset: Boolean(bars), ticks: { maxRotation: 0, autoSkipPadding: 16 } };
  if (from && !bars) x.min = localDate(from).getTime();
  if (to && !bars) x.max = localDate(to).getTime();

  new Chart(canvas.getContext("2d"), {
    type: bars ? "bar" : "line",
    data: { datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x,
        y: { beginAtZero: Boolean(bars), ticks: { callback: (v) => `${num(v)}${unit}` } },
      },
      plugins: {
        legend: { display: !hideLegend, position: "bottom" },
        tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${num(c.parsed.y)}${unit}` } },
      },
      interaction: { mode: "nearest", intersect: false },
    },
  });
}

// Horizontal bars for a list of {label, value}, green for gains and red for losses.
function renderBarChart(canvasId, items) {
  const canvas = document.getElementById(canvasId);
  if (!canvas || !items || !items.length) return;

  new Chart(canvas.getContext("2d"), {
    type: "bar",
    data: {
      labels: items.map((i) => i.label),
      datasets: [
        {
          label: "MoM Δ (thousands)",
          data: items.map((i) => i.value),
          backgroundColor: items.map((i) => (i.value < 0 ? DOWN_COLOR : UP_COLOR)),
          borderRadius: 3,
        },
      ],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
    },
  });
}

// Maturity of each tenor label, in years.
function tenorYears(label) {
  const n = parseFloat(label);
  return label.endsWith("M") ? n / 12 : n;
}

// The x-axis is maturity on a square-root scale: true to the order and
// relative distances of maturities, without squashing 1M-1Y into a sliver
// next to 30Y.
function renderYieldCurveChart(canvasId, yieldCurve) {
  const canvas = document.getElementById(canvasId);
  if (!canvas || !yieldCurve) return;
  const css = getComputedStyle(document.documentElement);
  const muted = css.getPropertyValue("--text-muted").trim();
  const border = css.getPropertyValue("--border").trim();

  const points = (curve) => (curve || []).map(([label, y]) => ({ x: Math.sqrt(tenorYears(label)), y, label }));
  const current = points(yieldCurve.current);
  const labelAt = new Map(current.map((p) => [p.x, p.label]));

  new Chart(canvas.getContext("2d"), {
    type: "line",
    data: {
      datasets: [
        {
          label: "Current",
          data: current,
          borderColor: "#3b82f6",
          backgroundColor: "#3b82f6",
          borderWidth: 2.5,
          pointRadius: 4,
          pointHoverRadius: 6,
        },
        {
          label: "1Y Ago",
          data: points(yieldCurve.one_year_ago),
          borderColor: "#9ca3af",
          borderDash: [5, 5],
          borderWidth: 1.5,
          pointRadius: 0,
          pointHoverRadius: 4,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      layout: { padding: { left: 6, right: 12 } },
      datasets: { line: { clip: false, tension: 0 } }, // don't cut the end dots in half
      scales: {
        x: {
          type: "linear",
          min: current.length ? current[0].x : undefined,
          max: current.length ? current[current.length - 1].x : undefined,
          grid: { display: false },
          border: { display: false },
          // One tick per tenor, labelled with its name.
          afterBuildTicks: (axis) => { axis.ticks = current.map((p) => ({ value: p.x })); },
          ticks: { color: muted, autoSkip: true, autoSkipPadding: 6, maxRotation: 0, callback: (v) => labelAt.get(v) || "" },
        },
        y: {
          grid: { color: border },
          border: { display: false },
          ticks: { color: muted, maxTicksLimit: 6, callback: (v) => `${v.toLocaleString(undefined, { maximumFractionDigits: 2 })}%` },
        },
      },
      plugins: {
        legend: { position: "top", align: "start", labels: { boxHeight: 0, boxWidth: 28, color: muted } },
        tooltip: {
          callbacks: {
            title: (items) => items[0].raw.label,
            label: (c) => `${c.dataset.label}: ${c.parsed.y.toFixed(2)}%`,
          },
        },
      },
      interaction: { mode: "nearest", intersect: false, axis: "x" },
    },
  });
}

// ---------------------------------------------------------------- indicator pop-up chart

function localDate(isoDate) {
  const [y, m, d] = isoDate.split("-").map(Number);
  return new Date(y, m - 1, d);
}

// Gray bands behind the lines for each recession. Ranges are [firstMonth, lastMonth]
// from USREC, so a band runs to the end of its last month.
const recessionShading = {
  id: "recessionShading",
  beforeDatasetsDraw(chart, _args, opts) {
    const { ctx, chartArea: area, scales: { x } } = chart;
    ctx.save();
    ctx.fillStyle = opts.color;
    for (const [start, end] of opts.ranges || []) {
      const last = localDate(end);
      const x0 = Math.max(x.getPixelForValue(localDate(start).getTime()), area.left);
      const x1 = Math.min(x.getPixelForValue(new Date(last.getFullYear(), last.getMonth() + 1, 1).getTime()), area.right);
      if (x1 > x0) ctx.fillRect(x0, area.top, x1 - x0, area.bottom - area.top);
    }
    ctx.restore();
  },
};

let indicatorChart = null;

function renderIndicatorChart(canvasId, lines, recessions, from, to) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const css = getComputedStyle(document.documentElement);
  const muted = css.getPropertyValue("--text-muted").trim();
  const border = css.getPropertyValue("--border").trim();

  // Only plot the visible window so the y-axis fits it, like FRED does.
  const datasets = lines.map((line, i) => ({
    label: line.label,
    data: line.data.filter(([d]) => d >= from && d <= to).map(([d, v]) => ({ x: d, y: v })),
    borderColor: line.secondary ? muted : CHART_COLORS[i % CHART_COLORS.length],
    borderWidth: line.secondary ? 1 : 1.75,
    backgroundColor: "transparent",
    pointRadius: 0,
    tension: 0,
    order: line.secondary ? 1 : 0,
  }));
  const unit = lines[0].unit;

  if (indicatorChart) indicatorChart.destroy();
  indicatorChart = new Chart(canvas.getContext("2d"), {
    type: "line",
    data: { datasets },
    plugins: [recessionShading],
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      parsing: true,
      scales: {
        x: {
          type: "time",
          min: localDate(from).getTime(),
          max: localDate(to).getTime(),
          ticks: { maxRotation: 0, autoSkipPadding: 16, color: muted },
          grid: { color: border },
        },
        y: {
          ticks: { color: muted, callback: (v) => `${v.toLocaleString(undefined, { maximumFractionDigits: 2 })}${unit}` },
          // Emphasize zero, where spreads invert and payrolls turn negative.
          grid: { color: (c) => (c.tick && c.tick.value === 0 ? muted : border) },
        },
      },
      plugins: {
        legend: { display: lines.length > 1, position: "bottom", labels: { color: muted } },
        tooltip: {
          callbacks: {
            label: (c) => `${c.dataset.label}: ${c.parsed.y.toLocaleString(undefined, { maximumFractionDigits: 2 })}${unit}`,
          },
        },
        recessionShading: { ranges: recessions, color: css.getPropertyValue("--recession").trim() },
      },
      interaction: { mode: "index", intersect: false },
    },
  });
}

// ---------------------------------------------------------------- regime history bars

// Dashed horizontal lines at fixed y values (e.g. the +3 Bullish cutoff) plus a solid zero line.
const referenceLines = {
  id: "referenceLines",
  afterDatasetsDraw(chart, _args, opts) {
    const { ctx, chartArea: area, scales: { y } } = chart;
    ctx.save();
    for (const line of opts.lines || []) {
      if (line.value < y.min || line.value > y.max) continue;
      const py = Math.round(y.getPixelForValue(line.value)) + 0.5;
      ctx.strokeStyle = line.color;
      ctx.lineWidth = 1;
      ctx.setLineDash(line.dash || []);
      ctx.beginPath();
      ctx.moveTo(area.left, py);
      ctx.lineTo(area.right, py);
      ctx.stroke();
      if (line.label) {
        // Value pill at the left edge, e.g. a green "80" on an overbought line.
        ctx.setLineDash([]);
        ctx.font = "600 11px system-ui, -apple-system, sans-serif";
        const w = ctx.measureText(line.label).width + 10;
        const h = 18;
        ctx.fillStyle = line.color;
        ctx.beginPath();
        ctx.roundRect(area.left + 6, py - h / 2, w, h, 4);
        ctx.fill();
        ctx.fillStyle = "#fff";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(line.label, area.left + 6 + w / 2, py + 0.5);
      }
    }
    ctx.restore();
  },
};

function renderRegimeHistoryChart(canvasId, monthly, total) {
  const canvas = document.getElementById(canvasId);
  if (!canvas || !monthly.length) return;
  const css = getComputedStyle(document.documentElement);
  const v = (name) => css.getPropertyValue(name).trim();
  const fill = { Bullish: v("--bull-fill"), Neutral: v("--neut-fill"), Bearish: v("--bear-fill") };
  const muted = v("--text-muted");
  const cutoff = 3; // keep in sync with NET_SCORE_THRESHOLD in scripts/regime_logic.py
  const anyNegative = monthly.some((m) => m.net < 0);
  const last = monthly.length - 1;

  new Chart(canvas.getContext("2d"), {
    type: "bar",
    data: {
      labels: monthly.map((m) => m.month),
      datasets: [{
        data: monthly.map((m) => m.net),
        backgroundColor: monthly.map((m) => fill[m.label]),
        borderRadius: 4,
        borderSkipped: false,
        minBarLength: 3, // keep net-zero months visible
        categoryPercentage: 0.92,
        barPercentage: 0.94,
      }],
    },
    plugins: [referenceLines],
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      scales: {
        x: {
          grid: { display: false },
          border: { display: false },
          // Label every 12th month counting back from the latest, like 2024-10 / 2025-10 / 2026-10.
          ticks: { color: muted, maxRotation: 0, autoSkip: false, callback: (_val, i) => ((last - i) % 12 === 0 ? monthly[i].month : "") },
        },
        y: { display: false, min: anyNegative ? -total : 0, max: total },
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          displayColors: false,
          callbacks: {
            title: (items) => `${monthly[items[0].dataIndex].month} — ${monthly[items[0].dataIndex].label}`,
            label: (item) => {
              const m = monthly[item.dataIndex];
              return [`Net score ${m.net > 0 ? "+" : ""}${m.net}`, `${m.bullish} bullish · ${m.neutral} neutral · ${m.bearish} bearish`];
            },
          },
        },
        referenceLines: {
          lines: [
            { value: 0, color: v("--border") },
            { value: cutoff, color: muted, dash: [4, 4] },
            { value: -cutoff, color: muted, dash: [4, 4] },
          ],
        },
      },
    },
  });
}

// ---------------------------------------------------------------- fear & greed

// Rating band colors come from the --fg-* CSS tokens so dark mode gets its own steps.
function fearGreedColors() {
  const css = getComputedStyle(document.documentElement);
  const get = (n) => css.getPropertyValue(n).trim();
  return {
    "Extreme Fear": get("--fg-xfear"), "Fear": get("--fg-fear"), "Neutral": get("--fg-neutral"),
    "Greed": get("--fg-greed"), "Extreme Greed": get("--fg-xgreed"),
    muted: get("--text-muted"), border: get("--border"), text: get("--text"),
  };
}

// Faint horizontal bands behind the timeline, one per rating zone.
const zoneBands = {
  id: "zoneBands",
  beforeDatasetsDraw(chart, _args, opts) {
    const { ctx, chartArea: area, scales: { y } } = chart;
    ctx.save();
    ctx.globalAlpha = 0.12;
    let lower = 0;
    for (const [upper, label] of opts.bands || []) {
      const top = y.getPixelForValue(Math.min(upper, 100));
      const bottom = y.getPixelForValue(lower);
      ctx.fillStyle = opts.colors[label];
      ctx.fillRect(area.left, top, area.right - area.left, bottom - top);
      lower = upper;
    }
    ctx.restore();
  },
};

function renderFearGreedTimeline(canvasId, history, bands) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const existing = Chart.getChart(canvas);
  if (existing) existing.destroy();
  const c = fearGreedColors();
  const ratingOf = (v) => {
    const s = Math.round(v);
    return (bands.find(([upper]) => s < upper) || bands[bands.length - 1])[1];
  };
  new Chart(canvas.getContext("2d"), {
    type: "line",
    data: {
      datasets: [{
        label: "Fear & Greed",
        data: history.map(([d, v]) => ({ x: d, y: v })),
        borderColor: c.text,
        borderWidth: 2,
        backgroundColor: "transparent",
        pointRadius: 0,
        pointHoverRadius: 4,
        tension: 0.15,
      }],
    },
    plugins: [zoneBands],
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      scales: {
        x: { type: "time", ticks: { maxRotation: 0, autoSkipPadding: 16, color: c.muted }, grid: { color: c.border } },
        y: { min: 0, max: 100, ticks: { stepSize: 25, color: c.muted }, grid: { color: c.border } },
      },
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: (ctx) => `${Math.round(ctx.parsed.y)} · ${ratingOf(ctx.parsed.y)}` } },
        zoneBands: { bands, colors: c },
      },
      interaction: { mode: "index", intersect: false },
    },
  });
}

// Compact chart for one indicator's raw signal (and its moving average, if any).
function renderMiniChart(canvasId, lines, unit) {
  const canvas = document.getElementById(canvasId);
  if (!canvas || !lines || !lines.length) return;
  const existing = Chart.getChart(canvas);
  if (existing) existing.destroy();
  const c = fearGreedColors();
  const num = (v) => v.toLocaleString(undefined, { maximumFractionDigits: 2 });
  new Chart(canvas.getContext("2d"), {
    type: "line",
    data: {
      datasets: lines.map((line, i) => ({
        label: line.label,
        data: line.data.map(([d, v]) => ({ x: d, y: v })),
        borderColor: i === 0 ? CHART_COLORS[0] : c.muted,
        borderWidth: i === 0 ? 1.75 : 1.25,
        borderDash: i === 0 ? [] : [4, 3],
        backgroundColor: "transparent",
        pointRadius: 0,
        tension: 0.1,
      })),
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      scales: {
        x: { type: "time", time: { unit: "month" }, ticks: { maxRotation: 0, autoSkipPadding: 12, color: c.muted, font: { size: 10 } }, grid: { display: false } },
        y: { ticks: { color: c.muted, font: { size: 10 }, maxTicksLimit: 4, callback: (v) => num(v) }, grid: { color: (g) => (g.tick && g.tick.value === 0 ? c.muted : c.border) } },
      },
      plugins: {
        legend: { display: lines.length > 1, position: "bottom", labels: { color: c.muted, boxWidth: 12, boxHeight: 2, font: { size: 10 } } },
        tooltip: { callbacks: { label: (ctx) => `${ctx.dataset.label}: ${num(ctx.parsed.y)}` } },
      },
      interaction: { mode: "index", intersect: false },
    },
  });
}

// ---------------------------------------------------------------- market breadth

// Shaded risk bands (0-high, high-risk) with a small label inside each, and a
// dashed 50% midline. Drawn behind the line.
const riskBands = {
  id: "riskBands",
  beforeDatasetsDraw(chart, _args, opts) {
    const { ctx, chartArea: area, scales: { y } } = chart;
    const yRisk = y.getPixelForValue(opts.risk);
    const yHigh = y.getPixelForValue(opts.high);
    const yZero = y.getPixelForValue(0);
    const y50 = Math.round(y.getPixelForValue(50)) + 0.5;
    ctx.save();
    ctx.globalAlpha = 0.2;
    ctx.fillStyle = opts.riskColor;
    ctx.fillRect(area.left, yRisk, area.right - area.left, yHigh - yRisk);
    ctx.fillStyle = opts.highColor;
    ctx.fillRect(area.left, yHigh, area.right - area.left, yZero - yHigh);
    ctx.globalAlpha = 1;
    ctx.strokeStyle = opts.muted;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(area.left, y50);
    ctx.lineTo(area.right, y50);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.font = "600 10px -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
    ctx.textBaseline = "middle";
    ctx.textAlign = "left";
    // Labels sit in the right-hand gutter (layout.padding.right), clear of the line.
    const x = area.right + 6;
    ctx.fillStyle = opts.text;
    ctx.fillText("Risk", x, (yRisk + yHigh) / 2);
    ctx.fillText("High risk", x, (yHigh + yZero) / 2);
    ctx.restore();
  },
};

function renderBreadthChart(canvasId, history, risk, high) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const existing = Chart.getChart(canvas);
  if (existing) existing.destroy();
  const css = getComputedStyle(document.documentElement);
  const get = (n) => css.getPropertyValue(n).trim();
  const colors = {
    line: CHART_COLORS[0], riskColor: get("--zone-risk"), highColor: get("--zone-high"),
    muted: get("--text-muted"), border: get("--border"), text: get("--text"),
  };
  // The line turns orange/red while it's inside a risk band.
  const segColor = (v) => (v < high ? colors.highColor : v < risk ? colors.riskColor : colors.line);
  const zoneOf = (v) => (v < high ? "High risk" : v < risk ? "Risk zone" : "Normal");

  new Chart(canvas.getContext("2d"), {
    type: "line",
    data: {
      datasets: [{
        label: "% above 20-day average",
        data: history.map(([d, v]) => ({ x: d, y: v })),
        borderWidth: 1.75,
        borderColor: colors.line,
        segment: { borderColor: (ctx) => segColor(Math.max(ctx.p0.parsed.y, ctx.p1.parsed.y)) },
        fill: { target: "origin", above: colors.line + "14" },
        pointRadius: 0,
        pointHoverRadius: 4,
        tension: 0.1,
      }],
    },
    plugins: [riskBands],
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      layout: { padding: { right: 58 } },
      scales: {
        x: { type: "time", ticks: { maxRotation: 0, autoSkipPadding: 16, color: colors.muted }, grid: { color: colors.border } },
        y: { min: 0, max: 100, ticks: { stepSize: 25, color: colors.muted, callback: (v) => `${v}%` }, grid: { color: colors.border } },
      },
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: (c) => `${c.parsed.y.toFixed(1)}% · ${zoneOf(c.parsed.y)}` } },
        riskBands: { risk, high, ...colors },
      },
      interaction: { mode: "index", intersect: false },
    },
  });
}
