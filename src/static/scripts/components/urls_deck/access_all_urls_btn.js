"use strict";

$(document).ready(function () {
  // Open all URLs in UTub in separate tabs
  $("#accessAllURLsBtn").on("click", function (_) {
    const ACCESS_ALL_URLS_LIMIT_WARNING = CONSTANTS.MAX_NUM_OF_URLS_TO_ACCESS;
    if (getNumOfVisibleURLs() > ACCESS_ALL_URLS_LIMIT_WARNING) {
      accessAllWarningShowModal();
    } else {
      accessAllURLsInUTub();
    }
  });
});

function hideAccessAllWarningShowModal() {
  $("#confirmModal").removeClass("accessAllUrlModal");
}

// Show confirmation modal for opening all URLs in UTub
function accessAllWarningShowModal() {
  const modalTitle =
    "Are you sure you want to open all " +
    getNumOfURLs() +
    " URLs in this UTub?";
  const modalText = "Performance issues may occur.";
  const modalDismiss = "Cancel";

  $("#confirmModalTitle").text(modalTitle);
  $("#confirmModalBody").text(modalText);

  $("#modalDismiss")
    .on("click", function (e) {
      e.preventDefault();
      $("#confirmModal").modal("hide");
    })
    .removeClass()
    .addClass("btn btn-danger")
    .text(modalDismiss);

  $("#modalSubmit")
    .removeClass()
    .addClass("btn btn-success")
    .on("click", function (e) {
      e.preventDefault();
      accessAllURLsInUTub();
      $("#confirmModal").modal("hide");
    })
    .text("Open all URLs");

  $("#confirmModal")
    .modal("show")
    .addClass("accessAllUrlModal")
    .on("hidden.bs.modal", hideAccessAllWarningShowModal);

  $("#modalRedirect").hide();
  $("#modalRedirect").hideClass();
}

// Opens all visible URLs in UTub in separate tabs
function accessAllURLsInUTub() {
  const visibleSelector = ".urlRow[filterable=true] .urlString";
  const visibleURLs = $(visibleSelector);
  if (visibleURLs.length === 0) return;

  const visibleURLsToAccess = $.map(visibleURLs, (url) => $(url).attr("href"));

  for (let i = 0; i < visibleURLsToAccess.length; i++) {
    accessLink(visibleURLsToAccess[i], null);
  }
}
