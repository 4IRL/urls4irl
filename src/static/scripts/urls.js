/** URL UI Interactions **/

$(document).ready(function () {
  /* Bind click functions */

  // Add new URL to current UTub
  $("#urlBtnCreate").on("click", function (e) {
    e.stopPropagation();
    e.preventDefault();
    hideInputs();
    if (getSelectedURLCard().length === 0) moveURLsToLowerRowOnCreateURLShown();
    deselectAllURLs();
    createURLShowInput();
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

// Prevent deselection of URL while modifying its values (e.g. adding a tag, updating URL string or title)
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

function bindEscapeToExitURLTitleUpdating() {
  $(document)
    .unbind("keyup.escapeUrlTitleUpdating")
    .bind("keyup.escapeUrlTitleUpdating", function (e) {
      if (e.which === 27) {
        console.log("Trying to hide URL title input");
        updateURLTitleHideInput();
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
  $("#urlTitleCreate").val("");
  $("#urlStringCreate").val("");
  hideIfShown($("#urlStringCreate").closest(".createDiv"));
}

// Clear the URL Deck
function resetURLDeck() {
  // Empty URL Deck
  // Detach NO URLs text and reattach after emptying

  const noURLsText = $("#NoURLsSubheader").remove();
  $("#UPRRow").empty().append(noURLsText);

  const createURLBlock = $("#createURL").parent().remove();
  $("#URLFocusRow").empty().append(createURLBlock);
  newURLInputRemoveEventListeners();

  $("#LWRRow").empty();
  $("#utubNameBtnUpdate").hide();
  $("#urlBtnCreate").hide();
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
  const URLTitleWrap = document.createElement("div"); // This element wraps the URL title and update button
  const URLTitleInnerWrap = document.createElement("div");
  const URLTitle = document.createElement("h5"); // This element displays the user-created title of the URL
  const urlTitleBtnUpdate = canModify ? makeUpdateButton(25) : null;
  const updateURLTitleWrap = canModify ? document.createElement("div") : null; // This element wraps the update field for URL title
  const updateURLTitleInput = canModify
    ? document.createElement("input")
    : null; // This element is instantiated with the URL title
  const urlBtnUpdateWrap = canModify ? document.createElement("div") : null;
  const urlTitleSubmitBtnUpdate = canModify ? makeSubmitButton(25) : null; // Submit changes after 'update' operations
  const urlTitleCancelBtnUpdate = canModify ? makeCancelButton(25) : null; // Cancel changes after 'update' operations, populate with pre-update values
  const URLWrap = document.createElement("div"); // This element wraps the URL title and update button
  const URL = document.createElement("a"); // This element displays the user's URL
  const updateURLWrap = canModify ? document.createElement("div") : null; // This element wraps the update field for URL string
  const updateURLInput = canModify ? document.createElement("input") : null; // This element is instantiated with the URL
  const urlSubmitBtnUpdate = canModify ? makeSubmitButton(25) : null; // Submit changes after 'update' operations
  const urlCancelBtnUpdate = canModify ? makeCancelButton(25) : null; // Cancel changes after 'update' operations, populate with pre-update values
  const URLTags = document.createElement("div");
  const tagsWrap = document.createElement("div");
  const URLOptions = document.createElement("div");
  const urlBtnAccess = document.createElement("button");
  const urlBtnUpdate = canModify ? document.createElement("button") : null;
  const tagBtnCreate = document.createElement("button");
  const urlBtnDelete = canModify ? document.createElement("button") : null;

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
  $(URLTitleInnerWrap).addClass("flex-row URLTitleInnerWrap");

  $(URLTitle).addClass("card-title").text(title);

  $(URLWrap).addClass("URL").attr({ style: "display:flex" });

  $(URL).addClass("card-text url-string").text(string);

  if (canModify) {
    $(urlTitleBtnUpdate)
      .addClass("urlTitleBtnUpdate visibleBtn")
      .on("click", function (e) {
        e.stopPropagation();
        e.preventDefault();
        updateURLTitleShowInput();
      })
      .attr({ style: "display: none" });

    $(updateURLTitleWrap)
      .addClass("createDiv flex-row form-group")
      .attr({ style: "display: none" });

    $(updateURLTitleInput)
      .addClass("card-title userInput updateURLTitle")
      .attr({
        id: "updateURLTitle-" + URLID,
        type: "text",
        size: "40",
        value: title,
        placeholder: "Edit URL Title",
      });

    $(urlTitleSubmitBtnUpdate)
      .addClass("urlTitleSubmitBtnUpdate")
      .on("click", function (e) {
        e.stopPropagation();
        e.preventDefault();
        updateURLTitle();
      });

    $(urlTitleCancelBtnUpdate)
      .addClass("urlTitleCancelBtnUpdate")
      .on("click", function (e) {
        e.stopPropagation();
        e.preventDefault();
        updateURLTitleHideInput();
      });

    $(updateURLWrap)
      .addClass("createDiv flex-row form-group")
      .attr({ style: "display: none" });

    $(urlBtnUpdateWrap)
      .addClass("urlBtnUpdateWrap createDiv flex-row form-group")
      .attr({ style: "display: none;" });

    $(updateURLInput)
      .addClass("card-text userInput updateURL")
      .attr({
        id: "updateURL-" + URLID,
        type: "text",
        size: "40",
        value: string,
        placeholder: "Edit URL",
      });

    $(urlSubmitBtnUpdate)
      .addClass("urlSubmitBtnUpdate")
      .on("click", function (e) {
        e.stopPropagation();
        e.preventDefault();
        updateURL();
        $(document).bind("keypress", function (e) {
          if (e.which == 13) {
            updateURL();
          }
        });
      });

    $(urlCancelBtnUpdate)
      .addClass("urlCancelBtnUpdate")
      .on("click", function (e) {
        e.stopPropagation();
        e.preventDefault();
        updateURLHideInput();
        $(document).bind("keypress", function (e) {
          if (e.which === 27) {
            hideInputs();
          }
        });
      });

    $(urlBtnUpdateWrap).append(urlSubmitBtnUpdate).append(urlCancelBtnUpdate);
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

  $(urlBtnAccess)
    .addClass("card-link btn btn-primary urlBtnAccess")
    .attr({ type: "button" })
    .text("Access Link")
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      accessLink(string);
    });

  $(tagBtnCreate)
    .addClass("card-link btn btn-info tagBtnCreate")
    .attr({ type: "button" })
    .text("Add Tag")
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      createTagShowInput();
    });

  if (canModify) {
    $(urlBtnDelete)
      .addClass("card-link btn btn-danger urlBtnDelete")
      .attr({ type: "button" })
      .text("Delete")
      .on("click", function (e) {
        e.stopPropagation();
        e.preventDefault();
        deleteURLShowModal();
      });

    $(urlBtnUpdate)
      .addClass("card-link btn btn-light urlBtnUpdate")
      .attr({ type: "button" })
      .text("Edit Link")
      .on("click", function (e) {
        e.stopPropagation();
        e.preventDefault();
        updateURLShowInput();
      });
  }

  // Assemble url list items
  $(col).append(card);

  $(card).append(URLInfo);

  if (canModify) {
    $(URLTitleWrap).append(URLTitleInnerWrap);
    $(URLTitleInnerWrap).append(URLTitle).append(urlTitleBtnUpdate);
    $(updateURLTitleWrap)
      .append(updateURLTitleInput)
      .append(urlTitleSubmitBtnUpdate)
      .append(urlTitleCancelBtnUpdate);
    $(URLWrap).append(URL).append(urlBtnUpdate);
    $(updateURLWrap).append(updateURLInput).append(urlBtnUpdateWrap);
    //.append(urlSubmitBtnUpdate)
    //.append(urlCancelBtnUpdate);
    $(URLInfo)
      .append(URLTitleWrap)
      .append(updateURLTitleWrap)
      .append(URLWrap)
      .append(updateURLWrap);

    $(card).append(URLTags);

    $(card).append(URLOptions);
    $(URLOptions)
      .append(urlBtnAccess)
      .append(urlBtnUpdate)
      .append(tagBtnCreate)
      .append(urlBtnDelete);
  } else {
    $(URLTitleWrap).append(URLTitle);
    $(URLWrap).append(URL);
    $(URLInfo).append(URLTitleWrap).append(URLWrap);

    $(card).append(URLTags);

    $(card).append(URLOptions);
    $(URLOptions).append(urlBtnAccess).append(tagBtnCreate);
  }
  // $(URLOptions).append(submitUpdateBtn);
  // $(URLOptions).append(cancelUpdateBtn);

  return col;
}

// New URL card and input text fields. Initially hidden, shown when create URL is requested. Input field recreated here to ensure at the end of list after creation of new URL
function newURLInputAddEventListeners() {
  const urlBtnCreate = $("#urlSubmitBtnCreate");
  const urlBtnDelete = $("#urlCancelBtnCreate");

  $(urlBtnCreate)
    .off("click")
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      createURL();
    });

  $(urlBtnDelete)
    .off("click")
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      createURLHideInput();
    });
}

