/** URL-related constants **/

// Routes
const ADD_URL_ROUTE = "/url/add/"; // +<int:utub_id>
const EDIT_URL_ROUTE = "/url/edit/"; // +<int:utub_id>/<int:url_id>
const REMOVE_URL_ROUTE = "/url/remove/"; // +<int:utub_id>/<int:url_id>
const ACCESS_ALL_URLS_LIMIT_WARNING = 3;

/** URL UI Interactions **/

$(document).ready(function () {
  /* Bind click functions */

  // Add new URL to current UTub
  $("#addURLBtn").on("click", function (e) {
    // e.stopPropagation();
    // e.preventDefault();
    hideInputs();
    deselectAllURLs();
    addURLShowInput();

    // Bind enter key (keycode 13) to submit user input
    // DP 12/29 It'd be nice to have a single utils.js function with inputs of function and keyTarget (see failed attempt under bindKeyToFunction() in utils.js)
    unbindEnter();
    $(document).bind("keypress", function (e) {
      if (e.which == 13) {
        addURL();
      }
    });
  });

  // Open all URLs in UTub in separate tabs
  $("#accessAllURLsBtn").on("click", function (e) {
    // e.stopPropagation();
    // e.preventDefault();
    if (numOfURLs() > ACCESS_ALL_URLS_LIMIT_WARNING) {
      accessAllWarningShowModal();
    } else {
      accessAllURLsInUTub();
    }
  });
});

/** URL Utility Functions **/

// Function to count number of URLs in current UTub
function numOfURLs() {
  return $(".card.url").length - 1; // minus 1 to discount createURL block
}

// function to streamline the jQuery selector extraction of selected URL ID. And makes it easier in case the ID is encoded in a new location in the future
function getSelectedURLID() {
  return $(".selectedURL").attr("urlid");
}

// Simple function to streamline the jQuery selector extraction of selected URL card. Provides ease of reference by URL Functions.
function getSelectedURLCard() {
  return $("#listURLs").find(".card[urlid = " + getSelectedURLID() + "]")[0];
}

