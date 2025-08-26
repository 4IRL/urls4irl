"use strict";

const ACCESS_URL_MODAL_STRING_ID = "AccessURLModalURLString";

// Opens new tab
function accessLink(urlString) {
  // Still need to implement: Take user to a new tab with interstitial page warning they are now leaving U4I
  if (urlString.startsWith("http")) {
    window.open(urlString, "_blank").focus();
    return;
  }

  // For all non-http or non-https URLs, show a warning modal.
  accessURLWarningShowModal(urlString);
}

// Hide confirmation modal for removal of the selected URL
function accessURLHideModal() {
  $("#confirmModal").modal("hide").removeClass("accessExternalURLModal");
  $("#confirmModalBody").removeClass("white-space-pre-line");
  $("#" + ACCESS_URL_MODAL_STRING_ID).remove();
}

function urlStringInAccessModal(urlString) {
  const urlSpan = $(document.createElement("strong"));
  urlSpan.attr("id", ACCESS_URL_MODAL_STRING_ID).text(urlString);

  return urlSpan;
}

// Show confirmation modal for removal of the selected existing URL from current UTub
function accessURLWarningShowModal(urlString) {
  const modalTitle = "🚦 Caution! 🚦";
  const modalText = `${STRINGS.ACCESS_URL_WARNING}\n\n`;
  const buttonTextDismiss = "Nevermind";
  const buttonTextSubmit = "Let's go!";

  $("#confirmModalTitle").text(modalTitle);
  $("#confirmModalBody")
    .text(modalText)
    .addClass("white-space-pre-line")
    .append(urlStringInAccessModal(urlString));

  $("#modalDismiss")
    .offAndOn("click", function (e) {
      e.preventDefault();
      accessURLHideModal();
    })
    .text(buttonTextDismiss);

  $("#modalSubmit")
    .offAndOn("click", function (e) {
      e.preventDefault();
      window.open(urlString, "_blank").focus();
    })
    .text(buttonTextSubmit);

  $("#confirmModal")
    .addClass("accessExternalURLModal")
    .modal("show")
    .on("hidden.bs.modal", () => {
      $("#confirmModal").removeClass("accessExternalURLModal");
      $("#confirmModalBody").removeClass("white-space-pre-line");
      $("#" + ACCESS_URL_MODAL_STRING_ID).remove();
    });
  $("#modalRedirect").hide();
  $("#modalRedirect").hideClass();
}
