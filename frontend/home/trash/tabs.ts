/**
 * Tab controller for the Trash panel (URLs / UTubs).
 *
 * A port of `settings/settings-page.ts`'s WAI-ARIA APG tablist state machine
 * (roving tabindex, `aria-selected`, panel `hidden` toggling, arrow/Home/End
 * keyboard nav) under the `#Trash*` id namespace. It only toggles attributes
 * and moves focus; it never reads or writes user-facing label text.
 */

import { $ } from "../../lib/globals.js";

const TRASH_TABLIST_ID = "TrashTablist";
const TAB_ROLE_SELECTOR = '[role="tab"]';

export type TrashScope = "urls" | "utubs";

// Single source of the template↔TS id contract, in display order.
const TRASH_TABS = [
  { tab: "TrashTabUrls", panel: "TrashPanelUrls", scope: "urls" },
  { tab: "TrashTabUtubs", panel: "TrashPanelUtubs", scope: "utubs" },
] as const;

type TabChangedHandler = (scope: TrashScope) => void;

const tabChangedHandlers: TabChangedHandler[] = [];

/**
 * Registers a callback run whenever a tab is activated (Empty-trash enablement,
 * closing an open destination picker).
 */
export function onTrashTabChanged(handler: TabChangedHandler): void {
  tabChangedHandlers.push(handler);
}

/** The scope of the currently selected tab ("urls" when none is marked). */
export function getActiveTrashScope(): TrashScope {
  const active = TRASH_TABS.find(
    (entry) =>
      document.getElementById(entry.tab)?.getAttribute("aria-selected") ===
      "true",
  );
  return active?.scope ?? "urls";
}

/**
 * Applies the requested tab as active: roving `tabindex`/`aria-selected` on every
 * tab, `hidden` on each panel, then focuses the newly visible panel (the
 * unconditional focus for mouse activation; `handleTrashTabKeydown` re-focuses
 * the tab afterwards so keyboard users stay on the tablist).
 */
export function handleTrashTabClick({ tabId }: { tabId: string }): void {
  let activePanelId: string | null = null;
  let activeScope: TrashScope | null = null;

  for (const entry of TRASH_TABS) {
    const isActive = entry.tab === tabId;
    if (isActive) {
      activePanelId = entry.panel;
      activeScope = entry.scope;
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
  if (activeScope !== null) {
    const scope = activeScope;
    tabChangedHandlers.forEach((handler) => handler(scope));
  }
}

function handleTabButtonClick(event: JQuery.TriggeredEvent): void {
  const buttonId = (event.currentTarget as HTMLElement).id;
  if (!TRASH_TABS.some((entry) => entry.tab === buttonId)) {
    return;
  }
  handleTrashTabClick({ tabId: buttonId });
}

/**
 * Arrow-key navigation (ARIA APG): Left/Right cycle with wrap-around, Home/End
 * jump to the first/last tab; each handled key re-focuses the activated tab.
 */
// keydown (not keyup) — ARIA APG tablist spec; intentional deviation from repo's keyup convention — do not change to keyup
export function handleTrashTabKeydown(event: JQuery.TriggeredEvent): void {
  const key = event.key;
  if (
    key !== "ArrowLeft" &&
    key !== "ArrowRight" &&
    key !== "Home" &&
    key !== "End"
  ) {
    return;
  }

  const currentButtonId = (event.currentTarget as HTMLElement).id;
  const currentIndex = TRASH_TABS.findIndex(
    (entry) => entry.tab === currentButtonId,
  );
  if (currentIndex === -1) {
    return;
  }

  let nextIndex: number;
  if (key === "ArrowLeft") {
    nextIndex = (currentIndex - 1 + TRASH_TABS.length) % TRASH_TABS.length;
  } else if (key === "ArrowRight") {
    nextIndex = (currentIndex + 1) % TRASH_TABS.length;
  } else if (key === "Home") {
    nextIndex = 0;
  } else {
    nextIndex = TRASH_TABS.length - 1;
  }

  event.preventDefault();

  const nextTabId = TRASH_TABS[nextIndex].tab;
  handleTrashTabClick({ tabId: nextTabId });
  // Keyboard activation keeps focus on the tab (overriding the panel focus set
  // by `handleTrashTabClick`) so the user can keep arrow-navigating.
  document.getElementById(nextTabId)?.focus();
}

export function initTrashTabs(): void {
  $(`#${TRASH_TABLIST_ID} ${TAB_ROLE_SELECTOR}`).offAndOnExact(
    "click.trashTablist",
    handleTabButtonClick,
  );
  $(`#${TRASH_TABLIST_ID} ${TAB_ROLE_SELECTOR}`).offAndOnExact(
    "keydown.trashTablist",
    handleTrashTabKeydown,
  );
}

export function _resetTrashTabsForTests(): void {
  $(`#${TRASH_TABLIST_ID} ${TAB_ROLE_SELECTOR}`).off(".trashTablist");
  tabChangedHandlers.length = 0;
}
