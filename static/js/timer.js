function formatElapsed(totalSeconds) {
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60).toString().padStart(2, '0');
  const s = (totalSeconds % 60).toString().padStart(2, '0');
  return h > 0 ? `${h}:${m}:${s}` : `${m}:${s}`;
}

setInterval(() => {
  document.querySelectorAll('[data-focus-started-at]').forEach(el => {
    const startedAt = parseInt(el.dataset.focusStartedAt, 10) * 1000;
    const display = el.querySelector('.focus-timer-display');
    if (!display || !startedAt) return;
    display.textContent = formatElapsed(
      Math.max(0, Math.floor((Date.now() - startedAt) / 1000))
    );
  });
}, 1000);
