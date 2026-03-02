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
