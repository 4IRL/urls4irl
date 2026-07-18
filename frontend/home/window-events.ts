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
import { showURLDeckBannerError } from "./urls/deck.js";
import {
  exitCrossUtubSearchMode,
  isCrossUtubSearchActive,
  restoreCrossUtubSearchFromHistory,
} from "./search/cross-utub-search.js";
import {
  CROSS_UTUB_SEARCH_CLOSE_TRIGGER,
  MOBILE_NAV_TRIGGER,
  TAG_SHEET_TOGGLE_TRIGGER,
} from "../types/metrics-dim-values.js";
import {
  openTagSheet,
  closeTagSheet,
  isTagSheetOpen,
  getTagSheetOriginPanel,
  beginPopstateClose,
  endPopstateClose,
  consumeTagSheetSelfBackClose,
} from "./tags/sheet.js";
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

// The three persisted mobile panels (the tag sheet is never a persisted panel).
const VALID_MOBILE_PANELS: ReadonlySet<string> = new Set([
  "utubs",
  "urls",
  "members",
]);

/**
 * Normalize an untrusted panel value (from `?panel=` or `history.state`) to a
 * known MobilePanel, or null when absent/unrecognized (caller defaults to url-deck).
 */
function toValidMobilePanel(
  panel: string | null | undefined,
): MobilePanel | null {
  return panel != null && VALID_MOBILE_PANELS.has(panel)
    ? (panel as MobilePanel)
    : null;
}

/**
 * On reload/cold-load (pageshow), route the mobile UI to the restored panel.
 * A restore is not a navigation, so — unlike the popstate branch — this emits no
 * metric and sets no screen-reader announcement. Desktop shows all panels, so
 * this is a no-op there. A null/unrecognized panel lands on the url-deck.
 */
function routeMobilePanelOnPageShow({
  mobilePanel,
}: {
  mobilePanel: MobilePanel | null;
}): void {
  if (($(window).width() ?? 0) >= TABLET_WIDTH) return;
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
  setCurrentMobilePanel({ mobilePanel: mobilePanel ?? "urls" });
}

/**
 * Initialize browser history (popstate) and page load (pageshow) event handlers
 */
export function initWindowEvents(): void {
  window.addEventListener("popstate", handlePopState);
  window.addEventListener("pageshow", handlePageShow);
}

/**
 * Close an open tag sheet when Back/Forward pops FROM a sheet-open entry TO a
 * non-sheet entry (DD-31). Runs inside the popstate-close bracket, so
 * closeTagSheet() skips its own history traversal — this handler owns it.
 * Focus target depends on whether the panel Back landed on matches the panel the
 * sheet was opened over: same-panel returns focus to the opener/handle;
 * cross-panel (neither is guaranteed visible) falls back to the navbar landmark.
 */
function closeTagSheetForPopstateNav({
  poppedToPanel,
  suppressAnnouncement,
}: {
  poppedToPanel: MobilePanel;
  suppressAnnouncement: boolean;
}): void {
  if (!isTagSheetOpen()) return;
  const samePanel = poppedToPanel === getTagSheetOriginPanel();
  closeTagSheet({
    returnFocus: samePanel,
    focusLandmark: !samePanel,
    suppressAnnouncement,
    trigger: TAG_SHEET_TOGGLE_TRIGGER.HISTORY_NAV,
  });
}

