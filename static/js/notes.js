/* Notes page*/

function getCsrfToken() {
  for (const cookie of document.cookie.split(';')) {
    const [key, val] = cookie.trim().split('=');
    if (key === 'csrftoken') return decodeURIComponent(val);
  }
  return '';
}

function updatePinIcon(item, pinned) {
  const header = item.querySelector('.nt-item__header');
  const existing = header.querySelector('.nt-pin-icon');
  if (pinned && !existing) {
    const icon = document.createElement('span');
    icon.className = 'nt-pin-icon';
    icon.title = 'Pinned';
    icon.textContent = '\uD83D\uDCCC';
    header.insertBefore(icon, header.firstChild);
  } else if (!pinned && existing) {
    existing.remove();
  }
}

function togglePin(noteId, btn) {
  fetch('/notes/' + noteId + '/pin/', {
    method: 'POST',
    headers: { 'X-CSRFToken': getCsrfToken() },
  })
  .then(function(res) { return res.json(); })
  .then(function(data) {
    btn.textContent = data.pinned ? 'Unpin' : 'Pin';
    btn.dataset.pinned = data.pinned;
    const item = document.getElementById('note-' + noteId);
    updatePinIcon(item, data.pinned);
  })
  .catch(function(err) { console.error('Pin toggle failed:', err); });
}
