// Filters the "All environments" table in place as the user types, and keeps
// the ?q= query parameter in sync so the current view can be shared or
// reloaded. The server renders every row and only echoes ?q= into the input.
(function () {
  var searchForm = document.getElementById("environment-search-form");
  var searchInput = document.getElementById("environment-search-input");
  var environmentTable = document.getElementById("all-environments-table");
  var noMatchMessage = document.getElementById("environment-search-no-match");

  if (!searchForm || !searchInput || !environmentTable || !noMatchMessage) {
    return;
  }

  var environmentRows = Array.prototype.slice.call(
    environmentTable.querySelectorAll("tbody tr[data-environment-name]")
  );

  function normalise(text) {
    return text.trim().toLowerCase();
  }

  function isMatchingRow(environmentRow, searchTerm) {
    var environmentName = normalise(environmentRow.getAttribute("data-environment-name"));
    var ownerEmail = normalise(environmentRow.getAttribute("data-owner-email"));

    return environmentName.indexOf(searchTerm) !== -1 || ownerEmail.indexOf(searchTerm) !== -1;
  }

  function syncSearchTermToUrl(searchTerm) {
    var url = new URL(window.location.href);

    if (searchTerm) {
      url.searchParams.set("q", searchTerm);
    } else {
      url.searchParams.delete("q");
    }

    window.history.replaceState(null, "", url);
  }

  function applySearch() {
    var searchTerm = normalise(searchInput.value);
    var visibleRowCount = 0;

    environmentRows.forEach(function (environmentRow) {
      var isVisible = searchTerm === "" || isMatchingRow(environmentRow, searchTerm);

      environmentRow.classList.toggle("d-none", !isVisible);

      if (isVisible) {
        visibleRowCount += 1;
      }
    });

    var hasRowsToSearch = environmentRows.length > 0;
    noMatchMessage.classList.toggle("d-none", !hasRowsToSearch || visibleRowCount > 0);

    syncSearchTermToUrl(searchTerm);
  }

  // Typing filters immediately. Enter and the Search button apply the same
  // filter without a page load; a page load (or a shared link) re-renders the
  // full list and this script re-applies the term from the pre-filled input.
  searchInput.addEventListener("input", applySearch);

  searchForm.addEventListener("submit", function (submitEvent) {
    submitEvent.preventDefault();
    applySearch();
  });

  applySearch();
})();
