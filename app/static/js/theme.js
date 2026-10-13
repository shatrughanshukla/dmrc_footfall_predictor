(function () {
  const root = document.documentElement;
  const buttons = () => document.querySelectorAll('[data-theme-toggle]');
  const icons = {
    sun: '<svg viewBox="0 0 24 24" focusable="false"><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.93 4.93l1.42 1.42m11.3 11.3 1.42 1.42M2 12h2m16 0h2M4.93 19.07l1.42-1.42m11.3-11.3 1.42-1.42"/></svg>',
    moon: '<svg viewBox="0 0 24 24" focusable="false"><path d="M20.2 15.4A8.7 8.7 0 0 1 8.6 3.8 8.8 8.8 0 1 0 20.2 15.4Z"/></svg>'
  };

  function applyTheme(theme) {
    const activeTheme = theme === 'dark' ? 'dark' : 'light';
    root.dataset.theme = activeTheme;
    try { localStorage.setItem('metroflow-theme', activeTheme); } catch (_) { /* Theme still works for this page. */ }
    buttons().forEach((button) => {
      const next = activeTheme === 'dark' ? 'light' : 'dark';
      button.setAttribute('aria-label', `Switch to ${next} theme`);
      button.setAttribute('title', `Switch to ${next} theme`);
      const label = button.querySelector('.theme-toggle-label');
      if (label) label.textContent = `${next === 'dark' ? 'Dark' : 'Light'} mode`;
      const icon = button.querySelector('.theme-icon');
      if (icon) icon.innerHTML = activeTheme === 'dark' ? icons.sun : icons.moon;
    });
    if (window.Chart) {
      const chartText = activeTheme === 'dark' ? '#a4adb7' : '#657184';
      const chartGrid = activeTheme === 'dark' ? 'rgba(255, 255, 255, 0.07)' : 'rgba(32, 38, 49, 0.08)';
      window.Chart.defaults.color = chartText;
      window.Chart.defaults.borderColor = chartGrid;
      Object.values(window.Chart.instances || {}).forEach((chart) => {
        chart.options.color = chartText;
        Object.values(chart.options.scales || {}).forEach((scale) => {
          scale.ticks = { ...scale.ticks, color: chartText };
          scale.grid = { ...scale.grid, color: chartGrid };
          if (scale.title) scale.title = { ...scale.title, color: chartText };
        });
        if (chart.options.plugins?.legend?.labels) {
          chart.options.plugins.legend.labels.color = chartText;
        }
        chart.update('none');
      });
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    applyTheme(root.dataset.theme || 'light');
    buttons().forEach((button) => button.addEventListener('click', () => {
      applyTheme(root.dataset.theme === 'dark' ? 'light' : 'dark');
    }));
  });
}());
