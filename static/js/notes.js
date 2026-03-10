/* ============================================
   Notes Page — Pomodoro, Focus Mode, Streaks
   ============================================ */

/* ---------- Helpers ---------- */

function getCsrfToken() {
  for (const cookie of document.cookie.split(';')) {
    const [key, val] = cookie.trim().split('=');
    if (key === 'csrftoken') return decodeURIComponent(val);
  }
  return window.NOTES_CONFIG?.csrfToken || '';
}

function updatePinIcon(item, pinned) {
  const header = item.querySelector('.note-header');
  const existing = header.querySelector('.pin-icon');
  if (pinned && !existing) {
    const icon = document.createElement('span');
    icon.className = 'pin-icon';
    icon.title = 'Pinned';
    icon.textContent = '\uD83D\uDCCC';
    header.insertBefore(icon, header.firstChild);
  } else if (!pinned && existing) {
    existing.remove();
  }
}

function togglePin(noteId, btn) {
  fetch('/notes/' + noteId + '/pin/', {
    method: 'POST',
    headers: { 'X-CSRFToken': getCsrfToken() },
  })
  .then(function(res) { return res.json(); })
  .then(function(data) {
    btn.textContent = data.pinned ? 'Unpin' : 'Pin';
    btn.dataset.pinned = data.pinned;
    const item = document.getElementById('note-' + noteId);
    updatePinIcon(item, data.pinned);
  })
  .catch(function(err) { console.error('Pin toggle failed:', err); });
}


/* ---------- Audio Utility ---------- */

function playBeep(freq, duration, volume) {
  try {
    var ctx = new (window.AudioContext || window.webkitAudioContext)();
    var osc = ctx.createOscillator();
    var gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.frequency.value = freq || 660;
    gain.gain.value = volume || 0.3;
    osc.start();
    setTimeout(function() { osc.stop(); ctx.close(); }, duration || 200);
  } catch(e) { /* AudioContext not supported */ }
}

function isSoundEnabled() {
  var cfg = window.NOTES_CONFIG || {};
  return cfg.sounds !== undefined ? cfg.sounds : true;
}

function playAlarm() {
  if (!isSoundEnabled()) return;
  // Triple beep for phase end
  playBeep(880, 150, 0.35);
  setTimeout(function() { playBeep(880, 150, 0.35); }, 250);
  setTimeout(function() { playBeep(1100, 300, 0.4); }, 500);
}

function playWarning() {
  if (!isSoundEnabled()) return;
  // Urgent double beep for inactivity
  playBeep(520, 300, 0.5);
  setTimeout(function() { playBeep(520, 300, 0.5); }, 400);
}


/* ---------- XP Toast ---------- */

function showXpToast(amount) {
  var toast = document.getElementById('xpToast');
  var text = document.getElementById('xpToastText');
  if (!toast) return;
  text.textContent = '+' + amount + ' XP';
  toast.style.display = 'flex';
  toast.classList.remove('nt-xp-toast--hide');
  toast.classList.add('nt-xp-toast--show');
  setTimeout(function() {
    toast.classList.remove('nt-xp-toast--show');
    toast.classList.add('nt-xp-toast--hide');
    setTimeout(function() { toast.style.display = 'none'; }, 400);
  }, 2000);
}

function updateStatsUI(data) {
  var badge = document.getElementById('levelBadge');
  var fill = document.getElementById('xpFill');
  var xpText = document.getElementById('xpText');
  var streak = document.getElementById('streakValue');
  if (badge) badge.textContent = 'Lv ' + data.level;
  if (fill) fill.style.width = data.xp_progress_pct + '%';
  if (xpText) xpText.textContent = data.xp + ' / ' + data.xp_for_next_level + ' XP';
  if (streak && data.note_streak !== undefined) streak.textContent = data.note_streak;
}


/* ============================================
   Pomodoro Timer
   ============================================ */

