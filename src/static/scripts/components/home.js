"use strict";

function setUIWhenNoUTubSelected() {
  hideInputs();
  setTagDeckSubheaderWhenNoUTubSelected();
  resetTagDeckIfNoUTubSelected();
  setURLDeckWhenNoUTubSelected();
  setMemberDeckWhenNoUTubSelected();
  resetMemberDeck();
  $(".dynamic-subheader").removeClass("height-2p5rem");
  $(".sidePanelTitle").addClass("pad-b-0-25rem");
}

function resetHomePageToInitialState() {
  setUIWhenNoUTubSelected();
  getAllUTubs().then((utubData) => {
    buildUTubDeck(utubData.utubs);
    setMemberDeckWhenNoUTubSelected();
    setTagDeckSubheaderWhenNoUTubSelected();
  });
}
