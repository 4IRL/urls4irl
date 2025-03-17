"use strict";

$(document).ready(function () {
  /* Bind click functions */
  const urlBtnCreateSelector = "#urlBtnCreate";
  const urlBtnDeckCreateSelector = "#urlBtnDeckCreate";
  const urlBtnCreate = $(urlBtnCreateSelector);
  const urlBtnDeckCreate = $(urlBtnDeckCreateSelector);

  // Add new URL to current UTub
  urlBtnCreate.on("click", function (e) {
    if ($(e.target).closest("#urlBtnCreate").length > 0) createURLShowInput();
  });
  urlBtnDeckCreate.on("click", function (e) {
    if ($(e.target).closest("#urlBtnDeckCreate").length > 0)
      createURLShowInput();
  });

  // Bind enter key
  urlBtnCreate.on("focus", bindCreateURLShowInputEnterKeyEventListener());
  urlBtnDeckCreate.on("focus", bindCreateURLShowInputEnterKeyEventListener());

  urlBtnCreate.on("blur", unbindCreateURLShowInputEnterKeyEventListener());
  urlBtnDeckCreate.on("blur", unbindCreateURLShowInputEnterKeyEventListener());
});

function bindCreateURLShowInputEnterKeyEventListener() {
  $(document).on("keyup.createURL", function (e) {
    if (e.which === 13) {
      createURLShowInput();
    }
  });
}

function unbindCreateURLShowInputEnterKeyEventListener() {
  $(document).off(".createURL");
}
