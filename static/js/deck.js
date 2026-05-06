(function () {
  function parseChart(canvas) {
    try {
      return JSON.parse(canvas.dataset.chart || "{}");
    } catch (error) {
      return null;
    }
  }

  function chartConfig(chart) {
    var firstSeries = (chart.series || [])[0] || {};
    var labels = chart.labels || [];
    var values = firstSeries.values || [];
    var type = chart.chart_type === "donut" ? "doughnut" : chart.chart_type;

    if (!labels.length || !values.length || !window.Chart) {
      return null;
    }

    return {
      type: type,
      data: {
        labels: labels,
        datasets: [
          {
            label: firstSeries.name || chart.title || "Показатель",
            data: values,
            borderColor: "#0077C8",
            backgroundColor: ["#0077C8", "#66B5E8", "#CFE6F7", "#003D73", "#7D8793", "#EAF4FC"],
            borderWidth: 2,
            tension: 0.35,
            fill: chart.chart_type !== "line",
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        plugins: {
          legend: { display: chart.chart_type === "donut" },
          title: { display: false },
        },
        scales: chart.chart_type === "donut" ? {} : {
          x: { grid: { display: false }, ticks: { color: "#5C6F88" } },
          y: { grid: { color: "rgba(0,119,200,.12)" }, ticks: { color: "#5C6F88" } },
        },
      },
    };
  }

  function renderCharts() {
    if (!window.Chart) {
      return;
    }
    document.querySelectorAll("canvas[data-chart]").forEach(function (canvas) {
      var chart = parseChart(canvas);
      var config = chart && chartConfig(chart);
      if (!config) {
        return;
      }
      canvas.style.display = "block";
      var fallback = canvas.parentElement && canvas.parentElement.querySelector(".mvp-chart-fallback");
      if (fallback) {
        fallback.style.display = "none";
      }
      new window.Chart(canvas, config);
    });
  }

  function loadLocalChartJs() {
    if (window.Chart || document.querySelector('script[data-local-chartjs="true"]')) {
      renderCharts();
      return;
    }
    var script = document.createElement("script");
    script.src = "/static/vendor/chart.umd.js";
    script.defer = true;
    script.dataset.localChartjs = "true";
    script.onload = renderCharts;
    script.onerror = function () {
      // Keep the HTML/CSS fallback chart when Chart.js is not installed locally.
    };
    document.head.appendChild(script);
  }

  function updateFullscreenButtons() {
    var label = document.fullscreenElement ? "Выйти из полного экрана" : "Полный экран";
    document.querySelectorAll("[data-fullscreen-toggle]").forEach(function (button) {
      button.textContent = label;
    });
  }

  function toggleFullscreen() {
    if (!document.fullscreenElement) {
      var target = document.querySelector(".mvp-deck-wrapper") || document.documentElement;
      if (target.requestFullscreen) {
        target.requestFullscreen().then(updateFullscreenButtons).catch(function () {});
      }
      return;
    }

    if (document.exitFullscreen) {
      document.exitFullscreen().then(updateFullscreenButtons).catch(function () {});
    }
  }

  function bindFullscreenControls() {
    document.querySelectorAll("[data-fullscreen-toggle]").forEach(function (button) {
      button.addEventListener("click", toggleFullscreen);
    });
    document.addEventListener("fullscreenchange", updateFullscreenButtons);
    updateFullscreenButtons();
  }

  document.addEventListener("DOMContentLoaded", function () {
    loadLocalChartJs();
    bindFullscreenControls();
  });
})();