var Pomodoro = (function() {
  var cfg = window.NOTES_CONFIG || {};
  var WORK = (cfg.pomoWork || 25) * 60;
  var SHORT_BREAK = (cfg.pomoShort || 5) * 60;
  var LONG_BREAK = (cfg.pomoLong || 15) * 60;
  var SOUNDS_ENABLED = cfg.sounds !== undefined ? cfg.sounds : true;
  var CIRCUMFERENCE = 2 * Math.PI * 54; // 339.292

  var state = {
    phase: 'work',       // 'work' | 'short_break' | 'long_break'
    remaining: WORK,
    total: WORK,
    running: false,
    session: 0,          // completed work sessions (0-3)
    todayCount: 0,
    intervalId: null,
  };

  // Load from localStorage
  function loadState() {
    try {
      var saved = JSON.parse(localStorage.getItem('pomo_state'));
      if (saved && saved.date === new Date().toDateString()) {
        state.todayCount = saved.todayCount || 0;
      }
    } catch(e) {}
  }

  function saveState() {
    localStorage.setItem('pomo_state', JSON.stringify({
      date: new Date().toDateString(),
      todayCount: state.todayCount,
    }));
  }

  function getDuration(phase) {
    if (phase === 'work') return WORK;
    if (phase === 'long_break') return LONG_BREAK;
    return SHORT_BREAK;
  }

  function getPhaseLabel(phase) {
    if (phase === 'work') return 'Work Session';
    if (phase === 'short_break') return 'Short Break';
    return 'Long Break';
  }

  function render() {
    var mins = Math.floor(state.remaining / 60);
    var secs = state.remaining % 60;
    var timeEl = document.getElementById('pomoTime');
    var ringEl = document.getElementById('pomoRing');
    var phaseEl = document.getElementById('pomoPhase');
    var countEl = document.getElementById('pomodoroCount');
    var startBtn = document.getElementById('pomoStartBtn');
    var pauseBtn = document.getElementById('pomoPauseBtn');

    if (timeEl) timeEl.textContent = String(mins).padStart(2, '0') + ':' + String(secs).padStart(2, '0');

    if (ringEl) {
      var progress = 1 - (state.remaining / state.total);
      ringEl.setAttribute('stroke-dashoffset', CIRCUMFERENCE * (1 - progress));
      // Color based on phase
      if (state.phase === 'work') {
        ringEl.style.stroke = '#5B73E8';
      } else {
        ringEl.style.stroke = '#4ECDC4';
      }
    }

    if (phaseEl) phaseEl.textContent = getPhaseLabel(state.phase);
    if (countEl) countEl.textContent = state.todayCount;

    if (startBtn && pauseBtn) {
      startBtn.style.display = state.running ? 'none' : '';
      pauseBtn.style.display = state.running ? '' : 'none';
    }

    // Session dots
    var dots = document.querySelectorAll('#pomoDots .nt-pomo-dot');
    dots.forEach(function(dot, i) {
      dot.classList.toggle('nt-pomo-dot--filled', i < state.session);
      dot.classList.toggle('nt-pomo-dot--active', i === state.session && state.phase === 'work');
    });
  }

  function tick() {
    if (state.remaining <= 0) {
      onPhaseEnd();
      return;
    }
    state.remaining--;
    render();
  }

  function onPhaseEnd() {
    clearInterval(state.intervalId);
    state.running = false;
    playAlarm();

    if (state.phase === 'work') {
      state.session++;
      state.todayCount++;
      saveState();

      // Award XP via AJAX
      var cfg = window.NOTES_CONFIG || {};
      if (cfg.pomodoroCompleteUrl) {
        fetch(cfg.pomodoroCompleteUrl, {
          method: 'POST',
          headers: { 'X-CSRFToken': getCsrfToken() },
        })
        .then(function(r) { return r.json(); })
        .then(function(data) {
          updateStatsUI(data);
          showXpToast(25);
        })
        .catch(function() {});
      }

      // Next phase
      if (state.session >= 4) {
        state.phase = 'long_break';
        state.session = 0;
      } else {
        state.phase = 'short_break';
      }
    } else {
      // Break ended — back to work
      state.phase = 'work';
    }

    state.total = getDuration(state.phase);
    state.remaining = state.total;
    render();
  }

  function start() {
    if (state.running) return;
    state.running = true;
    state.intervalId = setInterval(tick, 1000);
    render();
  }

  function pause() {
    clearInterval(state.intervalId);
    state.running = false;
    render();
  }

  function skip() {
    clearInterval(state.intervalId);
    state.running = false;
    state.remaining = 0;
    onPhaseEnd();
  }

  function reset() {
    clearInterval(state.intervalId);
    state.running = false;
    state.phase = 'work';
    state.session = 0;
    state.total = WORK;
    state.remaining = WORK;
    render();
  }

  function init() {
    loadState();
    render();

    var startBtn = document.getElementById('pomoStartBtn');
    var pauseBtn = document.getElementById('pomoPauseBtn');
    var skipBtn = document.getElementById('pomoSkipBtn');
    var resetBtn = document.getElementById('pomoResetBtn');

    if (startBtn) startBtn.addEventListener('click', start);
    if (pauseBtn) pauseBtn.addEventListener('click', pause);
    if (skipBtn) skipBtn.addEventListener('click', skip);
    if (resetBtn) resetBtn.addEventListener('click', reset);
  }

  return { init: init };
})();


