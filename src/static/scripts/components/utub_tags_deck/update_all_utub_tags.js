"use strict";

$(document).ready(function () {
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
});

function setTagDeckBtnsOnUpdateAllUTubTagsOpened() {
  $("#utubTagStandardBtns").hideClass();
  $("#utubTagCloseUpdateTagBtnContainer").showClassNormal();
}

function setTagDeckBtnsOnUpdateAllUTubTagsClosed() {
  $("#utubTagStandardBtns").showClassFlex();
  $("#utubTagCloseUpdateTagBtnContainer").hideClass();
}

function openUTubTagBtnMenuOnUTubTags() {
  $(".tagCountWrap").hideClass();
  $(".tagMenuWrap").showClassNormal();
  $(".tagFilter").addClass("disabled");
}

function closeUTubTagBtnMenuOnUTubTags() {
  $(".tagCountWrap").showClassNormal();
  $(".tagMenuWrap").hideClass();
  $(".tagFilter").removeClass("disabled");
}
