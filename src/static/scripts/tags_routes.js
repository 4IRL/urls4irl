/* Add tag to URL */

// DP 09/17 do we need the ability to createTagtoURL interstitially before addURL is completed?

// Displays new Tag input prompt on selected URL
function createTagShowInput() {
  // Prevent deselection of URL while modifying its values
  unbindSelectURLBehavior();
  unbindEscapeKey();
  unbindURLKeyboardEventListenersWhenUpdatesOccurring();

  let URLCard = getSelectedUrlCard();

  // Show temporary div element containing input
  let inputEl = URLCard.find(".createTag");
  inputEl.addClass("activeInput");

  const inputWrapper = inputEl.closest(".createDiv");
  showIfHidden(inputWrapper);
  highlightInput(inputEl);
  bindEscapeToExitCreateNewTag(inputWrapper);

  // Disable the other buttons in the URL
  disable(URLCard.find(".urlBtnAccess"));
  disable(URLCard.find(".urlBtnUpdate"));
  disable(URLCard.find(".urlBtnDelete"));

  // Modify add tag button
  const urlTagBtnCreate = URLCard.find(".urlTagBtnCreate");
  urlTagBtnCreate.removeClass("btn-info").addClass("btn-warning");
  urlTagBtnCreate.text("Return");
  urlTagBtnCreate.off("click").on("click", function (e) {
    e.stopPropagation();
    tagCancelBtnCreateHideInput(inputWrapper);
  });

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

function tagCancelBtnCreateHideInput(inputWrapper) {
  let URLCard = getSelectedUrlCard();
  bindEscapeToUnselectURL(getSelectedURLID());

  // Enable the buttons again
  enable(URLCard.find(".urlBtnAccess"));
  enable(URLCard.find(".urlBtnUpdate"));
  enable(URLCard.find(".urlBtnDelete"));

  // Modify add tag button
  const urlTagBtnCreate = URLCard.find(".urlTagBtnCreate");
  urlTagBtnCreate.removeClass("btn-warning").addClass("btn-info");
  urlTagBtnCreate.text("Add Tag");

  urlTagBtnCreate.off("click").on("click", function (e) {
    e.stopPropagation();
    createTagShowInput();
  });

  hideIfShown(inputWrapper);
  rebindSelectBehavior();
  bindURLKeyboardEventListenersWhenUpdatesNotOccurring();
}

// Handles addition of new Tag to URL after user submission
function createTag() {
  // Extract data to submit in POST request
  [postURL, data] = createTagSetup();

  AJAXCall("post", postURL, data);

  // Handle response
  request.done(function (response, textStatus, xhr) {
    console.log("success");

    if (xhr.status === 200) {
      createTagSuccess(response);
    }
  });

  request.fail(function (response, textStatus, xhr) {
    console.log("failed");

    if (xhr.status === 404) {
      // Reroute to custom U4I 404 error page
    } else {
      createTagFail(response);
    }
  });
}

// Prepares post request inputs for addition of a new Tag to URL
function createTagSetup() {
  // Assemble post request route
  let postURL = routes.createTag(getActiveUTubID(), getSelectedURLID());

  // Assemble submission data
  let newTag = getSelectedUrlCard().find(".createTag").val();
  data = {
    tagString: newTag,
  };

  return [postURL, data];
}

// Displays changes related to a successful addition of a new Tag
function createTagSuccess(response) {
  // Rebind selection behavior of current URL
  rebindSelectBehavior();

  let selectedURLCard = getSelectedUrlCard();

  // Clear input field
  let newTagInputField = selectedURLCard.find(".createTag");
  newTagInputField.val("");
  hideIfShown(newTagInputField.closest(".createDiv"));

  // Add SelectAll button if not yet there
  if (isEmpty($("#selectAll"))) {
    $("#listTags").append(createSelectAllTagFilterInDeck());
  }

  // Extract response data
  let tagID = response.tag.tagID;
  let string = response.tag.tagString;

  if (!isTagInDeck(tagID)) {
    $("#listTags").append(createTagFilterInDeck(tagID, string));
  }

  // Update tags in URL
  let URLTagDeck = selectedURLCard.find(".URLTags");
  let tagSpan = createTagBadgeInURL(tagID, string);
  URLTagDeck.append(tagSpan);

  displayState2TagDeck();
}

// Displays appropriate prompts and options to user following a failed addition of a new Tag
function createTagFail(response) {
  console.log("Basic implementation. Needs revision");
  console.log(response.responseJSON.errorCode);
  console.log(response.responseJSON.message);
}

/* Remove tag from URL */

// Remove tag from selected URL
function deleteTag(tagID) {
  // Extract data to submit in POST request
  postURL = deleteTagSetup(tagID);

  let request = AJAXCall("delete", postURL, []);

  // Handle response
  request.done(function (response, textStatus, xhr) {
    if (xhr.status === 200) {
      console.log("success");
      deleteTagSuccess(response);
    }
  });

  request.fail(function (response, textStatus, xhr) {
    console.log(
      "Failure. Status code: " + xhr.status + ". Status: " + textStatus,
    );
    if (xhr.status === 404) {
      // Reroute to custom U4I 404 error page
    } else {
      deleteTagFail(response);
    }
  });
}

// Prepares post request inputs for removal of a URL
function deleteTagSetup(tagID) {
  let postURL = routes.deleteTag(getActiveUTubID(), getSelectedURLID(), tagID);

  return postURL;
}

// Displays changes related to a successful removal of a URL
function deleteTagSuccess(response) {
  // If the removed tag is the last instance in the UTub, remove it from the Tag Deck. Else, do nothing.

  let tagID = response.tag.tagID;
  let tagBadgeJQuerySelector = ".tagBadge[tagid=" + tagID + "]";

  $(".selectedURL").find(tagBadgeJQuerySelector).remove();

  // Determine whether the removed tag is the last instance in the UTub. Remove, if yes
  if (!response.tagInUTub) {
    $(".tagFilter[tagid=" + tagID + "]").remove();
  }

  // Remove SelectAll button if no tags
  if (isEmpty($(".tagFilter"))) {
    $("#selectAll").remove();
    displayState1TagDeck();
  } else {
    displayState2TagDeck();
  }
}

// Displays appropriate prompts and options to user following a failed removal of a URL
function deleteTagFail(response) {
  console.log("Basic implementation. Needs revision");
  console.log(response);
  console.log(response.responseJSON);
  console.log(response.responseJSON.errorCode);
  console.log(response.responseJSON.message);
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