function handlePopState(event: PopStateEvent): void {
  // A standalone tap/Escape/backdrop close of the tag sheet consumes its own
  // pushed history entry via closeTagSheet()'s default history.back(). That
  // traversal fires this popstate purely to unwind the stack — the underlying
  // UTub and panel are unchanged, and their active tag filter must survive.
  // Recognize + swallow that self-close pop here (consume-once) so it never
  // rebuilds the UTub, which would reset selectedTagIDs and wipe the filter.
  // Genuine Back/Forward navigations leave the flag false and fall through.
  if (consumeTagSheetSelfBackClose()) return;

  const generation = ++_popstateGeneration;
  // Bracket the FULL invocation (DD-19): any closeTagSheet() this handler
  // triggers — directly (DD-31) or via a synchronous UTUB_SELECTED listener
  // fired from inside buildSelectedUTub — must skip its own history.back().
  beginPopstateClose();
  const state = event.state as
    | { UTubID: number }
    | { UTubID: number; mobilePanel: MobilePanel }
    | { UTubID: number; mobilePanel: MobilePanel; tagSheetOpen: true }
    | { crossSearch: { query: string; fields: MatchedField[] } }
    | null;

  // Returning to a recorded cross-UTub search: re-open search mode and re-run
  // the saved query (see pushCrossUtubSearchHistoryState in cross-utub-search).
  if (state !== null && "crossSearch" in state) {
    restoreCrossUtubSearchFromHistory(state.crossSearch);
    endPopstateClose();
    return;
  }

  // Any non-search entry (a UTub or /home) leaves search mode if it is open —
  // e.g. Forward out of restored results, or Back past them to a UTub.
  if (isCrossUtubSearchActive()) {
    exitCrossUtubSearchMode({
      trigger: CROSS_UTUB_SEARCH_CLOSE_TRIGGER.HISTORY_NAV,
    });
  }

  // Sheet-open entry restore. Checked BEFORE the mobilePanel branch (a
  // tagSheetOpen entry also carries mobilePanel:"urls"). Rebuild the UTub — its
  // UTUB_SELECTED emit routes the underlying url-deck via mobile.ts's listener —
  // then reopen the sheet directly (bare openTagSheet, no push: a restore is not
  // a navigation, and openTagSheet's own _openedViaHistoryPush bookkeeping
  // re-arms reconciliation for this restored entry).
  if (state !== null && "tagSheetOpen" in state) {
    if (!isUtubIdValidFromStateAccess(state.UTubID)) {
      log(
        "popstate: tagSheetOpen target UTubID no longer accessible — resetting to /home",
        { utubID: state.UTubID },
      );
      window.history.replaceState(null, "", "/home");
      resetHomePageToInitialState();
      endPopstateClose();
      return;
    }

    getUTubInfo(state.UTubID).then(
      (selectedUTub) => {
        if (generation !== _popstateGeneration) return;
        if (selectedUTub) {
          buildSelectedUTub(selectedUTub);
          if (($(window).width() ?? 0) < TABLET_WIDTH) {
            setCurrentMobilePanel({ mobilePanel: "urls" });
            openTagSheet({ trigger: TAG_SHEET_TOGGLE_TRIGGER.HISTORY_NAV });
          }
        }
        endPopstateClose();
      },
      () => {
        if (generation !== _popstateGeneration) return;
        resetHomePageToInitialState();
        endPopstateClose();
      },
    );
    return;
  }

  // Merged `{ UTubID, mobilePanel }` entry (pushed by a mobile deck-switch tap
  // or the freshly-selected-UTub replace). Restore the UTub, then route to the
  // recorded panel. This is a restore, not a navigation — no push here.
  if (state !== null && "mobilePanel" in state) {
    // Popping FROM an open sheet TO this panel entry: close the sheet (DD-31).
    // A mobilePanel destination always sets #MobilePanelAnnouncement below, so
    // suppress the competing tag-sheet close announcement (DD-32).
    closeTagSheetForPopstateNav({
      poppedToPanel: state.mobilePanel,
      suppressAnnouncement: true,
    });

    if (!isUtubIdValidFromStateAccess(state.UTubID)) {
      log(
        "popstate: mobilePanel target UTubID no longer accessible — resetting to /home",
        { utubID: state.UTubID },
      );
      window.history.replaceState(null, "", "/home");
      resetHomePageToInitialState();
      endPopstateClose();
      return;
    }

    const mobilePanel = state.mobilePanel;
    getUTubInfo(state.UTubID).then(
      (selectedUTub) => {
        // Gate the entire callback: a stale/superseded popstate must not apply.
        if (generation !== _popstateGeneration) return;
        if (selectedUTub) {
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
        }
        endPopstateClose();
      },
      () => {
        // Stale-guard the reject path too: a superseded popstate whose fetch
        // rejects after a newer one resolved must not reset and clobber it.
        if (generation !== _popstateGeneration) return;
        resetHomePageToInitialState();
        endPopstateClose();
      },
    );
    return;
  }

  if (state !== null && "UTubID" in state) {
    // Popping FROM an open sheet TO a legacy bare-`UTubID` entry: close the
    // sheet (DD-31). Bare entries default to the url-deck and carry no competing
    // #MobilePanelAnnouncement, so the sheet's own close text still fires (DD-32).
    closeTagSheetForPopstateNav({
      poppedToPanel: "urls",
      suppressAnnouncement: false,
    });

    if (!isUtubIdValidFromStateAccess(state.UTubID)) {
      // Handle when a user previously went back to a now deleted UTub
      log("popstate: target UTubID no longer accessible — resetting to /home", {
        utubID: state.UTubID,
      });
      window.history.replaceState(null, "", "/home");
      resetHomePageToInitialState();
      endPopstateClose();
      return;
    }

    // State will contain property UTub if URL contains query parameter UTubID
    getUTubInfo(state.UTubID).then(
      (selectedUTub) => {
        // Same stale-result guard as the mobilePanel branch above — this
        // pre-existing branch shares the identical async race.
        if (generation !== _popstateGeneration) return;
        if (selectedUTub) {
          buildSelectedUTub(selectedUTub);
          // If mobile, go straight to URL deck
          if (($(window).width() ?? 0) < TABLET_WIDTH) {
            setMobileUIWhenUTubSelectedOrURLNavSelected();
          }
        }
        endPopstateClose();
      },
      () => {
        // Stale-guard the reject path too: a superseded popstate whose fetch
        // rejects after a newer one resolved must not reset and clobber it.
        if (generation !== _popstateGeneration) return;
        resetHomePageToInitialState();
        endPopstateClose();
      },
    );
  } else {
    // If does not contain query parameter, user is at /home - then update UTub titles/IDs
    resetHomePageToInitialState();
    endPopstateClose();
  }
}

