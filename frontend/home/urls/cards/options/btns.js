import { createAccessLinkBtn } from "./access-btn.js";
import { createCopyURLBtn } from "./copy-btn.js";
import { createEditURLBtn } from "./edit-string-btn.js";
import { createDeleteURLBtn } from "./delete-btn.js";
import { createAddTagBtn } from "./tag-btn.js";
import { $ } from "../../../../lib/globals.js";

/**
 * Create all the buttons necessary for a URL card
 * @param {Object} url - URL data object
 * @param {jQuery} urlCard - URL card element
 * @param {number} utubID - UTub ID
 * @returns {jQuery} urlOptions element with all buttons
 */
export function createURLOptionsButtons(url, urlCard, utubID) {
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
