/**
 * Statistics Page Charts
 * Creates and initializes Chart.js visualizations for user activity statistics with theme support.
 */

const PALETTE = ['#6c63ff', '#00d4aa', '#ff6b9d', '#ffa94d', '#4dabf7', '#a855f7'];
const ACCENT = '#6c63ff';
const ACCENT_SOFT = 'rgba(108, 99, 255, 0.15)';

/**
 * Check if dark theme is currently active.
 */
function isDark() {
  return document.documentElement.getAttribute('data-theme') === 'dark';
}

/**
 * Get axis tick color based on current theme.
 */
function tickColor() { return isDark() ? '#6b7394' : '#6c757d'; }

/**
 * Get grid color based on current theme.
 */
function gridColor() { return isDark() ? '#2a2d45' : '#f3f4f6'; }

/**
 * Parse comma-separated dataset values from HTML element attribute.
 */
function parseList(el, attr) {
  return el.dataset[attr].split(',').map(s => s.trim()).filter(Boolean);
}

/**
 * Create and render a doughnut chart showing categorical data distribution.
 */
function makeDoughnutChart(id, labels, data) {
  new Chart(document.getElementById(id), {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{
        data,
        backgroundColor: PALETTE,
        borderWidth: 0,
        hoverOffset: 8,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
    }
  });
}

/**
 * Create chart axis scale configuration with theme-aware colors.
 */
function _chartScales() {
  return {
    x: { grid: { display: false }, ticks: { color: tickColor(), font: { size: 12 } } },
    y: { beginAtZero: true, ticks: { stepSize: 1, color: tickColor(), font: { size: 12 } }, grid: { color: gridColor() } }
  };
}

/**
 * Create base chart options shared by bar and line charts.
 */
function _baseChartOpts() {
  return { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: _chartScales() };
}

/**
 * Create and render a bar chart for time-series or categorical data.
 */
function makeBarChart(id, labels, data) {
  new Chart(document.getElementById(id), {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        data,
        backgroundColor: ACCENT_SOFT,
        borderColor: ACCENT,
        borderWidth: 2,
        borderRadius: 8,
      }]
    },
    options: _baseChartOpts(),
  });
}

/**
 * Create line chart dataset configuration with accent colors and styling.
 */
function _lineDataset(data) {
  return {
    data,
    borderColor: ACCENT,
    backgroundColor: ACCENT_SOFT,
    borderWidth: 3,
    pointBackgroundColor: ACCENT,
    pointRadius: 5,
    pointHoverRadius: 7,
    fill: true,
    tension: 0.4,
  };
}

/**
 * Create and render a line chart for trend visualization over time.
 */
function makeLineChart(id, labels, data) {
  new Chart(document.getElementById(id), {
    type: 'line',
    data: { labels, datasets: [_lineDataset(data)] },
    options: _baseChartOpts(),
  });
}

/**
 * Apply color palette values to CSS custom properties for chart colors.
 */
function applyPaletteToCssVars() {
  PALETTE.forEach((color, i) => {
    document.documentElement.style.setProperty(`--palette-${i + 1}`, color);
  });
}

/**
 * Initialize all statistics charts by parsing data and creating chart instances.
 */
function initCharts() {
  applyPaletteToCssVars();
  const el = document.getElementById('stats-data');
  const typeLabels    = parseList(el, 'typeLabels');
  const typeCounts    = parseList(el, 'typeCounts').map(Number);
  const weeklyLabels  = parseList(el, 'weeklyLabels');
  const weeklyCounts  = parseList(el, 'weeklyCounts').map(Number);
  const monthlyLabels = parseList(el, 'monthlyLabels');
  const monthlyCounts = parseList(el, 'monthlyCounts').map(Number);

  makeDoughnutChart('typeChart', typeLabels, typeCounts);
  makeBarChart('weeklyChart', weeklyLabels, weeklyCounts);
  makeLineChart('monthlyChart', monthlyLabels, monthlyCounts);
}

document.addEventListener('DOMContentLoaded', initCharts);
