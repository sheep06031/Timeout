/**
 * Shared Utilities
 * Common helpers used across multiple JS modules.
 */

/**
 * Retrieve CSRF token from browser cookies for secure Django form submissions.
 */
function getCSRFToken() {
    const match = document.cookie.split(';')
        .map(c => c.trim())
        .find(c => c.startsWith('csrftoken='));
    return match ? decodeURIComponent(match.split('=')[1]) : '';
}

/**
 * Perform a POST request with CSRF token, returning parsed JSON.
 * @param {string} url - The endpoint URL.
 * @param {Object} [options] - Optional { headers, body }.
 * @returns {Promise<Object>} Parsed JSON response.
 */
function postJSON(url, { headers = {}, body } = {}) {
    return fetch(url, {
        method: 'POST',
        headers: { 'X-CSRFToken': getCSRFToken(), ...headers },
        body,
    }).then(r => r.json());
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
