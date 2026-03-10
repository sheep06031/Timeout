async function submitAiEvent() {
  const input = document.getElementById('aiUserInput').value.trim();
  if (!input) return;

  const btn = document.getElementById('aiSubmitBtn');
  const spinner = document.getElementById('aiSpinner');
  const successEl = document.getElementById('aiSuccess');
  const errorEl = document.getElementById('aiError');
  const resultEl = document.getElementById('aiResult');

  btn.disabled = true;
  spinner.classList.remove('d-none');
  successEl.classList.add('d-none');
  errorEl.classList.add('d-none');
  resultEl.classList.remove('d-none');

  try {
    const formData = new FormData();
    formData.append('user_input', input);
    formData.append('csrfmiddlewaretoken', window.AI_CSRF_TOKEN);

    const res = await fetch(window.AI_ADD_URL, {
      method: 'POST',
      body: formData,
    });
    const data = await res.json();

    if (data.success) {
      successEl.textContent = `"${data.event.title}" added (${data.event.start} – ${data.event.end})`;
      successEl.classList.remove('d-none');
      document.getElementById('aiUserInput').value = '';
      setTimeout(() => location.reload(), 1500);
    } else {
      errorEl.textContent = data.error || 'Failed to create event.';
      errorEl.classList.remove('d-none');
    }
  } catch (err) {
    errorEl.textContent = 'Network error. Please try again.';
    errorEl.classList.remove('d-none');
  } finally {
    btn.disabled = false;
    spinner.classList.add('d-none');
  }
}
