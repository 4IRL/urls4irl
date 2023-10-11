/** URL-related constants **/

// Routes
const ADD_URL_ROUTE = "/url/add/"; // +<int:utub_id>
const EDIT_URL_ROUTE = "/url/edit/"; // +<int:utub_id>/<int:url_id>
const REMOVE_URL_ROUTE = "/url/remove/"; // +<int:utub_id>/<int:url_id>

/** URL UI Interactions **/

$(document).ready(function () {
  /* Bind click functions */

  // Add new URL to current UTub
  $("#addURLBtn").on("click", function (e) {
    e.stopPropagation();
    e.preventDefault();
    deselectAllURLs();
    addURLShowInput();
  });
});

/** URL Utility Functions **/

// Simple function to streamline the jQuery selector extraction of selected URL ID. And makes it easier in case the ID is encoded in a new location in the future
function selectedURLID() {
  return $(".selectedURL").attr("urlid");
}

// Simple function to streamline the jQuery selector extraction of selected URL card. Provides ease of reference by URL Functions.
function selectedURLCard() {
  return $("#listURLs").find(".card[urlid = " + selectedURLID() + "]")[0];
}

// Prevent deselection of URL while modifying its values (e.g. adding a tag, editing URL string or description)
function unbindSelectBehavior() {
  console.log(selectedURLCard());
  console.log(selectedURLCard().closest(".cardCol"));
  $(selectedURLCard().closest(".cardCol")).off("click");
}

// Rebinds selection click behavior after URL-modifying post requests are complete
function rebindSelectBehavior(response) {
  let selectedCardDiv = $(selectedURLCard());
  selectedCardDiv.closest(".cardCol").on("click", function (e) {
    e.stopPropagation();
    e.preventDefault();
    toggleSelectedURL(response.URL.url_ID);
  });
}

// Opens new tab
function accessLink(url_string) {
  // Still need to implement: Take user to a new tab with interstitial page warning they are now leaving U4I
  if (!url_string.startsWith("https://")) {
    window.open("https://" + url_string, "_blank");
  } else {
    window.open(url_string, "_blank");
  }
}

// Clear new URL Form
function resetNewURLForm() {
  $("#newURLDescription").val("");
  $("#newURL").val("");
  hideIfShown($("#createURL"));
}

// Clear the URL Deck
function resetURLDeck() {
  // Empty URL Deck
  $("#UPRRow").empty();
  $("#URLFocusRow").empty();
  $("#LWRRow").empty();
}

/* URL Functions */

// Build center panel URL list for selectedUTub
function buildURLDeck(dictURLs, dictTags) {
  resetURLDeck();

  for (let i = 0; i < dictURLs.length; i++) {
    let URLcol = createURLBlock(
      dictURLs[i].url_ID,
      dictURLs[i].url_string,
      dictURLs[i].url_description,
      dictURLs[i].url_tags,
      dictTags,
    );

    UPRRow.append(URLcol);
    // I actually don't know how 'UPRRow' and 'URLFocusRow' are referenced...but it works so I don't question it
  }

  // New URL create block
  URLFocusRow.append(createNewURLInputField());
}

