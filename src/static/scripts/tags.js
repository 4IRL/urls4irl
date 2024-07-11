/* Tag UI Interactions */

$(document).ready(function () {
  /* Bind click functions */

  // Complete update tags
  $("#submitTagButton").on("click", function (e) {
    e.stopPropagation();
    e.preventDefault();
    updateTags();
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
    if ($(tagFilter).hasClass("unselected"))
      activeTagIDList.push($(tagFilter).attr("tagid"));
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

// Bind escape key to exit adding of a tag
function bindEscapeToExitCreateNewTag(inputWrapper) {
  $(document)
    .unbind("keyup.27")
    .bind("keyup.27", function (e) {
      if (e.which === 27) {
        e.stopPropagation();
        cancelCreateTagHideInput(inputWrapper);
      }
    });
}

// 11/25/23 need to figure out how to map tagids to Array so I can evaluate whether the tag already exists in Deck before adding it
// Function to evaluate whether newly added tag already exists in Tag Deck

// Hide tag deletion button when needed
function disableTagRemovalInURLCard(urlCard) {
  const allTagsDelBtns = urlCard.find(".urlTagBtnDelete");
  for (let i = 0; i < allTagsDelBtns.length; i++) {
    $(allTagsDelBtns[i]).addClass("hidden");
  }
}

// Show tag deletion when needed
function enableTagRemovalInURLCard(urlCard) {
  const allTagsDelBtns = urlCard.find(".urlTagBtnDelete");
  for (let i = 0; i < allTagsDelBtns.length; i++) {
    $(allTagsDelBtns[i]).removeClass("hidden");
  }
}

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

// Given a set of tag badges, verify a given tagID exists within those badges
function isTagInUTub(tagBadges, tagID) {
  let tagExistsInUTub = false;
  tagBadges.each(function () {
    if (parseInt($(this).attr("tagid")) === tagID) {
      tagExistsInUTub = true;
    }
  });
  return tagExistsInUTub;
}

// Remove a tag from tag deck given its ID
function removeTagFromUTubDeckGivenTagID(tagID) {
  $(".tagFilter[tagid=" + tagID + "]")
    .addClass("unselected")
    .remove();
}

/** Tag Functions **/

// Build LH panel tag list in selectedUTub
function buildTagDeck(dictTags) {
  resetTagDeck();
  const parent = $("#listTags");

  // Select all checkbox if tags in UTub
  dictTags.length > 0 ? parent.append(createSelectAllTagFilterInDeck()) : null;

  // Loop through all tags and provide checkbox input for filtering
  for (let i in dictTags) {
    parent.append(createTagFilterInDeck(dictTags[i].id, dictTags[i].tagString));
  }

  updateCountOfTagFiltersApplied();
}

// Creates Select All tag filter for addition to Tag deck
function createSelectAllTagFilterInDeck() {
  const container = document.createElement("div");
  const span = document.createElement("span");

  $(container).addClass("pointerable unselected col-12").attr({
    id: "selectAll",
    tagid: "all",
    onclick: "filterAllTags(); filterAllTaggedURLs()",
  });

  $(span).text("Select All");

  $(container).append(span);

  return container;
}

// Creates tag filter for addition to Tag deck
function createTagFilterInDeck(tagID, string) {
  const container = document.createElement("div");
  const span = document.createElement("span");

  $(container)
    .addClass("tagFilter pointerable unselected col-12")
    .attr({
      tagid: tagID,
      onclick: "filterTag(" + tagID + "); filterURL(" + tagID + ")",
    });

  $(span).text(string);

  $(container).append(span);

  return container;
}

// Update Tag Deck display in response to selectAll selection
function filterAllTags() {
  let selAll = $("#selectAll");
  selAll.toggleClass("unselected");

  let selectedBool = selAll.hasClass("unselected");

  let tagFilterList = $(".tagFilter");
  // Toggle all filter tags to match "Select All" checked status
  if (selectedBool) {
    tagFilterList.addClass("unselected");
    selAll.html("Select All");
  } else {
    tagFilterList.removeClass("unselected");
    selAll.html("Deselect All");
  }

  updateCountOfTagFiltersApplied();
}

// Update Tag Deck display in response to tag filter selection
function filterTag(tagID) {
  let filteredTag = $(".tagFilter[tagid=" + tagID + "]");
  filteredTag.toggleClass("unselected");

  let tagFilters = $(".tagFilter");
  let selAllBool = true;

  for (let j = 0; j < tagFilters.length; j++) {
    if (!$(tagFilters[j]).hasClass("unselected")) selAllBool = false;
  }

  let selAll = $("#selectAll");
  if (selAllBool) {
    selAll.addClass("unselected");
    selAll.html("Select All");
  } else {
    selAll.removeClass("unselected");
    selAll.html("Deselect All");
  }

  updateCountOfTagFiltersApplied();
}

/** Tags Display State Functions **/

// Subheader prompt hidden when no UTub selected
function hideTagDeckSubheaderWhenNoUTubSelected() {
  hideIfShown($("#TagDeckSubheader").closest(".titleElement"));
}

// Selected UTub, show filters applied
function updateCountOfTagFiltersApplied() {
  const tagDeckSubheader = $("#TagDeckSubheader");
  showIfHidden(tagDeckSubheader.closest(".titleElement"));
  const numOfTags = getNumOfTags();
  tagDeckSubheader.text(
    numOfTags -
      getActiveTagIDs().length +
      " of " +
      numOfTags +
      " tag filters applied",
  );
}
