document.addEventListener("DOMContentLoaded", () => {

    const notifList = document.querySelector(".notifications-list");
    const badge = document.querySelector(".nav-link .badge");
    const pageUnread = document.getElementById("page-unread-count");
    const csrfToken = document.getElementById("notifications-config")?.dataset.csrfToken;

    if (!notifList) return;

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

    notifList.addEventListener("click", async (e) => {

        const notifItem = e.target.closest(".notification-item");
        if (!notifItem) return;

        const notificationId = notifItem.id.replace("notif-", "");
        const eventId = notifItem.dataset.eventId;

        if (e.target.classList.contains("mark-read-btn")) {
            try {
                const res = await fetch(`/notifications/read/${notificationId}/`, {
                    method: "POST",
                    headers: { "X-CSRFToken": csrfToken, "Content-Type": "application/json" }
                });
                if (res.ok) {
                    notifItem.classList.remove("notification-unread");
                    notifItem.classList.add("notification-read");
                    e.target.remove();
                    decreaseUnread();
                }
            } catch (err) {
                console.error("Read error:", err);
            }
            return;
        }

        if (e.target.classList.contains("accept-follow-btn") || e.target.classList.contains("reject-follow-btn")) {
            const username = e.target.dataset.username;
            const action = e.target.classList.contains("accept-follow-btn") ? "accept" : "reject";
            try {
                await fetch(`/social/user/${username}/follow/${action}/`, {
                    method: "POST",
                    headers: { "X-CSRFToken": csrfToken, "Content-Type": "application/json" }
                });
                if (notifItem.classList.contains("notification-unread")) decreaseUnread();
                notifItem.remove();
                if (!document.querySelectorAll(".notification-item").length) {
                    document.getElementById("no-notifications").style.display = "block";
                }
            } catch (err) {
                console.error("Follow request error:", err);
            }
            return;
        }

        if (e.target.classList.contains("delete-notif-btn")) {
            try {
                const res = await fetch(`/notifications/delete/${notificationId}/`, {
                    method: "POST",
                    headers: { "X-CSRFToken": csrfToken, "Content-Type": "application/json" }
                });
                if (res.ok) {
                    if (notifItem.classList.contains("notification-unread")) decreaseUnread();
                    notifItem.remove();
                    if (!document.querySelectorAll(".notification-item").length) {
                        document.getElementById("no-notifications").style.display = "block";
                    }
                }
            } catch (err) {
                console.error("Delete error:", err);
            }
            return;
        }

        try {
            if (notifItem.classList.contains("notification-unread")) {
                const res = await fetch(`/notifications/read/${notificationId}/`, {
                    method: "POST",
                    headers: { "X-CSRFToken": csrfToken, "Content-Type": "application/json" }
                });
                if (res.ok) {
                    notifItem.classList.remove("notification-unread");
                    notifItem.classList.add("notification-read");
                    decreaseUnread();
                    const readBtn = notifItem.querySelector(".mark-read-btn");
                    if (readBtn) readBtn.remove();
                }
            }
        } catch (err) {
            console.error("Auto read error:", err);
        }

        if (notifItem.dataset.type === "message") {
            const convoId = notifItem.dataset.convoId;
            if (convoId && convoId !== "None") {
                window.location.href = `/messaging/conversation/${convoId}/`;
            }
            return;
        }

        const postId = notifItem.dataset.postId;
        if (postId && postId !== "None") {
            window.location.href = `/social/feed/?highlight_post=${postId}`;
            return;
        }

        if (eventId && eventId !== "None") {
            window.location.href = `/calendar/?open_event=${eventId}`;
        }

    });

});
