"use strict";

function createTagInputBlock(urlCard) {
  const urlTagCreateTextInputContainer = makeTextInput(
    "urlTag",
    METHOD_TYPES.CREATE.description,
  )
    .addClass("createUrlTagWrap")
    .css("display", "none");

  urlTagCreateTextInputContainer.find("label").text("Tag");

  // Customize the input text box for the Url title
  const urlTagTextInput = urlTagCreateTextInputContainer
    .find("input")
    .prop("minLength", CONSTANTS.TAGS_MIN_LENGTH)
    .prop("maxLength", CONSTANTS.TAGS_MAX_LENGTH);

  setFocusEventListenersOnCreateURLTagInput(urlTagTextInput, urlCard);

  // Create Url Title submit button
  const urlTagSubmitBtnCreate = makeSubmitButton(30).addClass(
    "urlTagSubmitBtnCreate",
  );

  urlTagSubmitBtnCreate
    .find(".submitButton")
    .on("click.createURLTag", function () {
      createURLTag(urlTagTextInput, urlCard);
    })
    .on("focus.createURLTag", function () {
      $(document).on("keyup.createURLTag", function (e) {
        if (e.which === 13) createURLTag(urlTagTextInput, urlCard);
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
        if (e.which === 13) hideAndResetCreateURLTagForm(urlCard);
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
  $(tagInputFormContainer).showClassNormal();

  // Focus on the input to add a tag - with delay in case user opened by pressing enter
  setTimeout(function () {
    tagInputFormContainer.find("input").trigger("focus");
  }, 100);

  // Disable URL Buttons as url Tag is being created
  urlCard.find(".urlBtnAccess").hideClass();
  urlCard.find(".urlStringBtnUpdate").hideClass();
  urlCard.find(".urlBtnDelete").hideClass();

  // Prevent hovering on tags from adding padding
  urlCard.find(".tagBadge").removeClass("tagBadgeHoverable");

  // Modify add tag button
  urlTagBtnCreate
    .removeClass("btn-info")
    .addClass("btn-warning cancel urlTagCancelBigBtnCreate")
    .text("Cancel")
    .offAndOn("click", function (e) {
      e.stopPropagation();
      hideAndResetCreateURLTagForm(urlCard);
    });

  // For tablets, change some of the sizing
  if ($(window).width() < TABLET_WIDTH) {
    urlTagBtnCreate.addClass("full-width");
    urlTagBtnCreate.closest(".urlOptionsInner").addClass("half-width");
  }

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
    .removeClass("btn-warning cancel urlTagCancelBigBtnCreate")
    .addClass("btn-info")
    .text("Add Tag")
    .offAndOn("click", function (e) {
      e.stopPropagation();
      showCreateURLTagForm(urlCard, urlTagBtnCreate);
    });

  // Enable URL Buttons as url Tag creation form is hidden
  urlCard.find(".urlBtnAccess").showClassNormal();
  urlCard.find(".urlStringBtnUpdate").showClassNormal();
  urlCard.find(".urlBtnDelete").showClassNormal();

  // For tablets or in case of resize, change some of the sizing
  urlTagBtnCreate.removeClass("full-width");
  urlTagBtnCreate.closest(".urlOptionsInner").removeClass("half-width");

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
async function createURLTag(urlTagCreateInput, urlCard) {
  const utubID = getActiveUTubID();
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
        createURLTagSuccess(response, urlCard);
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
function createURLTagSuccess(response, urlCard) {
  // Clear and reset input field
  hideAndResetCreateURLTagForm(urlCard);

  // Extract response data
  const utubTagID = response.utubTag.utubTagID;
  const string = response.utubTag.tagString;

  // Update tags in URL
  urlCard
    .find(".urlTagsContainer")
    .append(createTagBadgeInURL(utubTagID, string, urlCard));

  // Add SelectAll button if not yet there
  $("#unselectAllTagFilters").showClassNormal();

  if (!isTagInUTubTagDeck(utubTagID)) {
    const newTag = buildTagFilterInDeck(utubTagID, string);
    // If max number of tags already selected
    $(".tagFilter.selected") === CONSTANTS.TAGS_MAX_ON_URL
      ? newTag.addClass("disabled").off(".tagFilterSelected")
      : null;
    $("#listTags").append(newTag);
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
