import { $ } from "../lib/globals.js";
import { emit } from "../lib/metrics-client.js";
import { UI_EVENTS } from "../types/metrics-events.js";
import { LHS_COLLAPSE_SOURCE } from "../types/metrics-dim-values.js";
import { isMobile } from "./mobile.js";
import { closeUTubNameFilter } from "./utubs/search.js";

type LhsToggleSource =
  (typeof LHS_COLLAPSE_SOURCE)[keyof typeof LHS_COLLAPSE_SOURCE];

const MAIN_PANEL_SELECTOR = "#mainPanel";
const LEFT_PANEL_SELECTOR = "#leftPanel";
const SEAM_TOGGLE_SELECTOR = "#lhsToggleSeam";
const HEADER_TOGGLE_SELECTOR = "#lhsToggleHeader";
const COLLAPSED_CLASS = "lhs-collapsed";
const CHEVRON_CLOSED_CLASS = "lhs-chevron--closed";
const MOBILE_HIDDEN_CLASS = "hidden";

let userCollapsedLHS = false;
let searchModeActive = false;

/**
 * Single source of truth for LHS visibility on desktop. The resolved hidden
 * state is the OR of a manual collapse and an active search mode, so neither
 * writer can clobber the other.
 */
function applyLeftPanelVisibility(): void {
  const hidden = userCollapsedLHS || searchModeActive;
  $(MAIN_PANEL_SELECTOR).toggleClass(COLLAPSED_CLASS, hidden);
  const ariaExpanded = String(!hidden);
  $(SEAM_TOGGLE_SELECTOR).attr("aria-expanded", ariaExpanded);
  $(HEADER_TOGGLE_SELECTOR).attr("aria-expanded", ariaExpanded);
  $(`${SEAM_TOGGLE_SELECTOR} .bi`).toggleClass(CHEVRON_CLOSED_CLASS, hidden);
}

/**
 * Record a user's manual intent to collapse/expand the LHS. Desktop-only; the
 * mobile single-screen nav governs panels there. Emits the matching metric.
 */
export function setUserCollapsedLHS({
  collapsed,
  source,
}: {
  collapsed: boolean;
  source: LhsToggleSource;
}): void {
  if (isMobile()) return;
  userCollapsedLHS = collapsed;
  applyLeftPanelVisibility();
  if (collapsed) closeUTubNameFilter();
  emit({
    event: collapsed ? UI_EVENTS.UI_LHS_COLLAPSE : UI_EVENTS.UI_LHS_EXPAND,
    source,
  });
}

/**
 * Record search mode's intent to hide/restore the LHS. Routed through the
 * shared resolver so it composes with a manual collapse. Emits no metric —
 * search mode owns its own metric. On mobile the LHS is hidden via the
 * `.hidden` class on `#leftPanel`; on desktop the resolver handles it.
 */
export function setSearchModeActive({ active }: { active: boolean }): void {
  searchModeActive = active;
  applyLeftPanelVisibility();
  if (isMobile()) {
    $(LEFT_PANEL_SELECTOR).toggleClass(MOBILE_HIDDEN_CLASS, active);
  }
}

/**
 * Reconcile the LHS visibility when the viewport crosses the desktop/mobile
 * breakpoint. On mobile, the desktop collapse class is removed (intent is
 * kept); on desktop, the resolver re-applies the retained intent.
 */
export function reapplyLeftPanelVisibilityForViewport(): void {
  if (isMobile()) {
    $(MAIN_PANEL_SELECTOR).removeClass(COLLAPSED_CLASS);
    return;
  }
  applyLeftPanelVisibility();
}

/**
 * Bind both LHS toggle affordances. Handlers are bound unconditionally — the
 * mobile CSS hides both buttons, so they are unreachable on mobile without a
 * JS guard. Native `<button>` elements provide Enter/Space activation.
 */
export function initLeftPanelToggle(): void {
  $(SEAM_TOGGLE_SELECTOR).offAndOn("click.lhsToggleSeam", () =>
    setUserCollapsedLHS({
      collapsed: !userCollapsedLHS,
      source: LHS_COLLAPSE_SOURCE.SEAM,
    }),
  );
  $(HEADER_TOGGLE_SELECTOR).offAndOn("click.lhsToggleHeader", () =>
    setUserCollapsedLHS({
      collapsed: !userCollapsedLHS,
      source: LHS_COLLAPSE_SOURCE.URL_HEADER,
    }),
  );
  applyLeftPanelVisibility();
}
