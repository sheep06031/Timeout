/**
 * Notes Page: Pomodoro Timer, Focus Mode, Streaks, Study Heatmap, Daily Goals
 * Handles study productivity tracking including pomodoro sessions, focus mode tracking, daily goal management, and study heatmap visualization.
 */

/**
 * Retrieve CSRF token from browser cookies for secure form submissions.
 */
function getCsrfToken() {
  for (var c of document.cookie.split(';')) {
    var parts = c.trim().split('=');
    if (parts[0] === 'csrftoken') return decodeURIComponent(parts[1]);
  }
  return window.NOTES_CONFIG?.csrfToken || '';
}

/**
 * Add or remove pin icon from note item header.
 */
function updatePinIcon(item, pinned) {
  var header = item.querySelector('.nt-item__header');
  if (!header) return;
  var existing = header.querySelector('.nt-pin-icon');
  if (pinned && !existing) {
    var icon = document.createElement('span');
    icon.className = 'nt-pin-icon';
    icon.title = 'Pinned';
    icon.textContent = '\uD83D\uDCCC';
    header.insertBefore(icon, header.firstChild);
  } else if (!pinned && existing) {
    existing.remove();
  }
}

/**
 * Toggle pin state for a note via API and update button.
 */
function togglePin(noteId, btn) {
  fetch('/notes/' + noteId + '/pin/', {
    method: 'POST',
    headers: { 'X-CSRFToken': getCsrfToken() },
  })
  .then(function(res) { return res.json(); })
  .then(function(data) {
    btn.textContent = data.pinned ? 'Unpin' : 'Pin';
    btn.dataset.pinned = data.pinned;
    var item = document.getElementById('note-' + noteId);
    if (item) updatePinIcon(item, data.pinned);
  })
  .catch(function(err) { console.error('Pin toggle failed:', err); });
}

/**
 * Play a beep tone at specified frequency, duration, and volume.
 */
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
  } catch(e) {}
}

/**
 * Check if sound notifications are enabled in config.
 */
function isSoundEnabled() {
  var cfg = window.NOTES_CONFIG || {};
  return cfg.sounds !== undefined ? cfg.sounds : true;
}

/**
 * Play alarm sound sequence (two beeps followed by a higher tone).
 */
function playAlarm() {
  if (!isSoundEnabled()) return;
  playBeep(880, 150, 0.35);
  setTimeout(function() { playBeep(880, 150, 0.35); }, 250);
  setTimeout(function() { playBeep(1100, 300, 0.4); }, 500);
}

/**
 * Play warning sound sequence (two identical beeps).
 */
function playWarning() {
  if (!isSoundEnabled()) return;
  playBeep(520, 300, 0.5);
  setTimeout(function() { playBeep(520, 300, 0.5); }, 400);
}

/**
 * Display XP reward toast notification with fade animation.
 */
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

/**
 * Update level badge, XP progress bar, and streak display with new stats.
 */
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

/**
 * Daily Goals Module
 * Manages daily goal progress tracking with circular progress indicators and edit functionality.
 */
