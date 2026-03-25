/**
 * AI Calendar Event Creation
 * Handles user input validation, API calls, and UI feedback for AI-powered event creation.
 */



/**
 * Reset the AI input UI to loading state with spinners and hidden result elements.
 */
function _resetAiUI() {
  document.getElementById('aiSubmitBtn').disabled = true;
  document.getElementById('aiSpinner').classList.remove('d-none');
  document.getElementById('aiSuccess').classList.add('d-none');
  document.getElementById('aiError').classList.add('d-none');
  document.getElementById('aiResult').classList.remove('d-none');
}

/**
 * Display an error message in the AI result panel.
 */
function _showAiError(msg) {
  var el = document.getElementById('aiError');
  el.textContent = msg;
  el.classList.remove('d-none');
}

/**
 * Process AI event creation response and show success or error message.
 */
function _handleAiResult(data) {
  if (data.success) {
    var el = document.getElementById('aiSuccess');
    el.textContent = '"' + data.event.title + '" added (' + data.event.start + ' \u2013 ' + data.event.end + ')';
    el.classList.remove('d-none');
    document.getElementById('aiUserInput').value = '';
    setTimeout(function() { location.reload(); }, 1500);
  } else {
    _showAiError(data.error || 'Failed to create event.');
  }
}

/**
 * Submit user input to AI event creation API and handle the response.
 */
async function submitAiEvent() {
  var input = document.getElementById('aiUserInput').value.trim();
  if (!input) return;

  _resetAiUI();

  try {
    var formData = new FormData();
    formData.append('user_input', input);
    formData.append('csrfmiddlewaretoken', window.AI_CSRF_TOKEN);
    var res = await fetch(window.AI_ADD_URL, { method: 'POST', body: formData });
    _handleAiResult(await res.json());
  } catch (err) {
    _showAiError('Network error. Please try again.');
  } finally {
    document.getElementById('aiSubmitBtn').disabled = false;
    document.getElementById('aiSpinner').classList.add('d-none');
  }
}