// Prevent deselection of URL while modifying its values (e.g. adding a tag, editing URL string or title)
function unbindSelectBehavior() {
  $(getSelectedURLCard().closest(".cardCol")).off("click");
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

// Show confirmation modal for opening all URLs in UTub
function accessAllWarningShowModal() {
  let modalTitle =
    "Are you sure you want to open all " + numOfURLs() + " URLs in this UTub?";
  let modalDismiss = "Cancel";

  $("#confirmModalTitle").text(modalTitle);

  $("#modalDismiss")
    .on("click", function (e) {
      e.preventDefault();
      $("#confirmModal").modal("hide");
    })
    .removeClass()
    .addClass("btn btn-danger")
    .text(modalDismiss);

  $("#modalSubmit")
    .removeClass()
    .addClass("btn btn-success")
    .on("click", function (e) {
      e.preventDefault();
      accessAllURLsInUTub();
    })
    .text("Open all URLs");

  $("#confirmModal").modal("show");

  hideIfShown($("#modalRedirect"));
}

// Opens all URLs in UTub in separate tabs
function accessAllURLsInUTub() {
  getUtubInfo(getActiveUTubID()).then(function (selectedUTub) {
    let dictURLs = selectedUTub.urls;

    for (i = 0; i < dictURLs.length; i++) {
      accessLink(dictURLs[i].url_string);
    }
  });
}

// Clear new URL Form
function resetNewURLForm() {
  $("#newURLTitle").val("");
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

/** URL Functions **/

// Build center panel URL list for selectedUTub
function buildURLDeck(UTubName, dictURLs, dictTags) {
  resetURLDeck();
  const parent = $("#UPRRow");
  let numOfURLs = dictURLs.length ? dictURLs.length : 0;

  if (numOfURLs !== 0) {
    displayState2URLDeck(UTubName, numOfURLs);

    // Instantiate deck with list of URLs stored in current UTub
    for (let i = 0; i < dictURLs.length; i++) {
      let URLcol = createURLBlock(
        dictURLs[i].url_ID,
        dictURLs[i].url_string,
        dictURLs[i].url_title,
        dictURLs[i].url_tags,
        dictTags,
      );

      parent.append(URLcol);
    }
  }
  else {
    console.log(UTubName)
    displayState1URLDeck(UTubName);
  }

  // New URL create block
  $("#URLFocusRow").append(createNewURLInputField());
}

// Create a URL block to add to current UTub/URLDeck
function createURLBlock(URLID, string, title, tagArray, dictTags) {
  const col = document.createElement("div");
  const card = document.createElement("div");
  // const cardImg = document.createElement('img');
  const urlInfo = document.createElement("div"); // This element holds the URL title and string
  const urlTitle = document.createElement("h5"); // This element displays the user-created title of the URL
  const urlString = document.createElement("p"); // This element displays the user's URL
  const editWrap = document.createElement("fieldset"); // This element wraps the edit field for URL title AND URL string
  const editWrap1 = document.createElement("div"); // This element wraps the edit field for URL title
  const editURLTitleLabel = document.createElement("label"); // This element labels the edit field for URL title
  const editURLTitleInput = document.createElement("input"); // This element is instantiated with the URL title
  const editWrap2 = document.createElement("div"); // This element wraps the edit field for URL string
  const editURLStringLabel = document.createElement("label"); // This element labels the edit field for URL string
  const editURLStringInput = document.createElement("input"); // This element is instantiated with the URL
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

  $(urlTitle).addClass("card-title URLTitle").text(title);

  $(urlString).addClass("card-text URLString").text(string);

  $(editWrap).attr({ style: "display: none" }).addClass("createDiv form-group");

  $(editURLTitleLabel)
    .attr({
      for: "editURLTitle-" + URLID,
      style: "display:block",
    })
    .html("<b> URL Title </b>");

  $(editURLTitleInput)
    .attr({
      id: "editURLTitle-" + URLID,
      type: "text",
      size: "40",
      value: title,
      placeholder: "Edit URL Title",
    })
    .addClass("card-title userInput editURLTitle");

  $(editWrap1)
    .addClass("form-group")
    .append(editURLTitleLabel)
    .append(editURLTitleInput);

  $(editURLStringLabel)
    .attr({
      for: "editURL-" + URLID,
      style: "display:block",
    })
    .html("<b> URL </b>");

  $(editURLStringInput)
    .attr({
      id: "editURL-" + URLID,
      type: "text",
      size: "40",
      value: string,
      placeholder: "Edit URL",
    })
    .addClass("card-text userInput editURLString");

  $(editWrap2)
    .addClass("form-group")
    .append(editURLStringLabel)
    .append(editURLStringInput);

  $(editWrap).append(editWrap1).append(editWrap2);

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
      $(document).bind("keypress", function (e) {
        if (e.which == 13) {
          editURL();
        }
      });
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
    .html(htmlString);

  // Assemble url list items
  $(col).append(card);
  $(card).append(urlInfo);

  $(urlInfo).append(urlTitle);
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
  const urlInfo = document.createElement("div"); // This element holds the URL title and string inputs
  const newWrap = document.createElement("fieldset"); // This element wraps the edit field for URL title AND URL string
  const newWrap1 = document.createElement("div"); // This element wraps the edit field for URL title
  const newURLTitleLabel = document.createElement("label"); // This element labels the input field for URL title
  const newURLTitle = document.createElement("input"); // This element is a blank input to accept a new URL title
  const newWrap2 = document.createElement("div"); // This element wraps the edit field for URL string
  const newURLStringLabel = document.createElement("label"); // This element labels the input field for URL string
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

  $(newWrap).addClass("form-group");

  $(newURLTitleLabel)
    .attr({
      for: "newURLTitle",
      style: "display:block",
    })
    .html("<b> URL Title </b>");

  $(newURLTitle).attr({
    id: "newURLTitle",
    class: "card-title userInput",
    placeholder: "New URL Title",
    type: "text",
    size: "50",
  });

  $(newWrap1).append(newURLTitleLabel).append(newURLTitle);

  $(newURLStringLabel)
    .attr({
      for: "newURLString",
      style: "display:block",
    })
    .html("<b> URL </b>");

  $(newURLString).attr({
    id: "newURLString",
    class: "card-text userInput",
    placeholder: "New URL",
    type: "text",
    size: "50",
  });

  $(newWrap2).append(newURLStringLabel).append(newURLString);

  $(newWrap).append(newWrap1).append(newWrap2);

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
      addURLHideInput();
    });

  // Assemble url list items
  $(col).append(card);
  $(card).append(urlInfo);

  $(urlInfo).append(newWrap);

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

/** URL Display State Functions **/

// Display state 0: Clean slate, no UTub selected
function displayState0URLDeck() {
  $("#URLDeckHeader").text("URLs");
  hideIfShown($(".URLDeckSubheader").closest(".row"));
  hideIfShown($(".editUTubBtn"));
  hideIfShown($("#addURLBtn"));
}

// Display state 1: UTub selected, URL list or subheader prompt
function displayState1URLDeck(UTubName, numOfURLs) {
  $("#URLDeckHeader").text(UTubName);
  $("#editUTubName").val(UTubName);
  showIfHidden($(".editUTubBtn"));
  showIfHidden($("#addURLBtn"));

  // Subheader prompt
  let URLDeckSubheader = $("#URLDeckSubheader")
  if (numOfURLs) {
    showIfHidden(URLDeckSubheader.closest(".row"));
    URLDeckSubheader.text(numOfURLs + numOfURLs === 1 ? "URL" : " URLs" + " stored");
  } else {
    showIfHidden(URLDeckSubheader.closest(".row"));
    URLDeckSubheader.text("Add a URL");
  }
}

/** Post data handling **/

/* Add URL */

// Displays new URL input prompt
function addURLHideInput() {
  hideInput("addURL");
}

// Displays new URL input prompt
function addURLShowInput() {
  showInput("addURL");
  highlightInput($("#newURLTitle"));
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
  let postURL = ADD_URL_ROUTE + getActiveUTubID();

  // Assemble submission data
  let newURLTitle = $("#newURLTitle").val();
  let newURL = $("#newURLString").val();
  data = {
    url_string: newURL,
    url_title: newURLTitle,
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
    response.URL.url_title,
    [],
    [],
  );

  $("#URLFocusRow").append(URLcol);

  showIfHidden($("#accessAllURLsBtn"));
}

// Displays appropriate prompts and options to user following a failed addition of a new URL
function addURLFailure(response) {
  console.log(response);
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
  showIfHidden(URLOptionsDiv.find(".editURLBtn"));
  showIfHidden(URLOptionsDiv.find(".addTagBtn"));
  showIfHidden(URLOptionsDiv.find(".remURLBtn"));

  // Show access URL button
  showIfHidden(URLOptionsDiv.find(".accessURLBtn"));

  // Hide input fields
  let inputElURLString = selectedCardDiv.find(".editURLString");
  let inputDivURLString = inputElURLString.closest(".createDiv");
  hideIfShown(inputDivURLString);

  // Show published values
  let URLInfoDiv = inputElURLString.closest(".URLInfo");
  showIfHidden(URLInfoDiv.find("h5"));
  showIfHidden(URLInfoDiv.find("p"));

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
  let postURL = EDIT_URL_ROUTE + getActiveUTubID() + "/" + getSelectedURLID();

  let selectedCardDiv = $(getSelectedURLCard());
  let editedURLfield = selectedCardDiv.find(".editURLString")[0];
  let editedURL = editedURLfield.value;
  let editedURLTitlefield = selectedCardDiv.find(".editURLTitle")[0];
  let editedURLTitle = editedURLTitlefield.value;
  data = {
    url_string: editedURL,
    url_title: editedURLTitle,
  };

  return [postURL, data];
}

// Displays changes related to a successful edition of a URL
function editURLSuccess(response) {
  // Extract response data
  let editedURLID = response.URL.url_ID;
  let editedURLTitle = response.URL.url_title;
  let editedURLString = response.URL.url_string;

  // If edit URL action, rebind the ability to select/deselect URL by clicking it
  rebindSelectBehavior(editedURLID);

  const selectedCardDiv = $(getSelectedURLCard());

  // Update URL ID
  selectedCardDiv.attr("urlid", editedURLID);

  // Updating input field placeholders
  let editURLTitleInput = selectedCardDiv.find(".editURLTitle");
  editURLTitleInput.text(editedURLTitle);
  let editURLStringInput = selectedCardDiv.find(".editURLString");
  editURLStringInput.text(editedURLString);

  // Update URL body with latest published data
  let URLTitleField = selectedCardDiv.find(".URLTitle");
  URLTitleField.text(editedURLTitle);
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

// Hide confirmation modal for removal of the selected URL
function removeURLHideModal() {
  $("#confirmModal").modal("hide");
  unbindEnter();
}

// Show confirmation modal for removal of the selected existing URL from current UTub
function removeURLShowModal() {
  let modalTitle = "Are you sure you want to delete this URL from the UTub?";
  let buttonTextDismiss = "Just kidding";
  let buttonTextSubmit = "Remove URL";

  $("#confirmModalTitle").text(modalTitle);

  $("#modalDismiss")
    .on("click", function (e) {
      e.preventDefault();
      removeURLHideModal();
    })
    .text(buttonTextDismiss);
  bindKeyToFunction(removeURLHideModal, 27);

  $("#modalSubmit")
    .on("click", function (e) {
      e.preventDefault();
      removeURL();
    })
    .text(buttonTextSubmit);
  bindKeyToFunction(removeURL, 13);

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
    REMOVE_URL_ROUTE + getActiveUTubID() + "/" + getSelectedURLID();

  return postURL;
}

// Displays changes related to a successful reomval of a URL
function removeURLSuccess() {
  // Close modal
  $("#confirmModal").modal("hide");

  let cardCol = $("div[urlid=" + getSelectedURLID() + "]").closest("li");
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
