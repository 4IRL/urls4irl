import { $ } from "../../lib/globals.js";
import { KEYS } from "../../lib/constants.js";
import { AppEvents, on } from "../../lib/event-bus.js";

// The Members title row's overflow (three-dot) menu. Below a narrow row width
// (the container query in members.css) the member filter funnel and the Members
// gear are hidden and these two menu items stand in for them. The items reuse
// the controls' own click handlers (the hidden buttons are clicked), so no
// filter or gear logic is duplicated here.

const BUTTON_SELECTOR = "#memberBtnOverflow";
const MENU_SELECTOR = "#memberOverflowMenu";
const ITEM_SELECTOR = ".memberOverflowItem";
const NAMESPACE = ".memberOverflow";

// Each item and the control whose handler it reuses.
const ITEM_TARGETS: Readonly<Record<string, string>> = {
  memberOverflowFilter: "#memberNameFilterBtn",
  memberOverflowSettings: "#memberBtnSettings",
};

function menuElement(): HTMLElement | undefined {
  return $(MENU_SELECTOR)[0];
}

export function isMemberOverflowMenuOpen(): boolean {
  const menu = menuElement();
  return menu !== undefined && !menu.classList.contains("hidden");
}

// An item is offered only while its control is available (carries no `.hidden`).
function syncItems(): HTMLElement[] {
  const available: HTMLElement[] = [];
  $(ITEM_SELECTOR).each(function () {
    const target = $(ITEM_TARGETS[this.id] ?? "");
    const offered = target.length > 0 && !target.hasClass("hidden");
    $(this).toggleClass("hidden", !offered);
    if (offered) available.push(this);
  });
  return available;
}

function visibleItems(): HTMLElement[] {
  return $(ITEM_SELECTOR).not(".hidden").toArray();
}

/** Closes the menu; with `restoreFocus` focus returns to the overflow button. */
export function closeMemberOverflowMenu({
  restoreFocus = false,
}: { restoreFocus?: boolean } = {}): void {
  const menu = menuElement();
  if (menu === undefined || menu.classList.contains("hidden")) return;
  menu.classList.add("hidden");
  $(BUTTON_SELECTOR).attr("aria-expanded", "false");
  if (restoreFocus) $(BUTTON_SELECTOR)[0]?.focus({ preventScroll: true });
}

function focusItem({ index }: { index: number }): void {
  const items = visibleItems();
  if (items.length === 0) return;
  const wrapped = (index + items.length) % items.length;
  items[wrapped]?.focus({ preventScroll: true });
}

function openMenu({ focusLast = false }: { focusLast?: boolean } = {}): void {
  const menu = menuElement();
  if (menu === undefined) return;
  const items = syncItems();
  if (items.length === 0) return;
  menu.classList.remove("hidden");
  $(BUTTON_SELECTOR).attr("aria-expanded", "true");
  focusItem({ index: focusLast ? items.length - 1 : 0 });
}

function handleButtonClick(): void {
  if (isMemberOverflowMenuOpen()) {
    closeMemberOverflowMenu({ restoreFocus: true });
    return;
  }
  openMenu();
}

function handleButtonKeydown(event: JQuery.KeyDownEvent): void {
  if (event.key === KEYS.ARROW_DOWN || event.key === KEYS.ARROW_UP) {
    event.preventDefault();
    if (!isMemberOverflowMenuOpen()) {
      openMenu({ focusLast: event.key === KEYS.ARROW_UP });
    }
  }
}

function handleMenuKeydown(event: JQuery.KeyDownEvent): void {
  const items = visibleItems();
  const current = items.indexOf(document.activeElement as HTMLElement);
  switch (event.key) {
    case KEYS.ARROW_DOWN:
      event.preventDefault();
      focusItem({ index: current + 1 });
      return;
    case KEYS.ARROW_UP:
      event.preventDefault();
      focusItem({ index: current < 0 ? items.length - 1 : current - 1 });
      return;
    case KEYS.HOME:
      event.preventDefault();
      focusItem({ index: 0 });
      return;
    case KEYS.END:
      event.preventDefault();
      focusItem({ index: items.length - 1 });
      return;
    case KEYS.ESCAPE:
      // Consumed so no document-level Escape handler also acts on it.
      event.preventDefault();
      event.stopPropagation();
      closeMemberOverflowMenu({ restoreFocus: true });
      return;
    case KEYS.TAB:
      // Focus moves on naturally; the menu just closes behind it.
      closeMemberOverflowMenu();
      return;
  }
}

// Closes the menu first, then runs the reused control's own handler, so the
// surface it opens (filter input, gear popover or sheet) owns focus.
function handleItemClick(event: JQuery.ClickEvent): void {
  const targetSelector = ITEM_TARGETS[event.currentTarget.id];
  closeMemberOverflowMenu();
  if (targetSelector === undefined) return;
  $(targetSelector)[0]?.click();
}

function handleDocumentClick(event: JQuery.ClickEvent): void {
  if (!isMemberOverflowMenuOpen()) return;
  const target = event.target as Node;
  if ($(BUTTON_SELECTOR)[0]?.contains(target)) return;
  if (menuElement()?.contains(target)) return;
  closeMemberOverflowMenu();
}

/** Binds the overflow button and menu. Returns the unbind function. */
export function initMemberOverflowMenu(): () => void {
  $(BUTTON_SELECTOR)
    .off(NAMESPACE)
    .on(`click${NAMESPACE}`, handleButtonClick)
    .on(`keydown${NAMESPACE}`, handleButtonKeydown);
  $(MENU_SELECTOR)
    .off(NAMESPACE)
    .on(`keydown${NAMESPACE}`, handleMenuKeydown)
    .on(`click${NAMESPACE}`, ITEM_SELECTOR, handleItemClick);
  $(document).off(NAMESPACE).on(`click${NAMESPACE}`, handleDocumentClick);
  $(window)
    .off(NAMESPACE)
    .on(`resize${NAMESPACE}`, () => {
      closeMemberOverflowMenu();
    });
  const disposeCollapse = on(
    AppEvents.DECK_COLLAPSE_CHANGED,
    ({ deck, collapsed }) => {
      if (deck === "members" && collapsed) closeMemberOverflowMenu();
    },
  );
  return () => {
    $(BUTTON_SELECTOR).off(NAMESPACE);
    $(MENU_SELECTOR).off(NAMESPACE);
    $(document).off(NAMESPACE);
    $(window).off(NAMESPACE);
    disposeCollapse();
  };
}
