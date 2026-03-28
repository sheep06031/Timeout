/**
 * Pomodoro Timer Module
 * Manages pomodoro work/break cycles with visual progress ring and session counter.
 */
var Pomodoro = (function() {
  var cfg = window.NOTES_CONFIG || {};
  var WORK        = Math.max(10, cfg.pomoWork  || 25) * 60;
  var SHORT_BREAK = Math.min((cfg.pomoShort ||  5) * 60, WORK);
  var LONG_BREAK  = Math.min((cfg.pomoLong  || 15) * 60, Math.floor(WORK * 1.5));
  var CIRCUMFERENCE = 2 * Math.PI * 54;

  // Minimum seconds actually worked before XP is awarded (50 % of the configured work session).
  var MIN_WORK_FOR_XP = Math.floor(WORK * 0.5);

  var state = {
    phase: 'work',
    remaining: WORK,
    total: WORK,
    running: false,
    session: 0,
    todayCount: 0,
    intervalId: null,
    elapsedWorkSeconds: 0,  // actual seconds ticked during current work phase
  };

  //  Persistence 

  /**
   * Persist the full timer state to sessionStorage so it survives page navigation.
   */
  function saveState() {
    sessionStorage.setItem('pomo_state', JSON.stringify({
      phase: state.phase,
      remaining: state.remaining,
      total: state.total,
      running: state.running,
      session: state.session,
      todayCount: state.todayCount,
      elapsedWorkSeconds: state.elapsedWorkSeconds,
      savedAt: Date.now(),
    }));
    // Keep today's count in localStorage so it survives session clears.
    localStorage.setItem('pomo_today', JSON.stringify({
      date: new Date().toDateString(),
      todayCount: state.todayCount,
    }));
  }

  /** Restore today's completed-session count from localStorage. */
  function _loadTodayCount() {
    try {
      var ls = JSON.parse(localStorage.getItem('pomo_today'));
      if (ls && ls.date === new Date().toDateString()) {
        state.todayCount = ls.todayCount || 0;
      }
    } catch(e) {}
  }

  /** Apply a saved state snapshot that has already expired, then fire phase-end. */
  function _applyExpiredState(saved) {
    state.phase              = saved.phase;
    state.session            = saved.session;
    state.todayCount         = saved.todayCount;
    state.elapsedWorkSeconds = saved.elapsedWorkSeconds || 0;
    state.total              = saved.total;
    state.remaining          = 0;
    state.running            = false;
    _processPhaseEnd(false);
    if (saved.phase !== 'work') _showBreakEndedPopup();
  }

  /** Apply a saved state snapshot that still has time remaining. */
  function _applyResumedState(saved, remaining) {
    state.phase              = saved.phase;
    state.remaining          = remaining;
    state.total              = saved.total;
    state.running            = false;
    state.session            = saved.session;
    state.todayCount         = saved.todayCount;
    state.elapsedWorkSeconds = saved.elapsedWorkSeconds || 0;
  }

  /**
   * Restore state from sessionStorage, accounting for time spent navigating.
   * Returns true if a running session was successfully restored.
   */
  function loadState() {
    _loadTodayCount();
    try {
      var saved = JSON.parse(sessionStorage.getItem('pomo_state'));
      if (!saved || !saved.running) return false;
      var elapsed   = Math.floor((Date.now() - saved.savedAt) / 1000);
      var remaining = saved.remaining - elapsed;
      if (remaining <= 0) {
        _applyExpiredState(saved);
        return false;
      }
      _applyResumedState(saved, remaining);
      return true;
    } catch(e) { return false; }
  }

  // Helpers

  /**  
   * Get the configured duration for a given phase, enforcing limits based on work duration. 
  */
  function getDuration(phase) {
    if (phase === 'work')       return WORK;
    if (phase === 'long_break') return LONG_BREAK;
    return SHORT_BREAK;
  }

  /** 
   * Get the display label for a given phase. 
   */
  function getPhaseLabel(phase) {
    if (phase === 'work')        return 'Work Session';
    if (phase === 'short_break') return 'Short Break';
    return 'Long Break';
  }

  /** 
   * Get the currently linked note ID from the dropdown, or fallback to the one in config. 
   */
  function getLinkedNoteId() {
    var sel = document.getElementById('pomoNoteSelect');
    return sel ? sel.value : (cfg.currentNoteId || '');
  }

  // Rendering

  /** 
   * Update the circular progress ring based on the current phase and remaining time. 
   */
  function _renderRing() {
    var ringEl = document.getElementById('pomoRing');
    if (!ringEl) return;
    var progress = 1 - (state.remaining / state.total);
    ringEl.setAttribute('stroke-dashoffset', CIRCUMFERENCE * (1 - progress));
    ringEl.style.stroke = state.phase === 'work' ? '#5B73E8' : '#4ECDC4';
  }

  /** 
   * Show/hide start and pause buttons based on whether the timer is running. 
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
   * Update all UI elements (timer, phase label, count, ring, buttons, mini-bar).
   */
  function render() {
    var mins = Math.floor(state.remaining / 60);
    var secs = state.remaining % 60;
    var timeStr = String(mins).padStart(2, '0') + ':' + String(secs).padStart(2, '0');
    var timeEl = document.getElementById('pomoTime');
    if (timeEl) timeEl.textContent = timeStr;
    _renderRing();
    var phaseEl = document.getElementById('pomoPhase');
    var countEl = document.getElementById('pomodoroCount');
    if (phaseEl) phaseEl.textContent = getPhaseLabel(state.phase);
    if (countEl) countEl.textContent = state.todayCount;
    _renderButtons();
    var dots = document.querySelectorAll('#pomoDots .nt-pomo-dot');
    dots.forEach(function(dot, i) {
      dot.classList.toggle('nt-pomo-dot--filled', i < state.session);
      dot.classList.toggle('nt-pomo-dot--active', i === state.session && state.phase === 'work');});
    var miniBar = document.getElementById('pomoMiniBar');
    if (miniBar) {
      miniBar.style.display = state.running ? 'flex' : 'none';
      var miniPhase = document.getElementById('pomoMiniPhase');
      var miniTime  = document.getElementById('pomoMiniTime');
      if (miniPhase) miniPhase.textContent = getPhaseLabel(state.phase);
      if (miniTime)  miniTime.textContent  = timeStr;}
  }

  // Timer logic

  function tick() {
    if (state.remaining <= 0) {
      _processPhaseEnd(false);
      return;
    }
    state.remaining--;
    if (state.phase === 'work') state.elapsedWorkSeconds++;
    saveState();
    render();
  }

  /**
   * Award XP for completing a work session.
   * Skips are never rewarded.  Minimum 50 % of configured work time must have been ticked.
   */
  function _awardWorkXP(wasSkipped) {
    if (wasSkipped) return;
    if (state.elapsedWorkSeconds < MIN_WORK_FOR_XP) return;
    if (!cfg.pomodoroCompleteUrl) return;

    var minutes = Math.floor(state.elapsedWorkSeconds / 60);
    var body = new FormData();
    var noteId = getLinkedNoteId();
    if (noteId) body.append('note_id', noteId);
    body.append('elapsed_minutes', minutes);

    postJSON(cfg.pomodoroCompleteUrl, { body: body })
      .then(function(data) {
        if (typeof updateStatsUI === 'function') updateStatsUI(data);
        if (data.xp_gained && typeof showXpToast === 'function') showXpToast(data.xp_gained);
        if (data.daily_progress && typeof DailyGoals !== 'undefined') DailyGoals.render(data.daily_progress);
      })
      .catch(function() {});
  }

  /**
   * Transition to the next phase and, for work → break, award XP when earned.
   */
  function _advancePhase(wasSkipped) {
    if (state.phase === 'work') {
      state.session++;
      state.todayCount++;
      _awardWorkXP(wasSkipped);
      state.elapsedWorkSeconds = 0;
      state.phase = state.session >= 4 ? 'long_break' : 'short_break';
      if (state.session >= 4) state.session = 0;
    } else {
      state.phase = 'work';
      state.elapsedWorkSeconds = 0;
    }
  }

  /**
   * Core phase-end handler: stop, play alarm, advance, reset duration, render.
   */
  function _processPhaseEnd(wasSkipped) {
    clearInterval(state.intervalId);
    state.running = false;
    if (typeof playAlarm === 'function') playAlarm();
    _advancePhase(wasSkipped);
    state.total     = getDuration(state.phase);
    state.remaining = state.total;
    saveState();
    render();
  }

  // Public controls  

  function start() {
    if (state.running) return;
    state.running = true;
    state.intervalId = setInterval(tick, 1000);
    saveState();
    render();
  }

  /**
   * Pause the timer, keeping all state intact for resumption.  No XP is awarded since the session isn't complete.
   */
  function pause() {
    clearInterval(state.intervalId);
    state.running = false;
    saveState();
    render();
  }

  /**
   * Skip the current phase.  Work skips never award XP.
   */
  function skip() {
    clearInterval(state.intervalId);
    state.running = false;
    state.remaining = 0;
    _processPhaseEnd(true);   // wasSkipped = true → no XP
  }

  /**
   * Reset the entire timer state, clearing sessions and counts.  No XP is awarded since the session isn't complete.
   */
  function reset() {
    clearInterval(state.intervalId);
    state.running = false;
    state.phase   = 'work';
    state.session = 0;
    state.total   = WORK;
    state.remaining = WORK;
    state.elapsedWorkSeconds = 0;
    sessionStorage.removeItem('pomo_state');
    render();
  }

  // Navigation guard 

  /**
   * Intercept link clicks while a work session is running.
   * Links within /notes/ are always allowed (the timer resumes on the next page).
   * All other navigation asks for confirmation; if accepted the session ends.
   */
  function _setupNavigationGuard() {
    document.addEventListener('click', function(e) {
      if (!state.running || state.phase !== 'work') return;
      var link = e.target.closest('a[href]');
      if (!link) return;
      var href = link.getAttribute('href') || '';
      // Allow navigation within the notes section freely.
      if (/^\/(notes|notes\/)/.test(href) || href === '/notes' || href.startsWith('/notes/')) return;
      // Warn before leaving the notes ecosystem.
      e.preventDefault();
      if (window.confirm('You have an active work session. Leaving will end your Pomodoro. Are you sure?')) {
        sessionStorage.removeItem('pomo_state');
        clearInterval(state.intervalId);
        window.location.href = href;
      }
    });

    // Always persist state on unload so the next notes page can restore it.
    window.addEventListener('beforeunload', function() {
      if (state.running) saveState();
    });
  }

  //  Break-ended popup 

  /**
   * Show an overlay popup when a break expired while the user was on another page.
   * Only displayed when we are NOT already on a notes page.
   */
  function _showBreakEndedPopup() {
    if (window.location.pathname.startsWith('/notes')) return;
    var overlay = document.createElement('div');
    overlay.id = 'pomoBreakEndedOverlay';
    overlay.style.cssText = [
      'position:fixed;inset:0;z-index:9999;display:flex;align-items:center;justify-content:center',
      'background:rgba(0,0,0,0.55)',
    ].join(';');
    overlay.innerHTML =
      '<div style="background:#fff;border-radius:16px;padding:32px 40px;max-width:380px;text-align:center;box-shadow:0 8px 32px rgba(0,0,0,0.18)">' +
        '<div style="font-size:2.5rem;margin-bottom:8px">🍅</div>' +
        '<h3 style="margin:0 0 8px;font-size:1.3rem">Break\'s over!</h3>' +
        '<p style="color:#666;margin:0 0 24px;font-size:.95rem">Your Pomodoro break has ended.<br>Ready to get back to work?</p>' +
        '<button id="pomoBreakGoBtn" style="background:#5B73E8;color:#fff;border:none;border-radius:8px;padding:10px 28px;font-size:1rem;cursor:pointer;margin-right:12px">Return to Notes</button>' +
        '<button id="pomoBreakNoBtn" style="background:#f1f3f7;color:#333;border:none;border-radius:8px;padding:10px 20px;font-size:1rem;cursor:pointer">End Session</button>' +
      '</div>';
    document.body.appendChild(overlay);
    document.getElementById('pomoBreakGoBtn').addEventListener('click', function() {
      window.location.href = '/notes/';});
    document.getElementById('pomoBreakNoBtn').addEventListener('click', function() {
      sessionStorage.removeItem('pomo_state');
      overlay.remove();});
  }

  //  Note-select population 

  function populateNoteSelect() {
    var sel = document.getElementById('pomoNoteSelect');
    if (!sel) return;
    var notes = cfg.userNotes || [];
    for (var i = 0; i < notes.length; i++) {
      var opt = document.createElement('option');
      opt.value = notes[i][0];
      opt.textContent = notes[i][1].length > 35 ? notes[i][1].substring(0, 35) + '...' : notes[i][1];
      // Pre-select the note being edited on note_edit pages.
      if (cfg.currentNoteId && String(notes[i][0]) === String(cfg.currentNoteId)) {
        opt.selected = true;
      }
      sel.appendChild(opt);
    }
  }

  //  Init 

  /**
   * Initialise the Pomodoro module.
   * Restores a running session from sessionStorage when navigating between notes pages.
   * Called unconditionally by notes.js on both notes.html and note_edit.html.
   */
  function init() {
    var hadRunningSession = loadState();    // restore from sessionStorage
    populateNoteSelect();
    render();

    var startBtn  = document.getElementById('pomoStartBtn');
    var pauseBtn  = document.getElementById('pomoPauseBtn');
    var skipBtn   = document.getElementById('pomoSkipBtn');
    var resetBtn  = document.getElementById('pomoResetBtn');

    if (startBtn)  startBtn.addEventListener('click', start);
    if (pauseBtn)  pauseBtn.addEventListener('click', pause);
    if (skipBtn)   skipBtn.addEventListener('click', skip);
    if (resetBtn)  resetBtn.addEventListener('click', reset);

    _setupNavigationGuard();

    // Auto-resume timer if a session was active.
    if (hadRunningSession) start();
  }

  return { init: init };
})();
