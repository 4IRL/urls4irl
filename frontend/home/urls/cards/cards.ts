import { $ } from "../../../lib/globals.js";
import { KEYS } from "../../../lib/constants.js";
import type { UtubTag, UtubUrlItem } from "../../../types/url.js";
import {
  selectURLCard,
  setURLCardSelectionEventListener,
} from "./selection.js";
import { createGoToURLIcon } from "./corner-access.js";
import { createURLTitle, createURLTitleAndUpdateBlock } from "./url-title.js";
import {
  createURLString,
  createURLStringAndUpdateBlock,
} from "./url-string.js";
import { createTagBadgeInURL, createTagBadgesAndWrap } from "../tags/tags.js";
import { createTagInputBlock } from "../tags/create.js";
import { createURLOptionsButtons } from "./options/btns.js";
import {
  createURL,
  createURLHideInput,
  bindCreateURLFocusEventListeners,
  unbindCreateURLFocusEventListeners,
  resetCreateURLFailErrors,
} from "./create.js";

export function updateURLAfterFindingStaleData(
  urlCard: JQuery,
  newUrl: UtubUrlItem,
  updatedUTubTags: UtubTag[],
  utubID: number,
): void {
  const urlTitle = urlCard.find(".urlTitle");
  const urlString = urlCard.find(".urlString");

  if (urlTitle.text() !== newUrl.urlTitle) {
    urlTitle.text(newUrl.urlTitle);
  }

  if (urlString.attr("href") !== newUrl.urlString) {
    urlString.text(newUrl.urlString).attr({ href: newUrl.urlString });
  }

  const currentURLTags = urlCard.find(".tagBadge");
  const currentURLTagIDs = $.map(currentURLTags, (tag) =>
    parseInt($(tag).attr("data-utub-tag-id")!),
  );

  // Find tag IDs that are in old and not in new and remove them
  for (
    let currentTagIndex = 0;
    currentTagIndex < currentURLTagIDs.length;
    currentTagIndex++
  ) {
    if (!newUrl.utubUrlTagIDs.includes(currentURLTagIDs[currentTagIndex])) {
      currentURLTags.each(function (_, tag) {
        if (
          parseInt($(tag).attr("data-utub-tag-id")!) ===
          currentURLTagIDs[currentTagIndex]
        ) {
          $(tag).remove();
          return false;
        }
      });
    }
  }

  // Find tag IDs that are in new and not old and add them
  const urlTagContainer = urlCard.find(".urlTagsContainer");
  let tagToAdd: UtubTag | undefined;
  for (
    let newTagIndex = 0;
    newTagIndex < newUrl.utubUrlTagIDs.length;
    newTagIndex++
  ) {
    if (!currentURLTagIDs.includes(newUrl.utubUrlTagIDs[newTagIndex])) {
      tagToAdd = updatedUTubTags.find(
        (tag) => tag.id === newUrl.utubUrlTagIDs[newTagIndex],
      );
      if (tagToAdd) {
        urlTagContainer.append(
          createTagBadgeInURL(tagToAdd.id, tagToAdd.tagString, urlCard, utubID),
        );
      }
    }
  }
}

// Create a URL block to add to current UTub/URLDeck
export function createURLBlock(
  url: UtubUrlItem,
  dictTags: UtubTag[],
  utubID: number,
): JQuery<HTMLElement> {
  const urlCard = $(document.createElement("div"))
    .addClass("urlRow flex-column full-width pad-in-15p pointerable")
    .enableTab(); // Holds everything in the URL

  const urlTitleGoToURLWrap = $(document.createElement("div")).addClass(
    "flex-row full-width align-center jc-sb",
  );

  // Append update URL title form if user can edit the URL
  if (url.canDelete) {
    urlTitleGoToURLWrap.append(
      createURLTitleAndUpdateBlock(url.urlTitle, urlCard, utubID),
    );
  } else {
    urlTitleGoToURLWrap.append(createURLTitle(url.urlTitle));
  }

  urlTitleGoToURLWrap.append(createGoToURLIcon(url.urlString));

  urlCard.append(urlTitleGoToURLWrap).attr({
    utubUrlID: url.utubUrlID,
    urlSelected: false,
    filterable: true,
    "data-utub-url-tag-ids": url.utubUrlTagIDs.join(","),
  });

  // Append update URL form if user can edit the URL
  if (url.canDelete) {
    urlCard.append(
      createURLStringAndUpdateBlock(url.urlString, urlCard, utubID),
    );
  } else {
    urlCard.append(createURLString(url.urlString));
  }

  urlCard.append(
    createTagsAndOptionsForUrlBlock(url, dictTags, urlCard, utubID),
  );

  setURLCardSelectionEventListener(urlCard);
  setFocusEventListenersOnURLCard(urlCard);

  return urlCard;
}

