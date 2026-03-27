/**
 * Social Feed Interactions
 * Handles user search, feed interactions (likes, bookmarks, follows), event dropdowns, and modal management.
 * Messaging and load-more functionality moved to social_messaging.js.
 */

/**
 * Retrieve CSRF token from browser cookies for secure form submissions.
 */
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

/**
 * Populate custom dropdown menu with options from native select element.
 */
function _createDropdownOptions(nativeSelect, dropdown, trigger) {
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
}

/**
 * Attach click and scroll listeners to toggle custom dropdown visibility.
 */
function _attachDropdownListeners(trigger, dropdown) {
    trigger.addEventListener('click', (e) => {
        e.stopPropagation();
        const isOpen = dropdown.classList.contains('open');
        if (!isOpen) _positionEventDropdown(trigger, dropdown);
        dropdown.classList.toggle('open', !isOpen);
        trigger.classList.toggle('open', !isOpen);
    });

    document.addEventListener('click', () => {
        dropdown.classList.remove('open');
        trigger.classList.remove('open');
    });

    window.addEventListener('scroll', () => {
        if (dropdown.classList.contains('open')) _positionEventDropdown(trigger, dropdown);
    }, { passive: true });
}

/**
 * Position custom dropdown below trigger element with matching width.
 */
function _positionEventDropdown(trigger, dropdown) {
    const rect = trigger.getBoundingClientRect();
    dropdown.style.position = 'fixed';
    dropdown.style.top = (rect.bottom + 4) + 'px';
    dropdown.style.left = rect.left + 'px';
    dropdown.style.width = rect.width + 'px';
}

/**
 * Initialize custom event type dropdown replacing native select element.
 */
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

    _createDropdownOptions(nativeSelect, dropdown, trigger);
    _attachDropdownListeners(trigger, dropdown);

    wrapper.appendChild(trigger);
    nativeSelect.insertAdjacentElement('afterend', wrapper);
}

/**
 * Update follow button appearance and text based on follow state.
 */
function applyFollowState(btn, following, requested) {
    btn.classList.remove('btn-primary', 'btn-secondary', 'btn-warning');
    if (following) {
        btn.textContent = 'Unfollow';
        btn.classList.add('btn-secondary');
    } else if (requested) {
        btn.textContent = 'Requested';
        btn.classList.add('btn-warning');
    } else {
        btn.textContent = 'Follow';
        btn.classList.add('btn-primary');
    }
    btn.dataset.following = following;
    btn.dataset.requested = requested;
}

/**
 * Position search results dropdown below input field with matching width.
 */
function _positionSearchDropdown(input, results) {
    const rect = input.getBoundingClientRect();
    results.style.position = 'fixed';
    results.style.top = (rect.bottom + 4) + 'px';
    results.style.left = rect.left + 'px';
    results.style.width = rect.width + 'px';
    results.style.zIndex = '9999';
}

/**
 * Generate HTML for a single user search result row with avatar and info.
 */
function _renderSearchResult(u) {
    const avatar = u.profile_picture
        ? `<img src="${u.profile_picture}" class="search-avatar" alt="">`
        : `<div class="search-avatar search-avatar--initial">${u.username[0].toUpperCase()}</div>`;
    return `<a href="${u.profile_url}" class="search-result-row">
        ${avatar}
        <div class="search-result-info">
            <span class="search-result-name">${u.full_name}</span>
            <span class="search-result-username">@${u.username}</span>
        </div>
        <span class="status-dot status-${u.status}"></span>
    </a>`;
}

/**
 * Render all search results or empty state and position dropdown.
 */
function _handleSearchResults(data, results, input) {
    results.innerHTML = '';
    if (!data.users.length) {
        results.innerHTML = '<div class="search-no-results">No users found</div>';
    } else {
        data.users.forEach(u => { results.innerHTML += _renderSearchResult(u); });
    }
    _positionSearchDropdown(input, results);
    results.hidden = false;
}

/**
 * Initialize user search with debounced API calls and click-outside dismissal.
 */
function initUserSearch() {
    const input = document.getElementById('userSearchInput');
    const results = document.getElementById('userSearchResults');
    if (!input) return;

    document.body.appendChild(results);
    let debounceTimer;

    input.addEventListener('input', function() {
        clearTimeout(debounceTimer);
        const query = this.value.trim();
        if (!query) { results.hidden = true; results.innerHTML = ''; return; }

        debounceTimer = setTimeout(function() {
            fetch(`/social/search/?q=${encodeURIComponent(query)}`)
                .then(r => r.json())
                .then(data => _handleSearchResults(data, results, input))
                .catch(() => { results.hidden = true; });
        }, 300);
    });

    document.addEventListener('click', function(e) {
        if (!input.contains(e.target) && !results.contains(e.target)) results.hidden = true;
    });

    input.addEventListener('focus', function() {
        if (results.innerHTML) { _positionSearchDropdown(input, results); results.hidden = false; }
    });

    window.addEventListener('scroll', () => _positionSearchDropdown(input, results), { passive: true });
    window.addEventListener('resize', () => _positionSearchDropdown(input, results), { passive: true });
}



