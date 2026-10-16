import { $ } from "../../../lib/globals.js";

export function isEmptyString(value: string | null | undefined): boolean {
  return !value || !value.trim();
}

export function updateColorOfFollowingURLCardsAfterURLCreated(): void {
  const urlCards = $(".urlRow[filterable=true]").toArray();
  let urlCard: JQuery;
  for (let index = 1; index < urlCards.length; index++) {
    urlCard = $(urlCards[index]);
    if (index % 2 === 0) {
      urlCard.removeClass("odd").addClass("even");
    } else {
      urlCard.removeClass("even").addClass("odd");
    }
  }
}

export function enableTabbingOnURLCardElements(urlCard: JQuery): void {
  urlCard.find(".tabbable").enableTab();
}

export function disableTabbingOnURLCardElements(urlCard: JQuery): void {
  urlCard.find(".tabbable").disableTab();
}

// A URL edit form (string or title) is open. An absent wrap counts as closed.
export function isURLEditFormOpen({ urlCard }: { urlCard: JQuery }): boolean {
  return (
    urlCard.find(
      ".updateUrlStringWrap:not(.hidden), .updateUrlTitleWrap:not(.hidden)",
    ).length > 0
  );
}

// Hide the tags while a URL is being edited. The container is hidden, never
// removed: tag renderers re-find `.urlTagsContainer` to rebuild badges.
export function hideURLTags({ urlCard }: { urlCard: JQuery }): void {
  urlCard.find(".urlTagsContainer").hideClass();
  urlCard.find(".urlTags").addClass("urlTagsHiddenForEdit");
}

// Undo hideURLTags once no URL edit form remains open. removeHideClass is the
// exact inverse of hideClass; showClassFlex would leave a permanent
// visible-flex on every deselect.
export function restoreURLTagsIfNotEditing({
  urlCard,
}: {
  urlCard: JQuery;
}): void {
  if (isURLEditFormOpen({ urlCard })) return;
  urlCard.find(".urlTags").removeClass("urlTagsHiddenForEdit");
  urlCard.find(".urlTagsContainer").removeHideClass();
}

// Prevent editing URL title when needed
export function disableEditingURLTitle(urlCard: JQuery): void {
  urlCard.find(".urlTitleBtnUpdate").hideClass();
}

// Allow editing URL title when needed
export function enableEditingURLTitle(urlCard: JQuery): void {
  urlCard.find(".urlTitleBtnUpdate").removeHideClass();
}

// Prevent editing URL string when needed
export function disableEditingURLString(urlCard: JQuery): void {
  urlCard.find(".urlStringBtnUpdate, .urlStringCancelBigBtnUpdate").hideClass();
}

// Allow editing URL string when needed
export function enableEditingURLString(urlCard: JQuery): void {
  urlCard
    .find(".urlStringBtnUpdate, .urlStringCancelBigBtnUpdate")
    .removeHideClass();
}
