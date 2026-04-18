import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { getNumOfURLs, getNumOfVisibleURLs } from "./utils.js";
import { accessLink } from "./cards/access.js";

function hideAccessAllWarningShowModal(): void {
  $("#confirmModal").removeClass("accessAllUrlModal");
}

// Show confirmation modal for opening all URLs in UTub
function accessAllWarningShowModal(): void {
  const modalTitle =
    "Are you sure you want to open all " +
    getNumOfURLs() +
    " URLs in this UTub?";
  const modalText = "Performance issues may occur.";
  const modalDismiss = "Cancel";

  $("#confirmModalTitle").text(modalTitle);
  $("#confirmModalBody").text(modalText);

  $("#modalDismiss")
    .on("click", function (event: JQuery.TriggeredEvent) {
      event.preventDefault();
      $("#confirmModal").modal("hide");
    })
    .removeClass()
    .addClass("btn btn-danger")
    .text(modalDismiss);

  $("#modalSubmit")
    .removeClass()
    .addClass("btn btn-success")
    .on("click", function (event: JQuery.TriggeredEvent) {
      event.preventDefault();
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
function accessAllURLsInUTub(): void {
  const visibleSelector = ".urlRow[filterable=true] .urlString";
  const visibleURLs = $(visibleSelector);
  if (visibleURLs.length === 0) return;

  const visibleURLsToAccess = $.map(visibleURLs.toArray(), (url: HTMLElement) =>
    $(url).attr("href"),
  ).filter((href): href is string => href !== undefined);

  for (const href of visibleURLsToAccess) {
    accessLink(href);
  }
}

export function initAccessAllURLsBtn(): void {
  // Open all URLs in UTub in separate tabs
  $("#accessAllURLsBtn").on("click", function () {
    const ACCESS_ALL_URLS_LIMIT_WARNING =
      APP_CONFIG.constants.MAX_NUM_OF_URLS_TO_ACCESS;
    if (getNumOfVisibleURLs() > ACCESS_ALL_URLS_LIMIT_WARNING) {
      accessAllWarningShowModal();
    } else {
      accessAllURLsInUTub();
    }
  });
}
