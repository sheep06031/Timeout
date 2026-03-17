/* Notes Page: Pomodoro, Focus Mode, Streaks, Heatmap, Daily Goals */

/* ═══ Helpers ═══ */

function getCsrfToken() {
  for (var c of document.cookie.split(';')) {
    var parts = c.trim().split('=');
    if (parts[0] === 'csrftoken') return decodeURIComponent(parts[1]);
  }
  return window.NOTES_CONFIG?.csrfToken || '';
}

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


/* ═══ Audio Utility ═══ */

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

function isSoundEnabled() {
  var cfg = window.NOTES_CONFIG || {};
  return cfg.sounds !== undefined ? cfg.sounds : true;
}

function playAlarm() {
  if (!isSoundEnabled()) return;
  playBeep(880, 150, 0.35);
  setTimeout(function() { playBeep(880, 150, 0.35); }, 250);
  setTimeout(function() { playBeep(1100, 300, 0.4); }, 500);
}

function playWarning() {
  if (!isSoundEnabled()) return;
  playBeep(520, 300, 0.5);
  setTimeout(function() { playBeep(520, 300, 0.5); }, 400);
}


/* ═══ XP Toast ═══ */

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


/* ═══ Daily Goals ═══ */

var DailyGoals = (function() {
  var CIRCUMFERENCE = 2 * Math.PI * 16; // 100.531

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

  function refresh() {
    var cfg = window.NOTES_CONFIG || {};
    if (!cfg.goalsProgressUrl) return;
    fetch(cfg.goalsProgressUrl)
      .then(function(r) { return r.json(); })
      .then(render)
      .catch(function() {});
  }

  function initToggle() {
    var toggle = document.getElementById('goalsToggle');
    var body = document.getElementById('goalsBody');
    if (!toggle || !body) return;
    // Restore collapsed state
    if (localStorage.getItem('goals_collapsed') === '1') {
      body.style.display = 'none';
      toggle.textContent = '\u25BC'; // ▼
    }
    toggle.addEventListener('click', function() {
      if (body.style.display === 'none') {
        body.style.display = '';
        toggle.textContent = '\u25B2'; // ▲
        localStorage.removeItem('goals_collapsed');
      } else {
        body.style.display = 'none';
        toggle.textContent = '\u25BC'; // ▼
        localStorage.setItem('goals_collapsed', '1');
      }
    });
  }

  function initEdit() {
    var editBtn = document.getElementById('goalsEditBtn');
    var saveBtn = document.getElementById('goalsSaveBtn');
    if (!editBtn || !saveBtn) return;

    editBtn.addEventListener('click', function() {
      var modal = new bootstrap.Modal(document.getElementById('editGoalsModal'));
      modal.show();
    });

    saveBtn.addEventListener('click', function() {
      var cfg = window.NOTES_CONFIG || {};
      var body = new FormData();
      body.append('daily_pomo_goal', document.getElementById('goalInputPomo').value);
      body.append('daily_notes_goal', document.getElementById('goalInputNotes').value);
      body.append('daily_focus_goal', document.getElementById('goalInputFocus').value);

      fetch(cfg.goalsUpdateUrl, {
        method: 'POST',
        headers: { 'X-CSRFToken': getCsrfToken() },
        body: body,
      })
      .then(function(r) { return r.json(); })
      .then(function() {
        bootstrap.Modal.getInstance(document.getElementById('editGoalsModal')).hide();
        refresh();
      })
      .catch(function() {});
    });
  }

  function init() {
    initToggle();
    initEdit();
    // Initial render from server data
    refresh();
  }

  return { init: init, render: render, refresh: refresh };
})();


/* ═══ Study Heatmap ═══ */

