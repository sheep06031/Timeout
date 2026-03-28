/**
 * Notification Polling System
 * Fetches unread notification count from server and updates navigation badge.
 * Polls immediately on load, when focus mode ends, and every 10 seconds.
 * Skips full polling when user is in focus mode (fire-and-forget only).
 * Reads poll URL from data-poll-url attribute on its own script tag.
 */
document.addEventListener('DOMContentLoaded', () => {
  const scriptTag = document.querySelector('script[data-poll-url]');
  if (!scriptTag) return;
  const pollUrl = scriptTag.dataset.pollUrl;
  const badge = document.querySelector('.nav-link .badge');

  /**
   * Fetch unread notification count from server and update badge display.
   */
  async function updateNotifications() {
    try {
      const response = await fetch(pollUrl);
      if (!response.ok) return;

      const data = await response.json();
      if (data.unread_count > 0) {
        if (badge) {
          badge.textContent = data.unread_count;
          badge.style.display = 'inline-block';
        }
      } else if (badge) {
        badge.style.display = 'none';
      }
    } catch (err) {
      console.error('Notification polling error:', err);
    }
  }

  /* Poll notifications immediately on page load and every 10 seconds */
  updateNotifications();
  setInterval(updateNotifications, 10000);
});