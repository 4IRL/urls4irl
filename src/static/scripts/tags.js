/* Tag-related constants */

// Routes
const ADD_TAG_ROUTE = "/tag/add/"; // +<int:utub_id>/<int:url_id>
const EDIT_TAG_ROUTE = "/tag/modify/"; // +<int:utub_id>/<int:url_id>/<int:tag_id>
const REMOVE_TAG_ROUTE = "/tag/remove/"; // +<int:utub_id>/<int:url_id>/<int:tag_id>
// Small DP 09/25 consistency to 'modify' -> 'edit'?

/* Tag UI Interactions */

$(document).ready(function () {
  /* Bind click functions */

  // Create unassociated tag
  // $("#createTagButton").on("click", function (e) {
  //   e.stopPropagation();
  //   e.preventDefault();
  //   addTagInDeckShowInput();
  // });

  // Edit tags
  // $("#editTagButton").on("click", function (e) {
  //   e.stopPropagation();
  //   e.preventDefault();
  //   editTagsInDeckShowInput();
  // });

  // Complete edit tags
  $("#submitTagButton").on("click", function (e) {
    e.stopPropagation();
    e.preventDefault();
    editTags();
  });
});

/* Tag Utility Functions */

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

/* Tag Functions */

// Build LH panel tag list in selectedUTub
function buildTagDeck(dictTags) {
  resetTagDeck();
  const parent = $("#listTags");

  // Tag deck display updates
  // showIfHidden($("#createTagButton"));

  if (dictTags.length == 0) {
    // User has no Tags in this UTub
    $("#TagDeck").find("h2")[0].innerHTML = "Create a Tag";
    // hideIfShown($("#editTagButton"));
    showIfHidden($("#noTagsHeader"));

    // New Tag input text field. Initially hidden, shown when create Tag is requested
    createTaginDeck(0, "newTag");
  } else {
    // Instantiate TagDeck (bottom left panel) with tags in current UTub
    hideIfShown($("#noTagsHeader"));
    $("#TagDeck").find("h2")[0].innerHTML = "Tags";
    // showIfHidden($("#editTagButton"));

    // 1. Select all checkbox
    createTaginDeck(0, "selectAll");

    // 2. New Tag input text field. Initially hidden, shown when create Tag is requested
    createTaginDeck(0, "newTag");

    // 3a. Alpha sort tags based on tag_string
    dictTags.sort(function (a, b) {
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

    // 3b. Loop through all tags and provide checkbox input for filtering
    for (let i in dictTags) {
      createTaginDeck(dictTags[i].id, dictTags[i].tag_string);
    }
  }
}

// Handle URL deck display changes related to creating a new tag
function createTaginURL(tagID, string) {
  let tagSpan = document.createElement("span");
  let removeButton = document.createElement("a");

  $(tagSpan)
    .attr({ tagid: tagID })
    .addClass("tag")
    .text(string);

  $(removeButton)
    .attr({ class: "btn btn-sm btn-outline-link border-0 tag-remove" })
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      removeTag(tagID);
    });
  removeButton.innerHTML = "&times;";

  $(tagSpan).append(removeButton);

  return tagSpan;
}

// New URL tag input text field. Initially hidden, shown when Create Tag is requested. Input field recreated here to ensure at the end of list after creation of new URL
function createNewTagInputField() {
  const wrapper = $(document.createElement("div"));
  const wrapperInput = $(document.createElement("div"));
  const wrapperBtns = $(document.createElement("div"));

  const input = document.createElement("input");
  const submit = document.createElement("i");
  const cancel = $(document.createElement("i"));

  $(wrapper)
    .attr({
      style: "display: none",
    })
    .addClass("createDiv row");

  $(wrapperInput).addClass("col-3 col-lg-3 mb-md-0");

  $(input)
    .attr({
      type: "text",
      placeholder: "Attribute Tag to URL",
    })
    .addClass("tag userInput addTag");

  wrapperInput.append(input);

  $(wrapperBtns).addClass("col-3 col-lg-3 mb-md-0 text-right d-flex flex-row");

  $(submit)
    .addClass("fa fa-check-square fa-2x text-success mx-1")
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      addTag();
    });

  wrapperBtns.append(submit);

  $(cancel)
    .addClass("fa bi-x-square-fill fa-2x text-danger mx-1")
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      hideIfShown(wrapper);
    });

  wrapperBtns.append(cancel);

  wrapper.append(wrapperInput);
  wrapper.append(wrapperBtns);

  return wrapper;
}

// Handle tag deck display changes related to creating a new tag
function createTaginDeck(tagid, string) {
  const container = document.createElement("div");
  const label = document.createElement("label");

  $(container).addClass("tagFilter selected");

  // Select all and new tag creation specific items
  if (tagid == 0) {
    if (string == "selectAll") {
      $(container).attr({
        id: "selectAll",
        tagid: "all",
        onclick: 'filterTags(event, "all"); filterURLDeck()',
      });
      $(label).attr({
        for: "selectAll",
      });
      label.innerHTML = "Select All";

      $(container).append(label);
    } else if (string == "newTag") {
      let input = document.createElement("input");
      let submit = document.createElement("i");

      $(container).attr({
        class: "createDiv",
        style: "display: none",
      });

      $(input).attr({
        type: "text",
        id: "createTag",
        class: "userInput",
        placeholder: "New Tag name",
        // onblur: 'postData(event, "createTag")',
      });

      $(submit).attr({ class: "fa fa-check-square fa-2x text-success mx-1" });

      container.append(input);
      container.append(submit);
    }

    $("#listTags").append(container);
  } else {
    // Regular tag creation

    $(container).attr({
      tagid: tagid,
      onclick: "filterTags(event," + tagid + "); filterURLDeck()",
    });

    $(label).attr({ for: "Tag-" + tagid });
    label.innerHTML += string;

    $(container).append(label);

    // Move "createTag" element to the end of list
    let tagList = $("#listTags").children();
    const createTagEl = $(tagList[tagList.length - 1]).detach();
    $("#listTags").append(container);
    $("#listTags").append(createTagEl);
  }
}

