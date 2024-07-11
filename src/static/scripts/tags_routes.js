/* Add tag to URL */

// DP 09/17 do we need the ability to createURLTagtoURL interstitially before addURL is completed?

// Displays new Tag input prompt on selected URL
function showCreateURLTagForm(urlCard, urlTagBtnCreate) {
  // Show form to add a tag to this URL
  const tagInputFormContainer = urlCard.find(".createUrlTagWrap");
  showIfHidden(tagInputFormContainer);

  // Focus on the input to add a tag
  tagInputFormContainer.find("input").focus();

  // Disable URL Buttons as url Tag is being created
  hideIfShown(urlCard.find(".urlBtnAccess"));
  hideIfShown(urlCard.find(".urlBtnUpdate"));
  hideIfShown(urlCard.find(".urlBtnDelete"));

  // Modify add tag button
  urlTagBtnCreate
    .removeClass("btn-info")
    .addClass("btn-warning")
    .text("Cancel")
    .off("click")
    .on("click", function (e) {
      e.stopPropagation();
      hideAndResetCreateURLTagForm(urlCard);
    });

  disableTagRemovalInURLCard(urlCard);
  disableEditingURLTitle(urlCard);
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
  hideIfShown(tagInputFormContainer);

  // Reset input form
  tagInputFormContainer.find("input").val(null);

  // Modify add tag button
  const urlTagBtnCreate = urlCard.find(".urlTagBtnCreate");
  urlTagBtnCreate
    .removeClass("btn-warning")
    .addClass("btn-info")
    .text("Add Tag")
    .off("click")
    .on("click", function (e) {
      e.stopPropagation();
      showCreateURLTagForm(urlCard, urlTagBtnCreate);
    });

  // Enable URL Buttons as url Tag creation form is hidden
  showIfHidden(urlCard.find(".urlBtnAccess"));
  showIfHidden(urlCard.find(".urlBtnUpdate"));
  showIfHidden(urlCard.find(".urlBtnDelete"));

  enableTagRemovalInURLCard(urlCard);
  enableEditingURLTitle(urlCard);
}

// Prepares post request inputs for addition of a new Tag to URL
function createURLTagSetup(urlTagCreateInput) {
  // Assemble post request route
  const postURL = routes.createURLTag(getActiveUTubID(), getSelectedURLID());

  // Assemble submission data
  const data = {
    tagString: urlTagCreateInput.val(),
  };

  return [postURL, data];
}

// Handles addition of new Tag to URL after user submission
function createURLTag(urlTagCreateInput, urlCard) {
  // Extract data to submit in POST request
  [postURL, data] = createURLTagSetup(urlTagCreateInput);

  AJAXCall("post", postURL, data);

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
}

// Displays changes related to a successful addition of a new Tag
function createURLTagSuccess(response, urlCard) {
  // Clear and reset input field
  hideAndResetCreateURLTagForm(urlCard);

  // Extract response data
  const tagID = response.tag.tagID;
  const string = response.tag.tagString;

  // Update tags in URL
  urlCard.find(".urlTagsContainer").append(createTagBadgeInURL(tagID, string));

  // Add SelectAll button if not yet there
  if (isEmpty($("#selectAll"))) {
    $("#listTags").append(createSelectAllTagFilterInDeck());
  }

  if (!isTagInDeck(tagID)) {
    $("#listTags").append(createTagFilterInDeck(tagID, string));
  }

  updateCountOfTagFiltersApplied();
}

// Displays appropriate prompts and options to user following a failed addition of a new Tag
function createURLTagFail(xhr, urlCard) {
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
function deleteURLTagSetup(tagID) {
  const deleteURL = routes.deleteURLTag(
    getActiveUTubID(),
    getSelectedURLID(),
    tagID,
  );

  return deleteURL;
}

// Remove tag from selected URL
async function deleteURLTag(tagID, tagBadge) {
  try {
    // Extract data to submit in POST request
    const deleteURL = deleteURLTagSetup(tagID);

    const request = AJAXCall("delete", deleteURL, []);

    // Handle response
    request.done(function (response, _, xhr) {
      if (xhr.status === 200) {
        deleteURLTagSuccess(response, tagBadge);
      }
    });

    request.fail(function (xhr, _, textStatus) {
      deleteURLTagFail(xhr);
    });
  } catch (error) {
    handleRejectFromGetURL(error);
  }
}

// Displays changes related to a successful removal of a URL
function deleteURLTagSuccess(response, tagBadge) {
  // If the removed tag is the last instance in the UTub, remove it from the Tag Deck. Else, do nothing.
  tagBadge.remove();
  const tagID = response.tag.tagID;

  // Determine whether the removed tag is the last instance in the UTub. Remove, if yes
  if (!response.tagInUTub) {
    $(".tagFilter[tagid=" + tagID + "]").remove();
  }

  // Remove SelectAll button if no tags
  if (isEmpty($(".tagFilter"))) {
    $("#selectAll").remove();
  }
  updateCountOfTagFiltersApplied();
}

// Displays appropriate prompts and options to user following a failed removal of a URL
function deleteURLTagFail(_) {
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
//         postData([tagID, tagText], "updateTags");
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
