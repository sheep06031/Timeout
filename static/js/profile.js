/**
 * User Profile Management
 * Handles status updates, user list rendering, following/unfollowing, and modal search functionality.
 */

const _cfg = document.getElementById('profile-status-config');
const FOLLOWERS_URL = _cfg?.dataset.followersUrl ?? '';
const FOLLOWING_URL = _cfg?.dataset.followingUrl ?? '';
const FRIENDS_URL   = _cfg?.dataset.friendsUrl   ?? '';

/**
 * Initialize status management with UI updates and event listeners.
 */
(() => {
  const cfg = document.getElementById('profile-status-config');
  if (!cfg) return;

  const url = cfg.dataset.updateUrl;
  const csrf = cfg.dataset.csrfToken;

  const navText = document.getElementById('nav-status-text');
  const navDot  = document.getElementById('nav-status-dot');
  const currentText = document.getElementById('current-status-display');

  /**
   * Update navigation status indicator dot with appropriate color class.
   */
  function setNavDot(status) {
    if (!navDot) return;
    [...navDot.classList].forEach((cls) => {
      if (cls.startsWith('status-')) {
        navDot.classList.remove(cls);
      }
    });
    navDot.classList.add(`status-${status}`);
  }

  /**
   * Highlight the currently active status button and deactivate others.
   */
  function setActiveStatusButton(status) {
    document.querySelectorAll('.status-btn').forEach((b) => {
      const val = b.dataset.status;
      const isActive = val === status;
      b.classList.remove('status-badge-focus', 'status-badge-social', 'status-badge-inactive', 'status-btn-idle');
      b.classList.add(isActive ? `status-badge-${val}` : 'status-btn-idle');
    });
  }

  /**
   * Update focus mode timer display based on status change.
   */
  function _updateFocusTimers(data) {
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
  }

  /**
   * Apply status update to all UI elements and dispatch focus mode event.
   */
  function _applyStatusUpdate(data) {
    if (!data?.status) return;
    if (currentText) currentText.textContent = data.status_display;
    setActiveStatusButton(data.status);
    if (navText) navText.textContent = data.status_display;
    setNavDot(data.status);
    document.body.dataset.userStatus = data.status;
    if (data.status != 'focus') {
      window.dispatchEvent(new CustomEvent('focusModeEnded'));
    }
    _updateFocusTimers(data);
  }

  document.querySelectorAll('.status-btn').forEach((btn) => {
    btn.addEventListener('click', function () {
      const status = this.dataset.status;
      fetch(url, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrf, 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `status=${encodeURIComponent(status)}`
      })
        .then((r) => r.json())
        .then(_applyStatusUpdate);
    });
  });
})();

/**
 * Generate HTML for user avatar image or initial badge.
 */
function _userAvatarHtml(u) {
  return u.profile_picture
    ? `<img src="${u.profile_picture}" class="rounded-circle" width="40" height="40" style="object-fit:cover;">`
    : `<div class="rounded-circle bg-secondary text-white d-flex align-items-center justify-content-center fw-bold" style="width:40px;height:40px;">${u.username[0].toUpperCase()}</div>`;
}

/**
 * Generate action button HTML for user item (follow, unfollow, or follow back).
 */
function _userActionBtn(u, options) {
  if (options.showUnfollow) {
    return `<button class="btn btn-sm btn-outline-danger unfollow-btn ms-2" data-username="${u.username}">Unfollow</button>`;
  }
  if (options.showFollowBack) {
    return u.is_followed_back
      ? `<span class="btn btn-sm btn-outline-secondary ms-2 disabled" aria-disabled="true">Following</span>`
      : `<button class="btn btn-sm btn-outline-primary follow-back-btn ms-2" data-username="${u.username}">Follow Back</button>`;
  }
  return '';
}

/**
 * Generate complete user list item HTML with avatar, name, and action button.
 */
function _userItemHtml(u, options) {
  return `
    <div class="user-item d-flex align-items-center justify-content-between mb-3">
      <a href="/social/user/${u.username}/" class="d-flex align-items-center gap-3 text-decoration-none text-dark">
        ${_userAvatarHtml(u)}
        <div>
          <div class="fw-semibold">@${u.username}</div>
          ${u.full_name ? `<div class="text-muted small">${u.full_name}</div>` : ''}
        </div>
      </a>
      ${_userActionBtn(u, options)}
    </div>`;
}

/**
 * Render complete user list HTML with optional action buttons based on context.
 */
function renderUserList(users, options = {}) {
  if (users.length === 0) return '<p class="text-center text-muted py-3">No users yet.</p>';
  return users.map(u => _userItemHtml(u, options)).join('');
}

/**
 * Update the following count badge with a delta (positive or negative).
 */
function _updateBadgeCount(delta) {
  const badge = document.getElementById('following-count-badge');
  if (badge) {
    const current = parseInt(badge.textContent, 10);
    if (!isNaN(current)) badge.textContent = `${Math.max(0, current + delta)} Following`;
  }
}

