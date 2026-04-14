import type { UtubTag } from "../../../types/url.js";

import { $ } from "../../../lib/globals.js";
import { KEYS } from "../../../lib/constants.js";
import { createURLTag, hideAndResetCreateURLTagForm } from "./create.js";
import { deleteURLTag } from "./delete.js";

/**
 * Hide tag deletion button when needed
 */
export function disableTagRemovalInURLCard(urlCard: JQuery): void {
  const allTagsDelBtns = urlCard.find(".urlTagBtnDelete");
  for (
    let delBtnIndex = 0;
    delBtnIndex < allTagsDelBtns.length;
    delBtnIndex++
  ) {
    $(allTagsDelBtns[delBtnIndex]).addClass("hidden");
  }
}

/**
 * Show tag deletion when needed
 */
export function enableTagRemovalInURLCard(urlCard: JQuery): void {
  const allTagsDelBtns = urlCard.find(".urlTagBtnDelete");
  for (
    let delBtnIndex = 0;
    delBtnIndex < allTagsDelBtns.length;
    delBtnIndex++
  ) {
    $(allTagsDelBtns[delBtnIndex]).removeClass("hidden");
  }
}

export function isTagInURL(utubTagID: number, urlCard: JQuery): boolean {
  return (
    urlCard.find(
      ".urlTagsContainer > .tagBadge[data-utub-tag-id=" + utubTagID + "]",
    ).length > 0
  );
}

/**
 * Create the outer container for the tag badges
 */
export function createTagBadgesAndWrap(
  dictTags: UtubTag[],
  tagArray: number[],
  urlCard: JQuery,
  utubID: number,
): JQuery<HTMLElement> {
  const tagBadgesWrap = $(document.createElement("div")).addClass(
    "urlTagsContainer flex-row flex-start",
  );

  for (const tagArrayIndex in tagArray) {
    // Find applicable tags in dictionary to apply to URL card
    const tag = dictTags.find(function (candidateTag) {
      if (candidateTag.id === tagArray[tagArrayIndex]) {
        return candidateTag;
      }
    });

    if (!tag) continue;

    const tagSpan = createTagBadgeInURL(tag.id, tag.tagString, urlCard, utubID);

    $(tagBadgesWrap).append(tagSpan);
  }

  return tagBadgesWrap;
}

export function setFocusEventListenersOnCreateURLTagInput(
  urlTagInput: JQuery,
  urlCard: JQuery,
  utubID: number,
): void {
  urlTagInput.offAndOn("focus.createURLTagFocus", function () {
    $(document).offAndOn(
      "keyup.createURLTagFocus",
      function (keyupEvent: JQuery.TriggeredEvent) {
        switch (keyupEvent.key) {
          case KEYS.ENTER:
            // Handle enter key pressed
            createURLTag(urlTagInput, urlCard, utubID);
            break;
          case KEYS.ESCAPE:
            // Handle escape key pressed
            hideAndResetCreateURLTagForm(urlCard);
            break;
          default:
          /* no-op */
        }
      },
    );
  });

  urlTagInput.offAndOn("blur.createURLTagFocus", function () {
    $(document).off("keyup.createURLTagFocus");
  });
}

/**
 * Handle URL deck display changes related to creating a new tag
 */
export function createTagBadgeInURL(
  utubTagID: number,
  tagString: string,
  urlCard: JQuery,
  utubID: number,
): JQuery<HTMLElement> {
  const tagSpan = $(document.createElement("span"));
  const removeButton = $(document.createElement("button"));
  const tagText = $(document.createElement("span"))
    .addClass("tagText")
    .text(tagString);

  tagSpan
    .addClass(
      "tagBadge tagBadgeHoverable flex-row-reverse align-center justify-flex-end",
    )
    .attr({ "data-utub-tag-id": utubTagID });

  removeButton
    .addClass("urlTagBtnDelete flex-row align-center pointerable tabbable")
    .onExact("click", function () {
      deleteURLTag(utubTagID, tagSpan, urlCard, utubID);
    });

  removeButton.append(createTagDeleteIcon());

  $(tagSpan).append(removeButton).append(tagText);

  return tagSpan;
}

/**
 * Dynamically generates the delete URL-Tag icon when needed
 */
export function createTagDeleteIcon(pixelSize: number = 15): JQuery<Element> {
  const WIDTH_HEIGHT_PX = pixelSize + "px";
  const SVG_NS = "http://www.w3.org/2000/svg";
  const deleteURLTagOuterIconSvg = $(document.createElementNS(SVG_NS, "svg"));
  const deleteURLTagInnerIconPath = $(document.createElementNS(SVG_NS, "path"));
  const path =
    "M11.46.146A.5.5 0 0 0 11.107 0H4.893a.5.5 0 0 0-.353.146L.146 4.54A.5.5 0 0 0 0 4.893v6.214a.5.5 0 0 0 .146.353l4.394 4.394a.5.5 0 0 0 .353.146h6.214a.5.5 0 0 0 .353-.146l4.394-4.394a.5.5 0 0 0 .146-.353V4.893a.5.5 0 0 0-.146-.353zm-6.106 4.5L8 7.293l2.646-2.647a.5.5 0 0 1 .708.708L8.707 8l2.647 2.646a.5.5 0 0 1-.708.708L8 8.707l-2.646 2.647a.5.5 0 0 1-.708-.708L7.293 8 4.646 5.354a.5.5 0 1 1 .708-.708";

  deleteURLTagInnerIconPath.attr({
    d: path,
  });

  deleteURLTagOuterIconSvg
    .attr({
      xmlns: SVG_NS,
      width: WIDTH_HEIGHT_PX,
      height: WIDTH_HEIGHT_PX,
      fill: "currentColor",
      class: "bi bi-x-octagon-fill",
      viewBox: "0 0 16 16",
    })
    .append(deleteURLTagInnerIconPath);

  return deleteURLTagOuterIconSvg;
}
