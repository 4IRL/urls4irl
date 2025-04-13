"use strict";

function updateURLsAndTagSubheaderWhenTagSelected() {
  const selectedTagIDs = $.map($(".tagFilter.selected"), (tagFilter) =>
    parseInt($(tagFilter).attr("data-utub-tag-id")),
  );
  const urlCards = $(".urlRow");
  const numSelectedTagIDs = selectedTagIDs.length;

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
  updateCountOfTagFiltersApplied(numSelectedTagIDs);
}

function reapplyAlternatingURLCardBackgroundAfterFilter() {
  const visibleURLCards = $(".urlRow[filterable=true]:visible");

  visibleURLCards.each((idx, urlCard) => {
    $(urlCard)
      .removeClass("odd even")
      .addClass(idx % 2 == 0 ? "even" : "odd");
  });
}

function isURLCurrentlyVisibleInURLDeck(urlString) {
  const visibleURLs = $(".urlString");

  for (let i = 0; i < visibleURLs.length; i++) {
    if ($(visibleURLs[i]).attr("href") === urlString) {
      return true;
    }
  }
  return false;
}
