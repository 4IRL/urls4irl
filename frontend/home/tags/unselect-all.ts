import { APP_CONFIG } from "../../lib/config.js";
import { KEYS } from "../../lib/constants.js";
import { debug } from "../../lib/debug.js";
import { $ } from "../../lib/globals.js";
import { emit } from "../../lib/metrics-client.js";
import { UI_EVENTS } from "../../types/metrics-events.js";
import { getState, setState } from "../../store/app-store.js";
import { updateURLsAndTagSubheaderWhenTagSelected } from "../urls/cards/filtering.js";
import { toggleTagFilterSelected } from "./tags.js";

const log = debug("tags");

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
  $("#TagDeckCount").text("(0/" + APP_CONFIG.constants.TAGS_MAX_ON_URLS + ")");
}

function unselectAllTags(): void {
  log("unselectAllTags fired — clearing all selectedTagIDs", {
    previouslySelected: getState().selectedTagIDs.length,
  });
  emit({ event: UI_EVENTS.UI_TAG_FILTER_TOGGLE });
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
