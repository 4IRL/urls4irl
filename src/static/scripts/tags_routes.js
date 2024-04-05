/* Add tag to URL */

// DP 09/17 do we need the ability to addTagtoURL interstitially before addURL is completed?

// Displays new Tag input prompt on selected URL
function addTagShowInput() {
    // Prevent deselection of URL while modifying its values
    unbindSelectURLBehavior();

    let URLCard = getSelectedURLCard();

    // Show temporary div element containing input
    let inputEl = URLCard.find(".addTag");
    inputEl.addClass("activeInput");
    showIfHidden(inputEl.closest(".createDiv"));
    highlightInput(inputEl);

    // 02/29/24 Ideally this input would be a dropdown select input that allowed typing. As user types, selection menu filters on each keypress. User can either choose a suggested existing option, or enter a new custom tag
    // Redefine UI interaction with showInputBtn
    // let showInputBtn = $(URLCard).find(".addTagBtn");
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

// Handles addition of new Tag to URL after user submission
function addTag() {
    // Extract data to submit in POST request
    [postURL, data] = addTagSetup();

    AJAXCall("post", postURL, data);

    // Handle response
    request.done(function (response, textStatus, xhr) {
        console.log("success");

        if (xhr.status == 200) {
            addTagSuccess(response);
        }
    });

    request.fail(function (response, textStatus, xhr) {
        console.log("failed");

        if (xhr.status == 404) {
            // Reroute to custom U4I 404 error page
        } else {
            addTagFailure(response);
        }
    });
}

// Prepares post request inputs for addition of a new Tag to URL
function addTagSetup() {
    // Assemble post request route
    let postURL = routes.addTag(getActiveUTubID(), getSelectedURLID());

    // Assemble submission data
    let newTag = getSelectedURLCard().find(".addTag").val();
    data = {
        tag_string: newTag
    };

    return [postURL, data];
}

// Displays changes related to a successful addition of a new Tag
function addTagSuccess(response) {
    // Rebind selection behavior of current URL
    rebindSelectBehavior(getSelectedURLID());

    let selectedURLCard = getSelectedURLCard();

    // Clear input field
    let newTagInputField = selectedURLCard.find(".addTag");
    newTagInputField.val("");
    hideIfShown(newTagInputField.closest(".createDiv"));

    // Add SelectAll button if not yet there
    if (isEmpty($("#selectAll"))) {
        $("#listTags").append(createSelectAllTagFilterInDeck());
    }

    // Extract response data
    let tagid = response.Tag.id;
    let string = response.Tag.tag_string;

    if (!isTagInDeck(tagid)) {
        $("#listTags").append(createTagFilterInDeck(tagid, string));
    }

    // Update tags in URL
    let URLTagDeck = selectedURLCard.find(".URLTags");
    let tagSpan = createTagBadgeInURL(tagid, string);
    URLTagDeck.append(tagSpan);

    displayState2TagDeck();
}

// Displays appropriate prompts and options to user following a failed addition of a new Tag
function addTagFailure(response) {
    console.log("Basic implementation. Needs revision");
    console.log(response.responseJSON.Error_code);
    console.log(response.responseJSON.Message);
    // DP 09/17 could we maybe have a more descriptive reason for failure sent from backend to display to user?
    // Currently STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_ADD_URL is too generic. the # * comments are ideal
}

/* Add tag to UTub */
// Unimplemented on backend

/* Edit tag in URL */
// Unimplemented on frontend

/* Edit tag in UTub */
// Unimplemented on backend
// Allows user to edit all tags in the UTub
// function editTagsInDeckShowInput(handle) {
//   hideIfShown($("#editTagButton"));
//   showIfHidden($("#submitTagButton"));
//   var listTagDivs = $("#listTags").children();

//   for (let i in listTagDivs) {
//     if (i == 0 || i >= listTagDivs.length - 1) {
//     } else {
//       if (handle == "submit") {
//         // Editing, then handle submission
//         console.log("submit initiated");
//         var tagID = $(listTagDivs[i]).find('input[type="checkbox"]')[0].tagid;
//         var tagText = $($(listTagDivs[i]).find('input[type="text"]')).val();
//         console.log(tagID);
//         console.log(tagText);
//         postData([tagID, tagText], "editTags");
//       } else {
//         // User wants to edit, handle input text field display
//         var tagText = $(listTagDivs[i]).find("label")[0].innerHTML;

//         var input = document.createElement("input");
//         $(input).attr({
//           type: "text",
//           class: "userInput",
//           placeholder: "Edit tag name",
//           value: tagText,
//         });
//         $(listTagDivs[i]).find("label").hide();
//         $(listTagDivs[i]).append(input);
//       }
//     }
//   }
// }

/* Remove tag from URL */

// Remove tag from selected URL
function removeTag(tagID) {
    // Extract data to submit in POST request
    postURL = removeTagSetup(tagID);

    let request = AJAXCall("post", postURL, []);

    // Handle response
    request.done(function (response, textStatus, xhr) {
        if (xhr.status == 200) {
            removeTagSuccess(tagID);
        }
    });

    request.fail(function (response, textStatus, xhr) {
        console.log(
            "Failure. Status code: " + xhr.status + ". Status: " + textStatus,
        );
        if (xhr.status == 404) {
            // Reroute to custom U4I 404 error page
        } else {
            removeTagFail(response);
        }
    });
}

// Prepares post request inputs for removal of a URL
function removeTagSetup(tagID) {
    let postURL = routes.removeTag(getActiveUTubID(), getSelectedURLID(), tagID);

    return postURL;
}

// Displays changes related to a successful removal of a URL
function removeTagSuccess(tagID) {
    // If the removed tag is the last instance in the UTub, remove it from the Tag Deck. Else, do nothing.

    let tagBadgeJQuerySelector = ".tagBadge[tagid=" + tagID + "]"

    $(".selectedURL")
        .find(tagBadgeJQuerySelector)
        .remove();

    // Determine whether the removed tag is the last instance in the UTub. Remove, if yes
    if (isEmpty($(tagBadgeJQuerySelector))) {
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
function removeTagFail(xhr, textStatus, error) {
    console.log("Error: Could not delete URL");

    if (xhr.status == 409) {
        console.log(
            "Failure. Status code: " + xhr.status + ". Status: " + textStatus,
        );
        console.log("Error: " + error.Error_code);
    }
}

/* Remove tag from all URLs in UTub */
// Unimplemented on backend
