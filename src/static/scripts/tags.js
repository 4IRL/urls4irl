/* Tag-related constants */

// Routes
const ADD_TAG_ROUTE = "/tag/add/"; // +<int:utub_id>/<int:url_id>
const EDIT_TAG_ROUTE = "/tag/modify/"; // +<int:utub_id>/<int:url_id>/<int:tag_id>
const REMOVE_TAG_ROUTE = "/tag/remove/"; // +<int:utub_id>/<int:url_id>/<int:tag_id>
// Small DP 09/25 consistency to 'modify' -> 'edit'?

/* Tag UI Interactions */

$(document).ready(function () {
  /* Bind click functions */

  // Complete edit tags
  $("#submitTagButton").on("click", function (e) {
    e.stopPropagation();
    e.preventDefault();
    editTags();
  });
});

/* Tag Utility Functions */

// Function to count number of tags in current UTub
function getNumOfTags() {
  return $(".tagFilter").length;
}

// Function to enumerate applied tag filters in current UTub
function getActiveTagIDs() {
  let activeTagIDList = [];
  let tagFilterList = $(".tagFilter");

  for (let i = 0; i < tagFilterList.length; i++) {
    let tagFilter = tagFilterList[i];
    // if ($(tagFilter).hasClass("selected")) activeTagIDList.push($(tagFilter).tagid)
    // if ($(tagFilter).hasClass("selected")) [activeTagIDList, $(tagFilter).tagid]
    if ($(tagFilter).hasClass("selected")) activeTagIDList.push($(tagFilter).attr('tagid'))
    // if ($(tagFilter).hasClass("selected")) [activeTagIDList, $(tagFilter).attr('tagid')]
  }

  return activeTagIDList;
}

// Simple function to streamline the jQuery selector extraction of what tag IDs are currently displayed in the Tag Deck
function currentTagDeckIDs() {
  let tagList = $(".tagFilter");
  let tagIDList = Object.keys(tagList).map(function (property) {
    return "" + $(tagList[property]).attr("tagid");
  });
  return tagIDList;
}

// 11/25/23 need to figure out how to map tagids to Array so I can evaluate whether the tag already exists in Deck before adding it
// Function to evaluate whether newly added tag already exists in Tag Deck
function isTagInDeck(tagid) {
  return currentTagDeckIDs().includes("" + tagid);
}

// Clear the Tag Deck
function resetTagDeck() {
  $("#listTags").empty();
}

// Alphasort tags
function alphasortTags(dictTags) {
  return dictTags.sort(function (a, b) {
    const tagA = a.tag_string.toUpperCase(); // ignore upper and lowercase
    const tagB = b.tag_string.toUpperCase(); // ignore upper and lowercase
    if (tagA < tagB) {
      return -1;
    }
    if (tagA > tagB) {
      return 1;
    }
    // tags must be equal
    return 0;
  });
}

/** Tag Functions **/

// Build LH panel tag list in selectedUTub
function buildTagDeck(dictTags) {
  resetTagDeck();

  let numOfTags = dictTags.length ? dictTags.length : 0;

  if (numOfTags) {
    const parent = $("#listTags");

    // Select all checkbox
    parent.append(createSelectAllTagFilterInDeck());

    // Loop through all tags and provide checkbox input for filtering
    for (let i in dictTags) {
      parent.append(createTagFilterInDeck(dictTags[i].id, dictTags[i].tag_string));
    }

    displayState2TagDeck();
  } else displayState1TagDeck();
}

// Creates Select All tag filter for addition to Tag deck
function createSelectAllTagFilterInDeck() {
  const container = document.createElement("div");
  const label = document.createElement("label");

  $(container).addClass("selected")
    .attr({
      id: "selectAll",
      tagid: "all",
      onclick: 'filterAllTags(); filterAllTaggedURLs()',
    });
  $(label).attr({
    for: "selectAll",
  });
  label.innerHTML = "Select All";

  $(container).append(label);

  return container;
}

// Creates tag filter for addition to Tag deck
function createTagFilterInDeck(tagID, string) {
  const container = document.createElement("div");
  const label = document.createElement("label");

  $(container).addClass("tagFilter selected")
    .attr({
      tagid: tagID,
      onclick: "filterTag(" + tagID + "); filterURL(" + tagID + ")",
    });

  $(label).attr({ for: "Tag-" + tagID });
  label.innerHTML += string;

  $(container).append(label);

  return container;
}

