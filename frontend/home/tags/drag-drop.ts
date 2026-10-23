import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { AppEvents, on } from "../../lib/event-bus.js";
import { getOpenForm } from "../../lib/modal-tracking.js";
import { getState } from "../../store/app-store.js";
import { isMobile } from "../mobile.js";
import { submitStagedTags } from "../urls/tags/combobox.js";
import { isTagInURL } from "../urls/tags/tags.js";
import { selectURLCard } from "../urls/cards/selection.js";
import { showURLOutcomeBanner } from "../urls/outcome-banner.js";
import { fillTemplate } from "../../lib/string-template.js";
import { getActiveUTubID } from "../utubs/utils.js";
import { debug } from "../../lib/debug.js";

const log = debug("tags:drag-drop");

const TAG_DRAG_MIME = "application/x-u4i-tag-id";

/**
 * Why a URL card can or cannot take the dragged tag. `'has-tag'` and
 * `'at-limit'` drive the dimmed state and hint; `'blocked'` is every other
 * refusal (no ring, no hint).
 */
export const DropReason = Object.freeze({
  VALID: "valid",
  HAS_TAG: "has-tag",
  AT_LIMIT: "at-limit",
  BLOCKED: "blocked",
} as const);
export type DropReason = (typeof DropReason)[keyof typeof DropReason];

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
const DROP_GHOST_CLASS = "tagDropGhost";
const DROP_EXISTING_CLASS = "tagDropExisting";
const DROP_HINT_ATTR = "data-drop-hint";
const TAGS_CONTAINER_SELECTOR = ".urlTagsContainer";
const URL_LIST_SELECTOR = "#listURLs";
const URL_CARD_SELECTOR = ".urlRow";
const OPEN_COMBOBOX_SELECTOR = "#listURLs .urlTagComboboxWrap:not(.hidden)";
const CARD_EDIT_OPEN_SELECTOR =
  ".updateUrlTitleWrap:not(.hidden), .updateUrlStringWrap:not(.hidden)";

let draggedTagID: number | null = null;
let draggedChip: HTMLElement | null = null;
// Single global in-flight flag (never keyed on a card: cards are rebuilt).
// Written only by the drop handler; read by card validity and the drop entry.
let dropInFlight = false;

export function getDraggedTagID(): number | null {
  return draggedTagID;
}

