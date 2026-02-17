import { $ } from "../../../lib/globals.js";
import { SHOW_LOADING_ICON_AFTER_MS } from "../../../lib/constants.js";

function showURLCardLoadingIcon(urlCard) {
  urlCard.find(".urlCardDualLoadingRing").addClass("dual-loading-ring");
}

function hideURLCardLoadingIcon(urlCard) {
  urlCard.find(".urlCardDualLoadingRing").removeClass("dual-loading-ring");
}

export function setTimeoutAndShowURLCardLoadingIcon(urlCard) {
  const timeoutID = setTimeout(function () {
    showURLCardLoadingIcon(urlCard);
  }, SHOW_LOADING_ICON_AFTER_MS);
  return timeoutID;
}

export function clearTimeoutIDAndHideLoadingIcon(timeoutID, urlCard) {
  clearTimeout(timeoutID);
  hideURLCardLoadingIcon(urlCard);
}
