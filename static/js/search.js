(function() {
  function handleSearch(searchBox) {
    let searchBoxes = Array.prototype.slice.call(
      document.querySelectorAll(searchBox)
    );

    searchBoxes.forEach(searchBox => {
      let searchBoxInput = searchBox.querySelector('.p-search-box__input');
      let searchBoxResetBtn = searchBox.querySelector('.p-search-box__reset');

      searchBoxResetBtn.addEventListener('click', function(e) {
        e.preventDefault();
        searchBoxInput.value = '';
        searchBoxInput.focus();
      }, false);
    });
  }

  handleSearch('.p-search-box');
})();
