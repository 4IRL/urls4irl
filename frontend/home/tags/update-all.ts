import { $ } from "../../lib/globals.js";
import {
  disableTabbableChildElements,
  enableTabbableChildElements,
} from "../../lib/jquery-plugins.js";
import { updateURLsAndTagSubheaderWhenTagSelected } from "../urls/cards/filtering.js";
import { closeTagNameFilter } from "./search.js";

export function initUpdateAllTags(): void {
  const utubTagBtnUnselectAll = $("#utubTagBtnUpdateAllOpen");
  utubTagBtnUnselectAll.on("click.openUTubTagUpdate", function () {
    setTagDeckBtnsOnUpdateAllUTubTagsOpened();
    openUTubTagBtnMenuOnUTubTags();
  });

  const utubTagBtnUpdateAllClose = $("#utubTagBtnUpdateAllClose");
  utubTagBtnUpdateAllClose.on("click.closeUTubTagUpdate", function () {
    setTagDeckBtnsOnUpdateAllUTubTagsClosed();
    closeUTubTagBtnMenuOnUTubTags();
  });
}

export function setUnselectUpdateUTubTagEventListeners(): void {
  const utubTagBtnUnselectAll = $("#utubTagBtnUpdateAllOpen");
  utubTagBtnUnselectAll.offAndOn("click.openUTubTagUpdate", function () {
    setTagDeckBtnsOnUpdateAllUTubTagsOpened();
    openUTubTagBtnMenuOnUTubTags();
  });

  const utubTagBtnUpdateAllClose = $("#utubTagBtnUpdateAllClose");
  utubTagBtnUpdateAllClose.offAndOn("click.closeUTubTagUpdate", function () {
    setTagDeckBtnsOnUpdateAllUTubTagsClosed();
    closeUTubTagBtnMenuOnUTubTags();
    updateURLsAndTagSubheaderWhenTagSelected();
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
  closeTagNameFilter();
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