// Update Tag Deck display in response to selectAll selection
function filterAllTags() {
  let selAll = $("#selectAll");
  selAll.toggleClass("selected");

  let selectedBool = selAll.hasClass("selected");

  let tagFilterList = $(".tagFilter");
  // Toggle all filter tags to match "Select All" checked status
  selectedBool ? tagFilterList.addClass("selected") : tagFilterList.removeClass("selected")

  displayState2TagDeck();
}

// Update Tag Deck display in response to tag filter selection
function filterTag(tagID) {
  let filteredTag = $(".tagFilter[tagid=" + tagID + "]");
  filteredTag.toggleClass("selected");
  
  let selAll = $("#selectAll");

  let selectedBool = filteredTag.hasClass("selected");
  // Toggle SelectAll filter to reflect tagFilter selection
  selectedBool ? selAll.addClass("selected") : selAll.removeClass("selected")

  displayState2TagDeck();
}

/** Tags Display State Functions **/

// Display state 0: Clean slate, no UTub selected
function displayState0TagDeck() {
  // Subheader prompt hidden
  hideIfShown($("#TagDeckSubheader").closest(".row"));
}

// Display state 1: Selected UTub has URLs, no Tags
function displayState1TagDeck() {
  // Subheader prompt shown
  let TagDeckSubheader = $("#TagDeckSubheader");
  showIfHidden(TagDeckSubheader.closest(".row"));
  TagDeckSubheader.text("Add a tag to a URL");
}

// Display state 2: Selected UTub has URLs and Tags
function displayState2TagDeck() {
  let numOfTags = getNumOfTags();
  let TagDeckSubheader = $("#TagDeckSubheader");
  showIfHidden(TagDeckSubheader.closest(".row"));
  TagDeckSubheader.text(numOfTags - getActiveTagIDs().length + " of " + numOfTags + " filters applied");
}

/** Post data handling **/

/* Add tag to URL */

// DP 09/17 do we need the ability to addTagtoURL interstitially before addURL is completed?

// Displays new Tag input prompt on selected URL
function addTagShowInput() {
  // Prevent deselection of URL while modifying its values
  unbindSelectURLBehavior();

  let URLCard = getSelectedURLCard();

  // Show temporary div element containing input
  let inputEl = $(URLCard).find(".addTag");
  let inputDiv = inputEl.closest(".createDiv");
  inputEl.addClass("activeInput");
  showIfHidden(inputDiv);
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
  let postURL = ADD_TAG_ROUTE + getActiveUTubID() + "/" + getSelectedURLID();

  // Assemble submission data
  let URLTagDeck = $(getSelectedURLCard()).find(".URLTags");
  let newTag = URLTagDeck.find(".addTag").val();
  data = {
    tag_string: newTag,
  };

  return [postURL, data];
}

// Displays changes related to a successful addition of a new Tag
function addTagSuccess(response) {
  // Rebind selection behavior of current URL
  rebindSelectBehavior(getSelectedURLID());

  // Clear input field
  let URLTagDeck = $(getSelectedURLCard()).find(".URLTags");
  let newTagInputField = URLTagDeck.find(".addTag");
  newTagInputField.val("");
  hideIfShown(newTagInputField.closest(".createDiv"));

  // Extract response data
  let tagid = response.Tag.id;
  let string = response.Tag.tag_string;

  if (!isTagInDeck(tagid)) createTaginDeck(tagid, string);

  // Update tags in URL
  let tagSpan = createTaginURL(tagid, string);
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
    console.log("success");

    if (xhr.status == 200) {
      removeTagSuccess(tagID);
    }
  });

  request.fail(function (response, textStatus, xhr) {
    console.log("failed");
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
  let postURL =
    REMOVE_TAG_ROUTE +
    getActiveUTubID() +
    "/" +
    getSelectedURLID() +
    "/" +
    tagID;

  return postURL;
}

// Displays changes related to a successful reomval of a URL
function removeTagSuccess(tagID) {
  // If the removed tag is the last instance in the UTub, remove it from the Tag Deck. Else, do nothing.

  $("div.url[urlid=" + getSelectedURLID() + "]")
    .find("span.tag[tagid=" + tagID + "]")
    .remove();

  // Determine whether the removed tag is the last instance in the UTub
  // Remove, if yes
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