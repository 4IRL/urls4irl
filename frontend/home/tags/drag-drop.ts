import { $ } from "../../lib/globals.js";
import { AppEvents, on } from "../../lib/event-bus.js";
import { getState } from "../../store/app-store.js";
import { isMobile } from "../mobile.js";

export const TAG_DRAG_MIME = "application/x-u4i-tag-id";

// Desktop only: wide viewport AND a fine primary pointer. `!isMobile()` is
// ANDed in because the jQuery window-width layout switch measures differently
// from this CSS query (scrollbar-width band).
const TAG_DRAG_MEDIA_QUERY = "(min-width: 992px) and (pointer: fine)";

const TAG_LIST_SELECTOR = "#listTags";
const TAG_CHIP_SELECTOR = "#listTags .tagFilter";
const EDIT_ALL_TAGS_OPEN_SELECTOR = "#listTags .tagMenuWrap:not(.hidden)";
const DRAGGING_CLASS = "tagDragging";
const DRAG_IMAGE_CLASS = "tagDragImage";
const DROP_TARGET_CLASS = "tagDropTarget";
const DROP_INVALID_CLASS = "tagDropInvalid";
const DROP_HINT_ATTR = "data-drop-hint";

let draggedTagID: number | null = null;
let draggedChip: HTMLElement | null = null;

export function getDraggedTagID(): number | null {
  return draggedTagID;
}

export function isTagDragEnabled(): boolean {
  return window.matchMedia(TAG_DRAG_MEDIA_QUERY).matches && !isMobile();
}

function isEditAllTagsActive(): boolean {
  return $(EDIT_ALL_TAGS_OPEN_SELECTOR).length > 0;
}

/**
 * Single shared cleanup for an in-flight drag: state, chip dimming and any
 * drop ring/hint left on URL cards.
 */
export function clearDragState(): void {
  draggedTagID = null;
  draggedChip = null;
  $(TAG_CHIP_SELECTOR).removeClass(DRAGGING_CLASS);
  $(`.${DROP_TARGET_CLASS}, .${DROP_INVALID_CLASS}`).removeClass(
    `${DROP_TARGET_CLASS} ${DROP_INVALID_CLASS}`,
  );
  $(`[${DROP_HINT_ATTR}]`).removeAttr(DROP_HINT_ATTR);
}

/**
 * Sets/removes `draggable` on every chip. Chips stay non-draggable in
 * edit-all-tags mode. Multi-select only cancels `dragstart`; the attribute is
 * left as is there.
 */
export function syncTagDragState(): void {
  const draggable = isTagDragEnabled() && !isEditAllTagsActive();
  $(TAG_CHIP_SELECTOR).each(function () {
    if (draggable) this.setAttribute("draggable", "true");
    else this.removeAttribute("draggable");
  });
}

function buildDragImage(chip: HTMLElement): HTMLElement {
  const pill = document.createElement("span");
  pill.className = `tagBadge ${DRAG_IMAGE_CLASS}`;
  pill.textContent = $(chip).children("span").first().text();
  document.body.appendChild(pill);
  setTimeout(() => pill.remove(), 0);
  return pill;
}

function handleDragStart(event: DragEvent): void {
  const target = event.target as HTMLElement | null;
  const chip = target?.closest?.(TAG_CHIP_SELECTOR) as HTMLElement | null;
  if (!chip) return;

  if (
    !isTagDragEnabled() ||
    isEditAllTagsActive() ||
    getState().multiSelectMode
  ) {
    event.preventDefault();
    return;
  }

  const tagID = parseInt(chip.getAttribute("data-utub-tag-id") ?? "", 10);
  if (Number.isNaN(tagID) || !event.dataTransfer) {
    event.preventDefault();
    return;
  }

  event.dataTransfer.setData(TAG_DRAG_MIME, String(tagID));
  event.dataTransfer.effectAllowed = "copy";
  event.dataTransfer.setDragImage(buildDragImage(chip), 0, 0);

  draggedTagID = tagID;
  draggedChip = chip;
  chip.classList.add(DRAGGING_CLASS);
}

function handleDragEnd(): void {
  clearDragState();
}

function handleGateMayHaveChanged(): void {
  if (!isTagDragEnabled()) clearDragState();
  syncTagDragState();
}

/**
 * Wires the Tag Deck drag source (Step 1). Step 2 extends this with the URL
 * card drop target.
 */
export function initTagDragDrop(): void {
  const tagDeck = document.getElementById("TagDeck");
  tagDeck?.addEventListener("dragstart", handleDragStart);
  tagDeck?.addEventListener("dragend", handleDragEnd);

  window.matchMedia(TAG_DRAG_MEDIA_QUERY).addEventListener("change", () => {
    clearDragState();
    syncTagDragState();
  });

  on(AppEvents.MOBILE_DECK_SWITCHED, handleGateMayHaveChanged);

  const tagList = document.querySelector(TAG_LIST_SELECTOR);
  if (tagList) {
    // Covers every rebuild path, including sortTagFiltersInPlace. A native
    // dragend is not reliably delivered when the source node is detached, so
    // a drag whose chip left the DOM is cleaned up here; a chip merely
    // re-appended by a re-sort is the same node and connected again.
    new MutationObserver(() => {
      syncTagDragState();
      if (draggedTagID !== null && !draggedChip?.isConnected) clearDragState();
    }).observe(tagList, { childList: true });
  }

  syncTagDragState();
}
