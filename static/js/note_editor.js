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

  /**
   * Initialize page mode (paged view) with automatic page break markers and numbering.
   */
  const pageModeSelect = document.getElementById('pageMode');
  const qlContainer = document.querySelector('.ql-container');
  const editorMainEl = document.getElementById('editorMain');
  let pageModeActive = config.notePageMode === 'paged';
  let lastSavedPageMode = config.notePageMode || '';

  /* Apply class on load so CSS switches editor height mode */
  if (pageModeActive) editorMainEl.classList.add('paged-active');

  const PAGE_HEIGHT = 1056;

  /**
   * Remove all page break lines and page number labels from editor.
   */
  function clearPageMarkers() {
    qlContainer.querySelectorAll('.page-break-line, .page-number-label').forEach(function(el) { el.remove(); });
  }

  /**
   * Calculate pages and render page break lines with page number labels based on content height.
   */
  function paginateContent() {
    clearPageMarkers();
    if (!pageModeActive) return;

    qlContainer.style.position = 'relative';

    var contentHeight = quill.root.scrollHeight;
    var totalPages = Math.max(1, Math.ceil(contentHeight / PAGE_HEIGHT));

    for (var i = 1; i < totalPages; i++) {
      var line = document.createElement('div');
      line.className = 'page-break-line';
      line.style.top = (i * PAGE_HEIGHT) + 'px';
      qlContainer.appendChild(line);
    }

    for (var i = 0; i < totalPages; i++) {
      var label = document.createElement('div');
      label.className = 'page-number-label';
      label.textContent = (i + 1) + ' / ' + totalPages;
      var labelTop = (i + 1) * PAGE_HEIGHT - 22;
      /* Last page may be shorter — cap label at actual content bottom */
      if (i === totalPages - 1 && labelTop > contentHeight - 22) {
        labelTop = contentHeight - 22;
      }
      label.style.top = labelTop + 'px';
      qlContainer.appendChild(label);
    }
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
    if (pageModeActive) requestAnimationFrame(paginateContent);
  });

  /**
   * Sync editor content and title to hidden form fields on manual submit.
   */
  const editForm = document.getElementById('noteEditForm');
  editForm.addEventListener('submit', function() {
    hiddenInput.value = quill.root.innerHTML;
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
    const currentContent = quill.root.innerHTML;
    const currentTitle = document.getElementById('noteTitleInput').value;
    const currentPageMode = pageModeSelect.value;

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
    clearTimeout(autosaveTimer);
    autosaveTimer = setTimeout(doAutosave, 2000);
  }

  quill.on('text-change', scheduleAutosave);
  document.getElementById('noteTitleInput').addEventListener('input', scheduleAutosave);
  pageModeSelect.addEventListener('change', scheduleAutosave);

  /**
   * Save content on page unload using sendBeacon if unsaved changes exist.
   */
  window.addEventListener('beforeunload', function() {
    const currentContent = quill.root.innerHTML;
    const currentTitle = document.getElementById('noteTitleInput').value;
    if (currentContent !== lastSavedContent || currentTitle !== lastSavedTitle || pageModeSelect.value !== lastSavedPageMode) {
      const formData = new FormData();
      formData.append('content', currentContent);
      formData.append('title', currentTitle);
      formData.append('page_mode', pageModeSelect.value);
      formData.append('csrfmiddlewaretoken', csrfToken);
      navigator.sendBeacon(autosaveUrl, formData);
    }
  });
})();