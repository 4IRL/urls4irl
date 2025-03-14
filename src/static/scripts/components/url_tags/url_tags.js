"use strict";

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

function isTagInURL(utubTagID, urlCard) {
  return (
    urlCard.find(
      ".urlTagsContainer > .tagBadge[data-utub-tag-id=" + utubTagID + "]",
    ).length > 0
  );
}
