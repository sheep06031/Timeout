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

// User search
document.addEventListener('DOMContentLoaded', function() {
    const input = document.getElementById('userSearchInput');
    const results = document.getElementById('userSearchResults');
    if (!input) return;

    // Move results to <body> so it's never clipped by parent overflow/stacking contexts
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

    // Hide results when clicking outside
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

    // Reposition if window scrolls or resizes
    window.addEventListener('scroll', positionDropdown, { passive: true });
    window.addEventListener('resize', positionDropdown, { passive: true });
});

// Like button functionality
document.addEventListener('DOMContentLoaded', function() {
    // Like buttons
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

    // Bookmark buttons
    document.querySelectorAll('.bookmark-btn').forEach(button => {
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

    // Follow buttons
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
});
