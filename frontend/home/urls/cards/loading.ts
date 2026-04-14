import { SHOW_LOADING_ICON_AFTER_MS } from "../../../lib/constants.js";

function showURLCardLoadingIcon(urlCard: JQuery): void {
  urlCard.find(".urlCardDualLoadingRing").addClass("dual-loading-ring");
}

function hideURLCardLoadingIcon(urlCard: JQuery): void {
  urlCard.find(".urlCardDualLoadingRing").removeClass("dual-loading-ring");
}

export function setTimeoutAndShowURLCardLoadingIcon(urlCard: JQuery): number {
  const timeoutID = setTimeout(function () {
    showURLCardLoadingIcon(urlCard);
  }, SHOW_LOADING_ICON_AFTER_MS);
  return timeoutID;
}

export function clearTimeoutIDAndHideLoadingIcon(
  timeoutID: number,
  urlCard: JQuery,
): void {
  clearTimeout(timeoutID);
  hideURLCardLoadingIcon(urlCard);
}