var Heatmap = (function() {
  function render(days) {
    var grid = document.getElementById('heatmapGrid');
    if (!grid || !days) return;
    grid.innerHTML = '';

    // Build 7-row grid (Mon-Sun)
    // First, organize by weeks
    var weeks = [];
    var week = [];
    for (var i = 0; i < days.length; i++) {
      var d = new Date(days[i].date + 'T00:00:00');
      var dow = d.getDay(); // 0=Sun
      // Convert to Mon=0
      var mdow = dow === 0 ? 6 : dow - 1;

      // If first entry, pad leading days
      if (i === 0 && mdow > 0) {
        for (var p = 0; p < mdow; p++) week.push(null);
      }
      week.push(days[i]);
      if (mdow === 6) {
        weeks.push(week);
        week = [];
      }
    }
    if (week.length > 0) weeks.push(week);

    // Render as columns (each week is a column)
    for (var w = 0; w < weeks.length; w++) {
      var col = document.createElement('div');
      col.className = 'nt-heatmap-col';
      for (var r = 0; r < 7; r++) {
        var cell = document.createElement('span');
        cell.className = 'nt-heatmap-cell';
        var day = weeks[w][r];
        if (day) {
          cell.setAttribute('data-level', day.level);
          cell.title = day.date + ': ' + day.pomodoros + ' pomodoros, ' + day.notes + ' notes, ' + day.focus + 'm focus';
        } else {
          cell.setAttribute('data-level', '-1');
          cell.style.visibility = 'hidden';
        }
        col.appendChild(cell);
      }
      grid.appendChild(col);
    }
  }

  function load() {
    var cfg = window.NOTES_CONFIG || {};
    if (!cfg.heatmapUrl) return;
    fetch(cfg.heatmapUrl)
      .then(function(r) { return r.json(); })
      .then(function(data) { render(data.days); })
      .catch(function() {});
  }

  function init() {
    load();
  }

  return { init: init };
})();


/* ═══ Pomodoro Timer ═══ */

var Pomodoro = (function() {
  var cfg = window.NOTES_CONFIG || {};
  var WORK = (cfg.pomoWork || 25) * 60;
  var SHORT_BREAK = (cfg.pomoShort || 5) * 60;
  var LONG_BREAK = (cfg.pomoLong || 15) * 60;
  var CIRCUMFERENCE = 2 * Math.PI * 54; // 339.292

  var state = {
    phase: 'work',
    remaining: WORK,
    total: WORK,
    running: false,
    session: 0,
    todayCount: 0,
    intervalId: null,
  };

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

  function getLinkedNoteId() {
    var sel = document.getElementById('pomoNoteSelect');
    return sel ? sel.value : '';
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
      ringEl.style.stroke = state.phase === 'work' ? '#5B73E8' : '#4ECDC4';
    }

    if (phaseEl) phaseEl.textContent = getPhaseLabel(state.phase);
    if (countEl) countEl.textContent = state.todayCount;

    if (startBtn && pauseBtn) {
      startBtn.style.display = state.running ? 'none' : '';
      pauseBtn.style.display = state.running ? '' : 'none';
    }

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

      // Award XP via AJAX, include linked note
      if (cfg.pomodoroCompleteUrl) {
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
          // Update daily goals
          if (data.daily_progress) {
            DailyGoals.render(data.daily_progress);
          }
        })
        .catch(function() {});
      }

      if (state.session >= 4) {
        state.phase = 'long_break';
        state.session = 0;
      } else {
        state.phase = 'short_break';
      }
    } else {
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


/* ═══ Focus Mode ═══ */

var FocusMode = (function() {
  var active = false;
  var startTime = null;
  var elapsedInterval = null;
  var lastActivity = 0;
  var inactivityInterval = null;
  var INACTIVITY_MS = 2 * 60 * 1000;
  var warningShown = false;

  function setServerStatus(status) {
    fetch('/social/status/update/', {
      method: 'POST',
      headers: { 'X-CSRFToken': getCsrfToken(), 'Content-Type': 'application/x-www-form-urlencoded' },
      body: 'status=' + encodeURIComponent(status),
    }).catch(function() {});
  }

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


/* ═══ Word Count (for note_edit) ═══ */

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


/* ═══ Init ═══ */

document.addEventListener('DOMContentLoaded', function() {
  if (document.getElementById('pomoPanel')) Pomodoro.init();
  FocusMode.init();
  initWordCount();
  DailyGoals.init();
  Heatmap.init();
});
