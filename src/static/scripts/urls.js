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
    const ACCESS_ALL_URLS_LIMIT_WARNING = 3;
    if (getNumOfURLs() > ACCESS_ALL_URLS_LIMIT_WARNING) {
      accessAllWarningShowModal();
    } else {
      accessAllURLsInUTub();
    }
  });
});

/** URL Utility Functions **/

// Function to count number of URLs in current UTub
function getNumOfURLs() {
  return $(".url").length;
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
function unbindSelectURLBehavior() {
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
    "Are you sure you want to open all " +
    getNumOfURLs() +
    " URLs in this UTub?";
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
  let numOfURLs = dictURLs.length;
  numOfURLs = numOfURLs ? numOfURLs : 0;

  if (numOfURLs !== 0) {
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

  // New URL create block
  $("#URLFocusRow").append(createNewURLInputField());

  displayState1URLDeck(UTubName);
}

// Create a URL block to add to current UTub/URLDeck
function createURLBlock(URLID, string, title, tagArray, dictTags) {
  const col = document.createElement("div");
  const card = document.createElement("div");
  // const cardImg = document.createElement('img');
  const urlInfo = document.createElement("div"); // This element holds the URL title and string
  const urlTitle = document.createElement("h5"); // This element displays the user-created title of the URL
  const editURLTitleBtn = document.createElement("i");
  const URL = document.createElement("p"); // This element displays the user's URL
  const editURLBtn = document.createElement("i");
  const editURLTitleWrap = document.createElement("div"); // This element wraps the edit field for URL title
  const editURLTitleLabel = document.createElement("label"); // This element labels the edit field for URL title
  const editURLTitleInput = document.createElement("input"); // This element is instantiated with the URL title
  const editURLWrap = document.createElement("div"); // This element wraps the edit field for URL string
  const editURLLabel = document.createElement("label"); // This element labels the edit field for URL string
  const editURLInput = document.createElement("input"); // This element is instantiated with the URL
  const urlTags = document.createElement("div");
  const urlOptions = document.createElement("div");
  const accessURLBtn = document.createElement("button");
  const addTagBtn = document.createElement("button");
  const submitEditBtn = document.createElement("i"); // Submit changes after 'edit' operations
  const cancelEditBtn = document.createElement("i"); // Cancel changes after 'edit' operations, populate with pre-edit values
  const delURLBtn = document.createElement("button");

  $(col)
    .addClass("cardCol mb-3 col-md-10 col-lg-4 col-xl-3")
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      toggleSelectedURL(URLID);
    });

  $(card)
    .addClass("card url")
    .attr({
      urlid: URLID,
      // draggable: "true",
      ondrop: "dropIt(event)",
      ondragover: "allowDrop(event)",
      ondragstart: "dragStart(event)",
    });

  // $(cardImg).attr({
  //     'src': '...',
  //     'alt': '"Card image cap'
  // })
  // .addClass("card-img-top")

  $(urlInfo)
    .addClass("card-body URLInfo");

  $(urlTitle)
    .addClass("card-title URLTitle")
    .text(title);

  $(editURLTitleBtn)
    .addClass("mx-1 py-2")
    .attr({
      style: "color: #545454;"
    });

  $(editURLTitleLabel)
    .attr({
      for: "editURLTitle-" + URLID,
      style: "display:block",
    })
    .html("<b> URL Title </b>");

  $(editURLTitleInput)
    .addClass("card-title userInput editURLTitle")
    .attr({
      id: "editURLTitle-" + URLID,
      type: "text",
      size: "40",
      value: title,
      placeholder: "Edit URL Title",
    });

  $(editURLTitleWrap)
    .addClass("createDiv form-group")
    .append(editURLTitleLabel)
    .append(editURLTitleInput);

  $(URL).addClass("card-text URLString")
    .text(string);

  $(editURLStringLabel)
    .attr({
      for: "editURL-" + URLID,
      style: "display:block",
    })
    .html("<b> URL </b>");

  $(editURLStringInput)
    .addClass("card-text userInput editURLString")
    .attr({
      id: "editURL-" + URLID,
      type: "text",
      size: "40",
      value: string,
      placeholder: "Edit URL",
    });

  $(editWrap2)
    .append(editURLStringLabel)
    .append(editURLStringInput);

  $(editWrap)
    .append(editWrap1)
    .append(editWrap2);

  $(urlTags)
    .addClass("card-body URLTags")
    .attr({ style: "display: none" });

  // Build tag html strings
  for (let j in tagArray) {
    // Find applicable tags in dictionary to apply to URL card
    let tag = dictTags.find(function (e) {
      if (e.id === tagArray[j]) {
        return e;
      }
    });

    let tagSpan = createTagBadgeInURL(tag.id, tag.tag_string);

    $(urlTags).append(tagSpan);
  }

  // New tag create span
  $(urlTags).append(createNewTagInputField());

  // Buttons
  $(urlOptions)
    .addClass("card-body URLOptions")
    .attr({ style: "display: none" });

  $(accessURLBtn)
    .addClass("card-link btn btn-primary accessURLBtn")
    .attr({ type: "button" })
    .text("Access Link")
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      accessLink(string);
    });

  $(addTagBtn)
    .addClass("card-link btn btn-info addTagBtn")
    .attr({ type: "button" })
    .text("Add Tag")
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      addTagShowInput();
    });

  $(editURLBtn)
    .addClass("card-link btn btn-warning editURLBtn")
    .attr({ type: "button" })
    .text("Edit")
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      editURLShowInput();
    });

  $(delURLBtn)
    .addClass("card-link btn btn-danger delURLBtn")
    .attr({ type: "button" })
    .text("Delete")
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      deleteURLShowModal();
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
    .addClass("mx-1 green-clickable submitEditURLBtn")
    .attr({ style: "display: none" })
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      editURL();
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
  $(urlInfo).append(editURLTitleWrap);
  $(urlInfo).append(URL);
  $(urlInfo).append(editURLWrap);

  $(card).append(urlTags);

  $(card).append(urlOptions);
  $(urlOptions).append(accessURLBtn);
  $(urlOptions).append(addTagBtn);
  $(urlOptions).append(editURLBtn);
  $(urlOptions).append(delURLBtn);
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

  $(col)
    .addClass("createDiv cardCol mb-3 col-md-10 col-lg-10 col-xl-10")
    .attr({
      style: "display: none",
      // onblur: "hideInput(event)",
    });

  $(card)
    .addClass("card selected")
    .attr({
      urlid: 0,
      id: "addURL",
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

  $(urlInfo).addClass("card-body URLInfo");

  $(newWrap).addClass("form-group");

  $(newURLTitleLabel)
    .attr({
      for: "newURLTitle",
      style: "display:block",
    })
    .html("<b> URL Title </b>");

  $(newURLTitle)
    .addClass("card-title userInput")
    .attr({
      id: "newURLTitle",
      placeholder: "New URL Title",
      type: "text",
      size: "50",
    });

  $(newWrap1)
    .append(newURLTitleLabel)
    .append(newURLTitle);

  $(newURLStringLabel)
    .attr({
      for: "newURLString",
      style: "display:block",
    })
    .html("<b> URL </b>");

  $(newURLString)
    .addClass("card-text userInput")
    .attr({
      id: "newURLString",
      placeholder: "New URL",
      type: "text",
      size: "50",
    });

  $(newWrap2)
    .append(newURLStringLabel)
    .append(newURLString);

  $(newWrap)
    .append(newWrap1)
    .append(newWrap2);

  $(urlTags).addClass("card-body URLTags");

  // Add tag input
  $(urlTags).append(createNewTagInputField());

  // Buttons
  $(urlOptions).addClass("card-body URLOptions");

  $(addURLBtn)
    .addClass("card-link btn btn-success")
    .attr({
      type: "button"
    })
    .text("Add URL")
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      addURL();
    });

  $(delURLBtn)
    .addClass("card-link btn btn-danger")
    .attr({
      type: "button"
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

// Handle URL deck display changes related to creating a new tag
function createTagBadgeInURL(tagID, string) {
  let tagSpan = document.createElement("span");
  let removeButton = document.createElement("a");

  $(tagSpan).addClass("tagBadge").attr({ tagid: tagID }).text(string);

  $(removeButton)
    .addClass("btn btn-sm btn-outline-link border-0 tag-remove")
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      removeTag(tagID);
    });
  removeButton.innerHTML = "&times;";

  $(tagSpan).append(removeButton);

  return tagSpan;
}

