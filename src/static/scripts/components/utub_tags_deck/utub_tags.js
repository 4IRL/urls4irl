"use strict";

// Creates tag filter for addition to Tag deck
function buildTagFilterInDeck(tagID, string, urlCount = 0) {
  const container = $(document.createElement("div"));
  const tagStringSpan = $(document.createElement("span"));
  const rightContainer = $(document.createElement("div"));
  const urlCountSpan = $(document.createElement("span"));
  const deleteTagButton = $(document.createElement("div"));

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

  tagStringSpan.text(string);

  // TODO: addClass("tagCountHoverable") only if utubUserID == utubOwnerID
  rightContainer.addClass("tagCountHoverable");

  urlCountSpan.addClass("tagAppliedToUrlsCount").text(urlCount);

  deleteTagButton
    .addClass("utubTagBtnDelete align-center pointerable tabbable")
    .on("click", function (e) {
      e.stopPropagation();
      deleteUtubTag(utubTagID, tagSpan, urlCard);
    })
    .offAndOn("focus.removeUtubTag", function () {
      $(document).on("keyup.removeUtubTag", function (e) {
        if (e.which === 13) deleteUtubTag(utubTagID, tagSpan, urlCard);
      });
    })
    .offAndOn("blur.removeUtubTag", function () {
      $(document).off("keyup.removeUtubTag");
    });

  deleteTagButton.append(createTagDeleteIcon(22));

  container.append(tagStringSpan);
  rightContainer.append(urlCountSpan);
  // rightContainer.append(deleteTagButton);
  container.append(rightContainer);

  return container;
}

// Handle tag filtered selected - tags are filtered based on a URL having one tag AND another tag.. etc
function toggleTagFilterSelected(activeTagFilter) {
  const currentSelectedTagIDs = $.map($(".tagFilter.selected"), (tagFilter) =>
    parseInt($(tagFilter).attr("data-utub-tag-id")),
  );

  // Prevent selecting more than tag limit
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
    case 0:
      // No tags left selected
      disableUnselectAllButtonAfterTagFilterRemoved();
    default:
      // Reapply filters based on tag removed
      updateURLsAndTagSubheaderWhenTagSelected();
  }
}

function updateTagFilterCount(tagID, count) {
  const tagFilter = $(`.tagFilter[data-utub-tag-id="${tagID}"]`);
  const urlCountSpan = tagFilter.find(".tagAppliedToUrlsCount");

  if (count === 0) {
    // Remove the tag filter if no URLs are associated with it
    tagFilter.remove();
  } else {
    // Update the count of URLs associated with the tag
    urlCountSpan.text(count);
  }
}
