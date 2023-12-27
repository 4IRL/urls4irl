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

  // Open all URLs in UTub in separate tabs
  $("#accessAllURLsBtn").on("click", function (e) {
    e.stopPropagation();
    e.preventDefault();
    accessAllLinksInUTub();
  });
});

/** URL Utility Functions **/

// Function to count number of URLs in current UTub
function numOfURLs() {
  return;
}

// function to streamline the jQuery selector extraction of selected URL ID. And makes it easier in case the ID is encoded in a new location in the future
function getSelectedURLID() {
  return $(".selectedURL").attr("urlid");
}

// Simple function to streamline the jQuery selector extraction of selected URL card. Provides ease of reference by URL Functions.
function getSelectedURLCard() {
  return $("#listURLs").find(".card[urlid = " + getSelectedURLID() + "]")[0];
}

// Prevent deselection of URL while modifying its values (e.g. adding a tag, editing URL string or description)
function unbindSelectBehavior() {
  $(getSelectedURLCard().closest(".cardCol")).off("click");
  $(document).on("keyup", function (e) {
    let keycode = e.keyCode ? e.keyCode : e.which;
    if (keycode == 27) {
      // ESC key, unbind action
    }
  });
}

// Rebinds selection click behavior after URL-modifying post requests are complete
function rebindSelectBehavior(URLID) {
  const selectedCardDiv = $(getSelectedURLCard());
  selectedCardDiv.closest(".cardCol").on("click", function (e) {
    e.stopPropagation();
    e.preventDefault();
    toggleSelectedURL(URLID);
  });
  $(document).on("keyup", function (e) {
    let keycode = e.keyCode ? e.keyCode : e.which;
    if (keycode == 27) {
      // ESC key, hide all URL cardCols
      deselectAllURLs();
      deselectAddURL();
    }
  });
}

// Opens new tab
function accessLink(url_string) {
  // Still need to implement: Take user to a new tab with interstitial page warning they are now leaving U4I

  if (!url_string.startsWith("https://")) {
    window.open("https://" + url_string, "_blank").focus();
  } else {
    window.open(url_string, "_blank").focus();
  }
}

// Opens all URLs in UTub in separate tabs
function accessAllLinksInUTub() {
  getUtubInfo(getCurrentUTubID()).then(function (selectedUTub) {
    let dictURLs = selectedUTub.urls;

    for (i = 0; i < dictURLs.length; i++) {
      accessLink(dictURLs[i].url_string);
    }
  });
}

// Clear new URL Form
function resetNewURLForm() {
  $("#newURLDescription").val("");
  $("#newURLString").val("");
  hideIfShown($("#newURLString").closest(".createDiv"));
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
  let UPRRow = $("#UPRRow");

  for (let i = 0; i < dictURLs.length; i++) {
    let URLcol = createURLBlock(
      dictURLs[i].url_ID,
      dictURLs[i].url_string,
      dictURLs[i].url_description,
      dictURLs[i].url_tags,
      dictTags,
    );

    UPRRow.append(URLcol);
  }

  // New URL create block
  $("#URLFocusRow").append(createNewURLInputField());
}

