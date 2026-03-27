/**
 * Study Session Rescheduling
 * Fetches AI-powered rescheduling suggestions, displays preview, and applies changes to user's calendar.
 */

let rsSuggestions = [];

/**
 * Fetch rescheduling suggestions from the server and display preview.
 */
function fetchRescheduleSuggestions() {
    rsShowLoading();

    fetch(window.RS_SUGGEST_URL, {
        method: 'POST',
        headers: { 'X-CSRFToken': window.AI_CSRF_TOKEN },
    })
    .then(r => r.json())
    .then(data => {
        if (!data.success) {
            rsShowError(data.error || 'Something went wrong.');
            rsShowStep1();
            return;
        }
        rsSuggestions = data.suggestions;
        rsRenderPreview(data.original, data.suggestions);
        rsShowStep2();
    })
    .catch(() => {
        rsShowError('Could not reach the server. Try again.');
        rsShowStep1();
    });
}

/**
 * Render rescheduling suggestions in preview table with original and new times.
 */
function rsRenderPreview(original, suggestions) {
    const tbody = document.getElementById('rs-preview-body');
    tbody.innerHTML = '';

    const originalMap = {};
    original.forEach(s => { originalMap[s.id] = s; });

    suggestions.forEach(s => {
        const old = originalMap[s.id];
        const oldTime = old ? fmtDatetime(old.start) + ' → ' + fmtTime(old.end) : '—';
        const newTime = fmtDatetime(s.start) + ' → ' + fmtTime(s.end);
        const changed = old && (old.start !== s.start);

        tbody.innerHTML += `
            <tr class="${changed ? 'table-warning' : ''}">
                <td>${s.title}</td>
                <td class="text-muted">${oldTime}</td>
                <td><strong>${newTime}</strong></td>
            </tr>`;
    });
}

/**
 * Apply accepted rescheduling suggestions to user's calendar and reload page.
 */
function applyReschedule() {
    const btn = document.getElementById('rs-apply-btn');
    btn.disabled = true;
    btn.textContent = 'Applying…';
    const formData = new FormData();
    formData.append('sessions', JSON.stringify(rsSuggestions));
    formData.append('csrfmiddlewaretoken', window.AI_CSRF_TOKEN);
    fetch(window.RS_APPLY_URL, {
        method: 'POST',
        headers: { 'X-CSRFToken': window.AI_CSRF_TOKEN },
        body: formData,})
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            bootstrap.Modal.getInstance(document.getElementById('rescheduleSessionsModal')).hide();
            window.location.reload();
        } else {
            rsShowError(data.error || 'Could not apply changes.');
            btn.disabled = false;
            btn.textContent = 'Apply Changes';
        }}) .catch(() => {
        rsShowError('Could not reach the server.');
        btn.disabled = false;
        btn.textContent = 'Apply Changes';});
}

/**
 * Display initial step with suggestion request button.
 */
function rsShowStep1() {
    document.getElementById('rs-step-1').classList.remove('d-none');
    document.getElementById('rs-step-2').classList.add('d-none');
    document.getElementById('rs-loading').classList.add('d-none');
    document.getElementById('rs-suggest-btn').classList.remove('d-none');
    document.getElementById('rs-back-btn').classList.add('d-none');
    document.getElementById('rs-apply-btn').classList.add('d-none');
    document.getElementById('rs-error').classList.add('d-none');
}

/**
 * Display preview step with suggested changes and apply/back buttons.
 */
function rsShowStep2() {
    document.getElementById('rs-step-1').classList.add('d-none');
    document.getElementById('rs-step-2').classList.remove('d-none');
    document.getElementById('rs-loading').classList.add('d-none');
    document.getElementById('rs-suggest-btn').classList.add('d-none');
    document.getElementById('rs-back-btn').classList.remove('d-none');
    document.getElementById('rs-apply-btn').classList.remove('d-none');
}

/**
 * Display loading spinner while fetching suggestions from server.
 */
function rsShowLoading() {
    document.getElementById('rs-step-1').classList.add('d-none');
    document.getElementById('rs-step-2').classList.add('d-none');
    document.getElementById('rs-loading').classList.remove('d-none');
    document.getElementById('rs-suggest-btn').classList.add('d-none');
    document.getElementById('rs-error').classList.add('d-none');
}

/**
 * Display error message to the user.
 */
function rsShowError(msg) {
    const el = document.getElementById('rs-error');
    el.textContent = msg;
    el.classList.remove('d-none');
}

/**
 * Format ISO datetime string to readable date and time (e.g., "Mon, 25 Mar 14:30").
 */
function fmtDatetime(str) {
    if (!str) return '—';
    const d = new Date(str);
    return d.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })
        + ' ' + fmtTime(str);
}

/**
 * Extract time portion from ISO datetime string (e.g., "14:30").
 */
function fmtTime(str) {
    if (!str) return '—';
    return str.slice(11, 16);
}

/**
 * Initialize modal event handler to reset UI when modal closes.
 */
document.addEventListener('DOMContentLoaded', function () {
    const modal = document.getElementById('rescheduleSessionsModal');
    if (modal) {
        modal.addEventListener('hidden.bs.modal', rsShowStep1);
    }
});
