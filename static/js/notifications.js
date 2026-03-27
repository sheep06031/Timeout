/**
 * Notification List Management
 * Handles notification interaction, marking as read/unread, deleting, mark all read,
 * infinite scroll, accepting/rejecting follow requests,
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
     * Increase unread count in both page and navigation badge elements.
     */
    function increaseUnread() {
        if (pageUnread) {
            pageUnread.textContent = parseInt(pageUnread.textContent) + 1;
        }
        if (badge) {
            badge.style.display = "";
            badge.textContent = parseInt(badge.textContent || 0) + 1;
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
                target.outerHTML = `<button class="mark-unread-btn notif-btn" data-id="${notificationId}">Unread</button>`;
                decreaseUnread();
            }
        } catch (err) { console.error("Read error:", err); }
    }

    /**
     * Mark a notification as unread and update UI.
     */
    async function _handleMarkUnread(notifItem, notificationId, target) {
        try {
            var res = await _postRequest("/notifications/unread/" + notificationId + "/");
            if (res.ok) {
                notifItem.classList.remove("notification-read");
                notifItem.classList.add("notification-unread");
                target.outerHTML = `<button class="mark-read-btn notif-btn notif-btn-read" data-id="${notificationId}">Read</button>`;
                increaseUnread();
            }
        } catch (err) { console.error("Unread error:", err); }
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
                    if (readBtn) {
                        readBtn.outerHTML = `<button class="mark-unread-btn notif-btn" data-id="${notificationId}">Unread</button>`;
                    }
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
        if (e.target.classList.contains("mark-unread-btn")) { await _handleMarkUnread(notifItem, notificationId, e.target); return; }
        if (e.target.classList.contains("accept-follow-btn") || e.target.classList.contains("reject-follow-btn")) { await _handleFollowAction(notifItem, e.target); return; }
        if (e.target.classList.contains("delete-notif-btn")) { await _handleDelete(notifItem, notificationId); return; }

        await _handleAutoRead(notifItem, notificationId);
        _navigateNotification(notifItem);
    });

    /**
     * Mark all read
     */
    document.getElementById("mark-all-read-btn")?.addEventListener("click", async () => {
        try {
            const res = await _postRequest("/notifications/read-all/");
            if (res.ok) {
                document.querySelectorAll(".notification-unread").forEach(item => {
                    const id = item.id.replace("notif-", "");
                    item.classList.remove("notification-unread");
                    item.classList.add("notification-read");
                    const readBtn = item.querySelector(".mark-read-btn");
                    if (readBtn) {
                        readBtn.outerHTML = `<button class="mark-unread-btn notif-btn" data-id="${id}">Unread</button>`;
                    }
                });
                if (pageUnread) pageUnread.textContent = "0";
                if (badge) badge.style.display = "none";
            }
        } catch (err) { console.error("Mark all read error:", err); }
    });

    /**
     * Mark all unread
     */
    document.getElementById("mark-all-unread-btn")?.addEventListener("click", async () => {
        try {
            const res = await _postRequest("/notifications/unread-all/");
            if (res.ok) {
                document.querySelectorAll(".notification-read").forEach(item => {
                    const id = item.id.replace("notif-", "");
                    item.classList.remove("notification-read");
                    item.classList.add("notification-unread");
                    const unreadBtn = item.querySelector(".mark-unread-btn");
                    if (unreadBtn) {
                        unreadBtn.outerHTML = `<button class="mark-read-btn notif-btn notif-btn-read" data-id="${id}">Read</button>`;
                    }
                });
                // Recount all visible items and update badge
                const total = document.querySelectorAll(".notification-unread").length;
                if (pageUnread) pageUnread.textContent = total;
                if (badge) {
                    badge.style.display = "";
                    badge.textContent = total > 99 ? "99+" : total;
                }
            }
        } catch (err) { console.error("Mark all unread error:", err); }
    });

    /**
     * Delete all
     */
    document.getElementById("delete-all-btn")?.addEventListener("click", async () => {
        if (!confirm("Delete all notifications?")) return;
        try {
            const res = await _postRequest("/notifications/delete-all/");
            if (res.ok) {
                document.querySelectorAll(".notification-item").forEach(item => item.remove());
                if (pageUnread) pageUnread.textContent = "0";
                if (badge) badge.style.display = "none";
                document.getElementById("no-notifications").style.display = "block";
            }
        } catch (err) { console.error("Delete all error:", err); }
    });

    /**
     * Infinite scroll for notifications
     */
    const sentinel = document.getElementById("scroll-sentinel");
    const loadingIndicator = document.getElementById("loading-indicator");
    if (!sentinel) return;

    const config = document.getElementById("notifications-config");
    let currentPage = parseInt(config?.dataset.currentPage || "1");
    let hasNext = config?.dataset.hasNext === "true";
    const currentFilter = config?.dataset.currentFilter || "";
    let isLoading = false;

    /**
     * Build a notification item 
     */
    function _buildNotifElement(n) {
        const div = document.createElement("div");
        div.id = `notif-${n.id}`;
        div.className = `notification-item ${n.is_read ? "notification-read" : "notification-unread"}`;
        div.dataset.type = n.type || "";
        div.dataset.eventId = n.deadline_id || "";
        div.dataset.convoId = n.conversation_id || "";
        div.dataset.postId = n.post_id || "";
        const timeStr = new Date(n.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
        const readBtn = n.is_read
            ? `<button class="mark-unread-btn notif-btn" data-id="${n.id}">Unread</button>`
            : `<button class="mark-read-btn notif-btn notif-btn-read" data-id="${n.id}">Read</button>`;
        div.innerHTML = `
            <div class="notification-main">
                <div class="notification-title">${n.title}</div>
                <div class="notification-message">${n.message}</div>
                <div class="notification-time">${timeStr}</div>
            </div>
            <div class="notification-actions">
                ${readBtn}
                <button class="delete-notif-btn notif-btn notif-btn-delete" data-id="${n.id}">Delete</button>
            </div>`;
        return div;
    }

    const observer = new IntersectionObserver(async (entries) => {
        if (!entries[0].isIntersecting || isLoading || !hasNext) return;
        isLoading = true;
        if (loadingIndicator) loadingIndicator.style.display = "block";
        currentPage++;

        try {
            const params = new URLSearchParams({ page: currentPage });
            if (currentFilter) params.set("filter", currentFilter);
            const res = await fetch("?" + params.toString(), {
                headers: { "X-Requested-With": "XMLHttpRequest" }
            });
            const data = await res.json();
            hasNext = data.has_next;
            data.notifications.forEach(n => {
                notifList.appendChild(_buildNotifElement(n));
            });
        } catch (err) { console.error("Infinite scroll error:", err); }

        if (loadingIndicator) loadingIndicator.style.display = "none";
        isLoading = false;
    }, { threshold: 1.0 });

    observer.observe(sentinel);

});