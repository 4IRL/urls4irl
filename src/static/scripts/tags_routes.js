/* Add tag to URL */

// Shows new UTub Tag input fields
function createUTubTagShowInput() {
  showIfHidden($("#createUTubTagWrap"));
  hideIfShown($("#listTags"));
  hideIfShown($("#utubTagBtnCreate"));
  setupCreateUTubTagEventListeners();
  $("#utubTagCreate").trigger("focus");
}

// Hides new UTubTag input fields
function createUTubTagHideInput() {
  hideIfShown($("#createUTubTagWrap"));
  $("#createUTubTagWrap").hide();
  showIfHidden($("#listTags"));
  if (getNumOfUTubs() !== 0) showIfHidden($("#utubTagBtnCreate"));
  removeCreateUTubTagEventListeners();
  resetCreateUTubTagFailErrors();
  resetNewUTubTagForm();
}

function createUTubTagSetup() {
  const postURL = routes.createUTubTag(getActiveUTubID());

  const newUTubTag = $("#utubTagCreate").val();
  const data = {
    tagString: newUTubTag,
  };

  return [postURL, data];
}

function createUTubTag() {
  // Extract data to submit in POST request
  [postURL, data] = createUTubTagSetup();
  resetCreateUTubTagFailErrors();

  const request = ajaxCall("post", postURL, data);

  // Handle response
  request.done(function (response, _, xhr) {
    if (xhr.status === 200) {
      createUTubTagSuccess(response);
    }
  });

  request.fail(function (xhr, _, textStatus) {
    createUTubTagFail(xhr);
  });
}

function setupCreateUTubTagEventListeners() {
  const utubTagSubmitBtnCreate = $("#utubTagSubmitBtnCreate");
  const utubTagCancelBtnCreate = $("#utubTagCancelBtnCreate");

  utubTagSubmitBtnCreate.offAndOn("click.createUTubTagSubmit", function (e) {
    if ($(e.target).closest("#utubTagSubmitBtnCreate").length > 0)
      createUTubTag();
  });

  utubTagSubmitBtnCreate.offAndOn("focus.createUTubTagSubmit", function () {
    $(document).on("keyup.createUTubTagSubmit", function (e) {
      if (e.which === 13) createUTubTag();
    });
  });

  utubTagSubmitBtnCreate.offAndOn("blur.createUTubTagSubmit", function () {
    $(document).off("keyup.createUTubTagSubmit");
  });

  utubTagCancelBtnCreate.offAndOn("click.createUTubTagEscape", function (e) {
    if ($(e.target).closest("#utubTagCancelBtnCreate").length > 0)
      createUTubTagHideInput();
  });

  utubTagCancelBtnCreate.offAndOn("focus.createUTubTagEscape", function () {
    $(document).on("keyup.createUTubTagEscape", function (e) {
      if (e.which === 13) createUTubTagHideInput();
    });
  });

  utubTagCancelBtnCreate.offAndOn("blur.createUTubTagEscape", function () {
    $(document).off("keyup.createUTubTagEscape");
  });

  const utubTagInput = $("#utubTagCreate");
  utubTagInput.on("focus.createUTubTagSubmitEscape", function () {
    bindCreateUTubTagFocusEventListeners();
  });
  utubTagInput.on("blur.createUTubTagSubmitSubmitEscape", function () {
    unbindCreateUTubTagFocusEventListeners();
  });
}

function removeCreateUTubTagEventListeners() {
  $("#memberCreate").off(".createUTubTagSubmitEscape");
}

function bindCreateUTubTagFocusEventListeners() {
  // Allow closing by pressing escape key
  $(document).on("keyup.createUTubTagSubmitEscape", function (e) {
    switch (e.which) {
      case 13:
        // Handle enter key pressed
        createUTubTag();
        break;
      case 27:
        // Handle escape  key pressed
        createUTubTagHideInput();
        break;
      default:
      /* no-op */
    }
  });
}

function unbindCreateUTubTagFocusEventListeners() {
  $(document).off(".createUTubTagSubmitEscape");
}

function createUTubTagSuccess(response) {
  resetNewUTubTagForm();

  // Create and append the new tag in the tag deck
  $("#listTags").append(
    createTagFilterInDeck(
      response.utubTag.utubTagID,
      response.utubTag.tagString,
    ),
  );

  createUTubTagHideInput();
}

function createUTubTagFail(xhr) {
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
      const hasErrors = responseJSON.hasOwnProperty("errors");
      const hasMessage = responseJSON.hasOwnProperty("message");
      if (hasErrors) {
        // Show form errors
        createUTubTagFailErrors(responseJSON.errors);
        break;
      } else if (hasMessage) {
        // Show message
        displayCreateUTubTagFailErrors("utubTag", responseJSON.message);
        break;
      }
    case 403:
    case 404:
    default:
      window.location.assign(routes.errorPage);
  }
}

function createUTubTagFailErrors(errors) {
  for (let key in errors) {
    switch (key) {
      case "tagString":
        let errorMessage = errors[key][0];
        displayCreateUTubTagFailErrors(key, errorMessage);
        return;
    }
  }
}

function displayCreateUTubTagFailErrors(_, errorMessage) {
  $("#utubTagCreate-error").addClass("visible").text(errorMessage);
  $("#utubTagCreate").addClass("invalid-field");
}

function resetCreateUTubTagFailErrors() {
  const createUTubTagFields = ["utubTag"];
  createUTubTagFields.forEach((fieldName) => {
    $("#" + fieldName + "Create-error").removeClass("visible");
    $("#" + fieldName + "Create").removeClass("invalid-field");
  });
}