// Add focus and blur on URL card when tabbing through URLs
export function setFocusEventListenersOnURLCard(urlCard: JQuery): void {
  const utubUrlID = urlCard.attr("utuburlid");
  urlCard.offAndOn("focus.focusURLCard" + utubUrlID, function () {
    urlCard.find(".goToUrlIcon").addClass("visible-on-focus");
    $(document).on(
      "keyup.focusURLCard" + utubUrlID,
      function (event: JQuery.TriggeredEvent) {
        if (event.key === KEYS.ENTER) {
          selectURLCard(urlCard);
          urlCard.trigger("focusout");
        }
      },
    );
  });

  urlCard.offAndOn(
    "focusout.focusURLCard" + utubUrlID,
    function (event: JQuery.TriggeredEvent) {
      const target = $(event.target);
      if (target.closest(".urlRow").is(urlCard)) {
        if (target.hasClass("goToUrlIcon")) {
          urlCard.find(".goToUrlIcon").removeClass("visible-on-focus");
        }
        $(document).off("keyup.focusURLCard" + utubUrlID);
      }
    },
  );
}

// Create both the tag container and the button container for a URL
function createTagsAndOptionsForUrlBlock(
  url: UtubUrlItem,
  dictTags: UtubTag[],
  urlCard: JQuery,
  utubID: number,
): JQuery<HTMLElement> {
  const tagsAndButtonsWrap = $(document.createElement("div")).addClass(
    "tagsAndButtonsWrap full-width",
  );
  const tagsAndTagCreateWrap = $(document.createElement("div")).addClass(
    "urlTags flex-column",
  );
  const tagBadgesWrap = createTagBadgesAndWrap(
    dictTags,
    url.utubUrlTagIDs,
    urlCard,
    utubID,
  );

  tagsAndButtonsWrap.append(tagsAndTagCreateWrap);
  tagsAndTagCreateWrap.append(tagBadgesWrap);

  tagsAndTagCreateWrap.append(createTagInputBlock(urlCard, utubID));

  tagsAndButtonsWrap.append(createURLOptionsButtons(url, urlCard, utubID));

  return tagsAndButtonsWrap;
}

// New URL card and input text fields. Initially hidden, shown when create URL is requested. Input field recreated here to ensure at the end of list after creation of new URL
export function newURLInputAddEventListeners(
  urlInputForm: JQuery,
  utubID: number,
): void {
  const urlBtnCreate = urlInputForm.find("#urlSubmitBtnCreate");
  const urlBtnDelete = urlInputForm.find("#urlCancelBtnCreate");
  const createURLTitleInput = urlInputForm.find("#urlTitleCreate");
  const createURLInput = urlInputForm.find("#urlStringCreate");

  $(urlBtnCreate).onExact("click.createURL", function () {
    createURL(createURLTitleInput, createURLInput, utubID);
  });

  $(urlBtnDelete).onExact("click.createURL", function () {
    createURLHideInput();
  });

  const inputArr = [createURLInput, createURLTitleInput];

  for (let inputIndex = 0; inputIndex < inputArr.length; inputIndex++) {
    $(inputArr[inputIndex]).on("focus.createURL", function () {
      bindCreateURLFocusEventListeners(
        $(inputArr[inputIndex]),
        createURLInput,
        createURLTitleInput,
        utubID,
      );
    });

    $(inputArr[inputIndex]).on("blur.createURL", function () {
      unbindCreateURLFocusEventListeners($(inputArr[inputIndex]));
    });
  }
}

export function newURLInputRemoveEventListeners(): void {
  resetCreateURLFailErrors();
  $("#urlSubmitBtnCreate").off();
  $("#urlCancelBtnCreate").off();
  $(document).off(".createURL");
  $("#urlTitleCreate").off(".createURL");
  $("#urlStringCreate").off(".createURL");
}
