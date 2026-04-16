import { KEYS } from "../../lib/constants.js";
import { $ } from "../../lib/globals.js";
import {
  disableTabbableChildElements,
  enableTabbableChildElements,
} from "../../lib/jquery-plugins.js";
import { updateURLsAndTagSubheaderWhenTagSelected } from "../urls/cards/filtering.js";

export function initUpdateAllTags(): void {
  const utubTagBtnUnselectAll = $("#utubTagBtnUpdateAllOpen");
  utubTagBtnUnselectAll
    .on("click.openUTubTagUpdate", function () {
      setTagDeckBtnsOnUpdateAllUTubTagsOpened();
      openUTubTagBtnMenuOnUTubTags();
    })
    .offAndOn("focus.openUTubTagUpdate", function () {
      $(document).offAndOn(
        "keyup.openUTubTagUpdate",
        function (event: JQuery.TriggeredEvent) {
          if (event.key === KEYS.ENTER) {
            setTagDeckBtnsOnUpdateAllUTubTagsOpened();
            openUTubTagBtnMenuOnUTubTags();
          }
        },
      );
    })
    .offAndOn("blur.openUTubTagUpdate", function () {
      $(document).off("keyup.openUTubTagUpdate");
    });

  const utubTagBtnUpdateAllClose = $("#utubTagBtnUpdateAllClose");
  utubTagBtnUpdateAllClose
    .on("click.closeUTubTagUpdate", function () {
      setTagDeckBtnsOnUpdateAllUTubTagsClosed();
      closeUTubTagBtnMenuOnUTubTags();
    })
    .offAndOn("focus.closeUTubTagUpdate", function () {
      $(document).offAndOn(
        "keyup.closeUTubTagUpdate",
        function (event: JQuery.TriggeredEvent) {
          if (event.key === KEYS.ENTER) {
            setTagDeckBtnsOnUpdateAllUTubTagsClosed();
            closeUTubTagBtnMenuOnUTubTags();
          }
        },
      );
    })
    .offAndOn("blur.closeUTubTagUpdate", function () {
      $(document).off("keyup.closeUTubTagUpdate");
    });
}

export function setUnselectUpdateUTubTagEventListeners(): void {
  const utubTagBtnUnselectAll = $("#utubTagBtnUpdateAllOpen");
  utubTagBtnUnselectAll
    .offAndOn("click.openUTubTagUpdate", function () {
      setTagDeckBtnsOnUpdateAllUTubTagsOpened();
      openUTubTagBtnMenuOnUTubTags();
    })
    .offAndOn("focus.openUTubTagUpdate", function () {
      $(document).offAndOn(
        "keyup.openUTubTagUpdate",
        function (event: JQuery.TriggeredEvent) {
          if (event.key === KEYS.ENTER) {
            setTagDeckBtnsOnUpdateAllUTubTagsOpened();
            openUTubTagBtnMenuOnUTubTags();
          }
        },
      );
    })
    .offAndOn("blur.openUTubTagUpdate", function () {
      $(document).off("keyup.openUTubTagUpdate");
    });

  const utubTagBtnUpdateAllClose = $("#utubTagBtnUpdateAllClose");
  utubTagBtnUpdateAllClose
    .offAndOn("click.closeUTubTagUpdate", function () {
      setTagDeckBtnsOnUpdateAllUTubTagsClosed();
      closeUTubTagBtnMenuOnUTubTags();
      updateURLsAndTagSubheaderWhenTagSelected();
    })
    .offAndOn("focus.closeUTubTagUpdate", function () {
      $(document).offAndOn(
        "keyup.closeUTubTagUpdate",
        function (event: JQuery.TriggeredEvent) {
          if (event.key === KEYS.ENTER) {
            setTagDeckBtnsOnUpdateAllUTubTagsClosed();
            closeUTubTagBtnMenuOnUTubTags();
            updateURLsAndTagSubheaderWhenTagSelected();
          }
        },
      );
    })
    .offAndOn("blur.closeUTubTagUpdate", function () {
      $(document).off("keyup.closeUTubTagUpdate");
    });
}

export function setTagDeckBtnsOnUpdateAllUTubTagsOpened(): void {
  $("#utubTagStandardBtns").hideClass();
  $("#utubTagCloseUpdateTagBtnContainer").showClassNormal();
}

export function setTagDeckBtnsOnUpdateAllUTubTagsClosed(): void {
  $("#utubTagStandardBtns").showClassFlex();
  $("#utubTagCloseUpdateTagBtnContainer").hideClass();
}

export function openUTubTagBtnMenuOnUTubTags(): void {
  $(".tagCountWrap").hideClass();
  $(".tagMenuWrap").showClassNormal();
  $(".tagFilter").addClass("disabled").disableTab();
  enableTabbableChildElements($("#listTags"));
}

export function closeUTubTagBtnMenuOnUTubTags(): void {
  disableTabbableChildElements($("#listTags"));
  $(".tagCountWrap").showClassNormal();
  $(".tagMenuWrap").hideClass();
  $(".tagFilter").removeClass("disabled").enableTab();
}