// Create a URL block to add to current UTub/URLDeck
function createURLBlock(URLID, string, description, tagArray, dictTags) {
  let col = document.createElement("div");
  let card = document.createElement("div");
  // let cardImg = document.createElement('img');
  let urlInfo = document.createElement("div"); // This element holds the URL description and string
  let urlDescription = document.createElement("h5"); // This element displays the user-created description of the URL
  let urlString = document.createElement("p"); // This element displays the user's URL
  let editWrap = document.createElement("div"); // This element wraps the edit field for URL description AND URL string
  let editWrap1 = document.createElement("div"); // This element wraps the edit field for URL description
  let editURLDescription = document.createElement("input"); // This element is instantiated with the URL description
  let editWrap2 = document.createElement("div"); // This element wraps the edit field for URL string
  let editURLString = document.createElement("input"); // This element is instantiated with the URL
  let urlTags = document.createElement("div");
  let urlOptions = document.createElement("div");
  let accessURLBtn = document.createElement("button");
  let addTagBtn = document.createElement("button");
  let editURLBtn = document.createElement("button");
  let submitEditBtn = document.createElement("i"); // Submit changes after 'edit' operations
  let remURLBtn = document.createElement("button");

  $(col)
    .attr({
      class: "cardCol mb-3 col-md-10 col-lg-4 col-xl-3",
    })
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      toggleSelectedURL(URLID);
    });

  $(card).attr({
    urlid: URLID,
    class: "card url",
    draggable: "true",
    ondrop: "dropIt(event)",
    ondragover: "allowDrop(event)",
    ondragstart: "dragStart(event)",
  });

  // $(cardImg).attr({
  //     'class': 'card-img-top',
  //     'src': '...',
  //     'alt': '"Card image cap'
  // })

  $(urlInfo).attr({ class: "card-body URLInfo" });

  $(urlDescription)
    .attr({ class: "card-title URLDescription" })
    .text(description);

  $(urlString).attr({ class: "card-text URLString" }).text(string);

  $(editWrap).attr({
    class: "createDiv",
    style: "display: none",
  });

  $(editURLDescription).attr({
    class: "card-title userInput editURLDescription",
    type: "text",
    size: "50",
    value: description,
    placeholder: "Edit URL Description",
    // 'onblur': "postData(event, '" + editURLid + "')"
  });

  $(editWrap1).append(editURLDescription);

  $(editURLString).attr({
    class: "card-text userInput editURLString",
    type: "text",
    size: "50",
    value: string,
    placeholder: "Edit URL",
  });

  $(editWrap2).append(editURLString);

  $(editWrap).append(editWrap1);
  $(editWrap).append(editWrap2);

  $(urlTags).attr({
    class: "card-body URLTags",
    style: "display: none",
  });

  // Build tag html strings
  for (let j in tagArray) {
    // Find applicable tags in dictionary to apply to URL card
    let tag = dictTags.find(function (e) {
      if (e.id === tagArray[j]) {
        return e;
      }
    });

    let tagSpan = createTaginURL(tag.id, tag.tag_string);

    $(urlTags).append(tagSpan);
  }

  // New tag create span
  $(urlTags).append(createNewTagInputField());

  // Buttons
  $(urlOptions).attr({
    class: "card-body URLOptions",
    style: "display: none",
  });

  $(accessURLBtn)
    .attr({
      class: "card-link btn btn-primary accessURL",
      type: "button",
    })
    .text("Access Link")
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      accessLink(string);
    });

  $(addTagBtn)
    .attr({
      class: "card-link btn btn-info addTagBtn",
      type: "button",
    })
    .text("Add Tag")
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      addTagToURLShowInput();
    });

  $(editURLBtn)
    .attr({
      class: "card-link btn btn-warning editURLBtn",
      type: "button",
    })
    .text("Edit")
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      editURLShowInput();
    });

  $(remURLBtn)
    .attr({
      class: "card-link btn btn-danger remURLBtn",
      type: "button",
    })
    .text("Remove")
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      removeURLShowModal();
    });

  $(submitEditBtn)
    .attr({
      class: "fa fa-check-square fa-2x text-success mx-1 submitEditURLBtn",
      type: "button",
      style: "display: none",
    })
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      editURL();
    });

  // Assemble url list items
  $(col).append(card);
  $(card).append(urlInfo);

  $(urlInfo).append(urlDescription);
  $(urlInfo).append(urlString);
  $(urlInfo).append(editWrap);

  $(card).append(urlTags);

  $(card).append(urlOptions);
  $(urlOptions).append(accessURLBtn);
  $(urlOptions).append(addTagBtn);
  $(urlOptions).append(editURLBtn);
  $(urlOptions).append(remURLBtn);
  $(urlOptions).append(submitEditBtn);

  return col;
}

