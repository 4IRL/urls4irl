"use strict";

function updateURLAfterFindingStaleData(urlCard, newUrl, updatedUTubTags) {
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
        createTagBadgeInURL(tagToAdd.id, tagToAdd.tagString, urlCard),
      );
    }
  }
}

// Create a URL block to add to current UTub/URLDeck
function createURLBlock(url, tagArray) {
  const urlCard = $(document.createElement("div"))
    .addClass("urlRow flex-column full-width pad-in-15p pointerable")
    .enableTab(); // Holds everything in the URL

  const urlTitleGoToURLWrap = $(document.createElement("div")).addClass(
    "flex-row full-width align-center justify-space-between",
  );

  // Append update URL title form if user can edit the URL
  url.canDelete
    ? urlTitleGoToURLWrap.append(
        createURLTitleAndUpdateBlock(url.urlTitle, urlCard),
      )
    : urlTitleGoToURLWrap.append(createURLTitle(url.urlTitle));

  urlTitleGoToURLWrap.append(createGoToURLIcon(url.urlString));

  urlCard.append(urlTitleGoToURLWrap).attr({
    utubUrlID: url.utubUrlID,
    urlSelected: false,
    filterable: true,
  });

  // Append update URL form if user can edit the URL
  url.canDelete
    ? urlCard.append(createURLStringAndUpdateBlock(url.urlString, urlCard))
    : urlCard.append(createURLString(url.urlString));

  urlCard.append(createTagsAndOptionsForUrlBlock(url, tagArray, urlCard));

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
      if (e.which === 13) {
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
function createTagsAndOptionsForUrlBlock(url, tagArray, urlCard) {
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
  );

  tagsAndButtonsWrap.append(tagsAndTagCreateWrap);
  tagsAndTagCreateWrap.append(tagBadgesWrap);

  tagsAndTagCreateWrap.append(createTagInputBlock(urlCard));

  tagsAndButtonsWrap.append(createURLOptionsButtons(url, urlCard));

  return tagsAndButtonsWrap;
}

// Create all the buttons necessary for a url card
function createURLOptionsButtons(url, urlCard) {
  const urlOptions = $(document.createElement("div")).addClass(
    "urlOptions justify-content-start",
  );
  const urlBtnAccess = $(document.createElement("button"));
  const urlTagBtnCreate = $(document.createElement("button"));

  const accessAndTagBtns = $(document.createElement("div")).addClass(
    "urlOptionsInner flex-row justify-content-start gap-15p",
  );

  // Access the URL button
  urlBtnAccess
    .addClass("btn btn-primary urlBtnAccess tabbable")
    .attr({ type: "button" })
    .text("Access Link")
    .disableTab()
    .on("click", function (e) {
      e.stopPropagation();
      accessLink(url.urlString);
    });

  // Add a tag button
  urlTagBtnCreate
    .addClass("btn btn-info urlTagBtnCreate tabbable")
    .attr({ type: "button" })
    .text("Add Tag")
    .disableTab()
    .on("click", function (e) {
      e.stopPropagation();
      showCreateURLTagForm(urlCard, urlTagBtnCreate);
    })
    .on("focus", function (e) {
      if ($(e.target).hasClass("cancel")) return;
      $(document).on("keyup.showURLTagCreate", function (e) {
        if (e.which === 13) showCreateURLTagForm(urlCard, urlTagBtnCreate);
      });
    })
    .on("blur", function () {
      $(document).off("keyup.showURLTagCreate");
    });

  accessAndTagBtns.append(urlBtnAccess).append(urlTagBtnCreate);
  urlOptions.append(accessAndTagBtns);

  if (url.canDelete) {
    const urlStringBtnUpdate = $(document.createElement("button"));
    const urlBtnDelete = $(document.createElement("button"));
    const urlUpdateAndDeleteBtns = $(document.createElement("div")).addClass(
      "urlOptionsInner flex-row justify-content-start gap-15p",
    );
    urlBtnDelete
      .addClass("btn btn-danger urlBtnDelete tabbable")
      .attr({ type: "button" })
      .text("Delete")
      .disableTab()
      .on("click", function (e) {
        e.stopPropagation();
        deleteURLShowModal(url.utubUrlID, urlCard);
      });

    urlStringBtnUpdate
      .addClass("btn btn-light urlStringBtnUpdate tabbable")
      .attr({ type: "button" })
      .text("Edit URL")
      .disableTab()
      .on("click", function (e) {
        e.stopPropagation();
        showUpdateURLStringForm(urlCard, urlStringBtnUpdate);
      });

    urlUpdateAndDeleteBtns.append(urlStringBtnUpdate).append(urlBtnDelete);
    urlOptions.append(urlUpdateAndDeleteBtns);
  }
  const urlCardLoadingIcon = $(document.createElement("div")).addClass(
    "urlCardDualLoadingRing",
  );
  urlOptions.append(urlCardLoadingIcon);

  return urlOptions;
}

// New URL card and input text fields. Initially hidden, shown when create URL is requested. Input field recreated here to ensure at the end of list after creation of new URL
function newURLInputAddEventListeners(urlInputForm) {
  const urlBtnCreate = urlInputForm.find("#urlSubmitBtnCreate");
  const urlBtnDelete = urlInputForm.find("#urlCancelBtnCreate");
  const createURLTitleInput = urlInputForm.find("#urlTitleCreate");
  const createURLInput = urlInputForm.find("#urlStringCreate");

  $(urlBtnCreate).on("click.createURL", function (e) {
    e.stopPropagation();
    createURL(createURLTitleInput, createURLInput);
  });

  $(urlBtnDelete).on("click.createURL", function (e) {
    if ($(e.target).closest(urlBtnDelete).length > 0) createURLHideInput();
  });

  const inputArr = [createURLInput, createURLTitleInput];

  for (let i = 0; i < inputArr.length; i++) {
    $(inputArr[i]).on("focus.createURL", function () {
      bindCreateURLFocusEventListeners(createURLTitleInput, createURLInput);
    });

    $(inputArr[i]).on("blur.createURL", function () {
      unbindCreateURLFocusEventListeners();
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
