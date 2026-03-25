/**
 * Event Rescheduling Management
 * Handles AI-powered event rescheduling suggestions, user acceptance, and deadline completion/dismissal.
 */

let _rescheduleData = null;

/**
 * Reset rescheduling modal to loading state with event title.
 */
function _resetRescheduleModal(title) {
  document.getElementById('rescheduleEventName').textContent = '"' + title + '"';
  document.getElementById('rescheduleTime').textContent = '';
  document.getElementById('rescheduleReason').textContent = '';
  document.getElementById('rescheduleLoadingMsg').style.display = '';
  document.getElementById('rescheduleErrorMsg').style.display = 'none';
  document.getElementById('rescheduleAcceptBtn').style.display = 'none';
}

/**
 * Display error message in rescheduling modal.
 */
function _showRescheduleError(msg) {
  document.getElementById('rescheduleLoadingMsg').style.display = 'none';
  document.getElementById('rescheduleErrorMsg').textContent = msg;
  document.getElementById('rescheduleErrorMsg').style.display = '';
}

/**
 * Display the suggested rescheduling details and store for later acceptance.
 */
function _displayRescheduleSuggestion(s, eventId, reason) {
  document.getElementById('rescheduleLoadingMsg').style.display = 'none';
  s._originalEventId = eventId;
  s._reason = reason;
  _rescheduleData = s;
  document.getElementById('rescheduleTime').textContent = s.start_datetime.replace('T', ' ') + ' \u2013 ' + s.end_datetime.replace('T', ' ');
  document.getElementById('rescheduleReason').textContent = s.reason || '';
  document.getElementById('rescheduleAcceptBtn').style.display = '';
}

/**
 * Fetch rescheduling suggestion for an event and display it in modal.
 */
function suggestReschedule(eventId, title, durationMinutes, reason) {
  _rescheduleData = null;
  var modal = new bootstrap.Modal(document.getElementById('rescheduleResultModal'));
  _resetRescheduleModal(title);
  modal.show();

  fetch(window.RESCHEDULE_URL, {
    method: 'POST',
    headers: {'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': window.AI_CSRF_TOKEN},
    body: 'event_id=' + encodeURIComponent(eventId),
  })
  .then(function(r) { return r.json(); })
  .then(function(data) {
    if (!data.success) { _showRescheduleError(data.error || 'Could not get a suggestion.'); return; }
    _displayRescheduleSuggestion(data.suggestion, eventId, reason);
  })
  .catch(function() { _showRescheduleError('Network error. Please try again.'); });
}

/**
 * Create a hidden form with given action and field values for submission.
 */
function _buildHiddenForm(action, fields) {
  var form = document.createElement('form');
  form.method = 'POST';
  form.action = action;
  for (var k in fields) {
    var input = document.createElement('input');
    input.type = 'hidden';
    input.name = k;
    input.value = fields[k];
    form.appendChild(input);
  }
  return form;
}

/**
 * Accept the suggested reschedule and create new event with updated time.
 */
function acceptReschedule() {
  if (!_rescheduleData) return;
  var s = _rescheduleData;

  var banner = document.getElementById('reschedule-banner-' + s._originalEventId);
  if (banner) banner.remove();

  if (s._reason === 'missed' && s._originalEventId) {
    fetch(window.RESCHEDULE_CANCEL_URL_TPL.replace('{id}', s._originalEventId), {
      method: 'POST',
      headers: {'X-CSRFToken': window.AI_CSRF_TOKEN},
    });
  }

  var form = _buildHiddenForm(window.EVENT_CREATE_URL, {
    csrfmiddlewaretoken: window.AI_CSRF_TOKEN,
    title: s.title,
    event_type: s.event_type || 'study_session',
    start_datetime: s.start_datetime,
    end_datetime: s.end_datetime,
    visibility: 'private',
    recurrence: 'none',
  });
  document.body.appendChild(form);
  form.submit();
}

/**
 * Mark a deadline as complete and remove its rescheduling banner.
 */
function markBannerComplete(eventId, btn) {
  btn.disabled = true;
  btn.textContent = '...';
  fetch('/deadlines/' + eventId + '/complete/', {
    method: 'POST',
    headers: {'X-CSRFToken': window.AI_CSRF_TOKEN},
  })
  .then(function(r) { return r.json(); })
  .then(function(data) {
    if (data.is_completed) {
      var banner = document.getElementById('reschedule-banner-' + eventId);
      if (banner) banner.remove();
    } else {
      btn.disabled = false;
      btn.textContent = 'Mark Complete';
    }
  })
  .catch(function() {
    btn.disabled = false;
    btn.textContent = 'Mark Complete';
  });
}

/**
 * Dismiss a rescheduling banner and cancel the suggestion if it was for a missed event.
 */
function dismissReschedule(eventId, reason) {
  var banner = document.getElementById('reschedule-banner-' + eventId);
  if (banner) banner.remove();

  if (reason === 'missed') {
    fetch(window.RESCHEDULE_CANCEL_URL_TPL.replace('{id}', eventId), {
      method: 'POST',
      headers: {'X-CSRFToken': window.AI_CSRF_TOKEN},
    });
  }
}