// New URL card and input text fields. Initially hidden, shown when create URL is requested. Input field recreated here to ensure at the end of list after creation of new URL
function createNewURLInputField() {
  let col = document.createElement("div");
  let card = document.createElement("div");
  // let cardImg = document.createElement('img');
  let urlInfo = document.createElement("div"); // This element holds the URL description and string inputs
  let newWrap = document.createElement("div"); // This element wraps the edit field for URL description AND URL string
  let newWrap1 = document.createElement("div"); // This element wraps the edit field for URL description
  let newURLDescription = document.createElement("input"); // This element is a blank input to accept a new URL description
  let newWrap2 = document.createElement("div"); // This element wraps the edit field for URL string
  let newURLString = document.createElement("input"); // This element is instantiated with the URL, or is blank for the creation block
  let urlTags = document.createElement("div");
  let urlOptions = document.createElement("div");
  let addURLBtn = document.createElement("button");
  let addTagBtn = document.createElement("button");
  let delURLBtn = document.createElement("button");

  $(col).attr({
    class: "createDiv cardCol mb-3 col-md-10 col-lg-10 col-xl-10",
    style: "display: none",
    // onblur: "hideInput(event)",
  });

  $(card).attr({
    urlid: 0,
    id: "addURL",
    class: "card url selected",
    draggable: "true",
    ondrop: "dropIt(event)",
    ondragover: "allowDrop(event)",
    ondragstart: "dragStart(event)",
  });

  // $(cardImg).attr({
  //     'class': 'card-img-top',
  //     'src': '...',
  //     'alt': '"Card image cap'
  // })

  $(urlInfo).attr({ class: "card-body URLInfo" });

  $(newURLDescription).attr({
    id: "newURLDescription",
    class: "card-title userInput",
    placeholder: "New URL Description",
    type: "text",
    size: "50",
  });

  $(newWrap1).append(newURLDescription);

  $(newURLString).attr({
    id: "newURLString",
    class: "card-text userInput",
    placeholder: "New URL",
    type: "text",
    size: "50",
  });

  $(newWrap2).append(newURLString);

  $(urlTags).attr({ class: "card-body URLTags" });

  // Add tag input
  $(urlTags).append(createNewTagInputField());

  // Buttons
  $(urlOptions).attr({ class: "card-body URLOptions" });

  $(addURLBtn)
    .attr({
      class: "card-link btn btn-success",
      type: "button",
    })
    .text("Add URL")
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      addURL();
    });

  $(addTagBtn)
    .attr({
      class: "card-link btn btn-info",
      type: "button",
    })
    .text("Add Tag")
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      addTagToURLShowInput();
    });

  $(delURLBtn)
    .attr({
      class: "card-link btn btn-danger",
      type: "button",
    })
    .text("Cancel")
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      hideIfShown($("#addURL").closest(".createDiv"));
    });

  // Assemble url list items
  $(col).append(card);
  $(card).append(urlInfo);

  $(urlInfo).append(newWrap1);
  $(urlInfo).append(newWrap2);

  $(card).append(urlTags);

  $(card).append(urlOptions);
  $(urlOptions).append(addURLBtn);
  $(urlOptions).append(addTagBtn);
  $(urlOptions).append(delURLBtn);

  return col;
}

// Display updates related to selection of a URL
function selectURL(selectedCardCol) {
  let card = selectedCardCol.find(".card");
  let URLTags = selectedCardCol.find(".URLTags");
  let URLOptions = selectedCardCol.find(".URLOptions");

  selectedCardCol.addClass("col-lg-10 col-xl-10");
  selectedCardCol.removeClass("col-lg-4 col-xl-3");
  card.addClass("selectedURL");
  card.attr("draggable", "");
  showIfHidden(URLTags);
  showIfHidden(URLOptions);
}

// Display updates related to deselection of a URL
function deselectURL(deselectedCardCol) {
  let card = deselectedCardCol.find(".card");
  let URLTags = deselectedCardCol.find(".URLTags");
  let URLOptions = deselectedCardCol.find(".URLOptions");

  deselectedCardCol.addClass("col-lg-4 col-xl-3");
  deselectedCardCol.removeClass("col-lg-10 col-xl-10");
  card.removeClass("selectedURL");
  card.attr("draggable");
  hideIfShown(URLTags);
  hideIfShown(URLOptions);
}

// Deselects all URLs in preparation for creation URL
function deselectAllURLs() {
  let cardCols = $(".cardCol");

  for (let i = 0; i < cardCols.length; i++) {
    let cardCol = $(cardCols[i]);
    let createURLBlockBool = cardCol.hasClass("createDiv");

    if (!createURLBlockBool) deselectURL(cardCol);
  }
}

// User clicks a URL. If already selected, URL is deselected, else it is selected. All other URLs are deselected. This function places all URLs prior to selected URL into #UPRRow, inserts selected URL into a separate #URLFocusRow, and places all subsequent URLs into #LWRRow. It also adjusts css displays accordingly
// REHch goal 09/12/23 may want a "display order" attribute stored in backend. Option to sort by alpha, date added, or custom prescribed "display order". This display can be manipulated by drag-drop of the URL card.
function toggleSelectedURL(selectedURLID) {
  let cardCols = $(".cardCol");

  let activeRow = $("#UPRRow");
  let focusRow = $("#URLFocusRow");

  // Hide createURL block
  hideInput("addURL");

  // Loop through all cardCols and add to UPR row until selected URL card, then subsequent cardCols are added to LWR row
  for (let i = 0; i < cardCols.length; i++) {
    let cardCol = $(cardCols[i]);
    let card = cardCol.find(".card");
    let URLID = card.attr("urlid");
    let selectBool = card.hasClass("selectedURL");
    let clickedCardBool = URLID == selectedURLID;
    let createURLBlockBool = card.attr("id") === "createURL";

    // If this cardCol is the creation block, skip it and move to the next iteration
    if (createURLBlockBool) continue;
    // If this is not the card the user clicked or it's already selected, deselect it and add it to the activeRow
    if (!clickedCardBool || selectBool) {
      deselectURL(cardCol);
      activeRow.append(cardCol);
    }
    // URL the user clicked is deselected, select it
    if (!selectBool && clickedCardBool) {
      selectURL(cardCol);
      focusRow.append(cardCol);

      // Reorder createURL card to before selected URL
      let createCardCol = $("#createURL").closest(".cardCol").detach();
      focusRow.prepend(createCardCol);

      // All subsequent cardCols should be added below the focusRow
      activeRow = $("#LWRRow");
    }
  }
}

