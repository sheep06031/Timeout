/**
 * Study Session Planner
 * AI-powered study session planning tool that generates and schedules study sessions based on deadline and duration.
 */

let plannedSessions = [];

/**
 * Request AI-generated study session plan from server based on user inputs.
 */
async function fetchPlan() {
  const body = new FormData();
  body.append('event_id', document.getElementById('spDeadline').value);
  body.append('hours_needed', document.getElementById('spHours').value);
  body.append('session_length', document.getElementById('spSessionLen').value);
  const res = await fetch(window.SP_PLAN_URL, { method: 'POST', headers: { 'X-CSRFToken': getCSRFToken() }, body });
  return res.json();
}

/**
 * Submit study plan request and display preview if successful.
 */
async function submitPlan() {
  const btn = document.getElementById('spPlanBtn');
  const errorBox = document.getElementById('spError');
  btn.disabled = true;
  errorBox.classList.add('d-none');

  try {
    const data = await fetchPlan();
    if (data.success) {
      plannedSessions = data.sessions;
      showPreview(data.sessions);
      showStep2();
    } else {
      errorBox.textContent = data.error;
      errorBox.classList.remove('d-none');
    }
  } catch {
    errorBox.textContent = 'Network error. Please try again.';
    errorBox.classList.remove('d-none');
  } finally {
    btn.disabled = false;
  }
}

/**
 * Display preview of planned study sessions with dates and times.
 */
function showPreview(sessions) {
  document.getElementById('spPreview').innerHTML = sessions.map(s => {
    const start = new Date(s.start);
    const end = new Date(s.end);
    const day = start.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' });
    const time = start.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
      + ' – ' + end.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
    return `<div class="d-flex justify-content-between py-2 border-bottom small">
      <span class="fw-semibold">${s.title}</span>
      <span class="text-muted">${day} · ${time}</span>
    </div>`;
  }).join('');
  document.getElementById('confirmBtn').onclick = () => saveSessions(sessions);
}

/**
 * Save confirmed study sessions to calendar and reload page.
 */
async function saveSessions(sessions) {
  const btn = document.getElementById('confirmBtn');
  btn.disabled = true;

  const body = new FormData();
  body.append('sessions', JSON.stringify(sessions));

  try {
    const res = await fetch(window.SP_CONFIRM_URL, { method: 'POST', headers: { 'X-CSRFToken': getCSRFToken() }, body });
    const data = await res.json();
    if (data.success) setTimeout(() => location.reload(), 500);
  } catch {
    btn.disabled = false;
  }
}

/**
 * Display preview/confirmation step with session details and confirm button.
 */
function showStep2() {
  document.getElementById('sp-step-1').classList.add('d-none');
  document.getElementById('sp-step-2').classList.remove('d-none');
  document.getElementById('spPlanBtn').classList.add('d-none');
  document.getElementById('backBtn').classList.remove('d-none');
  document.getElementById('confirmBtn').classList.remove('d-none');
}

/**
 * Display planning input step with deadline, hours, and session length fields.
 */
function showStep1() {
  document.getElementById('sp-step-1').classList.remove('d-none');
  document.getElementById('sp-step-2').classList.add('d-none');
  document.getElementById('spPlanBtn').classList.remove('d-none');
  document.getElementById('backBtn').classList.add('d-none');
  document.getElementById('confirmBtn').classList.add('d-none');
}
