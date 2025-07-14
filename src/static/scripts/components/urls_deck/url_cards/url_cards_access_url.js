"use strict";

// Opens new tab
function accessLink(urlString, accessLinkBtn) {
  // Still need to implement: Take user to a new tab with interstitial page warning they are now leaving U4I
  if (urlString != null && !urlString.startsWith("https://")) {
    window.open("https://" + urlString, "_blank").focus();
  } else {
    window.open(urlString, "_blank").focus();
  }
}