// Create a URL block to add to current UTub/URLDeck
function createURLBlock(URLID, string, description, tagArray, dictTags) {
  const col = document.createElement("div");
  const card = document.createElement("div");
  // const cardImg = document.createElement('img');
  const urlInfo = document.createElement("div"); // This element holds the URL description and string
  const urlDescription = document.createElement("h5"); // This element displays the user-created description of the URL
  const urlString = document.createElement("p"); // This element displays the user's URL
  const editWrap = document.createElement("div"); // This element wraps the edit field for URL description AND URL string
  const editWrap1 = document.createElement("div"); // This element wraps the edit field for URL description
  const editURLDescription = document.createElement("input"); // This element is instantiated with the URL description
  const editWrap2 = document.createElement("div"); // This element wraps the edit field for URL string
  const editURLString = document.createElement("input"); // This element is instantiated with the URL
  const urlTags = document.createElement("div");
  const urlOptions = document.createElement("div");
  const accessURLBtn = document.createElement("button");
  const addTagBtn = document.createElement("button");
  const editURLBtn = document.createElement("button");
  const submitEditBtn = document.createElement("i"); // Submit changes after 'edit' operations
  const cancelEditBtn = document.createElement("i"); // Cancel changes after 'edit' operations, populate with pre-edit values
  const remURLBtn = document.createElement("button");

  $(col)
    .addClass("cardCol mb-3 col-md-10 col-lg-4 col-xl-3")
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      toggleSelectedURL(URLID);
    });

  $(card)
    .attr({
      urlid: URLID,
      // draggable: "true",
      ondrop: "dropIt(event)",
      ondragover: "allowDrop(event)",
      ondragstart: "dragStart(event)",
    })
    .addClass("card url");

  // $(cardImg).attr({
  //     'src': '...',
  //     'alt': '"Card image cap'
  // })
  // .addClass("card-img-top")

  $(urlInfo).addClass("card-body URLInfo");

  $(urlDescription).addClass("card-title URLDescription").text(description);

  $(urlString).addClass("card-text URLString").text(string);

  $(editWrap)
    .attr({
      style: "display: none",
    })
    .addClass("createDiv");

  $(editURLDescription)
    .attr({
      type: "text",
      size: "50",
      value: description,
      placeholder: "Edit URL Description",
      // 'onblur': "postData(event, '" + editURLid + "')"
    })
    .addClass("card-title userInput editURLDescription");

  $(editWrap1).append(editURLDescription);

  $(editURLString)
    .attr({
      type: "text",
      size: "50",
      value: string,
      placeholder: "Edit URL",
    })
    .addClass("card-text userInput editURLString");

  $(editWrap2).append(editURLString);

  $(editWrap).append(editWrap1);
  $(editWrap).append(editWrap2);

  $(urlTags)
    .attr({
      style: "display: none",
    })
    .addClass("card-body URLTags");

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
  $(urlOptions)
    .attr({
      style: "display: none",
    })
    .addClass("card-body URLOptions");

  $(accessURLBtn)
    .attr({
      type: "button",
    })
    .addClass("card-link btn btn-primary accessURLBtn")
    .text("Access Link")
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      accessLink(string);
    });

  $(addTagBtn)
    .attr({
      type: "button",
    })
    .addClass("card-link btn btn-info addTagBtn")
    .text("Add Tag")
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      addTagToURLShowInput();
    });

  $(editURLBtn)
    .attr({
      type: "button",
    })
    .addClass("card-link btn btn-warning editURLBtn")
    .text("Edit")
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      editURLShowInput();
    });

  $(remURLBtn)
    .attr({ type: "button" })
    .addClass("card-link btn btn-danger remURLBtn")
    .text("Remove")
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      removeURLShowModal();
    });

  // Submit editURL checkbox
  let htmlString =
    '<svg xmlns="http://www.w3.org/2000/svg" fill="currentColor" class="b=i bi-check-square-fill" viewBox="0 0 16 16" width="' +
    ICON_WIDTH +
    '" height="' +
    ICON_HEIGHT +
    '">' +
    '<path d="M2 0a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V2a2 2 0 0 0-2-2zm10.03 4.97a.75.75 0 0 1 .011 1.05l-3.992 4.99a.75.75 0 0 1-1.08.02L4.324 8.384a.75.75 0 1 1 1.06-1.06l2.094 2.093 3.473-4.425a.75.75 0 0 1 1.08-.022z"/>' +
    "</svg>";

  $(submitEditBtn)
    .attr({ style: "display: none" })
    .addClass("mx-1 green-clickable submitEditURLBtn")
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      editURL();
    })
    .html(htmlString);

  // Cancel editURL x-box
  htmlString =
    '<svg xmlns="http://www.w3.org/2000/svg" fill="currentColor" class="bi bi-x-square-fill text-danger" viewBox="0 0 16 16" width="' +
    ICON_WIDTH +
    '" height="' +
    ICON_HEIGHT +
    '">' +
    '<path d="M2 0a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V2a2 2 0 0 0-2-2zm3.354 4.646L8 7.293l2.646-2.647a.5.5 0 0 1 .708.708L8.707 8l2.647 2.646a.5.5 0 0 1-.708.708L8 8.707l-2.646 2.647a.5.5 0 0 1-.708-.708L7.293 8 4.646 5.354a.5.5 0 1 1 .708-.708"/>' +
    "</svg>";

  $(cancelEditBtn)
    .attr({ style: "display: none" })
    .addClass("mx-1 cancelEditURLBtn")
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      // cancelEditURL();
    })
    .html(htmlString);

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
  $(urlOptions).append(cancelEditBtn);

  return col;
}