function handlePageShow(): void {
  setUTubEventListenersOnInitialPageLoad();
  setCreateUTubEventListeners();

  if (history.state && history.state.UTubID) {
    // Restore the panel recorded on the warm history entry. A tagSheetOpen entry
    // also carries mobilePanel:"urls", so ignoring tagSheetOpen (the sheet does
    // not auto-reopen on reload) lands on the underlying url-deck automatically.
    const warmPanel = toValidMobilePanel(history.state.mobilePanel);
    getUTubInfo(history.state.UTubID).then(
      (selectedUTub) => {
        if (!selectedUTub) return;
        buildSelectedUTub(selectedUTub);
        routeMobilePanelOnPageShow({ mobilePanel: warmPanel });
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

  const validatedPanel = toValidMobilePanel(panel);

  // DD-24: a UTubID-absent request (only a recognized `panel` param supplied) is
  // functionally the "no UTub selected" state regardless of the panel value —
  // degrade gracefully to the no-utub landing instead of erroring. No banner: an
  // ordinary empty landing has nothing to explain.
  if (utubId === null) {
    log("pageshow: panel-only cold load, degrading to no-UTub state (DD-24)", {
      panel,
    });
    setUIWhenNoUTubSelected();
    setMemberDeckWhenNoUTubSelected();
    setTagDeckSubheaderWhenNoUTubSelected();
    return;
  }

  // DD-24 + DD-33: a syntactically-invalid or no-longer-accessible UTubID that
  // carries a recognized `panel` param (a stale/deleted-UTub bookmark) also
  // degrades gracefully — with an explanatory, auto-hiding banner — instead of
  // redirecting to /error. A bare invalid UTubID with NO panel keeps its existing
  // /error redirect below (narrower scope — unrelated to this panel feature).
  if (
    panel !== null &&
    (!isValidUTubID(utubId) || !isUtubIdValidOnPageLoad(utubId))
  ) {
    log(
      "pageshow: invalid/inaccessible UTubID with a panel param, degrading gracefully (DD-24/DD-33)",
      { utubId, panel },
    );
    setUIWhenNoUTubSelected();
    setMemberDeckWhenNoUTubSelected();
    setTagDeckSubheaderWhenNoUTubSelected();
    showURLDeckBannerError(APP_CONFIG.strings.UTUB_NO_LONGER_AVAILABLE);
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
      // Route to the recorded panel on mobile after the UTub is built.
      routeMobilePanelOnPageShow({ mobilePanel: validatedPanel });
    },
    () => {
      window.location.assign(APP_CONFIG.routes.errorPage);
    },
  );
}
