import { $ } from "../lib/globals.js";
import { APP_CONFIG } from "../lib/config.js";
import { TABLET_WIDTH } from "../lib/constants.js";
import { emit } from "../lib/metrics-client.js";
import { UI_EVENTS } from "../types/metrics-events.js";
import {
  setMobileUIWhenUTubSelectedOrURLNavSelected,
  setMobileUIWhenUTubDeckSelected,
  setMobileUIWhenMemberDeckSelected,
  setCurrentMobilePanel,
  type MobilePanel,
} from "./mobile.js";
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
import {
  exitCrossUtubSearchMode,
  isCrossUtubSearchActive,
  restoreCrossUtubSearchFromHistory,
} from "./search/cross-utub-search.js";
import {
  CROSS_UTUB_SEARCH_CLOSE_TRIGGER,
  MOBILE_NAV_TRIGGER,
} from "../types/metrics-dim-values.js";
import type { MatchedField } from "../types/search.js";
import { debug } from "../lib/debug.js";

const log = debug("home-shell");

// Monotonic generation counter for popstate handling. A rapid Back-Back-Back
// sequence can leave an older popstate's async `getUTubInfo` in flight when a
// newer one lands; each handler captures the generation it started at and bails
// out of its resolved callback if a newer popstate has since superseded it, so
// stale data never clobbers the current state (or a screen-reader announcement).
let _popstateGeneration = 0;

/**
 * Resolve the visually-hidden screen-reader announcement copy for a restored
 * mobile panel. Read from the string bridge (never hardcoded in TS).
 */
function announcementForMobilePanel({
  mobilePanel,
}: {
  mobilePanel: MobilePanel;
}): string {
  switch (mobilePanel) {
    case "utubs":
      return APP_CONFIG.strings.MOBILE_PANEL_ANNOUNCEMENT_UTUBS;
    case "members":
      return APP_CONFIG.strings.MOBILE_PANEL_ANNOUNCEMENT_MEMBERS;
    case "urls":
    default:
      return APP_CONFIG.strings.MOBILE_PANEL_ANNOUNCEMENT_URLS;
  }
}

/**
 * Initialize browser history (popstate) and page load (pageshow) event handlers
 */
export function initWindowEvents(): void {
  window.addEventListener("popstate", handlePopState);
  window.addEventListener("pageshow", handlePageShow);
}

function handlePopState(event: PopStateEvent): void {
  const generation = ++_popstateGeneration;
  const state = event.state as
    | { UTubID: number }
    | { UTubID: number; mobilePanel: MobilePanel }
    | { crossSearch: { query: string; fields: MatchedField[] } }
    | null;

  // Returning to a recorded cross-UTub search: re-open search mode and re-run
  // the saved query (see pushCrossUtubSearchHistoryState in cross-utub-search).
  if (state !== null && "crossSearch" in state) {
    restoreCrossUtubSearchFromHistory(state.crossSearch);
    return;
  }

  // Any non-search entry (a UTub or /home) leaves search mode if it is open —
  // e.g. Forward out of restored results, or Back past them to a UTub.
  if (isCrossUtubSearchActive()) {
    exitCrossUtubSearchMode({
      trigger: CROSS_UTUB_SEARCH_CLOSE_TRIGGER.HISTORY_NAV,
    });
  }

  // Merged `{ UTubID, mobilePanel }` entry (pushed by a mobile deck-switch tap
  // or the freshly-selected-UTub replace). Restore the UTub, then route to the
  // recorded panel. This is a restore, not a navigation — no push here.
  if (state !== null && "mobilePanel" in state) {
    if (!isUtubIdValidFromStateAccess(state.UTubID)) {
      log(
        "popstate: mobilePanel target UTubID no longer accessible — resetting to /home",
        { utubID: state.UTubID },
      );
      window.history.replaceState(null, "", "/home");
      resetHomePageToInitialState();
      return;
    }

    const mobilePanel = state.mobilePanel;
    getUTubInfo(state.UTubID).then(
      (selectedUTub) => {
        // Gate the entire callback: a stale/superseded popstate must not apply.
        if (generation !== _popstateGeneration) return;
        if (!selectedUTub) return;
        buildSelectedUTub(selectedUTub);
        // Route to the recorded panel only on mobile — desktop shows all panels.
        if (($(window).width() ?? 0) < TABLET_WIDTH) {
          switch (mobilePanel) {
            case "utubs":
              setMobileUIWhenUTubDeckSelected();
              break;
            case "members":
              setMobileUIWhenMemberDeckSelected();
              break;
            case "urls":
            default:
              setMobileUIWhenUTubSelectedOrURLNavSelected();
              break;
          }
          setCurrentMobilePanel({ mobilePanel });
          // History-nav panel switches are not visually obvious to a screen
          // reader (no tap), so announce them. Tap-driven switches never set this.
          $("#MobilePanelAnnouncement").text(
            announcementForMobilePanel({ mobilePanel }),
          );
          emit({
            event: UI_EVENTS.UI_MOBILE_NAV,
            target: mobilePanel,
            trigger: MOBILE_NAV_TRIGGER.HISTORY_NAV,
          });
        }
      },
      () => {
        // Stale-guard the reject path too: a superseded popstate whose fetch
        // rejects after a newer one resolved must not reset and clobber it.
        if (generation !== _popstateGeneration) return;
        resetHomePageToInitialState();
      },
    );
    return;
  }

  if (state !== null && "UTubID" in state) {
    if (!isUtubIdValidFromStateAccess(state.UTubID)) {
      // Handle when a user previously went back to a now deleted UTub
      log("popstate: target UTubID no longer accessible — resetting to /home", {
        utubID: state.UTubID,
      });
      window.history.replaceState(null, "", "/home");
      resetHomePageToInitialState();
      return;
    }

    // State will contain property UTub if URL contains query parameter UTubID
    getUTubInfo(state.UTubID).then(
      (selectedUTub) => {
        // Same stale-result guard as the mobilePanel branch above — this
        // pre-existing branch shares the identical async race.
        if (generation !== _popstateGeneration) return;
        if (!selectedUTub) return;
        buildSelectedUTub(selectedUTub);
        // If mobile, go straight to URL deck
        if (($(window).width() ?? 0) < TABLET_WIDTH) {
          setMobileUIWhenUTubSelectedOrURLNavSelected();
        }
      },
      () => {
        // Stale-guard the reject path too: a superseded popstate whose fetch
        // rejects after a newer one resolved must not reset and clobber it.
        if (generation !== _popstateGeneration) return;
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
  const panel = searchParams.get(APP_CONFIG.strings.MOBILE_PANEL_QUERY_PARAM);
  // Reject only when a genuinely-unrecognized param is present. A UTubID-absent
  // request (only `panel` supplied) is no longer treated as malformed here — it
  // falls through (DD-24); Step 5 owns the graceful no-UTub degradation.
  const recognizedParamCount =
    (utubId !== null ? 1 : 0) + (panel !== null ? 1 : 0);
  if (searchParams.size > recognizedParamCount) {
    log(
      "pageshow: rejecting malformed query params, redirecting to error page",
      {
        paramCount: searchParams.size,
        recognizedParamCount,
        utubId,
        panel,
      },
    );
    window.location.assign(APP_CONFIG.routes.errorPage);
    return;
  }

  if (!isValidUTubID(utubId)) {
    window.location.assign(APP_CONFIG.routes.errorPage);
    return;
  }

  if (!isUtubIdValidOnPageLoad(utubId)) {
    log("pageshow: UTubID in URL not in user's deck — redirecting to error", {
      utubId,
    });
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
