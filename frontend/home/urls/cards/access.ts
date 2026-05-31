import { $ } from "../../../lib/globals.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { emit } from "../../../lib/metrics-client.js";

import { UI_EVENTS } from "../../../lib/metrics-events.js";
const ACCESS_URL_MODAL_STRING_ID = "AccessURLModalURLString";

let _wasSubmitted: boolean = false;

// Opens new tab
export function accessLink(urlString: string): void {
  // Still need to implement: Take user to a new tab with interstitial page warning they are now leaving U4I
  if (urlString.startsWith("http")) {
    window.open(urlString, "_blank")?.focus();
    return;
  }

  // For all non-http or non-https URLs, show a warning modal.
  accessURLWarningShowModal(urlString);
}

// Hide confirmation modal for removal of the selected URL
function accessURLHideModal(): void {
  $("#confirmModal").modal("hide").removeClass("accessExternalURLModal");
  $("#confirmModalBody").removeClass("white-space-pre-line");
  $("#" + ACCESS_URL_MODAL_STRING_ID).remove();
}

function urlStringInAccessModal(urlString: string): JQuery<HTMLElement> {
  const urlSpan = $(document.createElement("strong"));
  urlSpan.attr("id", ACCESS_URL_MODAL_STRING_ID).text(urlString);

  return urlSpan;
}

// Show confirmation modal for removal of the selected existing URL from current UTub
function accessURLWarningShowModal(urlString: string): void {
  _wasSubmitted = false;
  emit({ event: UI_EVENTS.UI_URL_ACCESS_WARNING });

  const modalTitle = "🚦 Caution! 🚦";
  const modalText = `${APP_CONFIG.strings.ACCESS_URL_WARNING}\n\n`;
  const buttonTextDismiss = "Nevermind";
  const buttonTextSubmit = "Let's go!";

  $("#confirmModalTitle").text(modalTitle);
  $("#confirmModalBody")
    .text(modalText)
    .addClass("white-space-pre-line")
    .append(urlStringInAccessModal(urlString));

  $("#modalDismiss")
    .offAndOn("click", function (event: JQuery.TriggeredEvent) {
      event.preventDefault();
      accessURLHideModal();
    })
    .text(buttonTextDismiss);

  $("#modalSubmit")
    .offAndOn("click", function (event: JQuery.TriggeredEvent) {
      event.preventDefault();
      _wasSubmitted = true;
      window.open(urlString, "_blank")?.focus();
    })
    .text(buttonTextSubmit);

  // Cleanup runs unconditionally on every dismiss; the dismiss emit is gated
  // by !_wasSubmitted so a successful "Let's go!" does not double-count as a
  // dismiss. offAndOnExact rebinds without accumulation across repeat opens.
  $("#confirmModal").addClass("accessExternalURLModal").modal("show");
  $("#confirmModal").offAndOnExact(
    "hidden.bs.modal.accessWarning",
    function () {
      $("#" + ACCESS_URL_MODAL_STRING_ID).remove();
      $("#confirmModalBody").removeClass("white-space-pre-line");
      $("#confirmModal").removeClass("accessExternalURLModal");
      if (!_wasSubmitted) {
        emit({ event: UI_EVENTS.UI_URL_ACCESS_WARNING_DISMISS });
      }
    },
  );
  $("#modalRedirect").hide();
  $("#modalRedirect").hideClass();
}
