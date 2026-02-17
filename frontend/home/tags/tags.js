import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { KEYS } from "../../lib/constants.js";
import { deleteUTubTagShowModal } from "./delete.js";
import {
  enableUnselectAllButtonAfterTagFilterApplied,
  disableUnselectAllButtonAfterTagFilterRemoved,
} from "./unselect-all.js";
import { updateURLsAndTagSubheaderWhenTagSelected } from "../urls/cards/filtering.js";

// Dynamically generates the delete URL-Tag icon when needed
function createTagDeleteIcon(pixelSize = 15) {
  const WIDTH_HEIGHT_PX = pixelSize + "px";
  const SVG_NS = "http://www.w3.org/2000/svg";
  const deleteURLTagOuterIconSvg = $(document.createElementNS(SVG_NS, "svg"));
  const deleteURLTagInnerIconPath = $(document.createElementNS(SVG_NS, "path"));
  const path =
    "M11.46.146A.5.5 0 0 0 11.107 0H4.893a.5.5 0 0 0-.353.146L.146 4.54A.5.5 0 0 0 0 4.893v6.214a.5.5 0 0 0 .146.353l4.394 4.394a.5.5 0 0 0 .353.146h6.214a.5.5 0 0 0 .353-.146l4.394-4.394a.5.5 0 0 0 .146-.353V4.893a.5.5 0 0 0-.146-.353zm-6.106 4.5L8 7.293l2.646-2.647a.5.5 0 0 1 .708.708L8.707 8l2.647 2.646a.5.5 0 0 1-.708.708L8 8.707l-2.646 2.647a.5.5 0 0 1-.708-.708L7.293 8 4.646 5.354a.5.5 0 1 1 .708-.708";

  deleteURLTagInnerIconPath.attr({
    d: path,
  });

  deleteURLTagOuterIconSvg
    .attr({
      xmlns: SVG_NS,
      width: WIDTH_HEIGHT_PX,
      height: WIDTH_HEIGHT_PX,
      fill: "currentColor",
      class: "bi bi-x-octagon-fill",
      viewBox: "0 0 16 16",
    })
    .append(deleteURLTagInnerIconPath);

  return deleteURLTagOuterIconSvg;
}

// Creates tag filter for addition to Tag deck
export function buildTagFilterInDeck(utubID, tagID, string, urlCount = 0) {
  const container = $(document.createElement("div"));
  const tagStringSpan = $(document.createElement("span"));
  const tagCountContainer = $(document.createElement("div"));
  const tagMenuContainer = $(document.createElement("div"));
  const urlCountSpan = $(document.createElement("span"));
  const deleteTagButton = $(document.createElement("button"));

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
      container.offAndOn("keyup.tagFilterSelected", function (e) {
        if (e.key === KEYS.ENTER && $(e.target).hasClass("tagFilter"))
          toggleTagFilterSelected(container);
      });
    })
    .on("blur.tagFilterSelected", function () {
      container.off("keyup.tagFilterSelected");
    });

  tagStringSpan.text(string);

  tagCountContainer.addClass("tagCountWrap");
  tagMenuContainer.addClass("tagMenuWrap hidden");

  urlCountSpan
    .addClass("tagAppliedToUrlsCount")
    .text(`${urlCount}` + " / " + `${urlCount}`);

  deleteTagButton
    .addClass("utubTagBtnDelete align-center pointerable tabbable")
    .onExact("click.removeUtubTag", function (e) {
      deleteUTubTagShowModal(utubID, tagID, string);
    });

  deleteTagButton.append(createTagDeleteIcon(22));

  container.append(tagStringSpan);

  tagCountContainer.append(urlCountSpan);
  container.append(tagCountContainer);

  tagMenuContainer.append(deleteTagButton);
  container.append(tagMenuContainer);

  return container;
}

// Handle tag filtered selected - tags are filtered based on a URL having one tag AND another tag.. etc
export function toggleTagFilterSelected(activeTagFilter) {
  const currentSelectedTagIDs = $.map($(".tagFilter.selected"), (tagFilter) =>
    parseInt($(tagFilter).attr("data-utub-tag-id")),
  );

  // Prevent selecting more than tag limit
  if (
    currentSelectedTagIDs.length >= APP_CONFIG.constants.TAGS_MAX_ON_URLS &&
    activeTagFilter.hasClass("unselected")
  )
    return;

  if (activeTagFilter.hasClass("selected")) {
    // Unselect the tag
    switch (currentSelectedTagIDs.length) {
      case APP_CONFIG.constants.TAGS_MAX_ON_URLS:
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
      case APP_CONFIG.constants.TAGS_MAX_ON_URLS - 1:
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

export function enableUnselectedTagsAfterDisabledDueToLimit() {
  const unselectedTags = $(".tagFilter.unselected").removeClass("disabled");
  unselectedTags.each((_, tag) => {
    $(tag)
      .on("click.tagFilterSelected", function (e) {
        if (!$(e.target).closest(".tagFilter").is(this)) return;
        toggleTagFilterSelected($(tag));
      })
      .offAndOn("focus.tagFilterSelected", function () {
        $(tag).on("keyup.tagFilterSelected", function (e) {
          if (e.key === KEYS.ENTER) toggleTagFilterSelected($(tag));
        });
      })
      .offAndOn("blur.tagFilterSelected", function () {
        $(tag).off("keyup.tagFilterSelected");
      })
      .attr({ tabindex: 0 });
  });
}

export function disableUnselectedTagsAfterLimitReached() {
  const unselectedTags = $(".tagFilter.unselected").addClass("disabled");
  unselectedTags.each((_, tag) => {
    $(tag).off(".tagFilterSelected").attr({ tabindex: -1 });
  });
}

export function updateTagFilteringOnFindingStaleData() {
  // Update tag deck itself
  const selectedTagCount = $(".tagFilter.selected").length;

  switch (selectedTagCount) {
    case APP_CONFIG.constants.TAGS_MAX_ON_URLS:
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

export function updateTagFilteringOnURLOrURLTagDeletion() {
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
