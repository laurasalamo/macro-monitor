// Chart.js render helpers. One generic line-chart renderer serves every
// section because every metric in data.json shares the same leaf shape.

const CHART_COLORS = ["#2563eb", "#dc2626", "#d97706", "#16a34a", "#7c3aed", "#0891b2"];

function renderLineChart(canvasId, seriesDefs, data) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;

  const datasets = seriesDefs.map((s, i) => {
    const m = getPath(data, s.path);
    const hist = (m && m.history) || [];
    return {
      label: s.label,
      data: hist.map(([d, v]) => ({ x: d, y: v })),
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
        x: { type: "time", time: { unit: "month" }, ticks: { maxRotation: 0 } },
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
