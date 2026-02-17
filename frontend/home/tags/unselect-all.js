import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { KEYS } from "../../lib/constants.js";
import { toggleTagFilterSelected } from "./tags.js";
import { updateURLsAndTagSubheaderWhenTagSelected } from "../urls/cards/filtering.js";

export function initUnselectAllTags() {
  /* Bind click functions */
  const utubTagBtnUnselectAll = $("#unselectAllTagFilters");
  utubTagBtnUnselectAll.on("click.unselectAllTags", function () {
    unselectAllTags();
  });
}

export function enableUnselectAllButtonAfterTagFilterApplied() {
  $("#unselectAllTagFilters")
    .removeClass("red-icon-disabled")
    .on("click.unselectAllTags", function () {
      unselectAllTags();
    })
    .attr({ tabindex: 0 });
}

export function disableUnselectAllButtonAfterTagFilterRemoved() {
  $("#unselectAllTagFilters")
    .addClass("red-icon-disabled")
    .off(".unselectAllTags")
    .attr({ tabindex: -1 });
}

export function resetCountOfTagFiltersApplied() {
  $("#TagDeckSubheader").text(
    "0 of " + APP_CONFIG.constants.TAGS_MAX_ON_URLS + " tag filters applied",
  );
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