export function isDropInFlight(): boolean {
  return dropInFlight;
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
function clearDragState(): void {
  draggedTagID = null;
  draggedChip = null;
  $(TAG_CHIP_SELECTOR).removeClass(DRAGGING_CLASS);
  clearDropMarks();
}

function clearDropMarks(): void {
  $(`.${DROP_TARGET_CLASS}, .${DROP_INVALID_CLASS}`).removeClass(
    `${DROP_TARGET_CLASS} ${DROP_INVALID_CLASS}`,
  );
  $(`[${DROP_HINT_ATTR}]`).removeAttr(DROP_HINT_ATTR);
  $(`.${DROP_GHOST_CLASS}`).remove();
  $(`.${DROP_EXISTING_CLASS}`).removeClass(DROP_EXISTING_CLASS);
}

function getAppliedTagCount(urlCard: JQuery): number {
  const raw = (urlCard.attr("data-utub-url-tag-ids") || "").trim();
  if (!raw) return 0;
  return raw.split(",").filter((part) => part.trim().length > 0).length;
}

/**
 * Whether `urlCard` can take the tag `tagID`. Fail-closed: the default is
 * `'blocked'` and `'valid'` is returned only when every condition is
 * affirmatively true. Called by `dragenter`/`dragover` and again by `drop`.
 */
export function getCardDropReason({
  urlCard,
  tagID,
}: {
  urlCard: JQuery;
  tagID: number;
}): DropReason {
  const state = getState();
  if (dropInFlight) return DropReason.BLOCKED;
  if (state.isCurrentUTubLocked !== false) return DropReason.BLOCKED;
  if (getActiveUTubID() === null) return DropReason.BLOCKED;
  if (state.multiSelectMode !== false) return DropReason.BLOCKED;
  // Any open form on ANY card blocks every card: a drop would otherwise select
  // away from it and silently reset it.
  if (getOpenForm() !== null) return DropReason.BLOCKED;
  // A combobox left open after a failed submit has already cleared the
  // open-form token, so check the DOM across the whole list too.
  if ($(OPEN_COMBOBOX_SELECTOR).length > 0) return DropReason.BLOCKED;
  if (urlCard.length !== 1) return DropReason.BLOCKED;
  if (urlCard.attr("filterable") === "false") return DropReason.BLOCKED;
  if (urlCard.attr("searchable") === "false") return DropReason.BLOCKED;
  if (urlCard.find(CARD_EDIT_OPEN_SELECTOR).length > 0)
    return DropReason.BLOCKED;

  if (isTagInURL(tagID, urlCard)) return DropReason.HAS_TAG;
  if (getAppliedTagCount(urlCard) >= APP_CONFIG.constants.TAGS_MAX_ON_URLS)
    return DropReason.AT_LIMIT;
  return DropReason.VALID;
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

function carriesTagMime(event: DragEvent): boolean {
  const types = event.dataTransfer?.types;
  return !!types && Array.from(types).includes(TAG_DRAG_MIME);
}

function closestCard(target: EventTarget | null): HTMLElement | null {
  const element = target as Element | null;
  return (element?.closest?.(URL_CARD_SELECTOR) as HTMLElement | null) ?? null;
}

function findDraggedTagString(): string | null {
  const tag = getState().tags.find(
    (candidate) => candidate.id === draggedTagID,
  );
  return tag ? tag.tagString : null;
}

function hintFor({
  reason,
  tagString,
}: {
  reason: DropReason;
  tagString: string;
}): string {
  switch (reason) {
    case DropReason.VALID:
      return fillTemplate({
        template: APP_CONFIG.strings.TAG_DROP_HINT_ADD,
        values: { tag: tagString },
      });
    case DropReason.HAS_TAG:
      return fillTemplate({
        template: APP_CONFIG.strings.TAG_DROP_HINT_HAS,
        values: { tag: tagString },
      });
    case DropReason.AT_LIMIT:
      return fillTemplate({
        template: APP_CONFIG.strings.TAGS_LIMIT_REACHED,
        values: { max: String(APP_CONFIG.constants.TAGS_MAX_ON_URLS) },
      });
    default:
      return "";
  }
}

/**
 * Applies the ring/dim class and hint to `card` and nothing else. A no-op when
 * the card already shows exactly this state, so continuous `dragover` events
 * (including those from child elements) do not churn the DOM.
 */
function highlightCard({
  card,
  reason,
  hint,
  tagString,
}: {
  card: HTMLElement;
  reason: DropReason;
  hint: string;
  tagString: string;
}): void {
  const className =
    reason === DropReason.VALID ? DROP_TARGET_CLASS : DROP_INVALID_CLASS;
  // An expanded card hides nothing, so it shows the outcome in its tag list
  // (CSS suppresses the corner hint there); a collapsed card keeps the hint.
  const expanded = card.getAttribute("urlSelected") === "true";
  const wantGhost = expanded && reason === DropReason.VALID;
  const existingPill =
    expanded && reason === DropReason.HAS_TAG && draggedTagID !== null
      ? card.querySelector<HTMLElement>(
          `${TAGS_CONTAINER_SELECTOR} > .tagBadge[data-utub-tag-id="${draggedTagID}"]`,
        )
      : null;
  const unchanged =
    card.classList.contains(className) &&
    card.getAttribute(DROP_HINT_ATTR) === hint &&
    $(`.${DROP_TARGET_CLASS}, .${DROP_INVALID_CLASS}`).length === 1 &&
    $(`.${DROP_GHOST_CLASS}`).length === (wantGhost ? 1 : 0) &&
    $(`.${DROP_EXISTING_CLASS}`).length === (existingPill ? 1 : 0);
  if (unchanged) return;

  clearDropMarks();
  card.classList.add(className);
  card.setAttribute(DROP_HINT_ATTR, hint);
  existingPill?.classList.add(DROP_EXISTING_CLASS);
  const tagsContainer = wantGhost
    ? card.querySelector(TAGS_CONTAINER_SELECTOR)
    : null;
  if (tagsContainer) {
    // Not a `.tagBadge` and carries no tag data attribute, so no tag consumer
    // (counts, delete, filters) can mistake the ghost for an applied tag. The
    // leading "+" is drawn in CSS; the text is only the dragged tag's name.
    const ghost = document.createElement("span");
    ghost.className = DROP_GHOST_CLASS;
    ghost.setAttribute("aria-hidden", "true");
    ghost.textContent = tagString;
    tagsContainer.appendChild(ghost);
  }
}

/**
 * Shared `dragenter`/`dragover` handler. Accepts the drag (preventDefault +
 * `dropEffect = 'copy'`) only for a tag drag over a card whose reason is
 * `'valid'`; every other case refuses it. Fail-closed: a foreign drag (no tag
 * MIME) or a stale/absent `draggedTagID` is ignored entirely.
 */
function handleDragOverCard(event: DragEvent): void {
  if (!carriesTagMime(event)) {
    // A foreign drag entering means any tag-drag state is stale.
    if (event.type === "dragenter") clearDragState();
    return;
  }
  if (draggedTagID === null) return;

  const dataTransfer = event.dataTransfer;
  const card = closestCard(event.target);
  const tagString = findDraggedTagString();
  const reason =
    card && tagString !== null
      ? getCardDropReason({ urlCard: $(card), tagID: draggedTagID })
      : DropReason.BLOCKED;

  if (reason === DropReason.VALID && card && tagString !== null) {
    event.preventDefault();
    if (dataTransfer) dataTransfer.dropEffect = "copy";
    highlightCard({
      card,
      reason,
      hint: hintFor({ reason, tagString }),
      tagString,
    });
    return;
  }

  if (dataTransfer) dataTransfer.dropEffect = "none";
  if (
    card &&
    tagString !== null &&
    (reason === DropReason.HAS_TAG || reason === DropReason.AT_LIMIT)
  ) {
    highlightCard({
      card,
      reason,
      hint: hintFor({ reason, tagString }),
      tagString,
    });
    return;
  }
  clearDropMarks();
}

function handleDragLeaveCard(event: DragEvent): void {
  const card = closestCard(event.target);
  if (!card) return;
  const entered = event.relatedTarget as Node | null;
  // Crossing between children of the same card is not a leave.
  if (entered && card.contains(entered)) return;
  // Browsers fire `dragenter` on the new card BEFORE `dragleave` on the old
  // one, so a global clear would wipe the marks the new card just received.
  // Moving into another card only strips the card being left; a null or
  // non-card relatedTarget (some browsers report null) clears everything.
  if (closestCard(entered)) {
    clearCardMarks(card);
    return;
  }
  clearDropMarks();
}

function clearCardMarks(card: HTMLElement): void {
  card.classList.remove(DROP_TARGET_CLASS, DROP_INVALID_CLASS);
  card.removeAttribute(DROP_HINT_ATTR);
  card.querySelectorAll(`.${DROP_GHOST_CLASS}`).forEach((ghost) => {
    ghost.remove();
  });
  card
    .querySelectorAll(`.${DROP_EXISTING_CLASS}`)
    .forEach((pill) => pill.classList.remove(DROP_EXISTING_CLASS));
}

/**
 * Selects the dropped-on card (when safe) and shows the outcome banner for an
 * `'applied'`/`'noop'` drop. Re-checks the world at outcome time: the request
 * took time, and the pre-flight GET can rebuild or remove the card.
 */
function showDropOutcome({
  outcome,
  utubID,
  utubUrlID,
  tagString,
}: {
  outcome: "applied" | "noop";
  utubID: number;
  utubUrlID: number;
  tagString: string;
}): void {
  const card = $(URL_LIST_SELECTOR).find(
    `${URL_CARD_SELECTOR}[utuburlid="${utubUrlID}"]`,
  );
  // The UTub was switched (or the card removed): the new deck must not get a
  // selection or banner for a drop it never saw.
  if (card.length !== 1 || getActiveUTubID() !== utubID) return;

  const cardVisible =
    card.attr("filterable") !== "false" && card.attr("searchable") !== "false";
  const canSelect =
    getOpenForm() === null &&
    $(OPEN_COMBOBOX_SELECTOR).length === 0 &&
    getState().multiSelectMode === false &&
    cardVisible;
  if (canSelect && card.attr("urlSelected") !== "true") selectURLCard(card);

  const values = { tag: tagString, title: card.find(".urlTitle").text() };
  showURLOutcomeBanner({
    variant: outcome === "applied" ? "success" : "partial",
    message: fillTemplate({
      template:
        outcome === "applied"
          ? APP_CONFIG.strings.TAG_DROP_ADDED
          : APP_CONFIG.strings.TAG_DROP_NOOP,
      values,
    }),
    returnFocusTo: card,
  });
}

async function submitDrop({
  urlCard,
  utubID,
  utubUrlID,
  tagString,
}: {
  urlCard: JQuery;
  utubID: number;
  utubUrlID: number;
  tagString: string;
}): Promise<void> {
  try {
    const outcome = await submitStagedTags({
      urlCard,
      utubID,
      utubUrlID,
      stagedStrings: [tagString],
      applySource: "drag",
    });
    // `'failed'` banners come from `submitStagedTagsFail`; `'aborted'` from
    // `handleRejectFromGetURL`. Neither needs more here.
    if (outcome === "applied" || outcome === "noop") {
      showDropOutcome({ outcome, utubID, utubUrlID, tagString });
    }
  } catch (error) {
    // `submitStagedTags` always settles, but a synchronous throw must not
    // become an unhandled rejection; the finally below still releases the flag.
    log("drop request threw", error);
  } finally {
    // Every outcome, including a thrown error, releases the global flag.
    dropInFlight = false;
  }
}

function handleDropOnCard(event: DragEvent): void {
  const dataTransfer = event.dataTransfer;
  if (!carriesTagMime(event) || !dataTransfer) return;
  event.preventDefault();

  if (dropInFlight) return;
  const card = closestCard(event.target);
  if (!card || draggedTagID === null) return;

  // The payload must match the module state; a lost `dragend` or a foreign
  // drag can never apply a stale tag.
  const payloadTagID = parseInt(dataTransfer.getData(TAG_DRAG_MIME), 10);
  if (payloadTagID !== draggedTagID) return;

  const tagString = findDraggedTagString();
  if (tagString === null) return;

  const urlCard = $(card);
  // Re-validate at drop time: state may have changed since the last dragover.
  if (
    getCardDropReason({ urlCard, tagID: draggedTagID }) !== DropReason.VALID
  ) {
    return;
  }

  const utubID = getActiveUTubID();
  const utubUrlID = parseInt(urlCard.attr("utuburlid") ?? "", 10);
  if (utubID === null || Number.isNaN(utubUrlID)) return;

  // Locals above are captured first; never re-read `draggedTagID` afterwards.
  // Clear before taking the flag so a throw here cannot leave it held.
  clearDragState();
  dropInFlight = true;
  void submitDrop({ urlCard, utubID, utubUrlID, tagString });
}

function handleGateMayHaveChanged(): void {
  if (!isTagDragEnabled()) clearDragState();
  syncTagDragState();
}

/**
 * Wires the Tag Deck drag source and the URL card drop target (delegated on the
 * stable `#listURLs` container, since cards are rebuilt). There is no Escape
 * handler: a native drag owns the session and Escape cancels it via `dragend`.
 */
export function initTagDragDrop(): void {
  const tagDeck = document.getElementById("TagDeck");
  tagDeck?.addEventListener("dragstart", handleDragStart);

  const urlList = document.querySelector(URL_LIST_SELECTOR);
  urlList?.addEventListener("dragenter", handleDragOverCard as EventListener);
  urlList?.addEventListener("dragover", handleDragOverCard as EventListener);
  urlList?.addEventListener("dragleave", handleDragLeaveCard as EventListener);
  urlList?.addEventListener("drop", handleDropOnCard as EventListener);

  // Document-level cleanup: a drag cancelled or dropped anywhere (including
  // outside any card, or after the chip left the DOM) leaves no stale state.
  document.addEventListener("dragend", clearDragState);
  document.addEventListener("drop", clearDragState);

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
