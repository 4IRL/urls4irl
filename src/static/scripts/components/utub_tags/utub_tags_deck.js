"use strict";

function buildTagDeck(dictTags) {
  resetTagDeck();
  const parent = $("#listTags");

  // Select all checkbox if tags in UTub
  if (dictTags.length > 0) {
    const unselectAllBtn = $("#unselectAllTagFilters");
    showIfHidden(unselectAllBtn);
    unselectAllBtn.addClass("red-icon-disabled");
  }

  // Loop through all tags and provide checkbox input for filtering
  for (let i in dictTags) {
    parent.append(buildTagFilterInDeck(dictTags[i].id, dictTags[i].tagString));
  }

  showIfHidden($("#utubTagBtnCreate"));
}

function resetTagDeck() {
  $("#listTags").empty();
  resetCountOfTagFiltersApplied();
  disableUnselectAllButtonAfterTagFilterRemoved();
  hideIfShown($("#utubTagBtnCreate"));
  hideIfShown($("#unselectAllTagFilters"));
  createUTubTagHideInput();
}

function resetTagDeckIfNoUTubSelected() {
  $("#listTags").empty();
  $("#createUTubTagWrap").hide();
  hideIfShown($("#createUTubTagWrap"));
  hideIfShown($("#utubTagBtnCreate"));
  hideIfShown($("#unselectAllTagFilters"));
  removeCreateUTubTagEventListeners();
  resetCreateUTubTagFailErrors();
  resetNewUTubTagForm();
}

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
        buildTagFilterInDeck(updatedTags[i].id, updatedTags[i].tagString),
      );
    }
  }
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

function setTagDeckSubheaderWhenNoUTubSelected() {
  $("#TagDeckSubheader").text(null);
}

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