function newURLInputRemoveEventListeners() {
  $("#urlSubmitBtnCreate").off("click");
  $("#urlCancelBtnCreate").off("click");
}

// Handle URL deck display changes related to creating a new tag
function createTagBadgeInURL(tagID, string) {
  let tagSpan = document.createElement("span");
  let removeButton = document.createElement("a");

  $(tagSpan).addClass("tagBadge").attr({ tagid: tagID }).text(string);

  $(removeButton)
    .addClass("btn btn-sm btn-outline-link border-0 tagBtnDelete")
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      deleteTag(tagID);
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
    .addClass("tag userInput createTag");

  $(submitBtn)
    .addClass("mx-1 green-clickable tagSubmitBtnCreate")
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      createTag();
    });

  $(cancelBtn)
    .addClass("mx-1 tagCancelBtnCreate")
    .on("click", function (e) {
      e.stopPropagation();
      tagCancelBtnCreateHideInput($(wrapper));
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
  showIfHidden(selectedCardCol.find(".urlTitleBtnUpdate"));
  showIfHidden(selectedCardCol.find(".urlBtnUpdate"));

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
  hideIfShown(deselectedCardCol.find(".urlTitleBtnUpdate"));
  hideIfShown(deselectedCardCol.find(".urlBtnUpdate"));

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
  unbindURLKeyboardEventListenersWhenUpdatesOccurring();
}

// Deselects createURL block
function deselectCreateURL() {
  hideIfShown($("#newURL").closest(".cardCol"));
}

// User clicks a URL. If already selected, URL is deselected, else it is selected. All other URLs are deselected. This function places all URLs prior to selected URL into #UPRRow, inserts selected URL into a separate #URLFocusRow, and places all subsequent URLs into #LWRRow. It also adjusts css displays accordingly
// REHch goal 09/12/23 may want a "display order" attribute stored in backend. Option to sort by alpha, date added, or custom prescribed "display order". This display can be manipulated by drag-drop of the URL card.
function toggleSelectedURL(selectedURLID) {
  let cardCols = $(".cardCol");

  let activeRow = $("#UPRRow");
  let focusRow = $("#URLFocusRow");

  // Hide createURL block
  hideInput("#createURL");

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

  if (!isNaN(getSelectedURLID())) {
    bindURLKeyboardEventListenersWhenUpdatesNotOccurring();
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
function moveURLsToLowerRowOnCreateURLShown() {
  const upperRowChildren = $("#UPRRow").children();
  const upperRowChildrenLength = upperRowChildren.length;

  if (upperRowChildrenLength === 0) return;

  const lowerRow = $("#LWRRow");

  for (let i = 0; i < upperRowChildrenLength; i++) {
    let urlCard = upperRowChildren[upperRowChildrenLength - 1 - i];
    lowerRow.prepend(urlCard);
  }
}

function moveURLsToUpperRowOnSuccessfulCreateURL() {
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
  hideIfShown($(".updateUTubBtn"));
  hideIfShown($("#urlBtnCreate"));
  hideIfShown($("#accessAllURLsBtn"));
  hideIfShown($("#URLDeckSubheaderCreateDescription"));

  const URLDeckSubheader = $("#URLDeckSubheader");
  URLDeckSubheader.text("Select a UTub");
  showIfHidden(URLDeckSubheader);

  // Prevent on-hover of URL Deck Header to show update UTub name button in case of back button
  $("#utubNameBtnUpdate").removeClass("visibleBtn");
}

// Display state 1: UTub selected, URL list and subheader prompt
function displayState1URLDeck(UTubName) {
  let numOfURLs = getNumOfURLs();
  $("#URLDeckHeader").text(UTubName);
  $("#utubNameUpdate").val(UTubName);

  updateUTubNameHideInput();
}
