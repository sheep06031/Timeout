// CSRF token helper
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(
                    cookie.substring(name.length + 1)
                );
                break;
            }
        }
    }
    return cookieValue;
}

const csrftoken = getCookie('csrftoken');

function initEventDropdown() {
    const nativeSelect = document.getElementById('id_event');
    if (!nativeSelect) return;

    nativeSelect.style.display = 'none';

    const wrapper = document.createElement('div');
    wrapper.className = 'custom-event-select';

    const trigger = document.createElement('div');
    trigger.className = 'custom-event-trigger';
    trigger.textContent = nativeSelect.options[nativeSelect.selectedIndex]?.text || 'No event';

    const dropdown = document.createElement('div');
    dropdown.className = 'custom-event-dropdown';
    document.body.appendChild(dropdown); 

    function positionDropdown() {
        const rect = trigger.getBoundingClientRect();
        dropdown.style.position = 'fixed';
        dropdown.style.top = (rect.bottom + 4) + 'px';
        dropdown.style.left = rect.left + 'px';
        dropdown.style.width = rect.width + 'px';
    }

    Array.from(nativeSelect.options).forEach((opt) => {
        const item = document.createElement('div');
        item.className = 'custom-event-option' + (opt.selected ? ' selected' : '');
        item.textContent = opt.text;
        item.dataset.value = opt.value;

        item.addEventListener('click', () => {
            nativeSelect.value = opt.value;
            trigger.textContent = opt.text;
            dropdown.querySelectorAll('.custom-event-option').forEach(o => o.classList.remove('selected'));
            item.classList.add('selected');
            dropdown.classList.remove('open');
            trigger.classList.remove('open');
        });

        dropdown.appendChild(item);
    });

    trigger.addEventListener('click', (e) => {
        e.stopPropagation();
        const isOpen = dropdown.classList.contains('open');
        if (!isOpen) positionDropdown();
        dropdown.classList.toggle('open', !isOpen);
        trigger.classList.toggle('open', !isOpen);
    });

    document.addEventListener('click', () => {
        dropdown.classList.remove('open');
        trigger.classList.remove('open');
    });

    window.addEventListener('scroll', () => {
        if (dropdown.classList.contains('open')) positionDropdown();
    }, { passive: true });

    wrapper.appendChild(trigger);
    nativeSelect.insertAdjacentElement('afterend', wrapper);
}

document.addEventListener('DOMContentLoaded', function() {
    const input = document.getElementById('userSearchInput');
    const results = document.getElementById('userSearchResults');
    if (!input) return;

    document.body.appendChild(results);

    function positionDropdown() {
        const rect = input.getBoundingClientRect();
        results.style.position = 'fixed';
        results.style.top = (rect.bottom + 4) + 'px';
        results.style.left = rect.left + 'px';
        results.style.width = rect.width + 'px';
        results.style.zIndex = '9999';
    }

    let debounceTimer;

    input.addEventListener('input', function() {
        clearTimeout(debounceTimer);
        const query = this.value.trim();

        if (!query) {
            results.hidden = true;
            results.innerHTML = '';
            return;
        }

        debounceTimer = setTimeout(function() {
            fetch(`/social/search/?q=${encodeURIComponent(query)}`)
                .then(r => r.json())
                .then(data => {
                    results.innerHTML = '';
                    if (!data.users.length) {
                        results.innerHTML = '<div class="search-no-results">No users found</div>';
                    } else {
                        data.users.forEach(u => {
                            const avatar = u.profile_picture
                                ? `<img src="${u.profile_picture}" class="search-avatar" alt="">`
                                : `<div class="search-avatar search-avatar--initial">${u.username[0].toUpperCase()}</div>`;
                            results.innerHTML += `
                                <a href="${u.profile_url}" class="search-result-row">
                                    ${avatar}
                                    <div class="search-result-info">
                                        <span class="search-result-name">${u.full_name}</span>
                                        <span class="search-result-username">@${u.username}</span>
                                    </div>
                                    <span class="status-dot status-${u.status}"></span>
                                </a>`;
                        });
                    }
                    positionDropdown();
                    results.hidden = false;
                })
                .catch(() => { results.hidden = true; });
        }, 300);
    });

    document.addEventListener('click', function(e) {
        if (!input.contains(e.target) && !results.contains(e.target)) {
            results.hidden = true;
        }
    });

    input.addEventListener('focus', function() {
        if (results.innerHTML) {
            positionDropdown();
            results.hidden = false;
        }
    });

    window.addEventListener('scroll', positionDropdown, { passive: true });
    window.addEventListener('resize', positionDropdown, { passive: true });
});

