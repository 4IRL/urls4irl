"use strict";

function setUIWhenNoUTubSelected() {
  hideInputs();
  setTagDeckSubheaderWhenNoUTubSelected();
  resetTagDeckIfNoUTubSelected();
  setURLDeckWhenNoUTubSelected();
  setMemberDeckWhenNoUTubSelected();
  resetMemberDeck();
}

function resetHomePageToInitialState() {
  setUIWhenNoUTubSelected();
  getAllUTubs().then((utubData) => {
    buildUTubDeck(utubData.utubs);
    setMemberDeckWhenNoUTubSelected();
    setTagDeckSubheaderWhenNoUTubSelected();
  });
}
