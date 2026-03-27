/**
 * Social Messaging & Feed Loading
 * Handles conversation messaging (send/poll/display) and infinite scroll feed loading.
 * Depends on social.js being loaded first (for getCookie).
 */

/**
 * Append message to conversation container and auto-scroll to bottom.
 */
function _appendMessage(container, msg) {
    const empty = container.querySelector('.convo-empty');
    if (empty) empty.remove();

    const row = document.createElement('div');
    row.className = `msg-bubble-row ${msg.is_me ? 'msg-mine' : 'msg-theirs'}`;
    row.dataset.messageId = msg.id;
    row.innerHTML = `
        <div class="msg-bubble">
            <div class="msg-text">${msg.content}</div>
            <div class="msg-time">${msg.created_at}</div>
        </div>`;
    container.appendChild(row);
    container.scrollTop = container.scrollHeight;
}

/**
 * Send message via API and update UI on success.
 */
function _sendMessage(config, input, sendBtn, container, state) {
    const content = input.value.trim();
    if (!content) return;
    sendBtn.disabled = true;

    fetch(config.sendUrl, {
        method: 'POST',
        headers: { 'X-CSRFToken': config.csrfToken },
        body: new URLSearchParams({ content }),
    })
    .then(r => r.json())
    .then(msg => {
        if (msg.error) { console.error(msg.error); return; }
        _appendMessage(container, msg);
        state.lastMessageId = msg.id;
        input.value = '';
    })
    .catch(err => console.error('Send error:', err))
    .finally(() => { sendBtn.disabled = false; input.focus(); });
}

/**
 * Fetch new messages from server and append to conversation.
 */
function _pollMessages(config, container, state) {
    fetch(`${config.pollUrl}?last_id=${state.lastMessageId}`)
        .then(r => r.json())
        .then(data => {
            data.messages.forEach(msg => {
                _appendMessage(container, msg);
                state.lastMessageId = msg.id;
            });
        })
        .catch(err => console.error('Poll error:', err));
}

/**
 * Initialize messaging interface with send/poll handlers and auto-scroll.
 */
function initMessaging() {
    const config = window.CONVO_CONFIG;
    if (!config) return;

    const input     = document.getElementById('message-input');
    const sendBtn   = document.getElementById('send-btn');
    const container = document.getElementById('message-container');
    const state = { lastMessageId: 0 };

    document.querySelectorAll('[data-message-id]').forEach(el => {
        const id = parseInt(el.dataset.messageId, 10);
        if (id > state.lastMessageId) state.lastMessageId = id;
    });

    sendBtn.addEventListener('click', () => _sendMessage(config, input, sendBtn, container, state));
    input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); _sendMessage(config, input, sendBtn, container, state); }
    });

    setInterval(() => _pollMessages(config, container, state), 3000);
    container.scrollTop = container.scrollHeight;
}

/**
 * Initialize load-more button for infinite feed scrolling.
 */
function initLoadMore() {
    const loadMoreBtn = document.getElementById('load-more-btn');
    if (!loadMoreBtn) return;
    loadMoreBtn.addEventListener('click', function () {
        const tab = this.dataset.tab;
        const cursor = this.dataset.cursor;
        this.textContent = 'Loading…';
        this.disabled = true;
        fetch(`/social/feed/more/?tab=${tab}&cursor=${cursor}`)
            .then(r => r.json())
            .then(data => {
                document.getElementById('posts-container').insertAdjacentHTML('beforeend', data.html);
                if (data.has_more) {
                    this.dataset.cursor = data.next_cursor;
                    this.textContent = 'Load more';
                    this.disabled = false;
                } else {
                    document.getElementById('load-more-wrap').remove();
                }})
            .catch(() => {
                this.textContent = 'Load more';
                this.disabled = false;});});
}

document.addEventListener('DOMContentLoaded', function() {
    initMessaging();
    initLoadMore();
});
