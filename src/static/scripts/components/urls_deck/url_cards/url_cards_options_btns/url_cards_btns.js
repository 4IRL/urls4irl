"use strict";

// Create all the buttons necessary for a url card
function createURLOptionsButtons(url, urlCard, utubID) {
  const urlOptions = $(document.createElement("div")).addClass(
    "urlOptions justify-content-start flex-row gap-15p",
  );

  urlOptions
    .append(createAccessLinkBtn(url))
    .append(createAddTagBtn(urlCard))
    .append(createCopyURLBtn(url));

  if (url.canDelete) {
    urlOptions
      .append(createEditURLBtn(urlCard))
      .append(createDeleteURLBtn(url, urlCard, utubID));
  }

  const urlCardLoadingIcon = $(document.createElement("div")).addClass(
    "urlCardDualLoadingRing",
  );
  urlOptions.append(urlCardLoadingIcon);

  return urlOptions;
}