// Add a new URL tag input text field. Initially hidden, shown when Create Tag is requested. Input field recreated here to ensure at the end of list after creation of new URL
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

// Filters all URLs with tags
function filterAllTaggedURLs() {
  hideInputs();

  let selectedBool = $("#selectAll").hasClass("selected");

  let URLCards = $("div.url");

  // For each URL card, verify there remain at least one visible tagBadge, else hide card.
  for (let i = 0; i < URLCards.length; i++) {
    let cardCol = $(URLCards[i]).closest(".cardCol");
    let tagBadges = cardCol.find("span.tagBadge");

    // Only do something if URL has tags applied
    if (tagBadges.length > 0) {
      if (selectedBool) {
        // Show all tagBadges and URLs
        cardCol.show();
        tagBadges.show();
      } else {
        // Hide all tagBadges and URLs
        cardCol.hide();
        tagBadges.hide();
      }
    }
  }
}

// Filters URLs based on Tag Deck state
function filterURL(tagID) {
  hideInputs();

  let filteredTagList = $(".tagBadge[tagid=" + tagID + "]");
  filteredTagList.toggle();

  let URLCards = $("div.url");
  console.log(URLCards);

  for (let i = 0; i < URLCards.length; i++) {
    console.log($(URLCards[i]).closest(".cardCol").find(".URLTitle").text());
    let cardCol = $(URLCards[i]).closest(".cardCol");
    let tagBadges = cardCol.find("span.tagBadge");

    // Default to hiding URL if it has tags
    // Automaticaly show URL if it doesn't have tags
    let hideBool = tagBadges.length ? 0 : 1;

    // If all tags are filtered, hide URL
    for (let j = 0; j < tagBadges.length; j++) {
      console.log(!($(tagBadges[j]).attr("style") == "display: none;"));

      // If any 1 tag is not "display: none;", then URL remains shown
      if (!($(tagBadges[j]).attr("style") == "display: none;")) hideBool ||= 1;
    }

    if (hideBool) {
      cardCol.show();
    } else {
      deselectURL(cardCol);
      cardCol.hide();
    }
  }
}