document.addEventListener('DOMContentLoaded', function () {
    const config = window.CONVO_CONFIG;
    if (!config) return;

    const input     = document.getElementById('message-input');
    const sendBtn   = document.getElementById('send-btn');
    const container = document.getElementById('message-container');

    let lastMessageId = 0;

    document.querySelectorAll('[data-message-id]').forEach(el => {
        const id = parseInt(el.dataset.messageId, 10);
        if (id > lastMessageId) lastMessageId = id;
    });

    function scrollToBottom() {
        container.scrollTop = container.scrollHeight;
    }

    function appendMessage(msg) {
        const empty = container.querySelector('.convo-empty');
        if (empty) empty.remove();

        const row = document.createElement('div');
        row.className = `msg-bubble-row ${msg.is_me ? 'msg-mine' : 'msg-theirs'}`;
        row.dataset.messageId = msg.id;
        row.innerHTML = `
            <div class="msg-bubble">
                <div class="msg-text">${msg.content}</div>
                <div class="msg-time">${msg.created_at}</div>
            </div>`;
        container.appendChild(row);
        scrollToBottom();
    }

    function sendMessage() {
        const content = input.value.trim();
        if (!content) return;

        sendBtn.disabled = true;

        fetch(config.sendUrl, {
            method: 'POST',
            headers: { 'X-CSRFToken': config.csrfToken },
            body: new URLSearchParams({ content }),
        })
        .then(r => r.json())
        .then(msg => {
            if (msg.error) { console.error(msg.error); return; }
            appendMessage(msg);
            lastMessageId = msg.id;
            input.value = '';
        })
        .catch(err => console.error('Send error:', err))
        .finally(() => { sendBtn.disabled = false; input.focus(); });
    }

    function pollMessages() {
        fetch(`${config.pollUrl}?last_id=${lastMessageId}`)
            .then(r => r.json())
            .then(data => {
                data.messages.forEach(msg => {
                    appendMessage(msg);
                    lastMessageId = msg.id;
                });
            })
            .catch(err => console.error('Poll error:', err));
    }

    sendBtn.addEventListener('click', sendMessage);
    input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    setInterval(pollMessages, 3000);
    scrollToBottom();
});

document.addEventListener('DOMContentLoaded', function() {

    initEventDropdown();

    document.querySelectorAll('.like-btn').forEach(button => {
        button.addEventListener('click', function() {
            const postId = this.dataset.postId;
            const url = `/social/post/${postId}/like/`;

            fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrftoken,
                    'Content-Type': 'application/json'
                }
            })
            .then(response => response.json())
            .then(data => {
                const icon = this.querySelector('.like-icon');
                const count = this.querySelector('.like-count');
                icon.textContent = data.liked ? '❤️' : '🤍';
                count.textContent = data.like_count;
                this.dataset.liked = data.liked;
            })
            .catch(error => console.error('Error:', error));
        });
    });

    document.querySelectorAll('.bookmark-btn').forEach(button => {
        const icon = button.querySelector('.bookmark-icon');
        if (button.dataset.bookmarked === 'true') {
            icon.textContent = '🔖';
        }

        button.addEventListener('click', function() {
            const postId = this.dataset.postId;
            const url = `/social/post/${postId}/bookmark/`;

            fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrftoken,
                    'Content-Type': 'application/json'
                }
            })
            .then(response => response.json())
            .then(data => {
                const icon = this.querySelector('.bookmark-icon');
                icon.textContent = data.bookmarked ? '🔖' : '🏷️';
                this.dataset.bookmarked = data.bookmarked;
            })
            .catch(error => console.error('Error:', error));
        });
    });

    document.querySelectorAll('.follow-btn').forEach(button => {
        button.addEventListener('click', function() {
            const username = this.dataset.username;
            const url = `/social/user/${username}/follow/`;

            fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrftoken,
                    'Content-Type': 'application/json'
                }
            })
            .then(response => response.json())
            .then(data => {
                this.textContent = data.following ? 'Unfollow' : 'Follow';
                this.dataset.following = data.following;

                if (data.following) {
                    this.classList.remove('btn-primary');
                    this.classList.add('btn-secondary');
                } else {
                    this.classList.remove('btn-secondary');
                    this.classList.add('btn-primary');
                }
            })
            .catch(error => console.error('Error:', error));
        });
    });

    document.querySelectorAll('.btn-subscribe-event').forEach(btn => {
        btn.addEventListener('click', function () {
            const url = this.dataset.url;
            fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrftoken,
                    'Content-Type': 'application/json',
                },
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    btn.textContent = '✓ Added';
                    btn.disabled = true;
                    btn.style.background = '#198754';
                } else {
                    btn.textContent = data.error || 'Error';
                    btn.disabled = true;
                }
            })
            .catch(err => console.error('Subscribe error:', err));
        });
    });

});