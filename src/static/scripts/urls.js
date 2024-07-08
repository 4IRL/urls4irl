/** URL UI Interactions **/

$(document).ready(function () {
  /* Bind click functions */

  // Add new URL to current UTub
  $("#urlBtnCreate").on("click", function (e) {
    e.stopPropagation();
    hideInputs();
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
  return $(".urlRow").length;
}

// Simple function to streamline the jQuery selector extraction of selected URL card. Provides ease of reference by URL Functions.
function getSelectedUrlCard() {
  const selectedUrlCard = $(".urlRow[urlSelected=true]");
  return selectedUrlCard.length ? selectedUrlCard : null;
}

// function to streamline the jQuery selector extraction of selected URL ID. And makes it easier in case the ID is encoded in a new location in the future
function getSelectedURLID() {
  const selectedUrlCard = getSelectedUrlCard();
  return selectedUrlCard === null ? NaN : selectedUrlCard.attr("urlid");
}

// Prevent deselection of URL while modifying its values (e.g. adding a tag, updating URL string or title)
function unbindSelectURLBehavior() {
  getSelectedUrlCard().off(".urlSelected");
}

// Perform actions on selection of a URL card
function selectUrlCard(urlCard, url) {
  deselectAllUrls();
  urlCard
    .find(".urlString")
    .off("click.goToURL")
    .on("click.goToURL", function (e) {
      e.stopPropagation();
      accessLink(url.string);
    });
  urlCard.attr({ urlSelected: true });
  urlCard.find(".goToUrlIcon").addClass("visible-flex");
}

// Clean up when deselecting a URL card
function deselectUrl(urlCard) {
  urlCard.attr({ urlSelected: false });
  urlCard.find(".urlString").off("click.goToURL");
  urlCard.find(".goToUrlIcon").removeClass("visible-flex");
  resetUpdateUrlTitleForm(urlCard);
}

function deselectAllUrls() {
  const previouslySelectedCard = getSelectedUrlCard();
  if (previouslySelectedCard !== null) deselectUrl(previouslySelectedCard);
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
  $("#urlTitleCreate").val(null);
  $("#urlStringCreate").val(null);
  hideIfShown($("#createURLWrap"));
  newURLInputRemoveEventListeners();
}

// Clear the URL Deck
function resetURLDeck() {
  // Empty URL Deck
  // Detach NO URLs text and reattach after emptying

  resetNewURLForm();
  newURLInputRemoveEventListeners();
  $(".urlRow").remove();
}

/** URL Functions **/

// Build center panel URL list for selectedUTub
function buildURLDeck(UTubName, dictURLs, dictTags) {
  resetURLDeck();
  const parent = $("#listURLs");
  const numOfURLs = dictURLs.length ? dictURLs.length : 0;

  if (numOfURLs !== 0) {
    // Instantiate deck with list of URLs stored in current UTub
    for (let i = 0; i < dictURLs.length; i++) {
      parent.append(createURLBlock(dictURLs[i], dictTags));
    }

    // Show access all URLs button
    showIfHidden($("#accessAllURLsBtn"));
    hideIfShown($("#NoURLsSubheader"));
  } else {
    showIfHidden($("#NoURLsSubheader"));
    hideIfShown($("#accessAllURLsBtn"));
  }
  displayState1URLDeck(UTubName);
}

// Create a URL block to add to current UTub/URLDeck
function createURLBlock(url, tagArray) {
  const outerUrlCard = $(document.createElement("div")).addClass(
    "urlRow flex-column full-width pad-in-15p pointerable",
  ); // Holds everything in the URL

  const urlTitleGoToUrlWrap = $(document.createElement("div")).addClass(
    "flex-row full-width justify-space-between",
  );

  if (url.canDelete) {
    const urlTitleAndTitleUpdateBlock = createUrlTitleAndUpdateBlock(
      url.urlTitle,
      outerUrlCard,
    );
    urlTitleGoToUrlWrap.append(urlTitleAndTitleUpdateBlock);
  } else {
    const urlTitle = $(document.createElement("h6"))
      .addClass("urlTitle long-text-ellipsis")
      .text(url.urlTitle);
    urlTitleGoToUrlWrap.append(urlTitle);
  }
  urlTitleGoToUrlWrap.append(createGoToUrlIcon(url.urlString));

  const urlString = $(document.createElement("span"))
    .addClass("urlString long-text-ellipsis")
    .text(url.urlString);
  outerUrlCard.append(urlTitleGoToUrlWrap).append(urlString).attr({
    urlID: url.utubUrlID,
    urlSelected: false,
  });

  outerUrlCard.append(createTagsAndOptionsForUrlBlock(url, tagArray));
  outerUrlCard.off("click.urlSelected").on("click.urlSelected", function (e) {
    if ($(e.target).parents(".urlRow").length > 0) {
      if ($(e.target).closest(".urlRow").attr("urlSelected") === "true") return;
      console.log("Setting parent to selected");
      selectUrlCard(outerUrlCard, url);
    }
  });

  return outerUrlCard;
}

function createGoToUrlIcon(urlString) {
  const WIDTH_HEIGHT_PX = "20px";
  const SVG_NS = "http://www.w3.org/2000/svg";
  const goToUrlOuterIconSvg = $(document.createElementNS(SVG_NS, "svg"));
  const goToUrlInnerIconPath = $(document.createElementNS(SVG_NS, "path"));
  const path =
    "M14 0a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2V2a2 2 0 0 1 2-2zM5.904 10.803 10 6.707v2.768a.5.5 0 0 0 1 0V5.5a.5.5 0 0 0-.5-.5H6.525a.5.5 0 1 0 0 1h2.768l-4.096 4.096a.5.5 0 0 0 .707.707";

  goToUrlInnerIconPath.attr({
    d: path,
  });

  goToUrlOuterIconSvg
    .attr({
      xmlns: SVG_NS,
      width: WIDTH_HEIGHT_PX,
      height: WIDTH_HEIGHT_PX,
      fill: "currentColor",
      class: "bi bi-arrow-up-right-square-fill goToUrlIcon pointerable",
      viewBox: "0 0 16 16",
    })
    .append(goToUrlInnerIconPath)
    .on("click", (e) => {
      e.stopPropagation();
      accessLink(urlString);
    });

  return goToUrlOuterIconSvg;
}

function createUrlTitleAndUpdateBlock(urlTitleText, urlCard) {
  const urlTitleAndUpdateWrap = $(document.createElement("div")).addClass(
    "flex-row ninetyfive-width",
  );
  const urlTitleAndShowUpdateIconWrap = $(
    document.createElement("div"),
  ).addClass("flex-row ninetyfive-width urlTitleAndUpdateIconWrap");
  const urlTitleAndShowUpdateIconInnerWrap = $(
    document.createElement("div"),
  ).addClass("flex-row full-width urlTitleAndUpdateIconInnerWrap");

  const urlTitle = $(document.createElement("h6"))
    .addClass("urlTitle long-text-ellipsis")
    .text(urlTitleText);

  const urlTitleShowUpdateIcon = makeUpdateButton(20);
  urlTitleShowUpdateIcon
    .css("display", "none")
    .on("click.showUpdateUrlTitle", function (e) {
      if ($(e.target).parents(".urlTitleAndUpdateIconWrap").length > 0) {
        const urlTitleAndIcon = $(e.target).closest(
          ".urlTitleAndUpdateIconWrap",
        );
        hideIfShown(urlTitleAndIcon);
        const updateTitleForm = urlTitleAndIcon.siblings(".updateUrlTitleWrap");
        showIfHidden(updateTitleForm);
        highlightInput(updateTitleForm.find("input"));
      }
    });
  urlTitleAndShowUpdateIconInnerWrap
    .append(urlTitle)
    .append(urlTitleShowUpdateIcon);
  urlTitleAndShowUpdateIconWrap.append(urlTitleAndShowUpdateIconInnerWrap);

  const urlUpdateTextInputContainer = makeUpdateTextInput("urlTitle")
    .addClass("updateUrlTitleWrap")
    .css("display", "none");

  urlUpdateTextInputContainer.find("label").text("URL Title");

  const urlUpdateTextInput = urlUpdateTextInputContainer
    .find("input")
    .prop("minLength", CONSTANTS.URLS_TITLE_MIN_LENGTH)
    .prop("maxLength", CONSTANTS.URLS_TITLE_MAX_LENGTH)
    .val(urlTitleText);

  const urlTitleSubmitBtnUpdate = makeSubmitButton(30)
    .addClass("urlTitleSubmitBtnUpdate")
    .on("click.updateUrlTitle", function (e) {
      updateURLTitle(urlUpdateTextInput);
    });

  const urlTitleCancelBtnUpdate = makeCancelButton(30)
    .addClass("urlTitleCancelBtnUpdate")
    .on("click.updateUrlTitle", function (e) {
      resetUpdateUrlTitleForm(urlCard);
    });

  urlUpdateTextInputContainer
    .append(urlTitleSubmitBtnUpdate)
    .append(urlTitleCancelBtnUpdate);

  urlTitleAndUpdateWrap
    .append(urlTitleAndShowUpdateIconWrap)
    .append(urlUpdateTextInputContainer);

  return urlTitleAndUpdateWrap;
}

function resetUpdateUrlTitleForm(urlCard) {
  hideIfShown(urlCard.find(".updateUrlTitleWrap"));
  showIfHidden(urlCard.find(".urlTitleAndUpdateIconWrap"));
  urlCard.find(".urlTitleUpdate").val(urlCard.find(".urlTitle").text());
  resetUpdateURLTitleFailErrors(urlCard);
}

function createTagsAndOptionsForUrlBlock(url, tagArray) {
  const tagsAndButtonsWrap = $(document.createElement("div")).addClass(
    "tagsAndButtonsWrap full-width",
  );
  const tagsAndTagCreateWrap = $(document.createElement("div")).addClass(
    "urlTags flex-column",
  );
  const tagBadgesWrap = createTagBadgesAndWrap(tagArray, url.urlTagIDs);

  tagsAndButtonsWrap.append(tagsAndTagCreateWrap);
  tagsAndTagCreateWrap.append(tagBadgesWrap);

  if (url.canDelete) tagsAndTagCreateWrap.append(createTagInputBlock());

  tagsAndButtonsWrap.append(createUrlOptionsButtons(url));

  return tagsAndButtonsWrap;
}

function createTagBadgesAndWrap(dictTags, tagArray) {
  const tagBadgesWrap = $(document.createElement("div")).addClass(
    "urlTagsContainer flex-row flex-start",
  );

  for (let j in tagArray) {
    // Find applicable tags in dictionary to apply to URL card
    let tag = dictTags.find(function (e) {
      if (e.id === tagArray[j]) {
        return e;
      }
    });

    let tagSpan = createTagBadgeInURL(tag.id, tag.tagString);

    $(tagBadgesWrap).append(tagSpan);
  }

  return tagBadgesWrap;
}

function createTagInputBlock() {}

function createUrlOptionsButtons(url) {
  const urlOptions = $(document.createElement("div")).addClass(
    "urlOptions flex-row justify-content-start",
  );
  const urlBtnAccess = $(document.createElement("button"));
  const tagBtnCreate = $(document.createElement("button"));

  // Access the URL button
  $(urlBtnAccess)
    .addClass("btn btn-primary urlBtnAccess")
    .attr({ type: "button" })
    .text("Access Link")
    .on("click", function (e) {
      e.stopPropagation();
      accessLink(url.urlString);
    });

  // Add a tag button
  $(tagBtnCreate)
    .addClass("btn btn-info tagBtnCreate")
    .attr({ type: "button" })
    .text("Add Tag")
    .on("click", function (e) {
      e.stopPropagation();
      createTagShowInput();
    });

  urlOptions.append(urlBtnAccess).append(tagBtnCreate);

  if (url.canDelete) {
    const urlBtnUpdate = $(document.createElement("button"));
    const urlBtnDelete = $(document.createElement("button"));
    $(urlBtnDelete)
      .addClass("btn btn-danger urlBtnDelete")
      .attr({ type: "button" })
      .text("Delete")
      .on("click", function (e) {
        e.stopPropagation();
        deleteURLShowModal(url.utubUrlID);
      });

    $(urlBtnUpdate)
      .addClass("btn btn-light urlBtnUpdate")
      .attr({ type: "button" })
      .text("Edit Link")
      .on("click", function (e) {
        e.stopPropagation();
        updateURLShowInput();
      });

    urlOptions.append(urlBtnUpdate).append(urlBtnDelete);
  }

  return urlOptions;
}

// New URL card and input text fields. Initially hidden, shown when create URL is requested. Input field recreated here to ensure at the end of list after creation of new URL
function newURLInputAddEventListeners(urlInputForm) {
  const urlBtnCreate = urlInputForm.find("#urlSubmitBtnCreate");
  const urlBtnDelete = urlInputForm.find("#urlCancelBtnCreate");
  const createUrlTitleInput = urlInputForm.find("#urlTitleCreate");
  const createUrlInput = urlInputForm.find("#urlStringCreate");

  $(urlBtnCreate).on("click.createUrl", function (e) {
    e.stopPropagation();
    createURL(createUrlTitleInput, createUrlInput);
  });

  $(urlBtnDelete).on("click.createUrl", function (e) {
    e.stopPropagation();
    createURLHideInput();
  });

  // TODO: Escape and enter functionality
  $(document).on("keyup.createUrl", function (e) {
    switch (e.which) {
      case 13:
        // Handle enter key pressed
        createURL(createUrlTitleInput, createUrlInput);
        break;
      case 27:
        // Handle escape key pressed
        createURLHideInput();
        break;
      default:
      /* no-op */
    }
  });
}

function newURLInputRemoveEventListeners() {
  resetCreateUrlFailErrors();
  $("#urlSubmitBtnCreate").off();
  $("#urlCancelBtnCreate").off();
  $(document).off(".createUrl");
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
  $("#URLDeckHeader").text(UTubName);
  $("#utubNameUpdate").val(UTubName);

  updateUTubNameHideInput();
}
