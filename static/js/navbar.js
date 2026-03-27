/**
 * Navigation Bar Management
 * Handles Bootstrap tooltips, notification badges, real-time polling, and focus mode state.
 */

document.addEventListener("DOMContentLoaded", function () {

  /* Bootstrap tooltips */
  const tooltips = document.querySelectorAll('[data-bs-toggle="tooltip"]');
  tooltips.forEach(el => new bootstrap.Tooltip(el, { html: true }));

  /* Notification badge & tooltip */
  const badge = document.getElementById("nav-notif-badge");
  const _nav = document.querySelector('nav.timeout-nav');

  let currentUnread = parseInt(_nav?.dataset.unreadCount) || 0;


  /**
   * Update notification badge display with the current unread count.
   */
  function updateNotifBadge(count) {
      if (!badge) return;
      currentUnread = count;
      if (count > 0) {
          badge.style.display = "inline-block";
          badge.textContent = count > 99 ? "99+" : count;
      } else {
          badge.style.display = "none";
      }
  }

  // Set initial badge state from server-rendered count
  if (document.body.dataset.userStatus !== 'focus') {
    updateNotifBadge(currentUnread);
  }


  let lastNotifId = parseInt(_nav?.dataset.latestNotifId) || 0;

  /**
   * Poll for new notifications and update badge/tooltip if any exist.
   * Skips polling when user is in focus mode.
   */
  function pollNotifications() {
    if (document.body.dataset.userStatus === 'focus') {
      fetch(`/notifications/poll/?last_id=${lastNotifId}`).catch(() => {});
      return;}
    fetch(`/notifications/poll/?last_id=${lastNotifId}`)
      .then(res => res.json())
      .then(data => {
        const newNotifs = data.notifications;
        if (!newNotifs.length) return;
        // Update last ID to avoid re-fetching same notifications
        lastNotifId = Math.max(...newNotifs.map(n => n.id));
        // Only count genuinely unread ones
        const newUnread = newNotifs.filter(n => !n.is_read).length;
        if (newUnread > 0) {
          updateNotifBadge(currentUnread + newUnread);}})
      .catch(err => console.error("Polling error:", err));}
      
  window.addEventListener('focusModeEnded', pollNotifications);
  setInterval(pollNotifications, 10000);

});
