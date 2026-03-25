/**
 * Follow Request Management
 * Handles accepting and rejecting incoming follow requests with AJAX submission.
 */

/**
 * Initialize follow request action handlers for accept and reject buttons.
 */
document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.accept-request-btn, .reject-request-btn').forEach(btn => {
        btn.addEventListener('click', function () {
            const username = this.dataset.username;
            const action   = this.classList.contains('accept-request-btn') ? 'accept' : 'reject';

            fetch(`/social/user/${username}/follow/${action}/`, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrftoken, 'Content-Type': 'application/json' }
            })
            .then(r => r.json())
            .then(() => this.closest('.follow-request-row').remove())
            .catch(err => console.error('Follow request error:', err));
        });
    });
});
