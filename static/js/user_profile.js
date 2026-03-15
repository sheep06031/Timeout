(function () {
  if (typeof FOLLOWERS_URL === 'undefined' || typeof FOLLOWING_URL === 'undefined') return;

  function escapeHtml(str) {
    if (str == null) return '';
    return String(str)
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#39;');
  }

  function renderUserList(users) {
    if (!users || users.length === 0) {
      return '<p class="text-center text-muted py-3">No users yet.</p>';
    }

    return users.map(function (u) {
      const username = u && u.username ? String(u.username) : '';
      const fullName = u && u.full_name ? String(u.full_name) : '';
      const pic = u && u.profile_picture ? String(u.profile_picture) : '';

      const href = '/social/user/' + encodeURIComponent(username) + '/';

      const avatarHtml = pic
        ? '<img src="' + escapeHtml(pic) + '" class="rounded-circle" width="40" height="40" style="object-fit:cover;">'
        : '<div class="rounded-circle bg-secondary text-white d-flex align-items-center justify-content-center fw-bold" style="width:40px;height:40px;">' +
            escapeHtml(username.charAt(0).toUpperCase() || '?') +
          '</div>';

      const fullNameHtml = fullName
        ? '<div class="text-muted small">' + escapeHtml(fullName) + '</div>'
        : '';

      return (
        '<div class="user-item">' +
          '<a href="' + href + '" class="d-flex align-items-center gap-3 mb-3 text-decoration-none text-dark">' +
            avatarHtml +
            '<div>' +
              '<div class="fw-semibold">@' + escapeHtml(username) + '</div>' +
              fullNameHtml +
            '</div>' +
          '</a>' +
        '</div>'
      );
    }).join('');
  }

  function setupModal(modalId, url, listId, searchAttr) {
    const modalEl = document.getElementById(modalId);
    if (!modalEl) return;

    modalEl.addEventListener('show.bs.modal', function () {
      const input = document.querySelector('[data-modal-search="' + searchAttr + '"]');
      if (input) {
        input.value = '';
        input.oninput = null;
      }

      fetch(url)
        .then(function (r) { return r.json(); })
        .then(function (data) {
          const listEl = document.getElementById(listId);
          if (!listEl) return;

          listEl.innerHTML = renderUserList((data && data.users) ? data.users : []);

          if (input) {
            input.oninput = function () {
              const query = (this.value || '').toLowerCase().trim();
              listEl.querySelectorAll('.user-item').forEach(function (item) {
                const text = item.textContent.replace(/\s+/g, ' ').toLowerCase();
                item.style.display = text.includes(query) ? '' : 'none';
              });
            };
          }
        });
    });
  }

  setupModal('followersModal', FOLLOWERS_URL, 'followers-list', 'followers-list');
  setupModal('followingModal', FOLLOWING_URL, 'following-list', 'following-list');
  setupModal('friendsModal', FRIENDS_URL, 'friends-list', 'friends-list');
})();