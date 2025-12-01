"use strict";

window.addEventListener("popstate", function (e) {
  if (e.state && e.state.hasOwnProperty("UTubID")) {
    if (!isUtubIdValidFromStateAccess(e.state.UTubID)) {
      // Handle when a user previously went back to a now deleted UTub
      window.history.replaceState(null, null, "/home");
      resetHomePageToInitialState();
      return;
    }

    // State will contain property UTub if URL contains query parameter UTubID
    getUTubInfo(e.state.UTubID).then(
      (selectedUTub) => {
        buildSelectedUTub(selectedUTub);
        // If mobile, go straight to URL deck
        if ($(window).width() < TABLET_WIDTH) {
          setMobileUIWhenUTubSelectedOrURLNavSelected();
        }
      },
      () => {
        resetHomePageToInitialState();
      },
    );
  } else {
    // If does not contain query parameter, user is at /home - then update UTub titles/IDs
    resetHomePageToInitialState();
  }
});

window.addEventListener("pageshow", function (e) {
  setUTubEventListenersOnInitialPageLoad();
  setCreateUTubEventListeners();

  if (history.state && history.state.UTubID) {
    getUTubInfo(history.state.UTubID).then(
      (selectedUTub) => {
        buildSelectedUTub(selectedUTub);
        // If mobile, go straight to URL deck
        if ($(window).width() < TABLET_WIDTH) {
          setMobileUIWhenUTubSelectedOrURLNavSelected();
        }
        return;
      },
      () => {
        // Do nothing in error, as an invalid UTubID should indicate deleted UTub
      },
    );
    return;
  }

  // If a cold start, user might've been using URL with ID in it
  // First pull the query parameter
  // Then pull the UTub ID from the global UTubs variable and match
  // Handle if it doesn't exist
  const searchParams = new URLSearchParams(window.location.search);
  if (searchParams.size === 0) {
    setUIWhenNoUTubSelected();
    //setURLDeckWhenNoUTubSelected()
    setMemberDeckWhenNoUTubSelected();
    setTagDeckSubheaderWhenNoUTubSelected();
    return;
  }

  const utubId = searchParams.get(STRINGS.UTUB_QUERY_PARAM);
  if (searchParams.size > 1 || utubId === null) {
    window.location.assign(routes.errorPage);
  }

  if (!isValidUTubID(utubId)) window.location.assign(routes.errorPage);

  if (!isUtubIdValidOnPageLoad(parseInt(utubId))) {
    window.history.replaceState(null, null, "/home");
    window.location.assign(routes.errorPage);
  }

  getUTubInfo(parseInt(utubId)).then(
    (selectedUTub) => {
      buildSelectedUTub(selectedUTub);
      // If mobile, go straight to URL deck
      if ($(window).width() < TABLET_WIDTH) {
        setMobileUIWhenUTubSelectedOrURLNavSelected();
      }
    },
    () => {
      window.location.assign(routes.errorPage);
    },
  );
});
