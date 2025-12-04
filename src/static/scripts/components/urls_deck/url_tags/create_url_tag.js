"use strict";

function createTagInputBlock(urlCard, utubID) {
  const urlTagCreateTextInputContainer = makeTextInput(
    "urlTag",
    METHOD_TYPES.CREATE.description,
  ).addClass("createUrlTagWrap hidden");

  urlTagCreateTextInputContainer.find("label").text("Tag");

  // Customize the input text box for the Url title
  const urlTagTextInput = urlTagCreateTextInputContainer
    .find("input")
    .prop("minLength", CONSTANTS.TAGS_MIN_LENGTH)
    .prop("maxLength", CONSTANTS.TAGS_MAX_LENGTH);

  setFocusEventListenersOnCreateURLTagInput(urlTagTextInput, urlCard, utubID);

  // Create Url Title submit button
  const urlTagSubmitBtnCreate = makeSubmitButton(30).addClass(
    "urlTagSubmitBtnCreate",
  );

  urlTagSubmitBtnCreate
    .find(".submitButton")
    .on("click.createURLTag", function () {
      createURLTag(urlTagTextInput, urlCard, utubID);
    })
    .on("focus.createURLTag", function () {
      $(document).on("keyup.createURLTag", function (e) {
        if (e.key === KEYS.ENTER)
          createURLTag(urlTagTextInput, urlCard, utubID);
      });
    })
    .on("blur.createURLTag", function () {
      $(document).off("keyup.createURLTag");
    });

  // Create Url Title cancel button
  const urlTagCancelBtnCreate = makeCancelButton(30).addClass(
    "urlTagCancelBtnCreate",
  );

  urlTagCancelBtnCreate
    .find(".cancelButton")
    .on("click.createURLTag", function (e) {
      e.stopPropagation();
      hideAndResetCreateURLTagForm(urlCard);
    })
    .offAndOn("focus.createURLTag", function () {
      $(document).on("keyup.createURLTag", function (e) {
        if (e.key === KEYS.ENTER) hideAndResetCreateURLTagForm(urlCard);
      });
    })
    .offAndOn("blur.createURLTag", function () {
      $(document).off("keyup.createURLTag");
    });

  urlTagCreateTextInputContainer
    .append(urlTagSubmitBtnCreate)
    .append(urlTagCancelBtnCreate);

  return urlTagCreateTextInputContainer;
}

// Displays new Tag input prompt on selected URL
function showCreateURLTagForm(urlCard, urlTagBtnCreate) {
  // Show form to add a tag to this URL
  const tagInputFormContainer = urlCard.find(".createUrlTagWrap");
  enableTabbableChildElements(tagInputFormContainer);
  $(tagInputFormContainer).showClassFlex();

  // Handle case where iOS needs a direct focus not in a timeout, even with animation
  if (isMobile()) {
    tagInputFormContainer.find("input").focus();
  }

  // Focus on the input to add a tag - with delay in case user opened by pressing enter
  setTimeout(function () {
    tagInputFormContainer.find("input").trigger("focus");
  }, 100);

  // Disable URL Buttons as url Tag is being created
  urlCard.find(".urlBtnAccess").hideClass();
  urlCard.find(".urlStringBtnUpdate").hideClass();
  urlCard.find(".urlBtnDelete").hideClass();
  urlCard.find(".urlBtnCopy").hideClass();

  // Prevent hovering on tags from adding padding
  urlCard.find(".tagBadge").removeClass("tagBadgeHoverable");

  const tooltip = bootstrap.Tooltip.getInstance(urlTagBtnCreate);
  if (tooltip) {
    tooltip.hide();
    tooltip.disable();
  }

  // Modify add tag button
  urlTagBtnCreate
    .removeClass("fourty-p-width")
    .addClass("cancel urlTagCancelBigBtnCreate")
    .text("Cancel")
    .offAndOn("click", function (e) {
      e.stopPropagation();
      hideAndResetCreateURLTagForm(urlCard);
      if (tooltip) tooltip.enable();
    });

  disableTagRemovalInURLCard(urlCard);
  disableEditingURLTitle(urlCard);
  disableClickOnSelectedURLCardToHide(urlCard);
  // 02/29/24 Ideally this input would be a dropdown select input that allowed typing. As user types, selection menu filters on each keypress. User can either choose a suggested existing option, or enter a new custom tag
  // Redefine UI interaction with showInputBtn
  // let showInputBtn = $(URLCard).find(".urlTagBtnCreate");
  // showInputBtn.off("click");
  // showInputBtn.on("click", highlightInput(inputEl));

  // showIfHidden a new select input
  //   <select name="cars" id="cars">
  //   <option value="volvo">Volvo</option>
  //   <option value="saab">Saab</option>
  //   <option value="opel">Opel</option>
  //   <option value="audi">Audi</option>
  // </select>
}

function hideAndResetCreateURLTagForm(urlCard) {
  resetCreateURLTagFailErrors(urlCard);

  // Hide form to add a tag to this URL
  const tagInputFormContainer = urlCard.find(".createUrlTagWrap");
  disableTabbableChildElements(tagInputFormContainer);
  tagInputFormContainer.hideClass();

  // Reset input form
  tagInputFormContainer.find("input").val(null);

  // Modify add tag button
  const urlTagBtnCreate = urlCard.find(".urlTagBtnCreate");
  urlTagBtnCreate
    .removeClass("cancel urlTagCancelBigBtnCreate")
    .addClass("fourty-p-width")
    .offAndOn("click", function (e) {
      e.stopPropagation();
      showCreateURLTagForm(urlCard, urlTagBtnCreate);
    })
    .text("")
    .append(createAddTagIcon());

  // Enable URL Buttons as url Tag creation form is hidden
  urlCard.find(".urlBtnAccess").showClassFlex();
  urlCard.find(".urlStringBtnUpdate").showClassFlex();
  urlCard.find(".urlBtnDelete").showClassFlex();
  urlCard.find(".urlBtnCopy").showClassFlex();

  // Enable hovering on tags for deletion
  urlCard.find(".tagBadge").addClass("tagBadgeHoverable");

  enableTagRemovalInURLCard(urlCard);
  enableEditingURLTitle(urlCard);
  enableClickOnSelectedURLCardToHide(urlCard);
}

