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

function showNewPageOnAJAXHTMLResponse(htmlText) {
  $("body").fadeOut(150, function () {
    document.open();
    document.write(htmlText);
    document.close();

    // Hide body initially
    document.body.style.opacity = "0";

    // Wait for everything to load
    window.addEventListener("load", function () {
      $("body").css("opacity", "1").hide().fadeIn(150);
    });
  });
}
