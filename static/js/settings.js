/**
 * Settings form autosave, theme switching, and colorblind mode.
 * Handles real-time form autosave with debounce, live theme preview,
 * and colorblind mode switching with immediate visual feedback.
 */
(function() {
  var form = document.getElementById('settingsForm');
  var statusEl = document.getElementById('autosaveStatus');
  var statusText = document.getElementById('autosaveText');
  var saveUrl = '/settings/save/';
  var saveTimer = null;

  /**
   * Display autosave status message with optional auto-hide for success.
   * @param {string} text - Status message text to display.
   * @param {string} cls - CSS class suffix for styling (saved, saving, error).
   */
  function showStatus(text, cls) {
    statusText.textContent = text;
    statusEl.className = 'stg-autosave stg-autosave--' + cls;
    statusEl.style.display = '';
    clearTimeout(statusEl._hideTimer);
    if (cls === 'saved') {
      statusEl._hideTimer = setTimeout(function() { statusEl.style.display = 'none'; }, 2000);
    }
  }

  /**
   * Debounce autosave trigger to avoid excessive API calls (400ms delay).
   */
  function autoSave() {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(doSave, 400);
  }

  /**
   * Save form data to server via AJAX with CSRF token.
   * Handles checkbox deletion for unchecked fields and shows status feedback.
   */
  function doSave() {
    showStatus('Saving...', 'saving');
    var data = new FormData(form);
    // Checkboxes: if unchecked, FormData won't include them and delete explicitly
    if (!form.querySelector('[name="notification_sounds"]').checked) {
      data.delete('notification_sounds');
    }
    if (!form.querySelector('[name="auto_online"]').checked) {
      data.delete('auto_online');
    }
    postJSON(saveUrl, { body: data })
    .then(function(d) {
      if (d.success) showStatus('Saved', 'saved');
      else showStatus('Error', 'error');
    })
    .catch(function() { showStatus('Error', 'error'); });
  }

  /**
   * Initialize form input listeners to trigger autosave on any change.
   * Handles text inputs, checkboxes, selects, and range/number inputs.
   */
  form.querySelectorAll('input, select').forEach(function(el) {
    el.addEventListener('change', autoSave);
    if (el.type === 'range' || el.type === 'number') {
      el.addEventListener('input', autoSave);
    }
  });


  /**
   * Initialize theme selection with live preview and card highlight.
   * Supports dark, light, and system preference modes with immediate visual update.
   */
  document.querySelectorAll('.stg-theme-radio').forEach(function(radio) {
    radio.addEventListener('change', function() {
      document.querySelectorAll('.stg-theme-card').forEach(function(c) {
        c.classList.remove('stg-theme-card--active');
      });
      this.closest('.stg-theme-card').classList.add('stg-theme-card--active');

      var val = this.value;
      if (val === 'dark') {
        document.documentElement.setAttribute('data-theme', 'dark');
        document.documentElement.dataset.themeSource = 'explicit';
      } else if (val === 'system') {
        var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        document.documentElement.setAttribute('data-theme', prefersDark ? 'dark' : 'light');
        document.documentElement.dataset.themeSource = 'system';
      } else {
        document.documentElement.setAttribute('data-theme', 'light');
        document.documentElement.dataset.themeSource = 'explicit';
      }
    });
  });

  /**
   * Initialize colorblind mode selection with live preview and option highlight.
   * Updates document data attribute immediately to apply color scheme changes.
   */
  document.querySelectorAll('.stg-radio-option input').forEach(function(radio) {
    radio.addEventListener('change', function() {
      this.closest('.stg-radio-group').querySelectorAll('.stg-radio-option').forEach(function(o) {
        o.classList.remove('stg-radio-option--active');
      });
      this.closest('.stg-radio-option').classList.add('stg-radio-option--active');
      document.documentElement.setAttribute('data-colorblind', this.value);
    });
  });

  /**
   * Update short-break and long-break hint text to reflect the current work duration.
   */
  function updatePomoHints() {
    var workEl = document.getElementById('id_pomo_work_minutes');
    var sbHint = document.getElementById('shortBreakHint');
    var lbHint = document.getElementById('longBreakHint');
    if (!workEl || !sbHint || !lbHint) return;
    var w = parseInt(workEl.value, 10);
    if (!w || w < 10) w = 10;
    sbHint.textContent = 'Maximum ' + w + ' min (= work duration).';
    lbHint.textContent = 'Maximum ' + Math.floor(w * 1.5) + ' min (= 1.5× work duration).';
  }

  var workInput = document.getElementById('id_pomo_work_minutes');
  if (workInput) workInput.addEventListener('input', updatePomoHints);
  updatePomoHints();
})();