// New URL card and input text fields. Initially hidden, shown when create URL is requested. Input field recreated here to ensure at the end of list after creation of new URL
function createNewURLInputField() {
  const col = document.createElement("div");
  const card = document.createElement("div");
  // const cardImg = document.createElement('img');
  const urlInfo = document.createElement("div"); // This element holds the URL description and string inputs
  const newWrap = document.createElement("div"); // This element wraps the edit field for URL description AND URL string
  const newWrap1 = document.createElement("div"); // This element wraps the edit field for URL description
  const newURLDescription = document.createElement("input"); // This element is a blank input to accept a new URL description
  const newWrap2 = document.createElement("div"); // This element wraps the edit field for URL string
  const newURLString = document.createElement("input"); // This element is instantiated with the URL, or is blank for the creation block
  const urlTags = document.createElement("div");
  const urlOptions = document.createElement("div");
  const addURLBtn = document.createElement("button");
  const delURLBtn = document.createElement("button");

  $(col).attr({
    class: "createDiv cardCol mb-3 col-md-10 col-lg-10 col-xl-10",
    style: "display: none",
    // onblur: "hideInput(event)",
  });

  $(card).attr({
    urlid: 0,
    id: "addURL",
    class: "card url selected",
    // draggable: "true",
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

  $(delURLBtn)
    .attr({
      class: "card-link btn btn-danger",
      type: "button",
    })
    .text("Cancel")
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      hideIfShown($("#newURL").closest(".createDiv"));
    });

  // Assemble url list items
  $(col).append(card);
  $(card).append(urlInfo);

  $(urlInfo).append(newWrap1);
  $(urlInfo).append(newWrap2);

  $(card).append(urlTags);

  $(card).append(urlOptions);
  $(urlOptions).append(addURLBtn);
  $(urlOptions).append(delURLBtn);

  return col;
}

// Display updates related to selection of a URL
function selectURL(selectedCardCol) {
  const card = selectedCardCol.find(".card");
  const URLTags = selectedCardCol.find(".URLTags");
  const URLOptions = selectedCardCol.find(".URLOptions");

  selectedCardCol.addClass("col-lg-10 col-xl-10");
  selectedCardCol.removeClass("col-lg-4 col-xl-3");
  card.addClass("selectedURL");
  // card.attr("draggable", "");
  showIfHidden(URLTags);
  showIfHidden(URLOptions);
}

