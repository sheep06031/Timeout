/* Main JS Global settings & theme management */

(function() {
  'use strict';

  var html = document.documentElement;

  /* System theme listener */
  // If user chose "system", watch for OS-level changes
  var rawTheme = html.getAttribute('data-theme');

  function applySystemTheme(mq) {
    // Only act if the user's stored preference is "system"
    // The inline script in base.html already set the initial value,
    // but we tag it so this listener knows to keep updating.
    if (html.dataset.themeSource === 'system') {
      html.setAttribute('data-theme', mq.matches ? 'dark' : 'light');
    }
  }

  if (rawTheme === 'dark' || rawTheme === 'light') {
    // Explicit choice, mark so the listener doesn't override
    html.dataset.themeSource = 'explicit';
  } else {
    // "system" was resolved by inline script; mark for live updates
    html.dataset.themeSource = 'system';
  }

  var mq = window.matchMedia('(prefers-color-scheme: dark)');
  mq.addEventListener('change', function(e) { applySystemTheme(e); });

  /* Colorblind filter */
  // Already applied via data-colorblind attribute + CSS filters in custom.css.
  // Nothing extra needed here the attribute on <html> drives it.

  /* Font size */
  // Already applied via inline style="font-size: X%" on <html> in base.html.
})();
