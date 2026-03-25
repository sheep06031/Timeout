// Admin moderation AJAX handlers (staff only)

function getCsrfToken() {
    const match = document.cookie.split(';')
        .map(c => c.trim())
        .find(c => c.startsWith('csrftoken='));
    return match ? decodeURIComponent(match.split('=')[1]) : '';
}

const onProfilePage = () => window.location.pathname.match(/^\/social\/user\/[^/]+\/$/);

function transformButtons(username, toBanned) {
    if (toBanned) {
        document.querySelectorAll(`.btn-ban-user[data-username="${username}"]`).forEach(b => {
            b.classList.replace('btn-ban-user', 'btn-unban-user');
            b.dataset.url = b.dataset.url.replace('/ban/', '/unban/');
            b.textContent = 'Unban';
        });
    } else {
        document.querySelectorAll(`.btn-unban-user[data-username="${username}"]`).forEach(b => {
            b.classList.replace('btn-unban-user', 'btn-ban-user');
            b.dataset.url = b.dataset.url.replace('/unban/', '/ban/');
            b.textContent = 'Ban';
        });
    }
}

document.addEventListener('DOMContentLoaded', function () {
    const csrf = getCsrfToken();

    // Approve flag: delete the flagged post
    document.querySelectorAll('.btn-approve-flag').forEach(btn => {
        btn.addEventListener('click', function () {
            if (!confirm('Delete this post permanently?')) return;
            fetch(this.dataset.url, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrf },
            })
            .then(r => r.json())
            .then(data => { if (data.ok) this.closest('.flag-review-card').remove(); })
            .catch(err => console.error('Approve flag error:', err));
        });
    });

    // Deny flag: dismiss without removing the post
    document.querySelectorAll('.btn-deny-flag').forEach(btn => {
        btn.addEventListener('click', function () {
            fetch(this.dataset.url, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrf },
            })
            .then(r => r.json())
            .then(data => { if (data.ok) this.closest('.flag-review-card').remove(); })
            .catch(err => console.error('Deny flag error:', err));
        });
    });

    // Ban / Unban via event delegation (handles dynamically swapped buttons)
    document.addEventListener('click', function (e) {
        const banBtn = e.target.closest('.btn-ban-user');
        const unbanBtn = e.target.closest('.btn-unban-user');

        if (banBtn) {
            const username = banBtn.dataset.username;
            if (!username || !confirm(`Ban @${username}?`)) return;
            fetch(banBtn.dataset.url, {
                method: 'POST',
                headers: { 'X-CSRFToken': getCsrfToken(), 'X-Requested-With': 'XMLHttpRequest' },
            })
            .then(r => r.json())
            .then(data => {
                if (data.ok) {
                    if (onProfilePage()) window.location.reload();
                    else transformButtons(username, true);
                }
            })
            .catch(err => console.error('Ban error:', err));
        }

        if (unbanBtn) {
            const username = unbanBtn.dataset.username;
            if (!username || !confirm(`Unban @${username}?`)) return;
            fetch(unbanBtn.dataset.url, {
                method: 'POST',
                headers: { 'X-CSRFToken': getCsrfToken(), 'X-Requested-With': 'XMLHttpRequest' },
            })
            .then(r => r.json())
            .then(data => {
                if (data.ok) {
                    if (onProfilePage()) window.location.reload();
                    else transformButtons(username, false);
                }
            })
            .catch(err => console.error('Unban error:', err));
        }
    });

    // Delete message in conversation
    document.querySelectorAll('.btn-delete-msg').forEach(btn => {
        btn.addEventListener('click', function () {
            if (!confirm('Delete this message permanently?')) return;
            fetch(this.dataset.url, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrf },
            })
            .then(r => r.json())
            .then(data => { if (data.ok) this.closest('.msg-bubble-row').remove(); })
            .catch(err => console.error('Delete message error:', err));
        });
    });
});
