"use strict";

function setUIWhenNoUTubSelected() {
  hideInputs();
  setTagDeckSubheaderWhenNoUTubSelected();
  resetTagDeckIfNoUTubSelected();
  setURLDeckWhenNoUTubSelected();
  resetURLDeck();
  setMemberDeckWhenNoUTubSelected();
  resetMemberDeck();
}

function resetHomePageToInitialState() {
  setUIWhenNoUTubSelected();
  getAllUTubs().then((utubData) => {
    buildUTubDeck(utubData);
    setMemberDeckWhenNoUTubSelected();
    setTagDeckSubheaderWhenNoUTubSelected();
  });
}
