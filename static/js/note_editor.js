/**
 * Rich text note editor with Quill: word count, outline, page mode, and autosave.
 * Supports live preview, line spacing, paged view with page breaks, and 2-second autosave.
 * Reads configuration from window.NOTES_CONFIG (autosaveUrl, csrfToken, notePageMode, noteTitle).
 */
(function() {
  var config = window.NOTES_CONFIG || {};

  /**
   * Initialize Quill rich text editor with formatting toolbar and snow theme.
   */
  const quill = new Quill('#quill-editor', {
    theme: 'snow',
    placeholder: 'Start writing your note...',
    modules: {
      toolbar: [
        [{ 'font': [] }],
        [{ 'header': [1, 2, 3, false] }],
        [{ 'size': ['small', false, 'large', 'huge'] }],
        ['bold', 'italic', 'underline', 'strike'],
        [{ 'color': [] }, { 'background': [] }],
        [{ 'list': 'ordered' }, { 'list': 'bullet' }, { 'list': 'check' }],
        [{ 'indent': '-1' }, { 'indent': '+1' }],
        [{ 'align': [] }],
        ['blockquote', 'code-block'],
        ['link'],
        ['clean'],
      ],
    },
  });

  /* Load existing content into editor from hidden form field */
  const hiddenInput = document.getElementById('id_content');
  if (hiddenInput.value) {
    quill.root.innerHTML = hiddenInput.value;
  }

  /**
   * Update live word count display based on current editor content.
   */
  function updateWordCount() {
    const text = quill.getText().trim();
    const words = text ? text.split(/\s+/).length : 0;
    document.getElementById('wordCount').textContent = words + ' words';
  }
  quill.on('text-change', updateWordCount);
  updateWordCount();

  /**
   * Initialize outline panel for navigation via document headings.
   */
  const outlinePanel = document.getElementById('outlinePanel');
  const outlineList = document.getElementById('outlineList');
  const outlineToggleBtn = document.getElementById('outlineToggleBtn');
  const outlineCloseBtn = document.getElementById('outlineCloseBtn');
  const editorMain = document.getElementById('editorMain');

  /**
   * Extract headings from editor and rebuild outline list with scroll navigation.
   */
  function updateOutline() {
    var headings = quill.root.querySelectorAll('h1, h2, h3');
    outlineList.innerHTML = '';

    if (headings.length === 0) {
      var empty = document.createElement('li');
      empty.className = 'note-outline-empty';
      empty.textContent = 'No headings yet';
      outlineList.appendChild(empty);
      return;
    }

    headings.forEach(function(heading) {
      var text = heading.textContent.trim();
      if (!text) return;
      var li = document.createElement('li');
      var tag = heading.tagName.toLowerCase();
      li.className = 'note-outline-item note-outline-item--' + tag;
      li.textContent = text;
      li.title = text;
      li.addEventListener('click', function() {
        heading.scrollIntoView({ behavior: 'smooth', block: 'center' });
      });
      outlineList.appendChild(li);
    });

    /* If all headings were empty text */
    if (outlineList.children.length === 0) {
      var empty = document.createElement('li');
      empty.className = 'note-outline-empty';
      empty.textContent = 'No headings yet';
      outlineList.appendChild(empty);
    }
  }

  outlineToggleBtn.addEventListener('click', function() {
    outlinePanel.classList.toggle('collapsed');
  });

  outlineCloseBtn.addEventListener('click', function() {
    outlinePanel.classList.add('collapsed');
  });

  quill.on('text-change', updateOutline);
  updateOutline();

  /**
   * Initialize line spacing control to adjust editor line height.
   */
  const spacingSelect = document.getElementById('lineSpacing');
  spacingSelect.addEventListener('change', function() {
    quill.root.style.lineHeight = this.value;
    if (pageModeActive) requestAnimationFrame(paginateContent);
  });

  /* Page mode*/

  const pageModeSelect = document.getElementById('pageMode');
  const qlContainer = document.querySelector('.ql-container');
  const editorMainEl = document.getElementById('editorMain');
  let pageModeActive = config.notePageMode === 'paged';
  let lastSavedPageMode = config.notePageMode || '';

  if (pageModeActive) editorMainEl.classList.add('paged-active');

  const PAGE_HEIGHT = 1056;
  const GAP_HEIGHT = 40;
  let isPaginating = false;

  /**
   * Return editor HTML stripped of pagination margin artifacts.
   * Pagination adds temporary margin-top styles to push blocks across page
   * boundaries — these must not be persisted when saving.
   */
  function getCleanContent() {
    var pushed = quill.root.querySelectorAll('[data-page-break]');
    var saved = [];
    pushed.forEach(function(el) {
      saved.push({ el: el, margin: el.style.marginTop });
      el.style.marginTop = '';
    });
    var html = quill.root.innerHTML;
    saved.forEach(function(s) { s.el.style.marginTop = s.margin; });
    return html;
  }

  /**
   * Remove all page visual elements and reset block margin adjustments.
   */
  function clearPageMarkers() {
    qlContainer.querySelectorAll('.page-card, .page-gap, .page-number-label').forEach(function(el) { el.remove(); });
    quill.root.querySelectorAll('[data-page-break]').forEach(function(el) {
      el.style.marginTop = '';
      el.removeAttribute('data-page-break');
    });
  }

  /**
   * Paginate editor content into distinct pages separated by visible gaps.
   *
   * Phase 1 — Measure every block's position before any modifications.
   * Phase 2 — Walk blocks in order; when a block would span a page boundary
   *           and fits on a single page, push it to the next page via margin-top.
   * Phase 3 — Render white page-card backgrounds and gray gap separators
   *           with centered page numbers.
   */
  function paginateContent() {
    if (isPaginating) return;
    isPaginating = true;
    clearPageMarkers();

    if (!pageModeActive) {
      isPaginating = false;
      return;
    }

    qlContainer.style.position = 'relative';
    void quill.root.offsetHeight; /* force reflow after clearing */

    /* Phase 1 — snapshot every child block's position */
    var editorRect = quill.root.getBoundingClientRect();
    var scrollTop = quill.root.scrollTop;
    var blocks = Array.from(quill.root.children).map(function(el) {
      var r = el.getBoundingClientRect();
      return { el: el, top: r.top - editorRect.top + scrollTop, height: r.height };
    });

    /* Phase 2 — decide which blocks to push past the page boundary */
    var pushes = [];
    var offset = 0;
    var nextBreak = PAGE_HEIGHT;

    for (var i = 0; i < blocks.length; i++) {
      var b = blocks[i];
      var adjTop = b.top + offset;
      var adjBottom = adjTop + b.height;

      /* advance past page breaks the block is already beyond */
      while (nextBreak <= adjTop) nextBreak += PAGE_HEIGHT + GAP_HEIGHT;

      /* block spans the boundary and fits on one page → push it */
      if (adjTop < nextBreak && adjBottom > nextBreak && b.height <= PAGE_HEIGHT) {
        var push = nextBreak - adjTop + GAP_HEIGHT;
        pushes.push({ el: b.el, push: push });
        offset += push;
        nextBreak += PAGE_HEIGHT + GAP_HEIGHT;
      }
    }

    /* apply margin pushes */
    for (var j = 0; j < pushes.length; j++) {
      pushes[j].el.style.marginTop = pushes[j].push + 'px';
      pushes[j].el.setAttribute('data-page-break', 'true');
    }

    /* Phase 3 — render page cards and gap separators */
    void quill.root.offsetHeight; /* reflow with new margins */
    var totalHeight = quill.root.scrollHeight;
    var totalPages = Math.max(1, pushes.length + 1);

    /* walk through the height placing cards and gaps */
    var y = 0;
    for (var p = 0; p < totalPages; p++) {
      var pageH = Math.min(PAGE_HEIGHT, totalHeight - y);
      if (pageH <= 0) break;

      /* white page card behind content */
      var card = document.createElement('div');
      card.className = 'page-card';
      card.style.top = y + 'px';
      card.style.height = pageH + 'px';
      qlContainer.appendChild(card);

      y += pageH;

      /* gap between pages */
      if (p < totalPages - 1 && y < totalHeight) {
        var gap = document.createElement('div');
        gap.className = 'page-gap';
        gap.style.top = y + 'px';
        qlContainer.appendChild(gap);

        var label = document.createElement('div');
        label.className = 'page-number-label';
        label.textContent = (p + 1) + ' / ' + totalPages;
        label.style.top = y + 'px';
        qlContainer.appendChild(label);

        y += GAP_HEIGHT;
      }
    }

    /* page number on last page (bottom-right) */
    var lastLabel = document.createElement('div');
    lastLabel.className = 'page-number-label page-number-last';
    lastLabel.textContent = totalPages + ' / ' + totalPages;
    lastLabel.style.top = Math.max(0, totalHeight - 24) + 'px';
    qlContainer.appendChild(lastLabel);

    /* release flag after mutations settle */
    requestAnimationFrame(function() { isPaginating = false; });
  }

  pageModeSelect.addEventListener('change', function() {
    pageModeActive = this.value === 'paged';
    editorMainEl.classList.toggle('paged-active', pageModeActive);
    requestAnimationFrame(paginateContent);
  });

  if (pageModeActive) {
    requestAnimationFrame(paginateContent);
  }

  quill.on('text-change', function() {
    if (isPaginating) return;
    if (pageModeActive) requestAnimationFrame(paginateContent);
  });

  /*  Form sync & autosave  */

  /**
   * Sync editor content and title to hidden form fields on manual submit.
   */
  const editForm = document.getElementById('noteEditForm');
  editForm.addEventListener('submit', function() {
    hiddenInput.value = getCleanContent();
    document.getElementById('hiddenTitle').value = document.getElementById('noteTitleInput').value;
    document.getElementById('hiddenPageMode').value = pageModeSelect.value;
  });

  /**
   * Initialize autosave with 2-second debounce and visual status feedback.
   */
  const autosaveUrl = config.autosaveUrl;
  const csrfToken = config.csrfToken;
  const statusEl = document.getElementById('autosaveStatus');
  let autosaveTimer = null;
  let lastSavedContent = hiddenInput.value || '';
  let lastSavedTitle = config.noteTitle || '';
  let editCounted = false;

  /**
   * Set autosave status indicator text and CSS class.
   */
  function setStatus(text, className) {
    statusEl.textContent = text;
    statusEl.className = 'autosave-indicator' + (className ? ' ' + className : '');
  }

  /**
   * Build FormData payload with current editor state for autosave POST.
   */
  function buildSavePayload(content, title, pageMode) {
    const formData = new FormData();
    formData.append('content', content);
    formData.append('title', title);
    formData.append('page_mode', pageMode);
    formData.append('csrfmiddlewaretoken', csrfToken);
    if (!editCounted) {
      formData.append('count_edit', '1');
      editCounted = true;
    }
    return formData;
  }

  /**
   * POST current content, title, and page mode to server with status feedback.
   * Only saves if content differs from last saved version.
   */
  function doAutosave() {
    var currentContent = getCleanContent();
    var currentTitle = document.getElementById('noteTitleInput').value;
    var currentPageMode = pageModeSelect.value;

    if (currentContent === lastSavedContent && currentTitle === lastSavedTitle && currentPageMode === lastSavedPageMode) return;

    setStatus('Saving...', 'saving');

    fetch(autosaveUrl, { method: 'POST', body: buildSavePayload(currentContent, currentTitle, currentPageMode) })
      .then(function(res) { return res.json(); })
      .then(function(data) {
        if (data.status === 'ok') {
          lastSavedContent = currentContent;
          lastSavedTitle = currentTitle;
          lastSavedPageMode = currentPageMode;
          setStatus('Saved', 'saved');
          setTimeout(function() { if (statusEl.textContent === 'Saved') setStatus(''); }, 3000);
        }
      })
      .catch(function() { setStatus('Save failed'); });
  }

  /**
   * Debounce autosave trigger to 2 seconds to reduce unnecessary API calls.
   */
  function scheduleAutosave() {
    if (isPaginating) return;
    clearTimeout(autosaveTimer);
    autosaveTimer = setTimeout(doAutosave, 2000);
  }

  quill.on('text-change', function() {
    if (!isPaginating) scheduleAutosave();
  });
  document.getElementById('noteTitleInput').addEventListener('input', scheduleAutosave);
  pageModeSelect.addEventListener('change', scheduleAutosave);

  /**
   * Save content on page unload using sendBeacon if unsaved changes exist.
   */
  window.addEventListener('beforeunload', function() {
    var currentContent = getCleanContent();
    var currentTitle = document.getElementById('noteTitleInput').value;
    if (currentContent !== lastSavedContent || currentTitle !== lastSavedTitle || pageModeSelect.value !== lastSavedPageMode) {
      var formData = new FormData();
      formData.append('content', currentContent);
      formData.append('title', currentTitle);
      formData.append('page_mode', pageModeSelect.value);
      formData.append('csrfmiddlewaretoken', csrfToken);
      navigator.sendBeacon(autosaveUrl, formData);
    }
  });
})();