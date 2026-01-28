"use strict";

function updateURLAfterFindingStaleData(
  urlCard,
  newUrl,
  updatedUTubTags,
  utubID,
) {
  const urlTitle = urlCard.find(".urlTitle");
  const urlString = urlCard.find(".urlString");

  urlTitle.text() !== newUrl.urlTitle ? urlTitle.text(newUrl.urlTitle) : null;

  urlString.attr("href") !== newUrl.urlString
    ? urlString.text(newUrl.urlString).attr({ href: newUrl.urlString })
    : null;

  const currentURLTags = urlCard.find(".tagBadge");
  const currentURLTagIDs = $.map(currentURLTags, (tag) =>
    parseInt($(tag).attr("data-utub-tag-id")),
  );

  // Find tag IDs that are in old and not in new and remove them
  for (let i = 0; i < currentURLTagIDs.length; i++) {
    if (!newUrl.utubUrlTagIDs.includes(currentURLTagIDs[i])) {
      currentURLTags.each(function (_, tag) {
        if (parseInt($(tag).attr("data-utub-tag-id")) === currentURLTagIDs[i]) {
          $(tag).remove();
          return false;
        }
      });
    }
  }

  // Find tag IDs that are in new and not old and add them
  const urlTagContainer = urlCard.find(".urlTagsContainer");
  let tagToAdd;
  for (let i = 0; i < newUrl.utubUrlTagIDs.length; i++) {
    if (!currentURLTagIDs.includes(newUrl.utubUrlTagIDs[i])) {
      tagToAdd = updatedUTubTags.find(
        (tag) => tag.id === newUrl.utubUrlTagIDs[i],
      );
      urlTagContainer.append(
        createTagBadgeInURL(tagToAdd.id, tagToAdd.tagString, urlCard, utubID),
      );
    }
  }
}

// Create a URL block to add to current UTub/URLDeck
function createURLBlock(url, tagArray, utubID) {
  const urlCard = $(document.createElement("div"))
    .addClass("urlRow flex-column full-width pad-in-15p pointerable")
    .enableTab(); // Holds everything in the URL

  const urlTitleGoToURLWrap = $(document.createElement("div")).addClass(
    "flex-row full-width align-center jc-sb",
  );

  // Append update URL title form if user can edit the URL
  url.canDelete
    ? urlTitleGoToURLWrap.append(
        createURLTitleAndUpdateBlock(url.urlTitle, urlCard, utubID),
      )
    : urlTitleGoToURLWrap.append(createURLTitle(url.urlTitle));

  urlTitleGoToURLWrap.append(createGoToURLIcon(url.urlString));

  urlCard.append(urlTitleGoToURLWrap).attr({
    utubUrlID: url.utubUrlID,
    urlSelected: false,
    filterable: true,
    "data-utub-url-tag-ids": url.utubUrlTagIDs.join(","),
  });

  // Append update URL form if user can edit the URL
  url.canDelete
    ? urlCard.append(
        createURLStringAndUpdateBlock(url.urlString, urlCard, utubID),
      )
    : urlCard.append(createURLString(url.urlString));

  urlCard.append(
    createTagsAndOptionsForUrlBlock(url, tagArray, urlCard, utubID),
  );

  setURLCardSelectionEventListener(urlCard);
  setFocusEventListenersOnURLCard(urlCard);

  return urlCard;
}

// Add focus and blur on URL card when tabbing through URLs
function setFocusEventListenersOnURLCard(urlCard) {
  const utubUrlID = urlCard.attr("utuburlid");
  urlCard.offAndOn("focus.focusURLCard" + utubUrlID, function () {
    urlCard.find(".goToUrlIcon").addClass("visible-on-focus");
    $(document).on("keyup.focusURLCard" + utubUrlID, function (e) {
      if (e.key === KEYS.ENTER) {
        selectURLCard(urlCard);
        urlCard.trigger("focusout");
      }
    });
  });

  urlCard.offAndOn("focusout.focusURLCard" + utubUrlID, function (e) {
    const target = $(e.target);
    if (target.closest(".urlRow").is(urlCard)) {
      if (target.hasClass("goToUrlIcon")) {
        urlCard.find(".goToUrlIcon").removeClass("visible-on-focus");
      }
      $(document).off("keyup.focusURLCard" + utubUrlID);
    }
  });
}

// Create both the tag container and the button container for a URL
function createTagsAndOptionsForUrlBlock(url, tagArray, urlCard, utubID) {
  const tagsAndButtonsWrap = $(document.createElement("div")).addClass(
    "tagsAndButtonsWrap full-width",
  );
  const tagsAndTagCreateWrap = $(document.createElement("div")).addClass(
    "urlTags flex-column",
  );
  const tagBadgesWrap = createTagBadgesAndWrap(
    tagArray,
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
function newURLInputAddEventListeners(urlInputForm, utubID) {
  const urlBtnCreate = urlInputForm.find("#urlSubmitBtnCreate");
  const urlBtnDelete = urlInputForm.find("#urlCancelBtnCreate");
  const createURLTitleInput = urlInputForm.find("#urlTitleCreate");
  const createURLInput = urlInputForm.find("#urlStringCreate");

  $(urlBtnCreate).onExact("click.createURL", function (e) {
    createURL(createURLTitleInput, createURLInput, utubID);
  });

  $(urlBtnDelete).onExact("click.createURL", function (e) {
    createURLHideInput();
  });

  const inputArr = [createURLInput, createURLTitleInput];

  for (let i = 0; i < inputArr.length; i++) {
    $(inputArr[i]).on("focus.createURL", function () {
      bindCreateURLFocusEventListeners(
        $(inputArr[i]),
        createURLInput,
        createURLTitleInput,
        utubID,
      );
    });

    $(inputArr[i]).on("blur.createURL", function () {
      unbindCreateURLFocusEventListeners($(inputArr[i]));
    });
  }
}

function newURLInputRemoveEventListeners() {
  resetCreateURLFailErrors();
  $("#urlSubmitBtnCreate").off();
  $("#urlCancelBtnCreate").off();
  $(document).off(".createURL");
  $("#urlTitleCreate").off(".createURL");
  $("#urlStringCreate").off(".createURL");
}
