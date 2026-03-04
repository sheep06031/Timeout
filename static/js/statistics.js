const PALETTE = ['#6c63ff', '#00d4aa', '#ff6b9d', '#ffa94d', '#4dabf7', '#a855f7'];
const ACCENT = '#6c63ff';
const ACCENT_SOFT = 'rgba(108, 99, 255, 0.15)';

function parseList(el, attr) {
  return el.dataset[attr].split(',').map(s => s.trim()).filter(Boolean);
}

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
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false }, ticks: { color: '#6c757d', font: { size: 12 } } },
        y: { beginAtZero: true, ticks: { stepSize: 1, color: '#6c757d', font: { size: 12 } }, grid: { color: '#f3f4f6' } }
      }
    }
  });
}

function makeLineChart(id, labels, data) {
  new Chart(document.getElementById(id), {
    type: 'line',
    data: {
      labels,
      datasets: [{
        data,
        borderColor: ACCENT,
        backgroundColor: ACCENT_SOFT,
        borderWidth: 3,
        pointBackgroundColor: ACCENT,
        pointRadius: 5,
        pointHoverRadius: 7,
        fill: true,
        tension: 0.4,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false }, ticks: { color: '#6c757d', font: { size: 12 } } },
        y: { beginAtZero: true, ticks: { stepSize: 1, color: '#6c757d', font: { size: 12 } }, grid: { color: '#f3f4f6' } }
      }
    }
  });
}

function applyPaletteToCssVars() {
  PALETTE.forEach((color, i) => {
    document.documentElement.style.setProperty(`--palette-${i + 1}`, color);
  });
}

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