var DailyGoals = (function() {
  var CIRCUMFERENCE = 2 * Math.PI * 16;

  /**
   * Update circular progress ring stroke offset based on current/goal progress.
   */
  function updateRing(id, current, goal) {
    var ring = document.getElementById(id);
    if (!ring) return;
    var pct = Math.min(current / goal, 1);
    ring.setAttribute('stroke-dashoffset', CIRCUMFERENCE * (1 - pct));
    if (pct >= 1) {
      ring.classList.add('nt-goal-ring--done');
    } else {
      ring.classList.remove('nt-goal-ring--done');
    }
  }

  /**
   * Render daily goal progress rings and text for all three goals.
   */
  function render(data) {
    if (!data) return;
    updateRing('goalRingPomo', data.pomodoros, data.pomo_goal);
    updateRing('goalRingNotes', data.notes_edited, data.notes_goal);
    updateRing('goalRingFocus', data.focus_minutes, data.focus_goal);

    var pomoText = document.getElementById('goalPomoText');
    var notesText = document.getElementById('goalNotesText');
    var focusText = document.getElementById('goalFocusText');
    if (pomoText) pomoText.textContent = data.pomodoros + ' / ' + data.pomo_goal;
    if (notesText) notesText.textContent = data.notes_edited + ' / ' + data.notes_goal;
    if (focusText) focusText.textContent = data.focus_minutes + ' / ' + data.focus_goal + 'm';
  }

  /**
   * Fetch latest goal progress data from server and render.
   */
  function refresh() {
    var cfg = window.NOTES_CONFIG || {};
    if (!cfg.goalsProgressUrl) return;
    fetch(cfg.goalsProgressUrl)
      .then(function(r) { return r.json(); })
      .then(render)
      .catch(function() {});
  }

  /**
   * Initialize collapsible toggle for goals section with localStorage persistence.
   */
  function initToggle() {
    var toggle = document.getElementById('goalsToggle');
    var body = document.getElementById('goalsBody');
    if (!toggle || !body) return;
    // Restore collapsed state
    if (localStorage.getItem('goals_collapsed') === '1') {
      body.style.display = 'none';
      toggle.textContent = '\u25BC';
    }
    toggle.addEventListener('click', function() {
      if (body.style.display === 'none') {
        body.style.display = '';
        toggle.textContent = '\u25B2';
        localStorage.removeItem('goals_collapsed');
      } else {
        body.style.display = 'none';
        toggle.textContent = '\u25BC';
        localStorage.setItem('goals_collapsed', '1');
      }
    });
  }

  /**
   * Initialize goal edit modal with form handlers and API submission.
   */
  function initEdit() {
    var editBtn = document.getElementById('goalsEditBtn');
    var saveBtn = document.getElementById('goalsSaveBtn');
    if (!editBtn || !saveBtn) return;
    editBtn.addEventListener('click', function() {
      var modal = new bootstrap.Modal(document.getElementById('editGoalsModal'));
      modal.show();});
    saveBtn.addEventListener('click', function() {
      var cfg = window.NOTES_CONFIG || {};
      var body = new FormData();
      body.append('daily_pomo_goal', document.getElementById('goalInputPomo').value);
      body.append('daily_notes_goal', document.getElementById('goalInputNotes').value);
      body.append('daily_focus_goal', document.getElementById('goalInputFocus').value);
      fetch(cfg.goalsUpdateUrl, {
        method: 'POST',
        headers: { 'X-CSRFToken': getCsrfToken() },
        body: body,})
      .then(function(r) { return r.json(); })
      .then(function() {
        bootstrap.Modal.getInstance(document.getElementById('editGoalsModal')).hide();
        refresh();})
      .catch(function() {});});
  }

  /**
   * Initialize daily goals module with all event handlers and initial render.
   */
  function init() {
    initToggle();
    initEdit();
    // Initial render from server data
    refresh();
  }
  return { init: init, render: render, refresh: refresh };
})();

/**
 * Study Heatmap Module
 * Displays calendar-like heatmap visualization of daily study activity.
 */
var Heatmap = (function() {
  /**
   * Group daily data points into weeks, padding with nulls for alignment.
   */
  function _groupIntoWeeks(days) {
    var weeks = [];
    var week = [];
    for (var i = 0; i < days.length; i++) {
      var d = new Date(days[i].date + 'T00:00:00');
      var dow = d.getDay();
      var mdow = dow === 0 ? 6 : dow - 1;
      if (i === 0 && mdow > 0) {
        for (var p = 0; p < mdow; p++) week.push(null);
      }
      week.push(days[i]);
      if (mdow === 6) { weeks.push(week); week = []; }
    }
    if (week.length > 0) weeks.push(week);
    return weeks;
  }

  /**
   * Create a single heatmap cell DOM element with data attributes and tooltip.
   */
  function _createCell(day) {
    var cell = document.createElement('span');
    cell.className = 'nt-heatmap-cell';
    if (day) {
      cell.setAttribute('data-level', day.level);
      cell.title = day.date + ': ' + day.pomodoros + ' pomodoros, ' + day.notes + ' notes, ' + day.focus + 'm focus';
    } else {
      cell.setAttribute('data-level', '-1');
      cell.style.visibility = 'hidden';
    }
    return cell;
  }

  /**
   * Render a single week column with seven day cells.
   */
  function _renderWeekColumn(weekDays) {
    var col = document.createElement('div');
    col.className = 'nt-heatmap-col';
    for (var r = 0; r < 7; r++) col.appendChild(_createCell(weekDays[r]));
    return col;
  }

  /**
   * Render complete heatmap grid by grouping days into weeks.
   */
  function render(days) {
    var grid = document.getElementById('heatmapGrid');
    if (!grid || !days) return;
    grid.innerHTML = '';
    var weeks = _groupIntoWeeks(days);
    for (var w = 0; w < weeks.length; w++) grid.appendChild(_renderWeekColumn(weeks[w]));
  }

  /**
   * Fetch heatmap data from server and render.
   */
  function load() {
    var cfg = window.NOTES_CONFIG || {};
    if (!cfg.heatmapUrl) return;
    fetch(cfg.heatmapUrl)
      .then(function(r) { return r.json(); })
      .then(function(data) { render(data.days); })
      .catch(function() {});
  }

  return { init: load };
})();

