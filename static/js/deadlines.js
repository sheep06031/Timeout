/**
 * Deadline list management: Mark deadlines complete/incomplete and track status.
 * Handles checkbox events to complete or revert deadline status via AJAX,
 * updates UI with animations, and manages deadline list counts.
 */

/**
 * Open add event modal prefilled with start and end times for a specific date.
 * @param {string} dateStr - Date string in YYYY-MM-DD format.
 */
function openAddEvent(dateStr) {
  document.getElementById('eventStart').value = dateStr + 'T09:00';
  document.getElementById('eventEnd').value = dateStr + 'T10:00';
  var modal = new bootstrap.Modal(document.getElementById('addEventModal'));
  modal.show();
}

/**
 * Initialize deadline checkbox event listeners on page load.
 * Sets up handlers for marking deadlines complete and incomplete.
 */
document.addEventListener('DOMContentLoaded', function() {
   
  document.querySelectorAll('.dl-checkbox:not(.dl-checkbox--completed)').forEach(function(checkbox) {
    checkbox.addEventListener('change', function() {
      completeDeadline(this.dataset.eventId, this);
    });
  });

  // Mark incomplete — completed checkboxes
  document.querySelectorAll('.dl-checkbox--completed').forEach(function(checkbox) {
    checkbox.addEventListener('change', function() {
      if (!this.checked) {
        incompleteDeadline(this.dataset.eventId, this);
      }
    });
  });

});

/**
 * Mark a deadline as complete and animate removal from the list.
 * Sends POST request to server, disables checkbox, removes item, updates count.
 * @param {string} eventId - ID of the deadline to complete.
 * @param {HTMLElement} checkbox - Checkbox element triggering the completion.
 */
function completeDeadline(eventId, checkbox) {
  var item = document.querySelector('[data-id="' + eventId + '"]');

  fetch('/deadlines/' + eventId + '/complete/', {
    method: 'POST',
    headers: {
      'X-CSRFToken': getCSRFToken(),
      'Content-Type': 'application/json',
    },
  })
  .then(function(res) {
    if (!res.ok) throw new Error('Request failed');
    return res.json();
  })
  .then(function(data) {
    if (data.is_completed && item) {
      checkbox.disabled = true;
      item.classList.add('dl-item--completing');
      setTimeout(function() {
        item.remove();
        // Update tab count badge
        var panel = document.querySelector('.dl-tab-panel--active');
        if (panel) {
          var remaining = panel.querySelectorAll('.dl-item').length;
          var activeBtn = document.querySelector('.dl-tab-btn--active .dl-tab-count');
          if (activeBtn) activeBtn.textContent = remaining;
          if (remaining === 0) location.reload(); }}, 400);
    }
  })
  .catch(function(err) {
    console.error('Complete failed:', err);
    checkbox.checked = false;
  });
}

/**
 * Mark a completed deadline as incomplete and animate removal from the list.
 * Sends POST request to server to revert completion status and removes item.
 * @param {string} eventId - ID of the deadline to mark incomplete.
 * @param {HTMLElement} checkbox - Checkbox element triggering the reversion.
 */
function incompleteDeadline(eventId, checkbox) {
  var item = document.querySelector('[data-id="' + eventId + '"]');

  fetch('/deadlines/' + eventId + '/incomplete/', {
    method: 'POST',
    headers: {
      'X-CSRFToken': getCSRFToken(),
      'Content-Type': 'application/json',
    },
  })
  .then(function(res) {
    if (!res.ok) throw new Error('Request failed');
    return res.json();
  })
  .then(function(data) {
    if (data.is_completed === false && item) {
      item.classList.add('dl-item--completing');
      setTimeout(function() {
        item.remove();
        if (document.querySelectorAll('.dl-item').length === 0) {
          location.reload();
        }
      }, 400);
    }
  })
  .catch(function(err) {
    console.error('Incomplete failed:', err);
    checkbox.checked = true;
  });
}

