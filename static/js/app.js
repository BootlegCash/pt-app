/* Shared UI behaviors: active nav highlighting + confirm dialogs. */
(function () {
  "use strict";

  // Highlight the nav link matching the current path prefix.
  var path = window.location.pathname;
  document.querySelectorAll("[data-nav]").forEach(function (link) {
    var href = link.getAttribute("href");
    if (!href) return;
    if (href === "/" ? path === "/" : path.indexOf(href) === 0) {
      link.classList.add("active");
    }
  });

  // Forms with data-confirm show a native confirm dialog before submitting.
  document.querySelectorAll("form[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (!window.confirm(form.getAttribute("data-confirm"))) {
        event.preventDefault();
      }
    });
  });
})();
