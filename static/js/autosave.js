/* Workout logger autosave.
   Every input inside a .set-row saves the whole row (debounced) to the
   autosave endpoint. Status is shown per exercise card: Saving… / Saved / Error. */
(function () {
  "use strict";

  var root = document.getElementById("logger");
  if (!root) return;
  var saveUrl = root.dataset.saveUrl;
  var removeUrl = root.dataset.removeUrl;
  var csrf = root.dataset.csrf;
  var timers = {};

  function statusEl(card) { return card.querySelector(".save-status"); }

  function setStatus(card, state, text) {
    var el = statusEl(card);
    if (!el) return;
    el.textContent = text;
    el.className = "save-status " + state;
  }

  function rowPayload(row, card) {
    function val(name) {
      var input = row.querySelector('[data-field="' + name + '"]');
      if (!input) return "";
      if (input.type === "checkbox") return input.checked;
      return input.value;
    }
    var subInput = card.querySelector("[data-substitution]");
    return {
      prescription: card.dataset.prescription,
      set_number: parseInt(row.dataset.setNumber, 10),
      is_warmup: row.dataset.warmup === "1",
      weight: val("weight"),
      reps: val("reps"),
      rir: val("rir"),
      rpe: val("rpe"),
      distance: val("distance"),
      duration: val("duration"),
      completed: val("completed"),
      failed: val("failed"),
      notes: val("notes"),
      substitution: subInput ? subInput.value : ""
    };
  }

  function saveRow(row, card) {
    setStatus(card, "saving", "Saving…");
    fetch(saveUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
      body: JSON.stringify(rowPayload(row, card))
    })
      .then(function (response) {
        if (!response.ok) throw new Error("save failed");
        return response.json();
      })
      .then(function (data) {
        if (!data.ok) throw new Error(data.error || "save failed");
        row.dataset.setUuid = data.set_uuid;
        setStatus(card, "saved", "Saved");
      })
      .catch(function () {
        setStatus(card, "error", "Error saving — retrying may help");
      });
  }

  function scheduleSave(row, card) {
    var key = card.dataset.prescription + ":" +
      (row.dataset.warmup === "1" ? "warmup:" : "work:") + row.dataset.setNumber;
    clearTimeout(timers[key]);
    setStatus(card, "saving", "Saving…");
    timers[key] = setTimeout(function () { saveRow(row, card); }, 500);
  }

  root.querySelectorAll(".exercise-card").forEach(function (card) {
    card.addEventListener("input", function (event) {
      var row = event.target.closest(".set-row");
      if (!row && event.target.hasAttribute("data-substitution")) {
        // Substitution request rides along with the first working set.
        row = card.querySelector(".set-row:not([data-warmup]):not([aria-hidden])");
      }
      if (row) scheduleSave(row, card);
    });
    card.addEventListener("change", function (event) {
      var row = event.target.closest(".set-row");
      if (row && (event.target.type === "checkbox")) saveRow(row, card);
    });

    // Add an extra set: clone the template row.
    var addButton = card.querySelector("[data-add-set]");
    if (addButton) {
      addButton.addEventListener("click", function () {
        var rows = card.querySelectorAll(".set-row");
        var last = rows[rows.length - 1];
        var next = last.cloneNode(true);
        var number = parseInt(last.dataset.setNumber, 10) + 1;
        next.dataset.setNumber = number;
        next.dataset.setUuid = "";
        next.querySelector(".setnum").textContent = number;
        next.querySelectorAll("input").forEach(function (input) {
          if (input.type === "checkbox") input.checked = false;
          else input.value = "";
        });
        var tag = document.createElement("div");
        tag.className = "set-extra-tag";
        tag.textContent = "extra set";
        last.after(next);
        next.appendChild(tag);
        var removeBtn = next.querySelector("[data-remove-set]");
        if (removeBtn) removeBtn.hidden = false;
      });
    }

    // Remove an extra set (server verifies it is actually extra).
    card.addEventListener("click", function (event) {
      var button = event.target.closest("[data-remove-set]");
      if (!button) return;
      var row = button.closest(".set-row");
      var uuid = row.dataset.setUuid;
      if (!uuid) { row.remove(); return; }
      var body = new URLSearchParams({ set_uuid: uuid });
      fetch(removeUrl, {
        method: "POST",
        headers: { "X-CSRFToken": csrf },
        body: body
      }).then(function (response) {
        if (response.ok) row.remove();
        else setStatus(card, "error", "Only extra sets can be removed");
      });
    });
  });
})();
