import { $ } from "../lib/globals.js";
import { APP_CONFIG } from "../lib/config.js";
import { TABLET_WIDTH } from "../lib/constants.js";
import { setMobileUIWhenUTubSelectedOrURLNavSelected } from "./mobile.js";
import {
  resetHomePageToInitialState,
  setUIWhenNoUTubSelected,
} from "./init.js";
import { setUTubEventListenersOnInitialPageLoad } from "./utubs/deck.js";
import { setCreateUTubEventListeners } from "./utubs/create.js";
import { getUTubInfo, buildSelectedUTub } from "./utubs/selectors.js";
import {
  isValidUTubID,
  isUtubIdValidOnPageLoad,
  isUtubIdValidFromStateAccess,
} from "./utubs/utils.js";
import { setMemberDeckWhenNoUTubSelected } from "./members/deck.js";
import { setTagDeckSubheaderWhenNoUTubSelected } from "./tags/deck.js";

/**
 * Initialize browser history (popstate) and page load (pageshow) event handlers
 */
export function initWindowEvents(): void {
  window.addEventListener("popstate", handlePopState);
  window.addEventListener("pageshow", handlePageShow);
}

function handlePopState(event: PopStateEvent): void {
  const state = event.state as { UTubID: number } | null;

  if (state !== null) {
    if (!isUtubIdValidFromStateAccess(state.UTubID)) {
      // Handle when a user previously went back to a now deleted UTub
      window.history.replaceState(null, "", "/home");
      resetHomePageToInitialState();
      return;
    }

    // State will contain property UTub if URL contains query parameter UTubID
    getUTubInfo(state.UTubID).then(
      (selectedUTub) => {
        if (!selectedUTub) return;
        buildSelectedUTub(selectedUTub);
        // If mobile, go straight to URL deck
        if (($(window).width() ?? 0) < TABLET_WIDTH) {
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
}

function handlePageShow(): void {
  setUTubEventListenersOnInitialPageLoad();
  setCreateUTubEventListeners();

  if (history.state && history.state.UTubID) {
    getUTubInfo(history.state.UTubID).then(
      (selectedUTub) => {
        if (!selectedUTub) return;
        buildSelectedUTub(selectedUTub);
        // If mobile, go straight to URL deck
        if (($(window).width() ?? 0) < TABLET_WIDTH) {
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

  const utubId = searchParams.get(APP_CONFIG.strings.UTUB_QUERY_PARAM);
  if (searchParams.size > 1 || utubId === null) {
    window.location.assign(APP_CONFIG.routes.errorPage);
    return;
  }

  if (!isValidUTubID(utubId)) {
    window.location.assign(APP_CONFIG.routes.errorPage);
    return;
  }

  if (!isUtubIdValidOnPageLoad(utubId)) {
    window.history.replaceState(null, "", "/home");
    window.location.assign(APP_CONFIG.routes.errorPage);
    return;
  }

  getUTubInfo(parseInt(utubId)).then(
    (selectedUTub) => {
      if (!selectedUTub) return;
      buildSelectedUTub(selectedUTub);
      // If mobile, go straight to URL deck
      if (($(window).width() ?? 0) < TABLET_WIDTH) {
        setMobileUIWhenUTubSelectedOrURLNavSelected();
      }
    },
    () => {
      window.location.assign(APP_CONFIG.routes.errorPage);
    },
  );
}
