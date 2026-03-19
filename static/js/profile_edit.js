const uniSelect = document.getElementById('id_university_choice');
const otherWrapper = document.getElementById('university-other-wrapper');

function toggleOther() {
  otherWrapper.style.display = uniSelect.value === '__other__' ? '' : 'none';
}

uniSelect.addEventListener('change', toggleOther);
toggleOther();
