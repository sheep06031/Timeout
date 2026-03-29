/**
 * Theme Initialisation (runs synchronously in <head>)
 * Resolves the 'system' theme preference to an actual 'dark' or 'light' value
 * before CSS is painted, preventing a flash of unstyled/wrong-theme content.
 */
(function () {
  var h = document.documentElement;
  if (h.getAttribute('data-theme') === 'system') {
    h.setAttribute('data-theme',
      window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  }
}());
