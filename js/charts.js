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
