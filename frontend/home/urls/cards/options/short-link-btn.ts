import { $ } from "../../../../lib/globals.js";
import { applyHoverTooltip } from "../../../../lib/tooltips.js";
import { copyShortLink } from "../short-link.js";
import { shortLinkTooltipTitle } from "../short-link-state.js";
import { createShortLinkIcon } from "./short-link-icon.js";
import type { UtubUrlItem } from "../../../../types/url.js";

/**
 * The "Copy short link" button. Rendered for every member (not behind
 * `canDelete`); making or reusing the link is open to any UTub member.
 */
export function createShortLinkBtn({
  url,
  urlCard,
  utubID,
}: {
  url: UtubUrlItem;
  urlCard: JQuery;
  utubID: number;
}): JQuery<HTMLElement> {
  const urlBtnShortLink = $(document.createElement("button"));

  urlBtnShortLink
    .addClass(
      "btn btn-info urlBtnShortLink tabbable flex-column flex-center justify-center fourty-p-width fourty-p-height",
    )
    .attr({ type: "button" })
    .append(createShortLinkIcon({ sizePx: 18 }));

  // Sets the aria-label as well as the desktop hover tooltip. A card that already
  // has a link shows its expiry; short-link.ts keeps it current afterwards.
  applyHoverTooltip({
    btn: urlBtnShortLink,
    tooltip: {
      title: shortLinkTooltipTitle({ expiresAt: url.shortLinkExpiresAt }),
      customClass: "urlBtnShortLink-tooltip",
    },
  });

  // Native `<button>`s already fire click on Enter/Space.
  urlBtnShortLink.disableTab().onExact("click", function () {
    void copyShortLink({
      button: urlBtnShortLink,
      urlCard,
      utubID,
      utubUrlID: url.utubUrlID,
    });
  });

  return urlBtnShortLink;
}
