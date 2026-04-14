import { createAccessLinkBtn } from "./access-btn.js";
import { createCopyURLBtn } from "./copy-btn.js";
import { createEditURLBtn } from "./edit-string-btn.js";
import { createDeleteURLBtn } from "./delete-btn.js";
import { createAddTagBtn } from "./tag-btn.js";
import { $ } from "../../../../lib/globals.js";
import type { UtubUrlItem } from "../../../../types/url.js";

/**
 * Create all the buttons necessary for a URL card
 */
export function createURLOptionsButtons(
  url: UtubUrlItem,
  urlCard: JQuery,
  utubID: number,
): JQuery<HTMLElement> {
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
