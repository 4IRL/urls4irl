import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { debug } from "../../lib/debug.js";
import { AppEvents, emit, on } from "../../lib/event-bus.js";
import { fillTemplate } from "../../lib/string-template.js";
import { setState } from "../../store/app-store.js";
import { setUIWhenNoUTubSelected } from "../init.js";
import { clearOutcomeBanner } from "../urls/outcome-banner.js";
import { TRASH_BANNER_MOUNT } from "./banner.js";

const log = debug("trash:panel");

const TRASH_SELECTOR = "#TrashSelector";
const TRASH_PANEL = "#TrashPanel";
const URL_DECK = "#URLDeck";

/** True while the Trash panel is the visible center destination. */
export function isTrashOpen(): boolean {
  return $(TRASH_SELECTOR).hasClass("active");
}

/**
 * Renders both tabs with `(0)` and shows both empty states. Step 5 replaces the
 * body with the real list fetch and row rendering.
 */
export function loadTrashList(): void {
  $("#TrashTabUrls").text(
    fillTemplate({
      template: APP_CONFIG.strings.TRASH_TAB_URLS,
      values: { n: "0" },
    }),
  );
  $("#TrashTabUtubs").text(
    fillTemplate({
      template: APP_CONFIG.strings.TRASH_TAB_UTUBS,
      values: { n: "0" },
    }),
  );
  $("#TrashUrlsEmptyState, #TrashUtubsEmptyState").removeClass("hidden");
  $("#TrashBtnEmpty").prop("disabled", true);
}

/**
 * Swaps the center panel from the URL deck to Trash. Never goes through
 * `selectUTub()` / `buildSelectedUTub()`: Trash is its own destination.
 */
export function openTrash({ fromHistory }: { fromHistory: boolean }): void {
  log("openTrash", { fromHistory });
  // setUIWhenNoUTubSelected() only toggles DOM, so clear the active UTub out of
  // the store too: modules that read it directly (stale-data, refresh-on-focus,
  // transfer picker, bulk copy, cross-UTub search) must not keep acting on the
  // previously selected UTub while Trash is open.
  setState({
    activeUTubID: null,
    activeUTubName: null,
    activeUTubDescription: null,
    urls: [],
    tags: [],
    members: [],
  });
  setUIWhenNoUTubSelected();
  $("#listUTubs > .UTubSelector").removeClass("active focus");

  $(TRASH_SELECTOR).addClass("active").attr("aria-current", "page");
  $(URL_DECK).addClass("hidden");
  $(TRASH_PANEL).removeClass("hidden");

  if (!fromHistory) {
    window.history.pushState(
      { trash: true },
      "",
      `/home?${APP_CONFIG.strings.TRASH_VIEW_QUERY_PARAM}=${APP_CONFIG.strings.TRASH_VIEW}`,
    );
  }

  emit(AppEvents.TRASH_OPENED);
  loadTrashList();
}

/** Reverses the panel swap and clears the Trash banner. */
export function closeTrash(): void {
  log("closeTrash");
  $(TRASH_SELECTOR).removeClass("active").removeAttr("aria-current");
  $(TRASH_PANEL).addClass("hidden");
  $(URL_DECK).removeClass("hidden");
  clearOutcomeBanner({ mount: TRASH_BANNER_MOUNT });
}

function handleTrashSelectorClick(): void {
  if (isTrashOpen()) return;
  openTrash({ fromHistory: false });
}

function handleTrashSelectorKeydown(event: JQuery.TriggeredEvent): void {
  if (event.key !== "Enter" && event.key !== " ") return;
  // The entry is a role=button div: stop Space from scrolling the deck.
  event.preventDefault();
  handleTrashSelectorClick();
}

export function initTrashPanel(): void {
  $(TRASH_SELECTOR).offAndOnExact("click.trashPanel", handleTrashSelectorClick);
  $(TRASH_SELECTOR).offAndOnExact(
    "keydown.trashPanel",
    handleTrashSelectorKeydown,
  );
  on(AppEvents.UTUB_SELECTED, () => {
    if (isTrashOpen()) closeTrash();
  });
}
