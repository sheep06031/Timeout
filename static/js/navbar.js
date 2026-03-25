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
      badge.textContent = count;
    } else {
      badge.style.display = "none";}}

  // Set initial badge state from server-rendered count
  if (document.body.dataset.userStatus !== 'focus') {
    updateNotifBadge(currentUnread);
  }

  /**
   * Display a temporary tooltip near the notification badge announcing a new notification.
   */
  function showNewNotificationTooltip() {
    if (!badge) return;
    badge.classList.add("new-notif-pulse");
    let tooltip = document.getElementById("notif-tooltip");
    if (!tooltip) {
      tooltip = document.createElement("div");
      tooltip.id = "notif-tooltip";
      tooltip.className = "new-notif-tooltip";
      tooltip.textContent = "New notification!";
      document.body.appendChild(tooltip);}
    const rect = badge.getBoundingClientRect();
    tooltip.style.top = rect.bottom + window.scrollY + 4 + "px";
    tooltip.style.left = rect.left + window.scrollX + rect.width / 2 + "px";
    tooltip.style.display = "block";
    setTimeout(() => tooltip.classList.add("show"), 50);
    setTimeout(() => {
      tooltip.classList.remove("show");
      tooltip.style.display = "none";
      badge.classList.remove("new-notif-pulse");
    }, 3000);}


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
          showNewNotificationTooltip();
          updateNotifBadge(currentUnread + newUnread);}})
      .catch(err => console.error("Polling error:", err));}
      
  window.addEventListener('focusModeEnded', pollNotifications);
  setInterval(pollNotifications, 10000);

});
