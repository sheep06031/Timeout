/**
 * Complete Profile - University Toggle
 * Toggles visibility of "other university" input field based on dropdown selection.
 * Shows text input only when "__other__" option is selected.
 */
;(function () {
  var choice = document.getElementById('id_university_choice')
  var otherWrap = document.getElementById('universityOtherWrap')
  if (!choice || !otherWrap) return

  /**
   * Show or hide the "other university" input wrapper.
   */
  function toggle() {
    otherWrap.style.display = choice.value === '__other__' ? '' : 'none'
  }
  toggle()
  choice.addEventListener('change', toggle)
})()