/* ============================================
   Focus Mode
   ============================================ */

var FocusMode = (function() {
  var active = false;
  var startTime = null;
  var elapsedInterval = null;
  var lastActivity = 0;
  var inactivityInterval = null;
  var INACTIVITY_MS = 2 * 60 * 1000; // 2 minutes
  var warningShown = false;

  function enter() {
    active = true;
    startTime = Date.now();
    lastActivity = Date.now();
    warningShown = false;

    // Show focus overlay bar
    var overlay = document.getElementById('focusOverlay');
    if (overlay) overlay.style.display = 'flex';

    // Hide navbar
    var nav = document.querySelector('.timeout-nav');
    if (nav) nav.style.display = 'none';

    // Add body class
    document.body.classList.add('nt-focus-active');

    // Update elapsed timer
    elapsedInterval = setInterval(updateElapsed, 1000);

    // Start inactivity watcher
    inactivityInterval = setInterval(checkInactivity, 5000);

    // Listen for activity
    document.addEventListener('keydown', onActivity);
    document.addEventListener('mousemove', onActivity);
    document.addEventListener('click', onActivity);
    document.addEventListener('scroll', onActivity);

    // Block navigation with beforeunload
    window.addEventListener('beforeunload', onBeforeUnload);
  }

  function exit() {
    active = false;
    clearInterval(elapsedInterval);
    clearInterval(inactivityInterval);

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

  function onBeforeUnload(e) {
    if (!active) return;
    e.preventDefault();
    e.returnValue = 'Focus mode is active. Are you sure you want to leave?';
    return e.returnValue;
  }

  function updateElapsed() {
    var secs = Math.floor((Date.now() - startTime) / 1000);
    var m = Math.floor(secs / 60);
    var s = secs % 60;
    var el = document.getElementById('focusElapsed');
    if (el) el.textContent = String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');
  }

  function onActivity() {
    lastActivity = Date.now();
    if (warningShown) dismissWarning();
  }

  function checkInactivity() {
    if (!active) return;
    var idle = Date.now() - lastActivity;
    if (idle >= INACTIVITY_MS && !warningShown) {
      showWarning();
    }
  }

  function showWarning() {
    warningShown = true;
    var warn = document.getElementById('warnOverlay');
    if (warn) warn.style.display = 'flex';
    playWarning();
  }

  function dismissWarning() {
    warningShown = false;
    var warn = document.getElementById('warnOverlay');
    if (warn) warn.style.display = 'none';
  }

  function init() {
    var btn = document.getElementById('focusModeBtn');
    var exitBtn = document.getElementById('focusExitBtn');
    var dismissBtn = document.getElementById('warnDismissBtn');

    if (btn) btn.addEventListener('click', function() {
      if (active) exit(); else enter();
    });
    if (exitBtn) exitBtn.addEventListener('click', exit);
    if (dismissBtn) dismissBtn.addEventListener('click', function() {
      dismissWarning();
      lastActivity = Date.now();
    });
  }

  return { init: init };
})();


/* ---------- Word Count (for note_edit) ---------- */

function initWordCount() {
  var textarea = document.getElementById('id_content');
  var counter = document.getElementById('wordCount');
  if (!textarea || !counter) return;

  function update() {
    var text = textarea.value.trim();
    var words = text ? text.split(/\s+/).length : 0;
    counter.textContent = words + ' word' + (words !== 1 ? 's' : '');
  }

  textarea.addEventListener('input', update);
  update();
}


/* ---------- Init ---------- */

document.addEventListener('DOMContentLoaded', function() {
  if (document.getElementById('pomoPanel')) Pomodoro.init();
  FocusMode.init();
  initWordCount();
});
