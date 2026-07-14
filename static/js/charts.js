/* Render every canvas[data-chart-url] with Chart.js using theme colors. */
(function () {
  "use strict";
  if (typeof Chart === "undefined") return;

  var css = getComputedStyle(document.documentElement);
  var colors = [
    css.getPropertyValue("--accent").trim() || "#2f81f7",
    css.getPropertyValue("--green").trim() || "#3fb950",
    css.getPropertyValue("--purple").trim() || "#a371f7",
    css.getPropertyValue("--yellow").trim() || "#d29922"
  ];
  var gridColor = "rgba(154, 167, 180, 0.15)";
  var textColor = css.getPropertyValue("--text-dim").trim() || "#9aa7b4";

  function render(canvas) {
    fetch(canvas.dataset.chartUrl)
      .then(function (response) { return response.json(); })
      .then(function (payload) {
        var type = canvas.dataset.chartType || "line";
        var datasets = (payload.series || []).map(function (series, index) {
          return {
            label: series.label,
            data: series.data,
            borderColor: colors[index % colors.length],
            backgroundColor: type === "bar"
              ? colors[index % colors.length] + "55"
              : colors[index % colors.length] + "22",
            tension: 0.25,
            spanGaps: true,
            fill: type === "line" && index === 0,
            pointRadius: 3
          };
        });
        var hasData = datasets.some(function (d) {
          return (d.data || []).some(function (v) { return v !== null && v !== undefined; });
        });
        var box = canvas.closest(".chart-box");
        if (!hasData && box) {
          box.innerHTML = '<div class="empty"><span class="icon">📊</span>No data yet</div>';
          return;
        }
        new Chart(canvas.getContext("2d"), {
          type: type,
          data: { labels: payload.labels, datasets: datasets },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { labels: { color: textColor } } },
            scales: {
              x: { ticks: { color: textColor, maxTicksLimit: 8 }, grid: { color: gridColor } },
              y: { ticks: { color: textColor }, grid: { color: gridColor } }
            }
          }
        });
      })
      .catch(function () { /* leave the empty canvas */ });
  }

  document.querySelectorAll("canvas[data-chart-url]").forEach(render);

  // Selects that retarget a chart (measurement field / exercise pickers).
  document.querySelectorAll("[data-chart-select]").forEach(function (select) {
    select.addEventListener("change", function () {
      var box = document.getElementById(select.dataset.chartSelect);
      if (!box) return;
      var canvas = document.createElement("canvas");
      canvas.dataset.chartUrl = select.value;
      canvas.dataset.chartType = box.dataset.chartType || "line";
      box.innerHTML = "";
      box.appendChild(canvas);
      render(canvas);
    });
  });
})();
