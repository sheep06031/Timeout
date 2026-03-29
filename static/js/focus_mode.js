/**
 * Focus Mode Module
 * Provides distraction-free study environment with inactivity warnings and session tracking.
 */
var FocusMode = (function() {
  var active = false;
  var startTime = null;
  var elapsedInterval = null;
  var lastActivity = 0;
  var inactivityInterval = null;
  var INACTIVITY_MS = 2 * 60 * 1000;
  var warningShown = false;

  /**
   * Update user status on server to reflect focus mode state.
   */
  function setServerStatus(status) {
    postJSON('/social/status/update/', {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: 'status=' + encodeURIComponent(status),
    }).catch(function() {});
  }

  /**
   * Enter focus mode: hide navigation, show overlay, start activity tracking.
   * @param {number} [resumeStartTime] - Existing start timestamp to restore elapsed time across navigation.
   */
  function enter(resumeStartTime) {
    active = true;
    startTime = resumeStartTime || Date.now();
    lastActivity = Date.now();
    warningShown = false;
    sessionStorage.setItem('focusModeActive', 'true');
    sessionStorage.setItem('focusModeStartTime', String(startTime));
    setServerStatus('focus');
    var overlay = document.getElementById('focusOverlay');
    if (overlay) overlay.style.display = 'flex';
    var nav = document.querySelector('.timeout-nav');
    if (nav) nav.style.display = 'none';
    document.body.classList.add('nt-focus-active');
    elapsedInterval = setInterval(updateElapsed, 1000);
    inactivityInterval = setInterval(checkInactivity, 5000);
    document.addEventListener('keydown', onActivity);
    document.addEventListener('mousemove', onActivity);
    document.addEventListener('click', onActivity);
    document.addEventListener('scroll', onActivity);
    window.addEventListener('beforeunload', onBeforeUnload);
  }

  /**
   * Exit focus mode: restore navigation, remove overlay, cleanup event listeners.
   */
  function exit() {
    active = false;
    clearInterval(elapsedInterval);
    clearInterval(inactivityInterval);
    sessionStorage.removeItem('focusModeActive');
    sessionStorage.removeItem('focusModeStartTime');
    setServerStatus('social');
    var overlay = document.getElementById('focusOverlay');
    if (overlay) overlay.style.display = 'none';
    var warn = document.getElementById('warnOverlay');
    if (warn) warn.style.display = 'none';
    var nav = document.querySelector('.timeout-nav');
    if (nav) nav.style.display = '';
    document.body.classList.remove('nt-focus-active');
    document.removeEventListener('keydown', onActivity);
    document.removeEventListener('mousemove', onActivity);
    document.removeEventListener('click', onActivity);
    document.removeEventListener('scroll', onActivity);
    window.removeEventListener('beforeunload', onBeforeUnload);
  }

  /**
   * Handle page unload during focus mode.
   * State is persisted in sessionStorage so focus mode resumes on the next notes page.
   * The server status beacon is intentionally omitted here — the next page's init() will
   * re-enter focus mode and set the status back to 'focus' automatically.
   */
  function onBeforeUnload() {
    if (!active) return;
    // Ensure sessionStorage is up-to-date before navigation.
    sessionStorage.setItem('focusModeActive', 'true');
    sessionStorage.setItem('focusModeStartTime', String(startTime));
  }

  /**
   * Update elapsed time display during focus mode.
   */
  function updateElapsed() {
    var secs = Math.floor((Date.now() - startTime) / 1000);
    var m = Math.floor(secs / 60);
    var s = secs % 60;
    var el = document.getElementById('focusElapsed');
    if (el) el.textContent = String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');
  }

  /**
   * Record user activity and dismiss inactivity warning if shown.
   */
  function onActivity() {
    lastActivity = Date.now();
    if (warningShown) dismissWarning();
  }

  /**
   * Check for user inactivity and show warning if idle threshold exceeded.
   */
  function checkInactivity() {
    if (!active) return;
    var idle = Date.now() - lastActivity;
    if (idle >= INACTIVITY_MS && !warningShown) {
      showWarning();
    }
  }

  /**
   * Display inactivity warning overlay with sound notification.
   */
  function showWarning() {
    warningShown = true;
    var warn = document.getElementById('warnOverlay');
    if (warn) warn.style.display = 'flex';
    playWarning();
  }

  /**
   * Hide inactivity warning overlay.
   */
  function dismissWarning() {
    warningShown = false;
    var warn = document.getElementById('warnOverlay');
    if (warn) warn.style.display = 'none';
  }

  /**
   * Initialize focus mode module with button event listeners.
   * Automatically resumes focus mode if it was active when the previous page was left.
   */
  function init() {
    var btn = document.getElementById('focusModeBtn');
    var exitBtn = document.getElementById('focusExitBtn');
    var dismissBtn = document.getElementById('warnDismissBtn');
    if (btn) btn.addEventListener('click', function() {
      if (active) exit(); else enter();});
    if (exitBtn) exitBtn.addEventListener('click', exit);
    if (dismissBtn) dismissBtn.addEventListener('click', function() {
      dismissWarning();
      lastActivity = Date.now();
    });
    var savedActive = sessionStorage.getItem('focusModeActive');
    var savedStart = sessionStorage.getItem('focusModeStartTime');
    if (savedActive === 'true' && savedStart) {
      var savedStartTime = parseInt(savedStart, 10);
      if (Date.now() - savedStartTime < 8 * 60 * 60 * 1000) {
        enter(savedStartTime);
      } else {
        sessionStorage.removeItem('focusModeActive');
        sessionStorage.removeItem('focusModeStartTime');
      }
    }
  }

  return { init: init };
})();

/**
 * Reset focus timer on page load when needed.
 * If the user is in focus mode and auto-online is OFF, send a beacon to reset
 * the session so a fresh session is created on the next focus-mode entry.
 *
 * The reset URL is read from the data-reset-url attribute on this script's
 * own <script> tag so that no Django template URL tag is needed in JS.
 */
(function () {
  var userStatus = document.documentElement.getAttribute('data-user-status');
  var autoOnline = document.documentElement.getAttribute('data-auto-online');

  if (userStatus === 'focus' && autoOnline !== 'true') {
    var scripts = document.querySelectorAll('script[data-reset-url]');
    var resetUrl = scripts.length ? scripts[scripts.length - 1].getAttribute('data-reset-url') : null;
    if (resetUrl) {
      var data = new FormData();
      data.append('csrfmiddlewaretoken', getCSRFToken());
      navigator.sendBeacon(resetUrl, data);
    }
  }
}());
