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
