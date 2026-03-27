/**
 * Notes Page: Streaks, Study Heatmap, Daily Goals
 * Handles study productivity tracking including daily goal management and study heatmap visualization.
 * Pomodoro timer is in pomodoro.js, Focus mode is in focus_mode.js.
 */

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
    headers: { 'X-CSRFToken': getCSRFToken() },
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
        headers: { 'X-CSRFToken': getCSRFToken() },
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