// Update tag display to reflect changes in response to a filter request
function filterTags(e, tagID) {
  let filteredTag = $(e.target).closest("div");
  filteredTag.toggleClass("selected");

  let selAll = $("#selectAll");
  let tagList = $(".tagFilter");

  if (tagID == "all") {
    // Toggle all filter tags to match "Select All" checked status
    filteredTag.hasClass("selected")
      ? tagList.addClass("selected")
      : tagList.removeClass("selected");

    // Handle filtering in URL deck
    let spanObjs = $("span.tag");
    if (filteredTag.hasClass("selected")) {
      spanObjs.show();
    } else {
      spanObjs.hide();
      selAll.removeClass("selected");
    }
  } else {
    // Different conditions for selectAll behavior. If any other filters are unselected, then selectAll should be unselected. If all other filters are selected, then selectAll should be selected.
    if (selAll.hasClass("selected")) {
      if ($(".tagFilter").length > $(".tagFilter.selected").length) {
        selAll.removeClass("selected");
      }
    } else {
      if ($(".tagFilter").length - 1 == $(".tagFilter.selected").length) {
        selAll.addClass("selected");
      }
    }

    // Alternate formulation, does not work as of 04/17/23. selectAll select status should match the summed boolean select status of all other filters

    // let selAllBool;

    // for (let i in tagList) {
    //     console.log(i)
    //     console.log(tagList[i])
    //     console.log($(tagList[i]))
    //     selAllBool &= $(tagList[i]).hasClass('selected');
    // }

    // selAllBool ? selAll.addClass('selected') :
    //     selAll.removeClass('selected')

    // Handle filtering in URL deck
    $("span[tagid=" + tagID + "]").toggle();
  }
}
// Update URL deck to reflect changes in response to a user change of tag options
function filterURLDeck() {
  let URLcardst = $("div.url");
  for (let i = 0; i < URLcardst.length; i++) {
    let tagList = $(URLcardst[i]).find("span.tag");

    // If no tags associated with this URL, ignore. Unaffected by filter functionality
    if (tagList.length === 0) {
      continue;
    }

    // If all tags for given URL are style="display: none;", hide parent URL card
    let inactiveTagBool = tagList.map((i) =>
      tagList[i].style.display == "none" ? true : false,
    );
    // Manipulate mapped Object
    let boolArray = Object.entries(inactiveTagBool);
    boolArray.pop();
    boolArray.pop();

    // Default to hide URL
    let hideURLBool = true;
    boolArray.forEach((e) => (hideURLBool &= e[1]));

    // If url <div.card.url> has no tag <span>s in activeTagIDs, hide card column (so other cards shift into its position)
    if (hideURLBool) {
      $(URLcardst[i]).parent().hide();
    }
    // If tag reactivated, show URL
    else {
      $(URLcardst[i]).parent().show();
    }
  }
}

/** Post data handling **/

/* Add tag to URL */

// DP 09/17 do we need the ability to addTagtoURL interstitially before addURL is completed?

// Displays new Tag input prompt on selected URL
function addTagToURLShowInput() {
  // Prevent deselection of URL while modifying its values
  unbindSelectBehavior();

  let URLCard = getSelectedURLCard();

  // Show temporary div element containing input
  let inputEl = $(URLCard).find(".addTag");
  let inputDiv = inputEl.closest(".createDiv");
  inputEl.addClass("activeInput");
  showIfHidden(inputDiv);
  highlightInput(inputEl);

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
  let postURL = ADD_TAG_ROUTE + getCurrentUTubID() + "/" + getSelectedURLID();

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

  // Update Tags deck
  hideIfShown($("#noTagsHeader"));

  if (!isTagInDeck(tagid)) createTaginDeck(tagid, string);

  // Update tags in URL
  let tagSpan = createTaginURL(tagid, string);
  URLTagDeck.append(tagSpan);
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
function editTagsInDeckShowInput(handle) {
  hideIfShown($("#editTagButton"));
  showIfHidden($("#submitTagButton"));
  var listTagDivs = $("#listTags").children();

  for (let i in listTagDivs) {
    if (i == 0 || i >= listTagDivs.length - 1) {
    } else {
      if (handle == "submit") {
        // Editing, then handle submission
        console.log("submit initiated");
        var tagID = $(listTagDivs[i]).find('input[type="checkbox"]')[0].tagid;
        var tagText = $($(listTagDivs[i]).find('input[type="text"]')).val();
        console.log(tagID);
        console.log(tagText);
        postData([tagID, tagText], "editTags");
      } else {
        // User wants to edit, handle input text field display
        var tagText = $(listTagDivs[i]).find("label")[0].innerHTML;

        var input = document.createElement("input");
        $(input).attr({
          type: "text",
          class: "userInput",
          placeholder: "Edit tag name",
          value: tagText,
        });
        $(listTagDivs[i]).find("label").hide();
        $(listTagDivs[i]).append(input);
      }
    }
  }
}

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
    getCurrentUTubID() +
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