// Prepares post request inputs for addition of a new Tag to URL
function createURLTagSetup(urlTagCreateInput, utubID, utubUrlID) {
  // Assemble post request route
  const postURL = routes.createURLTag(utubID, utubUrlID);

  // Assemble submission data
  const data = {
    tagString: urlTagCreateInput.val(),
  };

  return [postURL, data];
}

// Handles addition of new Tag to URL after user submission
async function createURLTag(urlTagCreateInput, urlCard, utubID) {
  const utubUrlID = parseInt(urlCard.attr("utuburlid"));
  // Extract data to submit in POST request
  let postURL, data;
  [postURL, data] = createURLTagSetup(urlTagCreateInput, utubID, utubUrlID);

  let timeoutID;
  try {
    timeoutID = setTimeoutAndShowURLCardLoadingIcon(urlCard);
    await getUpdatedURL(utubID, utubUrlID, urlCard);

    const request = ajaxCall("post", postURL, data);

    // Handle response
    request.done(function (response, _, xhr) {
      if (xhr.status === 200) {
        resetCreateURLTagFailErrors(urlCard);
        createURLTagSuccess(response, urlCard, utubID);
      }
    });

    request.fail(function (xhr, _, textStatus) {
      createURLTagFail(xhr, urlCard);
    });

    request.always(function () {
      clearTimeoutIDAndHideLoadingIcon(timeoutID, urlCard);
    });
  } catch (error) {
    clearTimeoutIDAndHideLoadingIcon(timeoutID, urlCard);
    handleRejectFromGetURL(error, urlCard, {
      showError: true,
      message: "Another user has deleted this URL",
    });
  }
}

// Displays changes related to a successful addition of a new Tag
function createURLTagSuccess(response, urlCard, utubID) {
  // Clear and reset input field
  hideAndResetCreateURLTagForm(urlCard);

  // Extract response data
  const utubTagID = response.utubTag.utubTagID;
  const string = response.utubTag.tagString;
  const tagCount = response.tagCountsInUtub;

  // Update tags in URL
  urlCard
    .find(".urlTagsContainer")
    .append(createTagBadgeInURL(utubTagID, string, urlCard, utubID));

  const currentURLTagIDs = urlCard.attr("data-utub-url-tag-ids") || "";

  currentURLTagIDs.trim()
    ? urlCard.attr("data-utub-url-tag-ids", currentURLTagIDs + `,${utubTagID}`)
    : urlCard.attr("data-utub-url-tag-ids", utubTagID);

  // Add SelectAll button if not yet there
  $("#unselectAllTagFilters").showClassNormal();

  if (!isTagInUTubTagDeck(utubTagID)) {
    const newTag = buildTagFilterInDeck(utubID, utubTagID, string, tagCount);
    // If max number of tags already selected
    $(".tagFilter.selected").length === CONSTANTS.TAGS_MAX_ON_URL
      ? newTag.addClass("disabled").off(".tagFilterSelected")
      : null;
    $("#listTags").append(newTag);
  } else {
    // Update tag filter in Tag Deck
    updateTagFilterCount(utubTagID, tagCount, TagCountOperation.INCREMENT);
  }
}

// Displays appropriate prompts and options to user following a failed addition of a new Tag
function createURLTagFail(xhr, urlCard) {
  if (!xhr.hasOwnProperty("responseJSON")) {
    if (
      xhr.status === 403 &&
      xhr.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
    ) {
      // Handle invalid CSRF token error response
      $("body").html(xhr.responseText);
      return;
    }
    window.location.assign(routes.errorPage);
    return;
  }

  switch (xhr.status) {
    case 400:
      const responseJSON = xhr.responseJSON;
      if (responseJSON.hasOwnProperty("message")) {
        responseJSON.hasOwnProperty("errors")
          ? createURLTagFailErrors(responseJSON.errors, urlCard)
          : displayCreateURLTagErrors("urlTag", responseJSON.message, urlCard);
        break;
      }
    case 403:
    case 404:
    default:
      window.location.assign(routes.errorPage);
  }
}

function createURLTagFailErrors(errors, urlCard) {
  for (let key in errors) {
    switch (key) {
      case "tagString":
        let errorMessage = errors[key][0];
        displayCreateURLTagErrors("urlTag", errorMessage, urlCard);
        return;
    }
  }
}

function displayCreateURLTagErrors(key, errorMessage, urlCard) {
  urlCard
    .find("." + key + "Create-error")
    .addClass("visible")
    .text(errorMessage);
  urlCard.find("." + key + "Create").addClass("invalid-field");
}

function resetCreateURLTagFailErrors(urlCard) {
  const urlTagCreateFields = ["urlTag"];
  urlTagCreateFields.forEach((fieldName) => {
    urlCard.find("." + fieldName + "Create").removeClass("invalid-field");
    urlCard.find("." + fieldName + "Create-error").removeClass("visible");
  });
}