/** Post data handling **/

/* Add URL */

// Displays new URL input prompt
function addURLShowInput() {
  showInput("addURL");
  highlightInput($("#newURLDescription"));
}

// Handles addition of new URL after user submission
function addURL() {
  // Extract data to submit in POST request
  [postURL, data] = addURLSetup();

  AJAXCall("post", postURL, data);

  // Handle response
  request.done(function (response, textStatus, xhr) {
    console.log("success");

    if (xhr.status == 200) {
      addURLSuccess(response);
    }
  });

  request.fail(function (response, textStatus, xhr) {
    console.log("failed");

    if (xhr.status == 404) {
      // Reroute to custom U4I 404 error page
    } else {
      addURLFailure(response);
    }
  });
}

// Prepares post request inputs for addition of a new URL
function addURLSetup() {
  // Assemble post request route
  let postURL = ADD_URL_ROUTE + currentUTubID();

  // Assemble submission data
  let newURLDescription = $("#newURLDescription").val();
  let newURL = $("#newURLString").val();
  data = {
    url_string: newURL,
    url_description: newURLDescription,
  };

  return [postURL, data];
}

// Displays changes related to a successful addition of a new URL
function addURLSuccess(response) {
  resetNewURLForm();

  // DP 09/17 need to implement ability to addTagtoURL interstitially before addURL is completed
  let URLcol = createURLBlock(
    response.URL.url_ID,
    response.URL.url_string,
    response.URL.url_description,
    [],
    [],
  );

  URLFocusRow.append(URLcol);
}

// Displays appropriate prompts and options to user following a failed addition of a new URL
function addURLFailure(response) {
  console.log("Basic implementation. Needs revision");
  console.log(response.responseJSON.Error_code);
  console.log(response.responseJSON.Message);
  // DP 09/17 could we maybe have a more descriptive reason for failure sent from backend to display to user?
  // Currently STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_ADD_URL is too generic. the # * comments are ideal
}

/* Edit URL */

// Shows edit URL inputs
function editURLShowInput() {
  // Show edit submission icon, hide edit request icon
  let selectedCardDiv = $(selectedURLCard());
  let URLOptionsDiv = selectedCardDiv.find(".URLOptions");
  showIfHidden(URLOptionsDiv.find("i"));
  hideIfShown(URLOptionsDiv.find(".editURLBtn"));

  // Show input fields
  let inputElURLString = selectedCardDiv.find(".editURLString");
  let inputDivURLString = inputElURLString.closest(".createDiv");
  showIfHidden($(inputDivURLString));

  // Hide published values
  let URLInfoDiv = selectedCardDiv.find(".URLInfo");
  hideIfShown($(URLInfoDiv.find("h5")));
  hideIfShown($(URLInfoDiv.find("p")));

  // Inhibit selection toggle behavior until user cancels edit, or successfully submits edit. User can still select and edit other URLs in UTub
  unbindSelectBehavior();
}

// Hides edit URL inputs
function editURLHideInput() {
  // Hide edit submission icon, show edit request icon
  let selectedCardDiv = $(selectedURLCard());
  let URLOptionsDiv = selectedCardDiv.find(".URLOptions");
  showIfHidden($(URLOptionsDiv.find(".editURLBtn")));
  hideIfShown($(URLOptionsDiv.find("i")));

  // Hide input fields
  let inputElURLString = selectedCardDiv.find(".editURLString");
  let inputDivURLString = inputElURLString.closest(".createDiv");
  hideIfShown($(inputDivURLString));

  // Show published values
  let URLInfoDiv = inputElURLString.closest(".URLInfo");
  showIfHidden($(URLInfoDiv.find("h5")));
  showIfHidden($(URLInfoDiv.find("p")));

  // Update URL options display
  hideIfShown(selectedCardDiv.find(".submitEditURLBtn"));
  showIfHidden(selectedCardDiv.find(".editURLBtn"));
}

