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

// Simple function to streamline the jQuery selector extraction of what tag IDs are currently displayed in the Tag Deck
function currentTagDeckIDs() {
  return $.map($(".tagFilter"), (tag) =>
    parseInt($(tag).attr("data-utub-tag-id")),
  );
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

function isTagInDeck(utubTagid) {
  return currentTagDeckIDs().includes(utubTagid);
}

// Clear the Tag Deck
function resetTagDeck() {
  $("#listTags").empty();
  resetCountOfTagFiltersApplied();
  disableUnselectAllButtonAfterTagFilterRemoved();
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
function isTagInUTub(tagBadges, utubTagID) {
  let tagExistsInUTub = false;
  tagBadges.each(function () {
    if (parseInt($(this).attr("data-utub-tag-id")) === utubTagID) {
      tagExistsInUTub = true;
    }
  });
  return tagExistsInUTub;
}

// Remove a tag from tag deck given its ID
function removeTagFromTagDeckGivenTagID(utubTagID) {
  $(".tagFilter[data-utub-tag-id=" + utubTagID + "]")
    .addClass("unselected")
    .remove();
}

// Is a tag in a given url deck
function isTagInURL(utubTagID, urlCard) {
  return (
    urlCard.find(
      ".urlTagsContainer > .tagBadge[data-utub-tag-id=" + utubTagID + "]",
    ).length > 0
  );
}

/** Tag Functions **/

// Update tags in LH panel based on asynchronous updates or stale data
function updateTagDeck(updatedTags) {
  const oldTags = $(".tagFilter");
  const oldTagIDs = $.map(oldTags, (tag) =>
    parseInt($(tag).attr("data-utub-tag-id")),
  );
  const newTagIDs = $.map(updatedTags, (tag) => tag.id);

  // Find any tags in old that aren't in new and remove them
  let oldTagID;
  for (let i = 0; i < oldTags.length; i++) {
    oldTagID = parseInt($(oldTags[i]).attr("data-utub-tag-id"));
    if (!newTagIDs.includes(oldTagID)) {
      $(".tagFilter[data-utub-tag-id=" + oldTagID + "]").remove();
    }
  }

  // Find any tags in new that aren't in old and add them
  const tagDeck = $("#listTags");
  for (let i = 0; i < updatedTags.length; i++) {
    if (!oldTagIDs.includes(updatedTags[i].id)) {
      tagDeck.append(
        createTagFilterInDeck(updatedTags[i].id, updatedTags[i].tagString),
      );
    }
  }
}

// Build LH panel tag list in selectedUTub
function buildTagDeck(dictTags) {
  resetTagDeck();
  const parent = $("#listTags");

  // Select all checkbox if tags in UTub
  dictTags.length > 0
    ? parent.append(createUnselectAllTagFilterInDeck())
    : null;

  // Loop through all tags and provide checkbox input for filtering
  for (let i in dictTags) {
    parent.append(createTagFilterInDeck(dictTags[i].id, dictTags[i].tagString));
  }
}

// Creates Select All tag filter for addition to Tag deck
function createUnselectAllTagFilterInDeck() {
  const container = $(document.createElement("div"));
  const span = $(document.createElement("span"));

  container
    .addClass("pointerable unselected disabled col-12")
    .attr({
      id: "unselectAll",
      "data-utub-tag-id": "all",
      tabindex: -1,
    })
    .on("focus.unselectAllSelected", function () {
      $(document).on("keyup.unselectAllSelected", function (e) {
        if (e.which === 13) {
          unselectAllTags();
          container.trigger("blur");
        }
      });
    })
    .on("blur.unselectAllSelected", function () {
      $(document).off("keyup.unselectAllSelected");
    });

  span.text("Unselect All");

  container.append(span);

  return container;
}

// Creates tag filter for addition to Tag deck
function createTagFilterInDeck(tagID, string) {
  const container = $(document.createElement("div"));
  const span = $(document.createElement("span"));

  container
    .addClass("tagFilter pointerable unselected col-12")
    .attr({
      "data-utub-tag-id": tagID,
      tabindex: 0,
    })
    .on("click.tagFilterSelected", function () {
      toggleTagFilterSelected(container);
    })
    .on("focus.tagFilterSelected", function () {
      $(document).on("keyup.tagFilterSelected", function (e) {
        if (e.which === 13) toggleTagFilterSelected(container);
      });
    })
    .on("blur.tagFilterSelected", function () {
      $(document).off("keyup.tagFilterSelected");
    });

  span.text(string);

  container.append(span);

  return container;
}

// Handle tag filtered selected - tags are filtered based on a URL having one tag AND another tag.. etc
function toggleTagFilterSelected(activeTagFilter) {
  console.log($(".tagFilter.selected"));
  const currentSelectedTagIDs = $.map($(".tagFilter.selected"), (tagFilter) =>
    parseInt($(tagFilter).attr("data-utub-tag-id")),
  );
  console.log(currentSelectedTagIDs);
  if (
    currentSelectedTagIDs.length >= CONSTANTS.TAGS_MAX_ON_URLS &&
    activeTagFilter.hasClass("unselected")
  )
    return;

  if (activeTagFilter.hasClass("selected")) {
    // Unselect the tag
    switch (currentSelectedTagIDs.length) {
      case CONSTANTS.TAGS_MAX_ON_URLS:
        // Unselecting at this point should enable all other tags again
        enableUnselectedTagsAfterDisabledDueToLimit();
        break;
      case 1:
        // Unselecting would leave no tags selected, so disable 'unselectAll' button
        disableUnselectAllButtonAfterTagFilterRemoved();
        break;
      default:
      /* no-op */
    }
    activeTagFilter.addClass("unselected").removeClass("selected");
  } else {
    // Select the tag
    activeTagFilter.removeClass("unselected").addClass("selected");
    switch (currentSelectedTagIDs.length) {
      case CONSTANTS.TAGS_MAX_ON_URLS - 1:
        // Selecting at this point should disable all other tags
        disableUnselectedTagsAfterLimitReached();
        break;
      case 0:
        // Selecting would select first tag, so enable 'unselectAll' button
        enableUnselectAllButtonAfterTagFilterApplied();
        break;
      default:
      /* no-op */
    }
  }

  updateURLsAndTagSubheaderWhenTagSelected();
}

function updateURLsAndTagSubheaderWhenTagSelected() {
  const selectedTagIDs = $.map($(".tagFilter.selected"), (tagFilter) =>
    parseInt($(tagFilter).attr("data-utub-tag-id")),
  );
  const urlCards = $(".urlRow");

  let tagBadgeIDsOnURL, shouldShow;
  urlCards.each((_, urlCard) => {
    tagBadgeIDsOnURL = $.map($(urlCard).find(".tagBadge"), (tagBadge) =>
      parseInt($(tagBadge).attr("data-utub-tag-id")),
    );

    shouldShow = true;
    for (let i = 0; i < selectedTagIDs.length; i++) {
      if (!tagBadgeIDsOnURL.includes(selectedTagIDs[i])) {
        shouldShow = false;
      }
    }

    shouldShow
      ? $(urlCard).attr({ filterable: true })
      : $(urlCard).attr({ filterable: false });
  });
  reapplyAlternatingURLCardBackgroundAfterFilter();
  updateCountOfTagFiltersApplied(selectedTagIDs.length);
}

function reapplyAlternatingURLCardBackgroundAfterFilter() {
  const visibleURLCards = $(".urlRow[filterable=true]:visible");

  visibleURLCards.each((idx, urlCard) => {
    $(urlCard)
      .removeClass("odd even")
      .addClass(idx % 2 == 0 ? "even" : "odd");
  });
}

function enableUnselectAllButtonAfterTagFilterApplied() {
  $("#unselectAll")
    .removeClass("disabled")
    .on("click.unselectAllTags", function () {
      unselectAllTags();
    })
    .attr({ tabindex: 0 });
}

function disableUnselectAllButtonAfterTagFilterRemoved() {
  $("#unselectAll")
    .addClass("disabled")
    .off(".unselectAllTags")
    .attr({ tabindex: -1 });
}

function enableUnselectedTagsAfterDisabledDueToLimit() {
  const unselectedTags = $(".tagFilter.unselected").removeClass("disabled");
  unselectedTags.each((_, tag) => {
    $(tag)
      .on("click.tagFilterSelected", function () {
        toggleTagFilterSelected($(tag));
      })
      .offAndOn("focus.tagFilterSelected", function () {
        $(document).on("keyup.tagFilterSelected", function (e) {
          if (e.which === 13) toggleTagFilterSelected($(tag));
        });
      })
      .offAndOn("blur.tagFilterSelected", function () {
        $(document).off("keyup.tagFilterSelected");
      })
      .attr({ tabindex: 0 });
  });
}

function disableUnselectedTagsAfterLimitReached() {
  const unselectedTags = $(".tagFilter.unselected").addClass("disabled");
  unselectedTags.each((_, tag) => {
    $(tag).off(".tagFilterSelected").attr({ tabindex: -1 });
  });
}

function unselectAllTags() {
  $(".tagFilter")
    .removeClass("selected unselected disabled")
    .addClass("unselected")
    .each((_, tag) => {
      $(tag)
        .offAndOn("click.tagFilterSelected", function () {
          toggleTagFilterSelected($(tag));
        })
        .offAndOn("focus.tagFilterSelected", function () {
          $(document).on("keyup.tagFilterSelected", function (e) {
            if (e.which === 13) toggleTagFilterSelected($(tag));
          });
        })
        .offAndOn("blur.tagFilterSelected", function () {
          $(document).off("keyup.tagFilterSelected");
        })
        .attr({ tabindex: 0 });
    });
  disableUnselectAllButtonAfterTagFilterRemoved();
  updateURLsAndTagSubheaderWhenTagSelected();
}

function updateTagFilteringOnFindingStaleData() {
  // Update tag deck itself
  const selectedTagCount = $(".tagFilter.selected").length;

  switch (selectedTagCount) {
    case CONSTANTS.TAGS_MAX_ON_URLS:
      // Handle if new tags are added and limit was already reached
      disableUnselectedTagsAfterLimitReached();
      break;
    case 0:
      // Handle if all selected tags were removed
      disableUnselectAllButtonAfterTagFilterRemoved();
      break;
    default:
    /* no-op */
  }

  // Apply filters to URLs, either showing or hiding all if necessary
  updateURLsAndTagSubheaderWhenTagSelected();
}

function updateTagFilteringOnURLOrURLTagDeletion() {
  const selectedTagsRemaining = $(".tagFilter.selected").length;

  switch (selectedTagsRemaining) {
    case CONSTANTS.TAGS_MAX_ON_URLS:
      // Max number of tags still applied, do nothing
      break;
    case 0:
      // No tags left selected
      disableUnselectAllButtonAfterTagFilterRemoved();
    default:
      // Reapply filters based on tag removed
      updateURLsAndTagSubheaderWhenTagSelected();
  }
}

/** Tags Display State Functions **/

// Subheader prompt hidden when no UTub selected
function setTagDeckSubheaderWhenNoUTubSelected() {
  $("#TagDeckSubheader").text(null);
}

// Selected UTub, show filters applied
function updateCountOfTagFiltersApplied(selectedTagCount) {
  $("#TagDeckSubheader").text(
    selectedTagCount +
      " of " +
      CONSTANTS.TAGS_MAX_ON_URLS +
      " tag filters applied",
  );
}

function resetCountOfTagFiltersApplied() {
  $("#TagDeckSubheader").text(
    "0 of " + CONSTANTS.TAGS_MAX_ON_URLS + " tag filters applied",
  );
}
