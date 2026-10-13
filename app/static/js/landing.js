(function () {
  const profile = window.METROINSIGHTS_PREVIEW;

  function drawPreviewChart() {
    const svg = document.querySelector('.preview-chart');
    if (!svg || !profile || !Array.isArray(profile.predicted) || !profile.predicted.length) return;
    const values = profile.predicted;
    const max = Math.max(...values) || 1;
    const min = Math.min(...values);
    const spread = max - min || 1;
    const points = values.map((value, index) => {
      const x = 12 + (index / Math.max(values.length - 1, 1)) * 576;
      const y = 132 - ((value - min) / spread) * 100;
      return [x, y];
    });
    const line = points.map((point) => point.map((v) => v.toFixed(1)).join(',')).join(' ');
    const area = `M ${points[0][0]} 145 L ${points.map((p) => `${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(' L ')} L ${points[points.length - 1][0]} 145 Z`;
    svg.querySelector('.chart-line').setAttribute('points', line);
    svg.querySelector('.chart-area').setAttribute('d', area);
    const selectedIndex = 4; // The sample card is set to 09:00.
    const current = points[selectedIndex] || points[0];
    svg.querySelector('.chart-current').setAttribute('cx', current[0]);
    svg.querySelector('.chart-current').setAttribute('cy', current[1]);
    svg.querySelector('.chart-cursor').setAttribute('x1', current[0]);
    svg.querySelector('.chart-cursor').setAttribute('x2', current[0]);
  }

  function initScrollMetro() {
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const rail = document.querySelector('.scroll-track');
    const train = rail && rail.querySelector('.scroll-train');
    const progressLine = rail && rail.querySelector('.scroll-track-progress');
    const update = () => {
      if (!rail) return;
      const scrollable = document.documentElement.scrollHeight - window.innerHeight;
      const progress = scrollable > 0 ? Math.min(1, Math.max(0, window.scrollY / scrollable)) : 0;
      const travel = reducedMotion ? 0 : progress;
      if (train) train.style.top = `${travel * Math.max(0, rail.clientHeight - train.offsetHeight)}px`;
      if (progressLine) progressLine.style.height = `${travel * rail.clientHeight}px`;
    };
    update();
    window.addEventListener('scroll', update, { passive: true });
    window.addEventListener('resize', update);
  }

  function initReveals() {
    const items = document.querySelectorAll('.reveal');
    if (!('IntersectionObserver' in window) || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      items.forEach((item) => item.classList.add('is-visible'));
      return;
    }
    document.documentElement.classList.add('motion-ready');
    const observer = new IntersectionObserver((entries, instance) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          instance.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -24px 0px' });
    items.forEach((item) => observer.observe(item));
  }

  function initMobileNavigation() {
    const toggle = document.querySelector('.mobile-menu-toggle');
    const menu = document.querySelector('.mobile-nav');
    if (!toggle || !menu) return;
    toggle.addEventListener('click', () => {
      const open = toggle.getAttribute('aria-expanded') !== 'true';
      toggle.setAttribute('aria-expanded', String(open));
      toggle.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
      toggle.textContent = open ? '×' : '☰';
      menu.hidden = !open;
    });
    menu.querySelectorAll('a').forEach((link) => link.addEventListener('click', () => {
      menu.hidden = true;
      toggle.setAttribute('aria-expanded', 'false');
      toggle.setAttribute('aria-label', 'Open navigation');
      toggle.textContent = '☰';
    }));
  }

  document.addEventListener('DOMContentLoaded', () => {
    drawPreviewChart();
    initScrollMetro();
    initReveals();
    initMobileNavigation();
  });
}());