/**
 * Initialize like button handlers with API calls and UI updates.
 */
function initLikeButtons() {
    document.querySelectorAll('.like-btn').forEach(button => {
        button.addEventListener('click', function() {
            const postId = this.dataset.postId;
            fetch(`/social/post/${postId}/like/`, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrftoken, 'Content-Type': 'application/json' }
            })
            .then(response => response.json())
            .then(data => {
                const icon = this.querySelector('.like-icon');
                const count = this.querySelector('.like-count');
                icon.className = data.liked ? 'bi bi-heart-fill like-icon' : 'bi bi-heart like-icon';
                this.classList.toggle('liked', data.liked);
                count.textContent = data.like_count;
                this.dataset.liked = data.liked;
            })
            .catch(error => console.error('Error:', error));
        });
    });
}

/**
 * Apply bookmarked visual state to button if previously bookmarked.
 */
function _initBookmarkState(button) {
    const icon = button.querySelector('.bookmark-icon');
    if (button.dataset.bookmarked === 'true') {
        icon.className = 'bi bi-bookmark-fill bookmark-icon';
        button.classList.add('bookmarked');
    }
}

/**
 * Initialize bookmark button handlers with API calls and state management.
 */
function initBookmarkButtons() {
    document.querySelectorAll('.bookmark-btn').forEach(button => {
        _initBookmarkState(button);
        button.addEventListener('click', function() {
            const postId = this.dataset.postId;
            fetch(`/social/post/${postId}/bookmark/`, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrftoken, 'Content-Type': 'application/json' }
            })
            .then(response => response.json())
            .then(data => {
                const icon = this.querySelector('.bookmark-icon');
                icon.className = data.bookmarked ? 'bi bi-bookmark-fill bookmark-icon' : 'bi bi-bookmark bookmark-icon';
                this.classList.toggle('bookmarked', data.bookmarked);
                this.dataset.bookmarked = data.bookmarked;
            })
            .catch(error => console.error('Error:', error));
        });
    });
}

/**
 * Initialize flag button handlers.
 */
function initFlagButtons() {
    document.querySelectorAll('.btn-flag-post').forEach(button => {
        button.addEventListener('click', function () {
            const postId = this.dataset.postId;
            const icon = this.querySelector('i');
            const alreadyFlagged = icon.className.includes('flag-fill');
            icon.className = alreadyFlagged ? 'bi bi-flag' : 'bi bi-flag-fill';
            fetch(`/social/post/${postId}/flag/`, {
                method: 'POST',
                headers: { 'X-CSRFToken': getCookie('csrftoken') },
            })
            .then(r => r.json())
            .catch(() => {
                icon.className = alreadyFlagged ? 'bi bi-flag-fill' : 'bi bi-flag';
            });
        });
    });
}

/**
 * Initialize follow button handlers with follow/unfollow toggle functionality.
 */
function initFollowButtons() {
    document.querySelectorAll('.follow-btn').forEach(button => {
        button.addEventListener('click', function() {
            const username = this.dataset.username;
            fetch(`/social/user/${username}/follow/`, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrftoken, 'Content-Type': 'application/json' }
            })
            .then(r => r.json())
            .then(data => applyFollowState(this, data.following, data.requested))
            .catch(error => console.error('Error:', error));
        });
    });
}

/**
 * Initialize event subscription button handlers with success feedback.
 */
function initSubscribeButtons() {
    document.querySelectorAll('.btn-subscribe-event').forEach(btn => {
        btn.addEventListener('click', function () {
            const url = this.dataset.url;
            fetch(url, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrftoken, 'Content-Type': 'application/json' },
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
}

/**
 * Scroll to and highlight a post based on URL parameter.
 */
function initHighlightPost() {
    const params = new URLSearchParams(window.location.search);
    const highlightId = params.get("highlight_post");
    if (!highlightId) return;
    const postEl = document.querySelector(`.post-card[data-post-id="${highlightId}"]`);
    if (postEl) {
        postEl.scrollIntoView({ behavior: "smooth", block: "center" });
        postEl.style.transition = "box-shadow 0.4s ease";
        postEl.style.boxShadow = "0 0 0 3px #5b73e8";
        setTimeout(() => postEl.style.boxShadow = "", 2500);
    }
}

/**
 * Initialize FAB (floating action button) modal with open/close handlers.
 */
function initFabModal() {
    const fab     = document.getElementById("fabBtn");
    const overlay = document.getElementById("cpOverlay");
    const cpClose = document.getElementById("cpClose");
    if (!fab || !overlay || !cpClose) return;
    fab.addEventListener("click", () => overlay.classList.add("open"));
    cpClose.addEventListener("click", () => overlay.classList.remove("open"));
    overlay.addEventListener("click", (e) => {
        if (e.target === overlay) overlay.classList.remove("open");
    });
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") overlay.classList.remove("open");
    });
}

// Init

document.addEventListener('DOMContentLoaded', function() {
    initUserSearch();
    initEventDropdown();
    initLikeButtons();
    initBookmarkButtons();
    initFlagButtons();
    initFollowButtons();
    initSubscribeButtons();
    initHighlightPost();
    initFabModal();
});
