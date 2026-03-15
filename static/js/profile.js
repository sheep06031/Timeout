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
      if (cls.startsWith('status-')) {
        navDot.classList.remove(cls);
      }
    });
    navDot.classList.add(`status-${status}`);
  }

  function setActiveStatusButton(status) {
    document.querySelectorAll('.status-btn').forEach((b) => {
      const val = b.dataset.status;
      const isActive = val === status;
      b.classList.remove('status-badge-focus', 'status-badge-social', 'status-badge-inactive', 'status-btn-idle');
      b.classList.add(isActive ? `status-badge-${val}` : 'status-btn-idle');
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
          document.body.dataset.userStatus = data.status;
          if (data.status != 'focus') {
            window.dispatchEvent(new CustomEvent('focusModeEnded'));
          }

          const navTimer = document.getElementById('nav-focus-timer');
          const profileTimer = document.getElementById('profile-focus-timer');
          if (data.status === 'focus' && data.focus_started_at) {
            [navTimer, profileTimer].forEach(el => {
              if (!el) return;
              el.dataset.focusStartedAt = data.focus_started_at;
              el.style.display = '';
            });
          } else {
            [navTimer, profileTimer].forEach(el => {
              if (!el) return;
              el.style.display = 'none';
              delete el.dataset.focusStartedAt;
            });
          }
        });
    });
  });
})();


function renderUserList(users) {
  if (users.length === 0) return '<p class="text-center text-muted py-3">No users yet.</p>';
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

document.getElementById('followersModal')?.addEventListener('show.bs.modal', () => {
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

document.getElementById('followingModal')?.addEventListener('show.bs.modal', () => {
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

document.getElementById('friendsModal')?.addEventListener('show.bs.modal', () => {
  const input = document.querySelector('[data-modal-search="friends-list"]');
  input.value = '';
  input.oninput = null;

  fetch(FRIENDS_URL)
    .then(r => r.json())
    .then(data => {
      document.getElementById('friends-list').innerHTML = renderUserList(data.users);
      input.oninput = function () {
        const query = this.value.toLowerCase().trim();
        document.getElementById('friends-list').querySelectorAll('.user-item').forEach(item => {
          const text = item.textContent.replace(/\s+/g, ' ').toLowerCase();
          item.style.display = text.includes(query) ? '' : 'none';
        });
      };
    });
});