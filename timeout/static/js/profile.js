(() => {
  const cfg = document.getElementById('profile-status-config');
  if (!cfg) return;

  const url = cfg.dataset.updateUrl;
  const csrf = cfg.dataset.csrfToken;

  const navText = document.getElementById('nav-status-text');
  const navDot  = document.getElementById('nav-status-dot');
  const currentText = document.getElementById('current-status-display');

  function setNavDot(status) {
    if (!navDot) return;
    [...navDot.classList].forEach((cls) => {
      if (cls.startsWith('status-') && cls !== 'status-dot-nav') {
        navDot.classList.remove(cls);
      }
    });
    navDot.classList.add(`status-${status}`);
  }

  function setActiveStatusButton(status) {
    document.querySelectorAll('.status-btn').forEach((b) => {
      const isActive = b.dataset.status === status;
      b.classList.toggle('btn-primary', isActive);
      b.classList.toggle('btn-outline-secondary', !isActive);
    });
  }

  document.querySelectorAll('.status-btn').forEach((btn) => {
    btn.addEventListener('click', function () {
      const status = this.dataset.status;
      fetch(url, {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrf,
          'Content-Type': 'application/x-www-form-urlencoded'
        },
        body: `status=${encodeURIComponent(status)}`
      })
        .then((r) => r.json())
        .then((data) => {
          if (!data?.status) return;
          if (currentText) currentText.textContent = data.status_display;
          setActiveStatusButton(data.status);
          if (navText) navText.textContent = data.status_display;
          setNavDot(data.status);
        });
    });
  });
})();

function renderUserList(users) {
  if (users.length === 0) {
    return '<p class="text-center text-muted py-3">No users yet.</p>';
  }
  return users.map(u => `
    <div class="user-item">
      <a href="/social/user/${u.username}/" class="d-flex align-items-center gap-3 mb-3 text-decoration-none text-dark">
        ${u.profile_picture
          ? `<img src="${u.profile_picture}" class="rounded-circle" width="40" height="40" style="object-fit:cover;">`
          : `<div class="rounded-circle bg-secondary text-white d-flex align-items-center justify-content-center fw-bold" style="width:40px;height:40px;">${u.username[0].toUpperCase()}</div>`
        }
        <div>
          <div class="fw-semibold">@${u.username}</div>
          ${u.full_name ? `<div class="text-muted small">${u.full_name}</div>` : ''}
        </div>
      </a>
    </div>
  `).join('');
}

document.getElementById('followersModal').addEventListener('show.bs.modal', () => {
  const input = document.querySelector('[data-modal-search="followers-list"]');
  input.value = '';
  input.oninput = null;

  fetch(FOLLOWERS_URL)
    .then(r => r.json())
    .then(data => {
      document.getElementById('followers-list').innerHTML = renderUserList(data.users);
      input.oninput = function () {
        const query = this.value.toLowerCase().trim();
        document.getElementById('followers-list').querySelectorAll('.user-item').forEach(item => {
          const text = item.textContent.replace(/\s+/g, ' ').toLowerCase();
          item.style.display = text.includes(query) ? '' : 'none';
        });
      };
    });
});

document.getElementById('followingModal').addEventListener('show.bs.modal', () => {
  const input = document.querySelector('[data-modal-search="following-list"]');
  input.value = '';
  input.oninput = null;

  fetch(FOLLOWING_URL)
    .then(r => r.json())
    .then(data => {
      document.getElementById('following-list').innerHTML = renderUserList(data.users);
      input.oninput = function () {
        const query = this.value.toLowerCase().trim();
        document.getElementById('following-list').querySelectorAll('.user-item').forEach(item => {
          const text = item.textContent.replace(/\s+/g, ' ').toLowerCase();
          item.style.display = text.includes(query) ? '' : 'none';
        });
      };
    });
});