/**
 * Pomodoro Timer Module
 * Manages pomodoro work/break cycles with visual progress ring and session counter.
 */
var Pomodoro = (function() {
  var cfg = window.NOTES_CONFIG || {};
  var WORK = (cfg.pomoWork || 25) * 60;
  var SHORT_BREAK = (cfg.pomoShort || 5) * 60;
  var LONG_BREAK = (cfg.pomoLong || 15) * 60;
  var CIRCUMFERENCE = 2 * Math.PI * 54;

  var state = {
    phase: 'work',
    remaining: WORK,
    total: WORK,
    running: false,
    session: 0,
    todayCount: 0,
    intervalId: null,
  };

  /**
   * Load pomodoro state from localStorage if it's today's session.
   */
  function loadState() {
    try {
      var saved = JSON.parse(localStorage.getItem('pomo_state'));
      if (saved && saved.date === new Date().toDateString()) {
        state.todayCount = saved.todayCount || 0;
      }
    } catch(e) {}
  }

  /**
   * Save current pomodoro session count and date to localStorage.
   */
  function saveState() {
    localStorage.setItem('pomo_state', JSON.stringify({
      date: new Date().toDateString(),
      todayCount: state.todayCount,
    }));
  }

  /**
   * Get duration in seconds for the given phase (work, short break, long break).
   */
  function getDuration(phase) {
    if (phase === 'work') return WORK;
    if (phase === 'long_break') return LONG_BREAK;
    return SHORT_BREAK;
  }

  /**
   * Get human-readable label for the given phase.
   */
  function getPhaseLabel(phase) {
    if (phase === 'work') return 'Work Session';
    if (phase === 'short_break') return 'Short Break';
    return 'Long Break';
  }

  /**
   * Get the currently selected note ID from dropdown if available.
   */
  function getLinkedNoteId() {
    var sel = document.getElementById('pomoNoteSelect');
    return sel ? sel.value : '';
  }

  /**
   * Render progress ring with appropriate color and offset for current phase.
   */
  function _renderRing() {
    var ringEl = document.getElementById('pomoRing');
    if (!ringEl) return;
    var progress = 1 - (state.remaining / state.total);
    ringEl.setAttribute('stroke-dashoffset', CIRCUMFERENCE * (1 - progress));
    ringEl.style.stroke = state.phase === 'work' ? '#5B73E8' : '#4ECDC4';
  }

  /**
   * Toggle start/pause button visibility based on running state.
   */
  function _renderButtons() {
    var startBtn = document.getElementById('pomoStartBtn');
    var pauseBtn = document.getElementById('pomoPauseBtn');
    if (startBtn && pauseBtn) {
      startBtn.style.display = state.running ? 'none' : '';
      pauseBtn.style.display = state.running ? '' : 'none';
    }
  }

  /**
   * Update all UI elements (timer, phase label, count, ring, buttons).
   */
  function render() {
    var mins = Math.floor(state.remaining / 60);
    var secs = state.remaining % 60;
    var timeEl = document.getElementById('pomoTime');
    if (timeEl) timeEl.textContent = String(mins).padStart(2, '0') + ':' + String(secs).padStart(2, '0');

    _renderRing();

    var phaseEl = document.getElementById('pomoPhase');
    var countEl = document.getElementById('pomodoroCount');
    if (phaseEl) phaseEl.textContent = getPhaseLabel(state.phase);
    if (countEl) countEl.textContent = state.todayCount;

    _renderButtons();

    var dots = document.querySelectorAll('#pomoDots .nt-pomo-dot');
    dots.forEach(function(dot, i) {
      dot.classList.toggle('nt-pomo-dot--filled', i < state.session);
      dot.classList.toggle('nt-pomo-dot--active', i === state.session && state.phase === 'work');
    });
  }

  /**
   * Decrement timer by one second and check for phase end.
   */
  function tick() {
    if (state.remaining <= 0) {
      onPhaseEnd();
      return;
    }
    state.remaining--;
    render();
  }

  /**
   * Submit completed pomodoro to server and award XP.
   */
  function _awardWorkXP() {
    if (!cfg.pomodoroCompleteUrl) return;
    var body = new FormData();
    var noteId = getLinkedNoteId();
    if (noteId) body.append('note_id', noteId);

    fetch(cfg.pomodoroCompleteUrl, {
      method: 'POST',
      headers: { 'X-CSRFToken': getCsrfToken() },
      body: body,
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      updateStatsUI(data);
      showXpToast(25);
      if (data.daily_progress) DailyGoals.render(data.daily_progress);
    })
    .catch(function() {});
  }

  /**
   * Advance to next phase (work->break->work) and update session count.
   */
  function _advancePhase() {
    if (state.phase === 'work') {
      state.session++;
      state.todayCount++;
      saveState();
      _awardWorkXP();
      state.phase = state.session >= 4 ? 'long_break' : 'short_break';
      if (state.session >= 4) state.session = 0;
    } else {
      state.phase = 'work';
    }
  }

  /**
   * Handle phase completion: stop timer, play alarm, advance phase, reset duration.
   */
  function onPhaseEnd() {
    clearInterval(state.intervalId);
    state.running = false;
    playAlarm();
    _advancePhase();
    state.total = getDuration(state.phase);
    state.remaining = state.total;
    render();
  }

  /**
   * Start the pomodoro timer interval.
   */
  function start() {
    if (state.running) return;
    state.running = true;
    state.intervalId = setInterval(tick, 1000);
    render();
  }

  /**
   * Pause the pomodoro timer without resetting progress.
   */
  function pause() {
    clearInterval(state.intervalId);
    state.running = false;
    render();
  }

  /**
   * Skip to end of current phase immediately.
   */
  function skip() {
    clearInterval(state.intervalId);
    state.running = false;
    state.remaining = 0;
    onPhaseEnd();
  }

  /**
   * Reset timer to initial work phase state.
   */
  function reset() {
    clearInterval(state.intervalId);
    state.running = false;
    state.phase = 'work';
    state.session = 0;
    state.total = WORK;
    state.remaining = WORK;
    render();
  }

  /**
   * Populate note dropdown with user's notes.
   */
  function populateNoteSelect() {
    var sel = document.getElementById('pomoNoteSelect');
    if (!sel) return;
    var notes = cfg.userNotes || [];
    for (var i = 0; i < notes.length; i++) {
      var opt = document.createElement('option');
      opt.value = notes[i][0];
      opt.textContent = notes[i][1].length > 35 ? notes[i][1].substring(0, 35) + '...' : notes[i][1];
      sel.appendChild(opt);
    }
  }

  /**
   * Initialize pomodoro module with state load and event listeners.
   */
  function init() {
    loadState();
    populateNoteSelect();
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
    fetch('/social/status/update/', {
      method: 'POST',
      headers: { 'X-CSRFToken': getCsrfToken(), 'Content-Type': 'application/x-www-form-urlencoded' },
      body: 'status=' + encodeURIComponent(status),
    }).catch(function() {});
  }

  /**
   * Enter focus mode: hide navigation, show overlay, start activity tracking.
   */
  function enter() {
    active = true;
    startTime = Date.now();
    lastActivity = Date.now();
    warningShown = false;

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
   * Handle page unload during focus mode by updating server status via sendBeacon.
   */
  function onBeforeUnload(e) {
    if (!active) return;
    // End focus session on server via beacon so FocusSession is recorded
    var data = new FormData();
    data.append('status', 'social');
    data.append('csrfmiddlewaretoken', getCsrfToken());
    navigator.sendBeacon('/social/status/update/', data);
    e.preventDefault();
    e.returnValue = 'Focus mode is active. Are you sure you want to leave?';
    return e.returnValue;
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
   */
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

/**
 * Initialize live word counter for note editing textarea.
 */
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


/* Init */
document.addEventListener('DOMContentLoaded', function() {
  if (document.getElementById('pomoPanel')) Pomodoro.init();
  FocusMode.init();
  initWordCount();
  DailyGoals.init();
  Heatmap.init();
});