function editURL() {
  // Extract data to submit in POST request
  [postURL, data] = editURLSetup();

  AJAXCall("post", postURL, data);

  // Handle response
  request.done(function (response, textStatus, xhr) {
    console.log("success");

    if (xhr.status == 200) {
      editURLSuccess(response);
    }
  });

  request.fail(function (response, textStatus, xhr) {
    console.log("failed");

    if (xhr.status == 404) {
      // Reroute to custom U4I 404 error page
    } else {
      editURLFail(response);
    }
  });
}

function editURLSetup() {
  let postURL = EDIT_URL_ROUTE + currentUTubID() + "/" + selectedURLID();

  let selectedCardDiv = $(selectedURLCard());
  console.log(selectedCardDiv);
  let editedURLfield = selectedCardDiv.find(".editURLString")[0];
  let editedURL = editedURLfield.value;
  let editedURLDescriptionfield = selectedCardDiv.find(
    ".editURLDescription",
  )[0];
  let editedURLDescription = editedURLDescriptionfield.value;
  data = {
    url_string: editedURL,
    url_description: editedURLDescription,
  };

  return [postURL, data];
}

function editURLSuccess(response) {
  // If edit URL action, rebind the ability to select/deselect URL by clicking it
  rebindSelectBehavior(response);

  // Extract response data
  let editedURLID = response.URL.url_ID;
  let editedURLDescription = response.URL.url_description;
  let editedURLString = response.URL.url_string;

  let selectedCardDiv = $(selectedURLCard());

  // Update URL ID
  selectedCardDiv.attr("urlid", editedURLID);

  // Updating input field placeholders
  let editURLDescriptionInput = selectedCardDiv.find(".editURLDescription");
  editURLDescriptionInput.text(editedURLDescription);
  let editURLStringInput = selectedCardDiv.find(".editURLString");
  editURLStringInput.text(editedURLString);

  // Update URL body with latest published data
  let URLDescriptionField = selectedCardDiv.find(".URLDescription");
  URLDescriptionField.text(editedURLDescription);
  let URLStringField = selectedCardDiv.find(".URLString");
  URLStringField.text(editedURLString);

  // Update URL options
  selectedCardDiv
    .find(".accessURL")
    .off("click")
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      accessLink(editedURLString);
    });

  editURLHideInput();
}

function editURLFail(response) {
  console.log("Unimplemented");
}

/* Remove URL */

// Show confirmation modal for removal of the selected existing URL from current UTub
function removeURLShowModal() {
  let modalTitle = "Are you sure you want to delete this URL from the UTub?";
  $(".modal-title").text(modalTitle);

  $("#modalDismiss").on("click", function (e) {
    e.preventDefault();
    $("#confirmModal").modal("hide");
  });

  $("#modalSubmit").on("click", function (e) {
    e.preventDefault();
    removeURL();
  });

  $("#confirmModal").modal("show");

  hideIfShown($("#modalRedirect"));
}

// Handles post request and response for removing an existing URL from current UTub, after confirmation
function removeURL() {
  // Extract data to submit in POST request
  postURL = removeURLSetup();

  let request = AJAXCall("post", postURL, []);

  // Handle response
  request.done(function (response, textStatus, xhr) {
    console.log("success");

    if (xhr.status == 200) {
      removeURLSuccess();
    }
  });

  request.fail(function (response, textStatus, xhr) {
    console.log("failed");

    if (xhr.status == 404) {
      // Reroute to custom U4I 404 error page
    } else {
      removeURLFail(response);
    }
  });
}

function removeURLSetup() {
  let postURL = REMOVE_URL_ROUTE + currentUTubID() + "/" + selectedURLID();

  return postURL;
}

function removeURLSuccess() {
  // Close modal
  $("#confirmModal").modal("hide");

  let cardCol = $("div[urlid=" + selectedURLID() + "]").parent();
  cardCol.fadeOut();
  cardCol.remove();
}

function removeURLFail(xhr, textStatus, error) {
  console.log("Error: Could not delete URL");

  if (xhr.status == 409) {
    console.log(
      "Failure. Status code: " + xhr.status + ". Status: " + textStatus,
    );
    console.log("Error: " + error.Error_code);
  }
}
