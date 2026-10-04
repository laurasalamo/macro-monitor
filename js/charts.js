// Chart.js render helpers. One generic line-chart renderer serves every
// section because every metric in data.json shares the same leaf shape.

const CHART_COLORS = ["#2563eb", "#dc2626", "#d97706", "#16a34a", "#7c3aed", "#0891b2"];

// `from`/`to` (ISO dates, optional) limit the chart to a window; only points
// inside it are plotted so the y-axis fits the visible range. Re-rendering the
// same canvas replaces its chart.
function renderLineChart(canvasId, seriesDefs, data, from, to) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const existing = Chart.getChart(canvas);
  if (existing) existing.destroy();
  const inWindow = ([d]) => (!from || d >= from) && (!to || d <= to);

  const datasets = seriesDefs.map((s, i) => {
    const m = getPath(data, s.path);
    const hist = (m && m.history) || [];
    return {
      label: s.label,
      data: hist.filter(inWindow).map(([d, v]) => ({ x: d, y: v })),
      borderColor: s.color || CHART_COLORS[i % CHART_COLORS.length],
      backgroundColor: "transparent",
      borderWidth: 1.5,
      pointRadius: 0,
      tension: 0.15,
    };
  });

  new Chart(canvas.getContext("2d"), {
    type: "line",
    data: { datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: from || to
          ? { type: "time", min: from ? localDate(from).getTime() : undefined, max: to ? localDate(to).getTime() : undefined,
              ticks: { maxRotation: 0, autoSkipPadding: 16 } }
          : { type: "time", time: { unit: "month" }, ticks: { maxRotation: 0 } },
        y: { beginAtZero: false },
      },
      plugins: { legend: { position: "bottom" } },
      interaction: { mode: "nearest", intersect: false },
    },
  });
}

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
          backgroundColor: "#16a34a",
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

function renderYieldCurveChart(canvasId, yieldCurve) {
  const canvas = document.getElementById(canvasId);
  if (!canvas || !yieldCurve) return;

  const labels = (yieldCurve.current || []).map((p) => p[0]);

  new Chart(canvas.getContext("2d"), {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Current",
          data: (yieldCurve.current || []).map((p) => p[1]),
          borderColor: "#2563eb",
          backgroundColor: "transparent",
          pointRadius: 3,
        },
        {
          label: "1 Year Ago",
          data: (yieldCurve.one_year_ago || []).map((p) => p[1]),
          borderColor: "#9ca3af",
          borderDash: [4, 4],
          backgroundColor: "transparent",
          pointRadius: 3,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: "bottom" } },
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
          ticks: { color: muted, callback: (v) => `${v}${unit}` },
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
