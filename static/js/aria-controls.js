(function() {

  function accordionToggles(tabCtrl) {
    let toggles = Array.prototype.slice.call(
      document.querySelectorAll(tabCtrl)
    );

    function toggle (toggle, open) {
      let button = toggle.getAttribute('aria-controls');
      let panel = document.querySelector(button);

      if (open) {
        panel.setAttribute('aria-hidden', false);
        toggle.setAttribute('aria-expanded', true);
      } else {
        panel.setAttribute('aria-hidden', true);
        toggle.setAttribute('aria-expanded', false);
      }
    }

    function toggleAll (event) {
      let target = event.target;

      // Filter through all toggles and toggle visiblity
      toggles.forEach(panel => {
        if (panel !== target) {
          toggle(panel);
        }
      });

      // Target toggle to be shown
      let targetOpen = target.getAttribute('aria-expanded');
      targetOpen === 'true' ? toggle(target, false) : toggle(target, true);
    }

    toggles.forEach(toggle => {
      toggle.addEventListener('click', toggleAll);
    });
  }

  accordionToggles('.p-accordion__tab');
})()
