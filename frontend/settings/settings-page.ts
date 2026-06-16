/**
 * Tab-switching controller for the user settings page.
 *
 * Intentionally isolated and dependency-free: it implements only the WAI-ARIA
 * Authoring Practices Guide tablist state machine (roving tabindex,
 * `aria-selected`, panel `hidden` toggling, arrow/Home/End keyboard nav). The
 * admin metrics dashboard has an equivalent controller, but its tab logic is
 * entangled with data-fetch/cache concerns the settings shell does not need, so
 * this is a deliberate, self-contained re-implementation under a distinct
 * `#Settings*` id namespace. The controller only toggles attributes and moves
 * focus — it never reads or writes user-facing label text, so no APP_CONFIG
 * string bridge is required.
 */

import { $ } from "../lib/globals.js";

const SETTINGS_PAGE_ID = "SettingsPage";
const SETTINGS_TABLIST_ID = "SettingsTablist";
const TAB_ROLE_SELECTOR = '[role="tab"]';

// Single source of the template↔TS id contract: the PascalCase tab/panel ids
// rendered by `pages/settings.html`, in display order.
const SETTINGS_TABS = [
  { tab: "SettingsTabAccount", panel: "SettingsPanelAccount" },
  { tab: "SettingsTabStats", panel: "SettingsPanelStats" },
  { tab: "SettingsTabPrivacyData", panel: "SettingsPanelPrivacyData" },
  { tab: "SettingsTabUiSettings", panel: "SettingsPanelUiSettings" },
] as const;

/**
 * Apply the requested tab as active: set roving `tabindex`/`aria-selected` on
 * every tab, toggle each panel's `hidden`, then focus the newly-visible panel.
 *
 * `tabId` is the PascalCase DOM button id (e.g. `"SettingsTabStats"`) and is the
 * only key the controller dispatches on — the snake_case `data-tab` attribute is
 * template-only metadata that this module never reads. The panel focus here is
 * the unconditional focus for mouse-click activation; `handleTabKeydown`
 * re-focuses the tab button afterwards so keyboard users keep focus on the
 * tablist (ARIA APG).
 */
function handleTabClick({ tabId }: { tabId: string }): void {
  let activePanelId: string | null = null;

  for (const entry of SETTINGS_TABS) {
    const isActive = entry.tab === tabId;
    if (isActive) {
      activePanelId = entry.panel;
    }

    const tabElement = document.getElementById(entry.tab);
    if (tabElement !== null) {
      tabElement.setAttribute("aria-selected", isActive ? "true" : "false");
      tabElement.setAttribute("tabindex", isActive ? "0" : "-1");
    }

    const panelElement = document.getElementById(entry.panel);
    if (panelElement !== null) {
      if (isActive) {
        panelElement.removeAttribute("hidden");
      } else {
        panelElement.setAttribute("hidden", "");
      }
    }
  }

  if (activePanelId !== null) {
    document.getElementById(activePanelId)?.focus();
  }
}

function handleTabButtonClick(event: JQuery.TriggeredEvent): void {
  const buttonId = (event.currentTarget as HTMLButtonElement).id;
  const matchingEntry = SETTINGS_TABS.find((entry) => entry.tab === buttonId);
  if (matchingEntry === undefined) {
    return;
  }
  handleTabClick({ tabId: buttonId });
}

/**
 * Arrow-key navigation for the tablist (ARIA APG): Left/Right cycle through
 * tabs with wrap-around, Home/End jump to the first/last tab. Each handled key
 * calls `preventDefault()` to suppress the browser's default keystroke
 * behavior, then re-focuses the activated tab button.
 */
// keydown (not keyup) — ARIA APG tablist spec; intentional deviation from repo's keyup convention — do not change to keyup
function handleTabKeydown(event: JQuery.TriggeredEvent): void {
  const key = event.key as string | undefined;
  if (
    key !== "ArrowLeft" &&
    key !== "ArrowRight" &&
    key !== "Home" &&
    key !== "End"
  ) {
    return;
  }

  const currentButtonId = (event.currentTarget as HTMLButtonElement).id;
  const currentIndex = SETTINGS_TABS.findIndex(
    (entry) => entry.tab === currentButtonId,
  );
  if (currentIndex === -1) {
    return;
  }

  let nextIndex: number;
  if (key === "ArrowLeft") {
    nextIndex =
      (currentIndex - 1 + SETTINGS_TABS.length) % SETTINGS_TABS.length;
  } else if (key === "ArrowRight") {
    nextIndex = (currentIndex + 1) % SETTINGS_TABS.length;
  } else if (key === "Home") {
    nextIndex = 0;
  } else {
    nextIndex = SETTINGS_TABS.length - 1;
  }

  event.preventDefault();

  const nextTabId = SETTINGS_TABS[nextIndex].tab;
  handleTabClick({ tabId: nextTabId });
  // Keyboard activation keeps focus on the tab (overriding the panel focus set
  // by `handleTabClick`) so the user can keep arrow-navigating the tablist.
  document.getElementById(nextTabId)?.focus();
}

export function initSettingsPage(): void {
  const root = document.getElementById(SETTINGS_PAGE_ID);
  if (root === null) {
    return;
  }

  $(`#${SETTINGS_TABLIST_ID} ${TAB_ROLE_SELECTOR}`).offAndOnExact(
    "click",
    handleTabButtonClick,
  );
  $(`#${SETTINGS_TABLIST_ID} ${TAB_ROLE_SELECTOR}`).offAndOnExact(
    "keydown.settingsTablist",
    handleTabKeydown,
  );
}

export function _resetSettingsPageForTests(): void {
  $(`#${SETTINGS_TABLIST_ID} ${TAB_ROLE_SELECTOR}`)
    .off("click")
    .off("keydown.settingsTablist");
}
