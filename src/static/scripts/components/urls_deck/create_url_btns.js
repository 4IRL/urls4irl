"use strict";

function createURLShowInputEventListeners(utubID) {
  /* Bind click functions */
  const urlBtnCreateSelector = "#urlBtnCreate";
  const urlBtnDeckCreateSelector = "#urlBtnDeckCreate";
  const urlBtnCreate = $(urlBtnCreateSelector);
  const urlBtnDeckCreate = $(urlBtnDeckCreateSelector);

  // Add new URL to current UTub
  urlBtnCreate.offAndOn("click", function (e) {
    if ($(e.target).closest("#urlBtnCreate").length > 0)
      createURLShowInput(utubID);
  });
  urlBtnDeckCreate.offAndOn("click", function (e) {
    if ($(e.target).closest("#urlBtnDeckCreate").length > 0)
      createURLShowInput(utubID);
  });

  // Bind enter key
  urlBtnCreate.offAndOn(
    "focus",
    bindCreateURLShowInputEnterKeyEventListener(utubID),
  );
  urlBtnDeckCreate.offAndOn(
    "focus",
    bindCreateURLShowInputEnterKeyEventListener(utubID),
  );

  urlBtnCreate.offAndOn(
    "blur",
    unbindCreateURLShowInputEnterKeyEventListener(),
  );
  urlBtnDeckCreate.offAndOn(
    "blur",
    unbindCreateURLShowInputEnterKeyEventListener(),
  );
}

function bindCreateURLShowInputEnterKeyEventListener(utubID) {
  $(document).on("keyup.createURL", function (e) {
    if (e.key === KEYS.ENTER) {
      createURLShowInput(utubID);
    }
  });
}

function unbindCreateURLShowInputEnterKeyEventListener() {
  $(document).off(".createURL");
}
