// Dashboard charts rendering (Step 4)
// This file only handles charts on the dashboard page.

(function () {
  function getChartDataFromDOM() {
    const el = document.getElementById('dashboardChartData');
    if (!el) return null;

    try {
      return JSON.parse(el.textContent);
    } catch (e) {
      console.error('Failed to parse dashboard chart data', e);
      return null;
    }
  }

  function safeNumber(v) {
    const n = Number(v);
    return Number.isFinite(n) ? n : 0;
  }

  function renderCharts() {
    const data = getChartDataFromDOM();
    if (!data) return;

    const clientsCtx = document.getElementById('clientsPerMonthChart');
    const statusCtx = document.getElementById('tasksByStatusChart');
    const priorityCtx = document.getElementById('tasksByPriorityChart');

    if (window.Chart && clientsCtx) {
      const labels = (data.clientsPerMonth.labels || []).map(String);
      const values = (data.clientsPerMonth.values || []).map(safeNumber);

      new Chart(clientsCtx.getContext('2d'), {
        type: 'bar',
        data: {
          labels,
          datasets: [
            {
              label: 'Clients',
              data: values,
              backgroundColor: 'rgba(109, 94, 252, 0.45)',
              borderColor: 'rgba(109, 94, 252, 0.95)',
              borderWidth: 1,
              borderRadius: 8,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: (ctx) => ` ${ctx.parsed.y} clients`,
              },
            },
          },
          scales: {
            x: {
              ticks: { color: '#755e4a' },
              grid: { color: 'rgba(255,255,255,0.06)' },
            },
            y: {
              beginAtZero: true,
              ticks: { color: '#755e4a' },
              grid: { color: 'rgba(255,255,255,0.06)' },
            },
          },
        },
      });
    }

    if (window.Chart && statusCtx) {
      const labels = (data.tasksByStatus.labels || []).map(String);
      const values = (data.tasksByStatus.values || []).map(safeNumber);

      new Chart(statusCtx.getContext('2d'), {
        type: 'pie',
        data: {
          labels,
          datasets: [
            {
              data: values,
              backgroundColor: [
                'rgba(239, 68, 68, 0.60)',
                'rgba(245, 158, 11, 0.60)',
                'rgba(16, 185, 129, 0.60)',
              ],
              borderColor: [
                'rgba(239, 68, 68, 0.95)',
                'rgba(245, 158, 11, 0.95)',
                'rgba(16, 185, 129, 0.95)',
              ],
              borderWidth: 1,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: 'bottom',
              labels: { color: '#755e4a' },
            },
          },
        },
      });
    }

    if (window.Chart && priorityCtx) {
      const labels = (data.tasksByPriority.labels || []).map(String);
      const values = (data.tasksByPriority.values || []).map(safeNumber);

      new Chart(priorityCtx.getContext('2d'), {
        type: 'doughnut',
        data: {
          labels,
          datasets: [
            {
              data: values,
              backgroundColor: [
                'rgba(239, 68, 68, 0.60)',
                'rgba(59, 130, 246, 0.60)',
                'rgba(148, 163, 184, 0.60)',
              ],
              borderColor: [
                'rgba(239, 68, 68, 0.95)',
                'rgba(59, 130, 246, 0.95)',
                'rgba(148, 163, 184, 0.95)',
              ],
              borderWidth: 1,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          cutout: '60%',
          plugins: {
            legend: {
              position: 'bottom',
              labels: { color: '#755e4a' },
            },
          },
        },
      });
    }
  }

  document.addEventListener('DOMContentLoaded', renderCharts);
})();


