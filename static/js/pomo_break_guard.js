/**
 * Pomodoro Break Guard
 * Watches for break expiry on non-notes pages and shows an action popup.
 * Fires immediately on load if the break has already elapsed, or schedules
 * a timeout for the exact moment the break expires while the user is on the page.
 */
(function () {
  /** Only active outside the notes section — notes pages handle this themselves. */
  if (window.location.pathname.startsWith('/notes')) return;

  /**
   * Build and insert the break-ended overlay.
   * Idempotent: will not create a second overlay if one already exists.
   */
  function _showPopup() {
    if (document.getElementById('pomoBreakEndedOverlay')) return;
    var overlay = document.createElement('div');
    overlay.id = 'pomoBreakEndedOverlay';
    overlay.style.cssText = [
      'position:fixed;inset:0;z-index:9999',
      'display:flex;align-items:center;justify-content:center',
      'background:rgba(0,0,0,0.55)',
    ].join(';');
    overlay.innerHTML =
      '<div style="background:#fff;border-radius:16px;padding:32px 40px;' +
        'max-width:380px;text-align:center;box-shadow:0 8px 32px rgba(0,0,0,0.18)">' +
        '<div style="font-size:2.5rem;margin-bottom:8px">&#127813;</div>' +
        '<h3 style="margin:0 0 8px;font-size:1.3rem">Break\'s over!</h3>' +
        '<p style="color:#666;margin:0 0 24px;font-size:.95rem">' +
          'Your Pomodoro break has ended.<br>Ready to get back to work?' +
        '</p>' +
        '<button id="pomoBreakGoBtn" style="background:#5B73E8;color:#fff;border:none;' +
          'border-radius:8px;padding:10px 28px;font-size:1rem;cursor:pointer;margin-right:12px">' +
          'Return to Notes' +
        '</button>' +
        '<button id="pomoBreakNoBtn" style="background:#f1f3f7;color:#333;border:none;' +
          'border-radius:8px;padding:10px 20px;font-size:1rem;cursor:pointer">' +
          'Reset Session' +
        '</button>' +
      '</div>';
    document.body.appendChild(overlay);
    document.getElementById('pomoBreakGoBtn').addEventListener('click', function () {
      window.location.href = '/notes/';
    });
    document.getElementById('pomoBreakNoBtn').addEventListener('click', function () {
      sessionStorage.removeItem('pomo_state');
      overlay.remove();
    });
  }

  /**
   * Read the saved pomodoro state and schedule (or immediately show) the popup.
   */
  function _scheduleBreakGuard() {
    try {
      var saved = JSON.parse(sessionStorage.getItem('pomo_state'));
      if (!saved || !saved.running || saved.phase === 'work') return;
      var elapsed   = Math.floor((Date.now() - saved.savedAt) / 1000);
      var remaining = saved.remaining - elapsed;
      if (remaining <= 0) {
        _showPopup();
      } else {
        setTimeout(_showPopup, remaining * 1000);
      }
    } catch (e) {}
  }

  _scheduleBreakGuard();
}());