/** URL Display State Functions **/

// Display state 0: Clean slate, no UTub selected
function displayState0URLDeck() {
  $("#URLDeckHeader").text("URLs");
  hideIfShown($("#URLDeckSubheader").closest(".row"));
  hideIfShown($(".editUTubBtn"));
  hideIfShown($("#addURLBtn"));
  hideIfShown($("#accessAllURLsBtn"));

  if (getNumOfUTubs() > 0) {
    let URLDeckSubheader = $("#URLDeckSubheader");
    showIfHidden(URLDeckSubheader.closest(".row"));
    URLDeckSubheader.text("Select a UTub");
  }
}

// Display state 1: UTub selected, URL list and subheader prompt
function displayState1URLDeck() {
  let numOfURLs = getNumOfURLs();
  let UTubName = getCurrentUTubName();
  $("#URLDeckHeader").text(UTubName);
  $("#editUTubName").val(UTubName);

  editUTubNameHideInput();

  // Subheader prompt
  let URLDeckSubheader = $("#URLDeckSubheader");
  showIfHidden(URLDeckSubheader.closest(".row"));
  if (numOfURLs) {
    let stringURLPlurality = numOfURLs === 1 ? " URL" : " URLs";
    let string = numOfURLs + stringURLPlurality + " stored";
    URLDeckSubheader.text(string);
    // URLDeckSubheader.text(numOfURLs + numOfURLs === 1 ? " URL" : " URLs" + " stored");
    showIfHidden($("#accessAllURLsBtn"));
  } else {
    URLDeckSubheader.text("Add a URL");
    hideIfShown($("#accessAllURLsBtn"));
  }
}