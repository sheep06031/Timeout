/**
 * Event Details Modal
 * Populates the event details modal with data from the triggering element's
 * data attributes, and sets action button hrefs dynamically.
 */

/* Colour map keyed by event type string */
const EVENT_TYPE_COLORS = {
    deadline:      '#5b5ddf',
    exam:          '#e53935',
    class:         '#43a047',
    meeting:       '#8e24aa',
    study_session: '#00acc1',
    other:         '#78909c',
};

/* Status badge colour map */
const STATUS_COLORS = {
    Past:     { bg: '#f5f5f5', color: '#9e9e9e' },
    Upcoming: { bg: '#e3f2fd', color: '#1565c0' },
    Ongoing:  { bg: '#e8f5e9', color: '#2e7d32' },
};

/**
 * Format a duration in minutes as a human-readable string.
 * e.g. 90 → "1h 30m", 60 → "1h", 45 → "45m", 0 → "All day"
 */
function formatDuration(totalMins) {
    const hours = Math.floor(totalMins / 60);
    const mins  = totalMins % 60;
    if (hours > 0 && mins > 0) return `${hours}h ${mins}m`;
    if (hours > 0)              return `${hours}h`;
    if (mins > 0)               return `${mins}m`;
    return 'All day';
}

/**
 * Format a countdown string relative to now given start and end Date objects.
 * Returns strings like "Starts in 2d 3h", "Ongoing — ends in 45m", "Ended 1h ago".
 */
function formatCountdown(startD, endD) {
    const now = new Date();

    if (now < startD) {
        const totalMins = Math.round((startD - now) / 60000);
        const days  = Math.floor(totalMins / 1440);
        const hours = Math.floor((totalMins % 1440) / 60);
        const mins  = totalMins % 60;
        if (days > 0)       return `Starts in ${days}d ${hours}h`;
        if (hours > 0)      return `Starts in ${hours}h ${mins}m`;
        return `Starts in ${mins}m`;
    }

    if (now <= endD) {
        const totalMins = Math.round((endD - now) / 60000);
        const hours = Math.floor(totalMins / 60);
        const mins  = totalMins % 60;
        if (hours > 0) return `Ongoing — ends in ${hours}h ${mins}m`;
        return `Ongoing — ends in ${mins}m`;
    }

    const totalMins = Math.round((now - endD) / 60000);
    const days  = Math.floor(totalMins / 1440);
    const hours = Math.floor((totalMins % 1440) / 60);
    if (days > 0)  return `Ended ${days}d ago`;
    if (hours > 0) return `Ended ${hours}h ago`;
    return 'Just ended';
}

/* Modal population */

const eventDetailsModal = document.getElementById('eventDetailsModal');
if (eventDetailsModal) {
    eventDetailsModal.addEventListener('show.bs.modal', function (event) {
        const btn = event.relatedTarget;
        if (!btn) return;

        /* Read data attributes from the triggering element */
        const eventId   = btn.getAttribute('data-event-id');
        const rawType   = (btn.getAttribute('data-event-type') || '').toLowerCase().replace(/ /g, '_');
        const color     = EVENT_TYPE_COLORS[rawType] || '#5b5ddf';
        const start     = btn.getAttribute('data-event-start') || '';
        const end       = btn.getAttribute('data-event-end')   || '';

        /* Colour bar */
        document.getElementById('eventModalBar').style.background = color;

        /* Type badge */
        const typeBadge = document.getElementById('eventBadge');
        typeBadge.textContent       = btn.getAttribute('data-event-type') || '';
        typeBadge.style.background  = color;

        /* Visibility badge */
        const vis      = btn.getAttribute('data-event-visibility') || 'private';
        const visBadge = document.getElementById('eventVisibilityBadge');
        visBadge.textContent       = vis.charAt(0).toUpperCase() + vis.slice(1);
        visBadge.style.background  = vis === 'public' ? '#e8f5e9' : '#f0f2f8';
        visBadge.style.color       = vis === 'public' ? '#2e7d32' : '#5a6a85';

        /* Status badge */
        const status      = btn.getAttribute('data-event-status') || '';
        const statusBadge = document.getElementById('eventStatusBadge');
        const sc          = STATUS_COLORS[status] || { bg: '#f0f2f8', color: '#5a6a85' };
        statusBadge.textContent      = status;
        statusBadge.style.background = sc.bg;
        statusBadge.style.color      = sc.color;

        /* Title and time range */
        document.getElementById('eventDetailsModalLabel').textContent = btn.getAttribute('data-event-title') || '';
        document.getElementById('eventTime').textContent = start && end ? `🕒 ${start} → ${end}` : '';

        /* Info grid cells */
        document.getElementById('eventLocation').textContent   = btn.getAttribute('data-event-location')   || '—';
        document.getElementById('eventRecurrence').textContent = btn.getAttribute('data-event-recurrence') || '—';

        /* Duration and countdown (require parseable start/end) */
        if (start && end) {
            const startD    = new Date(start.replace(' ', 'T'));
            const endD      = new Date(end.replace(' ', 'T'));
            const totalMins = Math.round((endD - startD) / 60000);

            document.getElementById('eventDuration').textContent  = formatDuration(totalMins);
            document.getElementById('eventCountdown').textContent = formatCountdown(startD, endD);
        } else {
            document.getElementById('eventDuration').textContent  = '—';
            document.getElementById('eventCountdown').textContent = '—';
        }

        /* Description — hide section if empty */
        const desc     = btn.getAttribute('data-event-description') || '';
        const descWrap = document.getElementById('eventDescriptionWrap');
        if (desc) {
            document.getElementById('eventDescription').textContent = desc;
            descWrap.style.display = 'flex';
        } else {
            descWrap.style.display = 'none';
        }

        /* Action button hrefs */
        document.getElementById('editEventBtn').href   = `/event/${eventId}/edit/`;
        document.getElementById('deleteEventBtn').href = `/event/${eventId}/delete/`;
    });
}