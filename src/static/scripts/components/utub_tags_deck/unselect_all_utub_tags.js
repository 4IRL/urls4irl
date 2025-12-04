"use strict";

$(document).ready(function () {
  /* Bind click functions */
  const utubTagBtnUnselectAll = $("#unselectAllTagFilters");
  utubTagBtnUnselectAll.on("click.unselectAllTags", function () {
    unselectAllTags();
  });
});

function enableUnselectAllButtonAfterTagFilterApplied() {
  $("#unselectAllTagFilters")
    .removeClass("red-icon-disabled")
    .on("click.unselectAllTags", function () {
      unselectAllTags();
    })
    .attr({ tabindex: 0 });
}

function disableUnselectAllButtonAfterTagFilterRemoved() {
  $("#unselectAllTagFilters")
    .addClass("red-icon-disabled")
    .off(".unselectAllTags")
    .attr({ tabindex: -1 });
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
            if (e.key === KEYS.ENTER) toggleTagFilterSelected($(tag));
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
