/**
 * Notification List Management
 * Handles notification interaction, marking as read, deleting, accepting/rejecting follow requests,
 * and navigating to associated content (messages, posts, events).
 */

document.addEventListener("DOMContentLoaded", () => {

    const notifList = document.querySelector(".notifications-list");
    const badge = document.querySelector(".nav-link .badge");
    const pageUnread = document.getElementById("page-unread-count");
    const csrfToken = document.getElementById("notifications-config")?.dataset.csrfToken;

    if (!notifList) return;

    /**
     * Decrease unread count in both page and navigation badge elements.
     */
    function decreaseUnread() {
        if (pageUnread && parseInt(pageUnread.textContent) > 0) {
            pageUnread.textContent = parseInt(pageUnread.textContent) - 1;
        }
        if (badge && parseInt(badge.textContent) > 0) {
            let count = parseInt(badge.textContent) - 1;
            if (count <= 0) badge.style.display = "none";
            else badge.textContent = count;
        }
    }

    /**
     * Send a POST request with CSRF token for notification actions.
     */
    function _postRequest(url) {
        return fetch(url, {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken, "Content-Type": "application/json" }
        });
    }

    /**
     * Show "no notifications" message if the notification list is now empty.
     */
    function _hideIfEmpty() {
        if (!document.querySelectorAll(".notification-item").length) {
            document.getElementById("no-notifications").style.display = "block";
        }
    }

    /**
     * Mark a notification as read and update UI.
     */
    async function _handleMarkRead(notifItem, notificationId, target) {
        try {
            var res = await _postRequest("/notifications/read/" + notificationId + "/");
            if (res.ok) {
                notifItem.classList.remove("notification-unread");
                notifItem.classList.add("notification-read");
                target.remove();
                decreaseUnread();
            }
        } catch (err) { console.error("Read error:", err); }
    }

    /**
     * Handle accepting or rejecting a follow request and remove the notification.
     */
    async function _handleFollowAction(notifItem, target) {
        var username = target.dataset.username;
        var action = target.classList.contains("accept-follow-btn") ? "accept" : "reject";
        try {
            await _postRequest("/social/user/" + username + "/follow/" + action + "/");
            if (notifItem.classList.contains("notification-unread")) decreaseUnread();
            notifItem.remove();
            _hideIfEmpty();
        } catch (err) { console.error("Follow request error:", err); }
    }

    /**
     * Delete a notification and update badge if needed.
     */
    async function _handleDelete(notifItem, notificationId) {
        try {
            var res = await _postRequest("/notifications/delete/" + notificationId + "/");
            if (res.ok) {
                if (notifItem.classList.contains("notification-unread")) decreaseUnread();
                notifItem.remove();
                _hideIfEmpty();
            }
        } catch (err) { console.error("Delete error:", err); }
    }

    /**
     * Auto-mark notification as read on click if it was unread.
     */
    async function _handleAutoRead(notifItem, notificationId) {
        try {
            if (notifItem.classList.contains("notification-unread")) {
                var res = await _postRequest("/notifications/read/" + notificationId + "/");
                if (res.ok) {
                    notifItem.classList.remove("notification-unread");
                    notifItem.classList.add("notification-read");
                    decreaseUnread();
                    var readBtn = notifItem.querySelector(".mark-read-btn");
                    if (readBtn) readBtn.remove();
                }
            }
        } catch (err) { console.error("Auto read error:", err); }
    }

    /**
     * Navigate to the relevant content associated with a notification (message, post, or event).
     */
    function _navigateNotification(notifItem) {
        if (notifItem.dataset.type === "message") {
            var convoId = notifItem.dataset.convoId;
            if (convoId && convoId !== "None") window.location.href = "/messaging/conversation/" + convoId + "/";
            return;
        }
        var postId = notifItem.dataset.postId;
        if (postId && postId !== "None") { window.location.href = "/social/feed/?highlight_post=" + postId; return; }
        var eventId = notifItem.dataset.eventId;
        if (eventId && eventId !== "None") window.location.href = "/calendar/?open_event=" + eventId;
    }

    notifList.addEventListener("click", async (e) => {
        var notifItem = e.target.closest(".notification-item");
        if (!notifItem) return;
        var notificationId = notifItem.id.replace("notif-", "");

        if (e.target.classList.contains("mark-read-btn")) { await _handleMarkRead(notifItem, notificationId, e.target); return; }
        if (e.target.classList.contains("accept-follow-btn") || e.target.classList.contains("reject-follow-btn")) { await _handleFollowAction(notifItem, e.target); return; }
        if (e.target.classList.contains("delete-notif-btn")) { await _handleDelete(notifItem, notificationId); return; }

        await _handleAutoRead(notifItem, notificationId);
        _navigateNotification(notifItem);
    });

});