/* Add tag to URL */

// Displays new Tag input prompt on selected URL
function showCreateURLTagForm(urlCard, urlTagBtnCreate) {
  // Show form to add a tag to this URL
  const tagInputFormContainer = urlCard.find(".createUrlTagWrap");
  enableTabbableChildElements(tagInputFormContainer);
  showIfHidden(tagInputFormContainer);

  // Focus on the input to add a tag - with delay in case user opened by pressing enter
  setTimeout(function () {
    tagInputFormContainer.find("input").trigger("focus");
  }, 100);

  // Disable URL Buttons as url Tag is being created
  hideIfShown(urlCard.find(".urlBtnAccess"));
  hideIfShown(urlCard.find(".urlStringBtnUpdate"));
  hideIfShown(urlCard.find(".urlBtnDelete"));

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
  hideIfShown(tagInputFormContainer);

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
  showIfHidden(urlCard.find(".urlBtnAccess"));
  showIfHidden(urlCard.find(".urlStringBtnUpdate"));
  showIfHidden(urlCard.find(".urlBtnDelete"));

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
function createURLTagSetup(urlTagCreateInput, utubID, urlID) {
  // Assemble post request route
  const postURL = routes.createURLTag(utubID, urlID);

  // Assemble submission data
  const data = {
    tagString: urlTagCreateInput.val(),
  };

  return [postURL, data];
}

// Handles addition of new Tag to URL after user submission
async function createURLTag(urlTagCreateInput, urlCard) {
  const utubID = getActiveUTubID();
  const urlID = parseInt(urlCard.attr("urlid"));
  // Extract data to submit in POST request
  [postURL, data] = createURLTagSetup(urlTagCreateInput, utubID, urlID);

  let timeoutID;
  try {
    timeoutID = setTimeoutAndShowLoadingIcon(urlCard);
    await getUpdatedURL(utubID, urlID, urlCard);

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
  if (isEmpty($("#unselectAll"))) {
    $("#listTags").append(createUnselectAllTagFilterInDeck());
  }

  if (!isTagInDeck(utubTagID)) {
    const newTag = createTagFilterInDeck(utubTagID, string);
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

/* Remove tag from URL */

// Prepares post request inputs for removal of a URL - tag
function deleteURLTagSetup(utubID, urlID, utubTagID) {
  const deleteURL = routes.deleteURLTag(utubID, urlID, utubTagID);

  return deleteURL;
}

// Remove tag from selected URL
async function deleteURLTag(utubTagID, tagBadge, urlCard) {
  const utubID = getActiveUTubID();
  const urlID = parseInt(urlCard.attr("urlid"));
  let timeoutID;
  try {
    timeoutID = setTimeoutAndShowLoadingIcon(urlCard);
    await getUpdatedURL(utubID, urlID, urlCard);

    // If tag was already deleted on update of URL, exit early
    if (!isTagInURL(utubTagID, urlCard)) {
      clearTimeoutIDAndHideLoadingIcon(timeoutID, urlCard);
      return;
    }

    // Extract data to submit in POST request
    const deleteURL = deleteURLTagSetup(utubID, urlID, utubTagID);

    const request = ajaxCall("delete", deleteURL, []);

    // Handle response
    request.done(function (response, _, xhr) {
      if (xhr.status === 200) {
        deleteURLTagSuccess(tagBadge);
      }
    });

    request.fail(function (xhr, _, textStatus) {
      deleteURLTagFail(xhr);
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

// Displays changes related to a successful removal of a URL
function deleteURLTagSuccess(tagBadge) {
  // If the removed tag is the last instance in the UTub, remove it from the Tag Deck. Else, do nothing.
  tagBadge.remove();

  // Hide the URL if selected tag is filtering
  updateTagFilteringOnURLOrURLTagDeletion();
}

// Displays appropriate prompts and options to user following a failed removal of a URL
function deleteURLTagFail(xhr) {
  if (
    xhr.status === 403 &&
    xhr.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
  ) {
    // Handle invalid CSRF token error response
    $("body").html(xhr.responseText);
    return;
  }
  window.location.assign(routes.errorPage);
}

/* Add tag to UTub */
// Unimplemented on backend

/* Update tag in URL */
// Unimplemented on frontend

/* Update tag in UTub */
// Unimplemented on backend
// Allows user to update all tags in the UTub
// function updateTagsInDeckShowInput(handle) {
//   hideIfShown($("#updateTagButton"));
//   showIfHidden($("#submitTagButton"));
//   var listTagDivs = $("#listTags").children();

//   for (let i in listTagDivs) {
//     if (i == 0 || i >= listTagDivs.length - 1) {
//     } else {
//       if (handle == "submit") {
//         // Updating, then handle submission
//         console.log("submit initiated");
//         var tagID = $(listTagDivs[i]).find('input[type="checkbox"]')[0].tagid;
//         var tagText = $($(listTagDivs[i]).find('input[type="text"]')).val();
//         console.log(tagID);
//         console.log(tagText);
//         postData([data-utub-tag-id, tagText], "updateTags");
//       } else {
//         // User wants to update, handle input text field display
//         var tagText = $(listTagDivs[i]).find("label")[0].innerHTML;

//         var input = document.createElement("input");
//         $(input).attr({
//           type: "text",
//           class: "userInput",
//           placeholder: "Update tag name",
//           value: tagText,
//         });
//         $(listTagDivs[i]).find("label").hide();
//         $(listTagDivs[i]).append(input);
//       }
//     }
//   }
// }

/* Remove tag from all URLs in UTub */
// Unimplemented on backend
