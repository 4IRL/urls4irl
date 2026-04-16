import { APP_CONFIG } from "../../lib/config.js";
import { KEYS } from "../../lib/constants.js";
import { $ } from "../../lib/globals.js";
import { setState } from "../../store/app-store.js";
import { updateURLsAndTagSubheaderWhenTagSelected } from "../urls/cards/filtering.js";
import { toggleTagFilterSelected } from "./tags.js";

export function initUnselectAllTags(): void {
  /* Bind click functions */
  const utubTagBtnUnselectAll = $("#unselectAllTagFilters");
  utubTagBtnUnselectAll.on("click.unselectAllTags", function () {
    unselectAllTags();
  });
}

export function enableUnselectAllButtonAfterTagFilterApplied(): void {
  $("#unselectAllTagFilters")
    .removeClass("red-icon-disabled")
    .on("click.unselectAllTags", function () {
      unselectAllTags();
    })
    .attr({ tabindex: 0 });
}

export function disableUnselectAllButtonAfterTagFilterRemoved(): void {
  $("#unselectAllTagFilters")
    .addClass("red-icon-disabled")
    .off(".unselectAllTags")
    .attr({ tabindex: -1 });
}

export function resetCountOfTagFiltersApplied(): void {
  $("#TagDeckSubheader").text(
    "0 of " + APP_CONFIG.constants.TAGS_MAX_ON_URLS + " tag filters applied",
  );
}

function unselectAllTags(): void {
  $(".tagFilter")
    .removeClass("selected unselected disabled")
    .addClass("unselected")
    .each((_index, tag) => {
      $(tag)
        .offAndOn("click.tagFilterSelected", function () {
          toggleTagFilterSelected($(tag));
        })
        .offAndOn("focus.tagFilterSelected", function () {
          $(document).on(
            "keyup.tagFilterSelected",
            function (event: JQuery.TriggeredEvent) {
              if (event.key === KEYS.ENTER) toggleTagFilterSelected($(tag));
            },
          );
        })
        .offAndOn("blur.tagFilterSelected", function () {
          $(document).off("keyup.tagFilterSelected");
        })
        .attr({ tabindex: 0 });
    });
  disableUnselectAllButtonAfterTagFilterRemoved();

  setState({ selectedTagIDs: [] });
  updateURLsAndTagSubheaderWhenTagSelected();
}
