"use strict";

function showURLCardLoadingIcon(urlCard) {
  urlCard.find(".urlCardDualLoadingRing").addClass("dual-loading-ring");
}

function hideURLCardLoadingIcon(urlCard) {
  urlCard.find(".urlCardDualLoadingRing").removeClass("dual-loading-ring");
}

function setTimeoutAndShowURLCardLoadingIcon(urlCard) {
  const timeoutID = setTimeout(function () {
    showURLCardLoadingIcon(urlCard);
  }, SHOW_LOADING_ICON_AFTER_MS);
  return timeoutID;
}

function clearTimeoutIDAndHideLoadingIcon(timeoutID, urlCard) {
  clearTimeout(timeoutID);
  hideURLCardLoadingIcon(urlCard);
}
