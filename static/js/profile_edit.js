/**
 * Profile Edit Form Management
 * Handles conditional display of custom university input field in user profile editing.
 */

const uniSelect = document.getElementById('id_university_choice');
const otherWrapper = document.getElementById('university-other-wrapper');

/**
 * Toggle visibility of custom university input field based on selected option.
 */
function toggleOther() {
  otherWrapper.style.display = uniSelect.value === '__other__' ? '' : 'none';
}

uniSelect.addEventListener('change', toggleOther);
toggleOther();