/**
 * Handle unfollow action result and update UI accordingly.
 */
function _handleUnfollowResult(data, btn) {
  if (data.following === false) {
    btn.closest('.user-item').remove();
    _updateBadgeCount(-1);
    const list = document.getElementById('following-list');
    if (list && !list.querySelector('.user-item')) {
      list.innerHTML = '<p class="text-center text-muted py-3">No users yet.</p>';
    }
  } else {
    btn.disabled = false;
    btn.textContent = 'Unfollow';
  }
}

/**
 * Attach click handlers to unfollow buttons and manage follow state updates.
 */
function attachUnfollowHandlers(container) {
  container.querySelectorAll('.unfollow-btn').forEach(btn => {
    btn.addEventListener('click', function () {
      const username = this.dataset.username;
      this.disabled = true;
      this.textContent = 'Unfollowing…';

      fetch(`/social/user/${username}/follow/`, {
        method: 'POST',
        headers: { 'X-CSRFToken': getCookie('csrftoken'), 'Content-Type': 'application/json' },
      })
        .then(r => r.json())
        .then(data => _handleUnfollowResult(data, this))
        .catch(err => {
          console.error('Unfollow error:', err);
          this.disabled = false;
          this.textContent = 'Unfollow';
        });
    });
  });
}

/**
 * Attach follow toggle handlers to follow back buttons in a container.
 */
function attachFollowBackHandlers(container) {
  container.querySelectorAll('.follow-back-btn').forEach(btn => {
    attachFollowToggle(btn);
  });
}

/**
 * Handle follow/unfollow action result and update button state.
 */
function _handleFollowToggleResult(data, btn) {
  if (data.following === true) {
    const label = document.createElement('span');
    label.className = 'btn btn-sm btn-outline-secondary ms-2 disabled';
    label.setAttribute('aria-disabled', 'true');
    label.textContent = 'Following';
    btn.replaceWith(label);
    _updateBadgeCount(1);
  } else if (data.requested === true) {
    btn.className = 'btn btn-sm btn-warning cancel-request-btn ms-2';
    btn.textContent = 'Requested';
    btn.disabled = false;
  } else {
    btn.className = 'btn btn-sm btn-outline-primary follow-back-btn ms-2';
    btn.textContent = 'Follow Back';
    btn.disabled = false;
  }
}

/**
 * Attach follow/unfollow toggle handler to a button with AJAX submission.
 */
function attachFollowToggle(btn) {
  btn.onclick = function () {
    const username = this.dataset.username;
    const cancelling = this.classList.contains('cancel-request-btn');
    this.disabled = true;
    this.textContent = cancelling ? 'Cancelling…' : 'Following…';

    fetch(`/social/user/${username}/follow/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': getCookie('csrftoken'), 'Content-Type': 'application/json' },
    })
      .then(r => r.json())
      .then(data => _handleFollowToggleResult(data, this))
      .catch(() => {
        this.disabled = false;
        this.textContent = cancelling ? 'Requested' : 'Follow Back';
      });
  };
}

/**
 * Initialize search filtering for user list within a modal.
 */
function _initModalSearch(input, listEl) {
  input.oninput = function () {
    const query = this.value.toLowerCase().trim();
    listEl.querySelectorAll('.user-item').forEach(item => {
      const text = item.textContent.replace(/\s+/g, ' ').toLowerCase();
      item.style.display = text.includes(query) ? '' : 'none';
    });
  };
}

document.getElementById('followersModal')?.addEventListener('show.bs.modal', () => {
  const input = document.querySelector('[data-modal-search="followers-list"]');
  input.value = '';
  input.oninput = null;
  fetch(FOLLOWERS_URL)
    .then(r => r.json())
    .then(data => {
      const list = document.getElementById('followers-list');
      list.innerHTML = renderUserList(data.users, { showFollowBack: true });
      attachFollowBackHandlers(list);
      _initModalSearch(input, list);
    });
});

document.getElementById('followingModal')?.addEventListener('show.bs.modal', () => {
  const input = document.querySelector('[data-modal-search="following-list"]');
  input.value = '';
  input.oninput = null;
  fetch(FOLLOWING_URL)
    .then(r => r.json())
    .then(data => {
      const list = document.getElementById('following-list');
      list.innerHTML = renderUserList(data.users, { showUnfollow: true });
      attachUnfollowHandlers(list);
      _initModalSearch(input, list);
    });
});

document.getElementById('friendsModal')?.addEventListener('show.bs.modal', () => {
  const input = document.querySelector('[data-modal-search="friends-list"]');
  input.value = '';
  input.oninput = null;
  fetch(FRIENDS_URL)
    .then(r => r.json())
    .then(data => {
      const list = document.getElementById('friends-list');
      list.innerHTML = renderUserList(data.users);
      _initModalSearch(input, list);
    });
});
