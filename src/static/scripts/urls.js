/** URL UI Interactions **/

$(document).ready(function () {
  /* Bind click functions */

  // Add new URL to current UTub
  $("#addURLBtn").on("click", function (e) {
    e.stopPropagation();
    e.preventDefault();
    hideInputs();
    if (getSelectedURLCard().length === 0) moveURLsToLowerRowOnAddURLShown();
    deselectAllURLs();
    addURLShowInput();
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
  return parseInt($(".selectedURL").attr("urlid"));
}

// Simple function to streamline the jQuery selector extraction of selected URL card. Provides ease of reference by URL Functions.
function getSelectedURLCard() {
  return $("#listURLs").find(".url[urlid = " + getSelectedURLID() + "]");
}

// Prevent deselection of URL while modifying its values (e.g. adding a tag, editing URL string or title)
function unbindSelectURLBehavior() {
  $(getSelectedURLCard().closest(".cardCol")).off("click");
}

// Rebinds selection click behavior after URL-modifying post requests are complete
function rebindSelectBehavior() {
  const urlID = getSelectedURLID();
  $(getSelectedURLCard())
    .closest(".cardCol")
    .off("click")
    .on("click", function () {
      toggleSelectedURL(urlID);
      bindEscapeToUnselectURL(urlID);
    });
}

function bindEscapeToUnselectURL(urlID) {
  $(document)
    .unbind("keyup.27")
    .bind("keyup.27", function (e) {
      if (e.which === 27) {
        toggleSelectedURL(urlID);
        unbindEscapeKey();
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
  let modalText = "Performance issues may occur.";
  let modalDismiss = "Cancel";

  $("#confirmModalTitle").text(modalTitle);
  $("#confirmModalBody").text(modalText);

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
  $("#modalRedirect").hide();
  hideIfShown($("#modalRedirect"));
}

// Opens all URLs in UTub in separate tabs
function accessAllURLsInUTub() {
  getUTubInfo(getActiveUTubID()).then(function (selectedUTub) {
    let dictURLs = selectedUTub.urls;

    for (i = 0; i < dictURLs.length; i++) {
      accessLink(dictURLs[i].urlString);
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
  // Detach NO URLs text and reattach after emptying

  const noURLsText = $("#NoURLsSubheader").remove();
  $("#UPRRow").empty().append(noURLsText);

  const createURLBlock = $("#addURL").parent().remove();
  $("#URLFocusRow").empty().append(createURLBlock);
  newURLInputRemoveEventListeners();

  $("#LWRRow").empty();
  $("#editUTubNameBtn").hide();
  $("#addURLBtn").hide();
  $("#accessAllURLsBtn").hide();
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
        dictURLs[i].utubUrlID,
        dictURLs[i].urlString,
        dictURLs[i].urlTitle,
        dictURLs[i].urlTagIDs,
        dictTags,
        dictURLs[i].canDelete,
      );

      parent.append(URLcol);
    }
  }
  displayState1URLDeck(UTubName);
}

// Create a URL block to add to current UTub/URLDeck
function createURLBlock(URLID, string, title, tagArray, dictTags, canModify) {
  const col = document.createElement("div");
  const card = document.createElement("div");
  // const cardImg = document.createElement('img');
  const URLInfo = document.createElement("div"); // This element holds the URL title and string
  const URLTitleWrap = document.createElement("div"); // This element wraps the URL title and edit button
  const URLTitle = document.createElement("h5"); // This element displays the user-created title of the URL
  const editURLTitleBtn = canModify ? makeEditButton(20) : null;
  const editURLTitleWrap = canModify ? document.createElement("div") : null; // This element wraps the edit field for URL title
  const editURLTitleLabel = canModify ? document.createElement("label") : null; // This element labels the edit field for URL title
  const editURLTitleInput = canModify ? document.createElement("input") : null; // This element is instantiated with the URL title
  const editURLBtnWrap = canModify ? document.createElement("div") : null;
  const submitEditURLTitleBtn = canModify ? makeSubmitButton(20) : null; // Submit changes after 'edit' operations
  const cancelEditURLTitleBtn = canModify ? makeCancelButton(20) : null; // Cancel changes after 'edit' operations, populate with pre-edit values
  const URLWrap = document.createElement("div"); // This element wraps the URL title and edit button
  const URL = document.createElement("a"); // This element displays the user's URL
  const editURLWrap = canModify ? document.createElement("div") : null; // This element wraps the edit field for URL string
  const editURLInput = canModify ? document.createElement("input") : null; // This element is instantiated with the URL
  const submitEditURLBtn = canModify ? makeSubmitButton(25) : null; // Submit changes after 'edit' operations
  const cancelEditURLBtn = canModify ? makeCancelButton(25) : null; // Cancel changes after 'edit' operations, populate with pre-edit values
  const URLTags = document.createElement("div");
  const tagsWrap = document.createElement("div");
  const URLOptions = document.createElement("div");
  const accessURLBtn = document.createElement("button");
  const editURLBtn = canModify ? document.createElement("button") : null;
  const addTagBtn = document.createElement("button");
  const delURLBtn = canModify ? document.createElement("button") : null;

  $(col)
    .addClass("cardCol mb-3 col-md-12 col-sm-12 col-lg-12 col-xl-12 col-xxl-6")
    .on("click", function (e) {
      toggleSelectedURL(URLID);
      bindEscapeToUnselectURL(URLID);
    });

  $(card).addClass("card url").attr({
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

  $(URLTitleWrap).addClass("URLTitle flex-row titleElement");

  $(URLTitle).addClass("card-title").text(title);

  $(URLWrap).addClass("URL").attr({ style: "display:flex" });

  $(URL).addClass("card-text url-string").text(string);

  if (canModify) {
    $(editURLTitleBtn)
      .addClass("editURLTitleBtn")
      .on("click", function (e) {
        e.stopPropagation();
        e.preventDefault();
        editURLTitleShowInput();
      })
      .attr({ style: "display: none" });

    $(editURLTitleWrap)
      .addClass("createDiv flex-row form-group")
      .attr({ style: "display: none" });

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

    $(submitEditURLTitleBtn)
      .addClass("submitEditURLTitleBtn")
      .on("click", function (e) {
        e.stopPropagation();
        e.preventDefault();
        editURLTitle();
      });

    $(cancelEditURLTitleBtn)
      .addClass("cancelEditURLTitleBtn")
      .on("click", function (e) {
        e.stopPropagation();
        e.preventDefault();
        editURLTitleHideInput();
      });

    $(editURLWrap)
      .addClass("createDiv flex-row form-group")
      .attr({ style: "display: none" });

    $(editURLBtnWrap)
      .addClass("editURLBtnWrap createDiv flex-row form-group")
      .attr({ style: "display: none;" });

    $(editURLInput)
      .addClass("card-text userInput editURL")
      .attr({
        id: "editURL-" + URLID,
        type: "text",
        size: "40",
        value: string,
        placeholder: "Edit URL",
      });

    $(submitEditURLBtn)
      .addClass("submitEditURLBtn")
      .on("click", function (e) {
        e.stopPropagation();
        e.preventDefault();
        editURL();
        $(document).bind("keypress", function (e) {
          if (e.which == 13) {
            editURL();
          }
        });
      });

    $(cancelEditURLBtn)
      .addClass("cancelEditURLBtn")
      .on("click", function (e) {
        e.stopPropagation();
        e.preventDefault();
        editURLHideInput();
        $(document).bind("keypress", function (e) {
          if (e.which === 27) {
            hideInputs();
          }
        });
      });

    $(editURLBtnWrap).append(submitEditURLBtn).append(cancelEditURLBtn);
  }

  $(URLInfo).addClass("card-body URLInfo");

  $(URLTags)
    .addClass("card-body URLTags flex-column")
    .attr({ style: "display: none" })
    .append(tagsWrap);

  $(tagsWrap).addClass("flex-row flex-start");

  // Add tag badges
  for (let j in tagArray) {
    // Find applicable tags in dictionary to apply to URL card
    let tag = dictTags.find(function (e) {
      if (e.id === tagArray[j]) {
        return e;
      }
    });

    let tagSpan = createTagBadgeInURL(tag.id, tag.tagString);

    $(tagsWrap).append(tagSpan);
  }
  // New tag create span
  $(URLTags).append(createNewTagInputField());

  // Buttons
  $(URLOptions)
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

  if (canModify) {
    $(delURLBtn)
      .addClass("card-link btn btn-danger delURLBtn")
      .attr({ type: "button" })
      .text("Delete")
      .on("click", function (e) {
        e.stopPropagation();
        e.preventDefault();
        deleteURLShowModal();
      });

    $(editURLBtn)
      .addClass("card-link btn btn-light editURLBtn")
      .attr({ type: "button" })
      .text("Edit Link")
      .on("click", function (e) {
        e.stopPropagation();
        e.preventDefault();
        editURLShowInput();
      });
  }

  // Assemble url list items
  $(col).append(card);

  $(card).append(URLInfo);

  if (canModify) {
    $(URLTitleWrap).append(URLTitle).append(editURLTitleBtn);
    $(editURLTitleWrap)
      .append(editURLTitleLabel)
      .append(editURLTitleInput)
      .append(submitEditURLTitleBtn)
      .append(cancelEditURLTitleBtn);
    $(URLWrap).append(URL).append(editURLBtn);
    $(editURLWrap).append(editURLInput).append(editURLBtnWrap);
    //.append(submitEditURLBtn)
    //.append(cancelEditURLBtn);
    $(URLInfo)
      .append(URLTitleWrap)
      .append(editURLTitleWrap)
      .append(URLWrap)
      .append(editURLWrap);

    $(card).append(URLTags);

    $(card).append(URLOptions);
    $(URLOptions)
      .append(accessURLBtn)
      .append(editURLBtn)
      .append(addTagBtn)
      .append(delURLBtn);
  } else {
    $(URLTitleWrap).append(URLTitle);
    $(URLWrap).append(URL);
    $(URLInfo).append(URLTitleWrap).append(URLWrap);

    $(card).append(URLTags);

    $(card).append(URLOptions);
    $(URLOptions).append(accessURLBtn).append(addTagBtn);
  }
  // $(URLOptions).append(submitEditBtn);
  // $(URLOptions).append(cancelEditBtn);

  return col;
}

// New URL card and input text fields. Initially hidden, shown when create URL is requested. Input field recreated here to ensure at the end of list after creation of new URL
function newURLInputAddEventListeners() {
  const addURLBtn = $("#SubmitNewURLBtn");
  const delURLBtn = $("#CancelAddURLBtn");

  $(addURLBtn)
    .off("click")
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      addURL();
    });

  $(delURLBtn)
    .off("click")
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      addURLHideInput();
    });
}

function newURLInputRemoveEventListeners() {
  $("#SubmitNewURLBtn").off("click");
  $("#CancelAddURLBtn").off("click");
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
  const wrapper = document.createElement("div");
  const wrapperInput = document.createElement("div");
  const wrapperBtns = document.createElement("div");

  const input = document.createElement("input");
  const submitBtn = makeSubmitButton(24);
  const cancelBtn = makeCancelButton(24);

  $(wrapper)
    .attr({
      style: "display: none",
    })
    .addClass("createDiv flex-row");

  $(input)
    .attr({
      type: "text",
      placeholder: "Attribute Tag to URL",
    })
    .addClass("tag userInput addTag");

  $(submitBtn)
    .addClass("mx-1 green-clickable submitAddTag")
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      addTag();
    });

  $(cancelBtn)
    .addClass("mx-1 cancelAddTag")
    .on("click", function (e) {
      e.stopPropagation();
      cancelAddTagHideInput($(wrapper));
      //hideIfShown(wrapper);
    });

  $(wrapperInput).append(input);

  $(wrapperBtns).append(submitBtn).append(cancelBtn);

  $(wrapper).append(wrapperInput).append(wrapperBtns);

  return wrapper;
}

// Display updates related to selection of a URL
function selectURL(selectedCardCol) {
  const card = selectedCardCol.find(".card");

  selectedCardCol.addClass("col-12");
  selectedCardCol.removeClass(
    "col-md-12 col-sm-12 col-lg-12 col-xl-12 col-xxl-6",
  );

  card.addClass("selectedURL");
  // card.attr("draggable", "");

  showIfHidden(selectedCardCol.find(".URLTags"));
  showIfHidden(selectedCardCol.find(".URLOptions"));
  showIfHidden(selectedCardCol.find(".editURLTitleBtn"));
  showIfHidden(selectedCardCol.find(".editURLBtn"));

  // Add clickability to the URL itself
  const urlString = card.find(".url-string");

  urlString.off("click").on("click", function (e) {
    e.stopPropagation();
    accessLink(urlString.text());
  });
}

// Display updates related to deselection of a URL
function deselectURL(deselectedCardCol) {
  const card = deselectedCardCol.find(".card");

  deselectedCardCol.addClass(
    "col-md-12 col-sm-12 col-lg-12 col-xl-12 col-xxl-6",
  );
  deselectedCardCol.removeClass("col-12");

  card.removeClass("selectedURL");
  // card.attr("draggable");

  hideIfShown(deselectedCardCol.find(".URLTags"));
  hideIfShown(deselectedCardCol.find(".URLOptions"));
  hideIfShown(deselectedCardCol.find(".editURLTitleBtn"));
  hideIfShown(deselectedCardCol.find(".editURLBtn"));

  // Remove clickability from the URL
  card.find(".url-string").off("click");
}

// Deselects all URLs in preparation for creation URL
function deselectAllURLs() {
  let cardCols = $(".cardCol");
  const lowerRow = $("#LWRRow");
  const selectedURL = getSelectedURLCard().parent();

  if (selectedURL.length !== 0) {
    selectedURL.detach();
    lowerRow.prepend(selectedURL);
  }

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

  if (!isNaN(getSelectedURLID())) {
    bindURLKeyboardEventListenersWhenEditsNotOccurring();
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

// Moves all upper row URLs to lower row on adding a new URL
function moveURLsToLowerRowOnAddURLShown() {
  const upperRowChildren = $("#UPRRow").children();
  const upperRowChildrenLength = upperRowChildren.length;

  if (upperRowChildrenLength === 0) return;

  const lowerRow = $("#LWRRow");

  for (let i = 0; i < upperRowChildrenLength; i++) {
    let urlCard = upperRowChildren[upperRowChildrenLength - 1 - i];
    lowerRow.prepend(urlCard);
  }
}

function moveURLsToUpperRowOnSuccessfulAddURL() {
  const lowerRowChildren = $("#LWRRow").children();
  const lowerRowChildrenLength = lowerRowChildren.length;

  if (lowerRowChildrenLength === 0) return;

  const upperRow = $("#UPRRow");

  for (let i = 0; i < lowerRowChildrenLength; i++) {
    let urlCard = lowerRowChildren[i];
    upperRow.append(urlCard);
  }
}

/** URL Display State Functions **/

// Display state 0: Clean slate, no UTub selected
function displayState0URLDeck() {
  $("#URLDeckHeader").text("URLs");
  hideIfShown($(".editUTubBtn"));
  hideIfShown($("#addURLBtn"));
  hideIfShown($("#accessAllURLsBtn"));

  let URLDeckSubheader = $("#URLDeckSubheader");
  URLDeckSubheader.text("Select a UTub");
}

// Display state 1: UTub selected, URL list and subheader prompt
function displayState1URLDeck(UTubName) {
  let numOfURLs = getNumOfURLs();
  $("#URLDeckHeader").text(UTubName);
  $("#editUTubName").val(UTubName);

  editUTubNameHideInput();

  // Subheader prompt
  let URLDeckSubheader = $("#URLDeckSubheader");
  showIfHidden(URLDeckSubheader.closest(".row"));
  if (numOfURLs) {
    $("#NoURLsSubheader").hide();
    let stringURLPlurality = numOfURLs === 1 ? " URL" : " URLs";
    let string = numOfURLs + stringURLPlurality + " stored";
    URLDeckSubheader.text(string);
    // URLDeckSubheader.text(numOfURLs + numOfURLs === 1 ? " URL" : " URLs" + " stored");
    showIfHidden($("#accessAllURLsBtn"));
  } else {
    URLDeckSubheader.text("");
    $("#NoURLsSubheader").show();
    hideIfShown($("#accessAllURLsBtn"));
  }
}
