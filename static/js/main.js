/**
 * Global Theme Management
 * Handles system-wide dark/light theme preference synchronization with OS settings.
 */

(function() {
  'use strict';
  var html = document.documentElement;
  var rawTheme = html.getAttribute('data-theme');

  /**
   * Apply system theme preference to document if user preference is "system".
   */
  function applySystemTheme(mq) {
    if (html.dataset.themeSource === 'system') {
      html.setAttribute('data-theme', mq.matches ? 'dark' : 'light');
    }
  }
  if (rawTheme === 'dark' || rawTheme === 'light') {
    html.dataset.themeSource = 'explicit';
  } else {
    html.dataset.themeSource = 'system';
  }

  var mq = window.matchMedia('(prefers-color-scheme: dark)');
  mq.addEventListener('change', function(e) { applySystemTheme(e); });
})();
