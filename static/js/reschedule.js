let _rescheduleData = null;

function suggestReschedule(eventId, title, durationMinutes, reason) {
  _rescheduleData = null;
  const modal = new bootstrap.Modal(document.getElementById('rescheduleResultModal'));

  document.getElementById('rescheduleEventName').textContent = '"' + title + '"';
  document.getElementById('rescheduleTime').textContent = '';
  document.getElementById('rescheduleReason').textContent = '';
  document.getElementById('rescheduleLoadingMsg').style.display = '';
  document.getElementById('rescheduleErrorMsg').style.display = 'none';
  document.getElementById('rescheduleAcceptBtn').style.display = 'none';
  modal.show();

  fetch(window.RESCHEDULE_URL, {
    method: 'POST',
    headers: {'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': window.AI_CSRF_TOKEN},
    body: 'event_id=' + encodeURIComponent(eventId),
  })
  .then(r => r.json())
  .then(data => {
    document.getElementById('rescheduleLoadingMsg').style.display = 'none';
    if (!data.success) {
      document.getElementById('rescheduleErrorMsg').textContent = data.error || 'Could not get a suggestion.';
      document.getElementById('rescheduleErrorMsg').style.display = '';
      return;
    }
    const s = data.suggestion;
    s._originalEventId = eventId;
    s._reason = reason;
    _rescheduleData = s;
    const startFmt = s.start_datetime.replace('T', ' ');
    const endFmt = s.end_datetime.replace('T', ' ');
    document.getElementById('rescheduleTime').textContent = startFmt + ' \u2013 ' + endFmt;
    document.getElementById('rescheduleReason').textContent = s.reason || '';
    document.getElementById('rescheduleAcceptBtn').style.display = '';
  })
  .catch(() => {
    document.getElementById('rescheduleLoadingMsg').style.display = 'none';
    document.getElementById('rescheduleErrorMsg').textContent = 'Network error. Please try again.';
    document.getElementById('rescheduleErrorMsg').style.display = '';
  });
}

function acceptReschedule() {
  if (!_rescheduleData) return;
  const s = _rescheduleData;

  const banner = document.getElementById('reschedule-banner-' + s._originalEventId);
  if (banner) banner.remove();

  if (s._reason === 'missed' && s._originalEventId) {
    fetch(window.RESCHEDULE_CANCEL_URL_TPL.replace('{id}', s._originalEventId), {
      method: 'POST',
      headers: {'X-CSRFToken': window.AI_CSRF_TOKEN},
    });
  }

  const form = document.createElement('form');
  form.method = 'POST';
  form.action = window.EVENT_CREATE_URL;
  const fields = {
    csrfmiddlewaretoken: window.AI_CSRF_TOKEN,
    title: s.title,
    event_type: s.event_type || 'study_session',
    start_datetime: s.start_datetime,
    end_datetime: s.end_datetime,
    visibility: 'private',
    recurrence: 'none',
  };
  for (const [k, v] of Object.entries(fields)) {
    const input = document.createElement('input');
    input.type = 'hidden';
    input.name = k;
    input.value = v;
    form.appendChild(input);
  }
  document.body.appendChild(form);
  form.submit();
}

function markBannerComplete(eventId, btn) {
  btn.disabled = true;
  btn.textContent = '...';
  fetch('/deadlines/' + eventId + '/complete/', {
    method: 'POST',
    headers: {'X-CSRFToken': window.AI_CSRF_TOKEN},
  })
  .then(r => r.json())
  .then(data => {
    if (data.is_completed) {
      const banner = document.getElementById('reschedule-banner-' + eventId);
      if (banner) banner.remove();
    } else {
      btn.disabled = false;
      btn.textContent = 'Mark Complete';
    }
  })
  .catch(() => {
    btn.disabled = false;
    btn.textContent = 'Mark Complete';
  });
}

function dismissReschedule(eventId, reason) {
  const banner = document.getElementById('reschedule-banner-' + eventId);
  if (banner) banner.remove();

  if (reason === 'missed') {
    fetch(window.RESCHEDULE_CANCEL_URL_TPL.replace('{id}', eventId), {
      method: 'POST',
      headers: {'X-CSRFToken': window.AI_CSRF_TOKEN},
    });
  }
}
