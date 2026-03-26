/**
 * Calendar event management: Add events, view day details, mark ongoing status.
 * Handles modal interactions for creating new events, viewing events by day,
 * and highlighting currently active events.
 */

function persistDismissAlert(key) {
    const meta = document.querySelector('meta[name="dismiss-alert-url"]');
    const csrf = document.querySelector('meta[name="csrf-token"]');
    if (!meta || !csrf) return;
    fetch(meta.content, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRFToken': csrf.content,
        },
        body: `key=${encodeURIComponent(key)}`,
    });
}

function dismissAlert(key, btn) {
    const alertEl = btn.closest('.alert');
    if (alertEl) alertEl.remove();
    persistDismissAlert(key);
}

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
 * Handle opening a specific event from URL parameter.
 * If ?open_event=ID is present, scroll to and highlight the event chip.
 */
(function () {
    const params = new URLSearchParams(window.location.search);
    const openId = params.get("open_event");
    if (openId) {
        const chip = document.querySelector(`[data-event-id="${openId}"]`);
        if (chip) {
            chip.scrollIntoView({ behavior: "smooth", block: "center" });
            chip.classList.add("event-highlight");
            setTimeout(() => chip.classList.remove("event-highlight"), 2500);
            chip.click();
        }
    }
    if (!openId) return;
    window.addEventListener('load', function () {
        const chip = document.querySelector(`[data-event-id="${openId}"]`);
        if (chip) chip.click();
    });
})();

window.AI_ADD_URL = document.querySelector('meta[name="ai-add-url"]').content;
window.AI_CSRF_TOKEN = document.querySelector('meta[name="csrf-token"]').content;
window.SP_PLAN_URL = document.querySelector('meta[name="sp-plan-url"]').content;
window.SP_CONFIRM_URL = document.querySelector('meta[name="sp-confirm-url"]').content;
window.RESCHEDULE_URL = document.querySelector('meta[name="reschedule-url"]').content;
window.RESCHEDULE_CANCEL_URL_TPL = '/calendar/{id}/cancel/';
window.EVENT_CREATE_URL = document.querySelector('meta[name="event-create-url"]').content;
window.RS_SUGGEST_URL = document.querySelector('meta[name="rs-suggest-url"]').content;
window.RS_APPLY_URL = document.querySelector('meta[name="rs-apply-url"]').content;

/**
 * Open modal displaying all events for a selected day with titles and times.
 * @param {string} dateStr - Date string in YYYY-MM-DD format.
 * @param {string} dateLabel - Human-readable date label for modal title.
 * @param {HTMLElement} el - Clicked element (used to find parent cell).
 */
function openDayEvents(dateStr, dateLabel, el) {
    const cell = el.closest('td');
    const chips = cell.querySelectorAll('.cal-chip');

    document.getElementById('dayEventsModalTitle').textContent = dateLabel;

    const body = document.getElementById('dayEventsModalBody');
    body.innerHTML = '';

    chips.forEach(chip => {
        const item = document.createElement('div');
        item.className = 'day-modal-event-item';

        const title = chip.dataset.eventTitle || chip.textContent.trim();
        const start = chip.dataset.eventStart || '';
        const end = chip.dataset.eventEnd || '';
        const eventClass = [...chip.classList]
            .find(c => c.startsWith('cal-chip--') && c !== 'cal-chip--conflict') || '';

        item.innerHTML = `
        <div class="day-modal-event ${eventClass}">
            <div class="day-modal-event-title">${title}</div>
            <div class="day-modal-event-time">${start} → ${end}</div>
        </div>
        `;

        item.addEventListener('click', () => {
            bootstrap.Modal.getInstance(document.getElementById('dayEventsModal'))?.hide();
            setTimeout(() => chip.click(), 300);
        });

        body.appendChild(item);
    });

    new bootstrap.Modal(document.getElementById('dayEventsModal')).show();
}

/**
 * Mark calendar event chips as 'ongoing' based on their data-event-status attribute.
 */
document.querySelectorAll('.cal-chip').forEach(chip => {
    const status = chip.getAttribute('data-event-status');
    if (status === 'Ongoing') {
        chip.classList.add('cal-chip--ongoing');
    }
});