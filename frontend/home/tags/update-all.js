import { $ } from "../../lib/globals.js";
import { KEYS } from "../../lib/constants.js";
import {
  enableTabbableChildElements,
  disableTabbableChildElements,
} from "../../lib/jquery-plugins.js";
import { updateURLsAndTagSubheaderWhenTagSelected } from "../urls/cards/filtering.js";

export function initUpdateAllTags() {
  const utubTagBtnUnselectAll = $("#utubTagBtnUpdateAllOpen");
  utubTagBtnUnselectAll
    .on("click.openUTubTagUpdate", function () {
      setTagDeckBtnsOnUpdateAllUTubTagsOpened();
      openUTubTagBtnMenuOnUTubTags();
    })
    .offAndOn("focus.openUTubTagUpdate", function () {
      $(document).offAndOn("keyup.openUTubTagUpdate", function (e) {
        if (e.key === KEYS.ENTER) {
          setTagDeckBtnsOnUpdateAllUTubTagsOpened();
          openUTubTagBtnMenuOnUTubTags();
        }
      });
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
      $(document).offAndOn("keyup.closeUTubTagUpdate", function (e) {
        if (e.key === KEYS.ENTER) {
          setTagDeckBtnsOnUpdateAllUTubTagsClosed();
          closeUTubTagBtnMenuOnUTubTags();
        }
      });
    })
    .offAndOn("blur.closeUTubTagUpdate", function () {
      $(document).off("keyup.closeUTubTagUpdate");
    });
}

export function setUnselectUpdateUTubTagEventListeners() {
  const utubTagBtnUnselectAll = $("#utubTagBtnUpdateAllOpen");
  utubTagBtnUnselectAll
    .offAndOn("click.openUTubTagUpdate", function () {
      setTagDeckBtnsOnUpdateAllUTubTagsOpened();
      openUTubTagBtnMenuOnUTubTags();
    })
    .offAndOn("focus.openUTubTagUpdate", function () {
      $(document).offAndOn("keyup.openUTubTagUpdate", function (e) {
        if (e.key === KEYS.ENTER) {
          setTagDeckBtnsOnUpdateAllUTubTagsOpened();
          openUTubTagBtnMenuOnUTubTags();
        }
      });
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
      $(document).offAndOn("keyup.closeUTubTagUpdate", function (e) {
        if (e.key === KEYS.ENTER) {
          setTagDeckBtnsOnUpdateAllUTubTagsClosed();
          closeUTubTagBtnMenuOnUTubTags();
          updateURLsAndTagSubheaderWhenTagSelected();
        }
      });
    })
    .offAndOn("blur.closeUTubTagUpdate", function () {
      $(document).off("keyup.closeUTubTagUpdate");
    });
}

export function setTagDeckBtnsOnUpdateAllUTubTagsOpened() {
  $("#utubTagStandardBtns").hideClass();
  $("#utubTagCloseUpdateTagBtnContainer").showClassNormal();
}

export function setTagDeckBtnsOnUpdateAllUTubTagsClosed() {
  $("#utubTagStandardBtns").showClassFlex();
  $("#utubTagCloseUpdateTagBtnContainer").hideClass();
}

export function openUTubTagBtnMenuOnUTubTags() {
  $(".tagCountWrap").hideClass();
  $(".tagMenuWrap").showClassNormal();
  $(".tagFilter").addClass("disabled").disableTab();
  enableTabbableChildElements($("#listTags"));
}

export function closeUTubTagBtnMenuOnUTubTags() {
  disableTabbableChildElements($("#listTags"));
  $(".tagCountWrap").showClassNormal();
  $(".tagMenuWrap").hideClass();
  $(".tagFilter").removeClass("disabled").enableTab();
}