// Display updates related to deselection of a URL
function deselectURL(deselectedCardCol) {
  const card = deselectedCardCol.find(".card");
  const URLTags = deselectedCardCol.find(".URLTags");
  const URLOptions = deselectedCardCol.find(".URLOptions");

  deselectedCardCol.addClass("col-lg-4 col-xl-3");
  deselectedCardCol.removeClass("col-lg-10 col-xl-10");
  card.removeClass("selectedURL");
  // card.attr("draggable");
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

// Deselects addURL block
function deselectAddURL() {
  hideIfShown($("#newURL").closest(".cardCol"));
}

// User clicks a URL. If already selected, URL is deselected, else it is selected. All other URLs are deselected. This function places all URLs prior to selected URL into #UPRRow, inserts selected URL into a separate #URLFocusRow, and places all subsequent URLs into #LWRRow. It also adjusts css displays accordingly
// REHch goal 09/12/23 may want a "display order" attribute stored in backend. Option to sort by alpha, date added, or custom prescribed "display order". This display can be manipulated by drag-drop of the URL card.
function toggleSelectedURL(selectedURLID) {
  let cardCols = $(".cardCol");

  let activeRow = $("#UPRRow");
  let focusRow = $("#URLFocusRow");

  // Hide addURL block
  hideInput("addURL");

  // Loop through all cardCols and add to UPR row until selected URL card, then subsequent cardCols are added to LWR row
  for (let i = 0; i < cardCols.length; i++) {
    let cardCol = $(cardCols[i]);
    let card = cardCol.find(".card");
    let URLID = card.attr("urlid");
    let selectBool = card.hasClass("selectedURL");
    let clickedCardBool = URLID == selectedURLID;
    let addURLBlockBool = card.attr("id") === "addURL";

    // If this cardCol is the creation block, skip it and move to the next iteration
    if (addURLBlockBool) continue;
    // If this is not the card the user clicked or it's already selected, deselect it and add it to the activeRow
    if (!clickedCardBool || selectBool) {
      deselectURL(cardCol);
      activeRow.append(cardCol);
    }
    // URL the user clicked is deselected, select it
    if (!selectBool && clickedCardBool) {
      selectURL(cardCol);
      focusRow.append(cardCol);

      // Reorder addURL card to before selected URL
      let createCardCol = $("#addURL").closest(".cardCol").detach();
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
  let postURL = ADD_URL_ROUTE + getCurrentUTubID();

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

  $("#URLFocusRow").append(URLcol);

  showIfHidden($("#accessAllURLsBtn"));
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
  // Show edit submission button, hide other buttons
  let selectedCardDiv = $(getSelectedURLCard());
  let URLOptionsDiv = selectedCardDiv.find(".URLOptions");
  showIfHidden(URLOptionsDiv.find(".submitEditURLBtn"));
  showIfHidden(URLOptionsDiv.find(".cancelEditURLBtn"));
  hideIfShown(URLOptionsDiv.find(".editURLBtn"));
  hideIfShown(URLOptionsDiv.find(".addTagBtn"));
  hideIfShown(URLOptionsDiv.find(".remURLBtn"));

  // Hide access URL button
  hideIfShown(URLOptionsDiv.find(".accessURLBtn"));

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
  // Hide edit submission button, show other buttons
  let selectedCardDiv = $(getSelectedURLCard());
  let URLOptionsDiv = selectedCardDiv.find(".URLOptions");
  hideIfShown(URLOptionsDiv.find(".submitEditURLBtn"));
  hideIfShown(URLOptionsDiv.find(".cancelEditURLBtn"));
  showIfHidden($(URLOptionsDiv.find(".editURLBtn")));
  showIfHidden(URLOptionsDiv.find(".addTagBtn"));
  showIfHidden(URLOptionsDiv.find(".remURLBtn"));

  // Show access URL button
  showIfHidden(URLOptionsDiv.find(".accessURLBtn"));

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

// Handles edition of an existing URL
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

// Prepares post request inputs for edition of a URL
function editURLSetup() {
  let postURL = EDIT_URL_ROUTE + getCurrentUTubID() + "/" + getSelectedURLID();

  let selectedCardDiv = $(getSelectedURLCard());
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

// Displays changes related to a successful edition of a URL
function editURLSuccess(response) {
  // Extract response data
  let editedURLID = response.URL.url_ID;
  let editedURLDescription = response.URL.url_description;
  let editedURLString = response.URL.url_string;

  // If edit URL action, rebind the ability to select/deselect URL by clicking it
  rebindSelectBehavior(editedURLID);

  const selectedCardDiv = $(getSelectedURLCard());

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

// Displays appropriate prompts and options to user following a failed edition of a URL
function editURLFail(response) {
  console.log("Unimplemented");
}

/* Remove URL */

// Show confirmation modal for removal of the selected existing URL from current UTub
function removeURLShowModal() {
  let modalTitle = "Are you sure you want to delete this URL from the UTub?";
  let modalDismiss = "Just kidding";

  $("#confirmModalTitle").text(modalTitle);

  $("#modalDismiss")
    .on("click", function (e) {
      e.preventDefault();
      $("#confirmModal").modal("hide");
    })
    .text(modalDismiss);

  $("#modalSubmit")
    .on("click", function (e) {
      e.preventDefault();
      removeURL();
    })
    .text("Remove URL");

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

// Prepares post request inputs for removal of a URL
function removeURLSetup() {
  let postURL =
    REMOVE_URL_ROUTE + getCurrentUTubID() + "/" + getSelectedURLID();

  return postURL;
}

// Displays changes related to a successful reomval of a URL
function removeURLSuccess() {
  // Close modal
  $("#confirmModal").modal("hide");

  let cardCol = $("div[urlid=" + getSelectedURLID() + "]").parent();
  cardCol.fadeOut();
  cardCol.remove();
}

// Displays appropriate prompts and options to user following a failed removal of a URL
function removeURLFail(xhr, textStatus, error) {
  console.log("Error: Could not delete URL");

  if (xhr.status == 409) {
    console.log(
      "Failure. Status code: " + xhr.status + ". Status: " + textStatus,
    );
    console.log("Error: " + error.Error_code);
  }
}
