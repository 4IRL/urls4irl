import { $ } from "../../lib/globals.js";
import { KEYS } from "../../lib/constants.js";
import { debug } from "../../lib/debug.js";
import { AppEvents, on } from "../../lib/event-bus.js";

// The app's first per-row overflow (kebab) menu. Each non-owner member row (owner
// viewer only) gets a kebab trigger + a floating `role="menu"` card built in
// members.ts's createMemberBadge; this module owns the shared open/close/toggle,
// keyboard, and outside-dismiss behavior. Open/close is expressed as the `.open`
// class + the `hidden` attribute on the menu and `aria-expanded` on the trigger.

const log = debug("members");

const KEBAB_SELECTOR = ".memberRowKebab";
const MENU_SELECTOR = ".memberRowMenu";
const MENU_ITEM_SELECTOR = ".memberRowMenuItem";
// Gate string for the DD-3 document-level closers: only act when the click /
// active element is inside a row menu or its kebab trigger.
const MENU_OR_KEBAB_SELECTOR = `${MENU_SELECTOR}, ${KEBAB_SELECTOR}`;

// Locate the kebab trigger paired with a given menu (both are siblings inside the
// row's `.member-right` cluster).
function kebabForMenu(menu: JQuery<HTMLElement>): JQuery<HTMLElement> {
  return menu.siblings(KEBAB_SELECTOR);
}

function closeRowMenu({
  kebab,
  menu,
}: {
  kebab: JQuery<HTMLElement>;
  menu: JQuery<HTMLElement>;
}): void {
  menu.removeClass("open").attr("hidden", "hidden");
  kebab.attr("aria-expanded", "false");
}

// Close every open row menu. Used both when opening a new menu (exclusivity,
// DD-4a) and as the event-bus close path (DD-5/DD-6).
export function closeAllMemberRowMenus(): void {
  $(`${MENU_SELECTOR}.open`).each(function () {
    const menu = $(this);
    closeRowMenu({ kebab: kebabForMenu(menu), menu });
  });
}

function openRowMenu({
  kebab,
  menu,
}: {
  kebab: JQuery<HTMLElement>;
  menu: JQuery<HTMLElement>;
}): void {
  // Opening one menu closes any other that is open (DD-4a).
  closeAllMemberRowMenus();
  menu.addClass("open").removeAttr("hidden");
  kebab.attr("aria-expanded", "true");
  // DD-15: on every open — mouse click or keyboard activation — land focus on
  // the first menu item, unconditionally (no branch on trigger type).
  menu.find(MENU_ITEM_SELECTOR).first().trigger("focus");
}

// DD-3: outside-click closer. Gated on the target NOT being inside a row menu or
// kebab, so a click anywhere else in the app never steals the event from other
// handlers — it only closes a menu that is genuinely being clicked away from.
function handleDocumentClick(event: JQuery.TriggeredEvent): void {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;
  if ($(target).closest(MENU_OR_KEBAB_SELECTOR).length === 0) {
    closeAllMemberRowMenus();
  }
}

// DD-3: Escape closer. Gated on document.activeElement being inside the open
// menu/trigger so it never swallows Escape from the member-name search filter or
// the UTub edit panel's own global closers. Returns focus to the kebab trigger.
function handleDocumentKeydown(event: JQuery.TriggeredEvent): void {
  if (event.key !== KEYS.ESCAPE) return;
  const active = document.activeElement;
  if (!active) return;
  if ($(active).closest(MENU_OR_KEBAB_SELECTOR).length === 0) return;
  const openMenu = $(`${MENU_SELECTOR}.open`);
  if (openMenu.length === 0) return;
  // Do not bubble Escape to the deck (search filter / edit panel closers).
  event.preventDefault();
  event.stopPropagation();
  const kebab = kebabForMenu(openMenu);
  closeRowMenu({ kebab, menu: openMenu });
  kebab.trigger("focus");
}

// Element-scoped menu keyboard navigation. Enter/Space activation is native to
// the `<button role="menuitem">` items (they fire `click`), so only Arrow
// movement is handled here. This handler is bound to the menu, not the document,
// so it needs no target-gate.
function handleMenuKeydown({
  menu,
  event,
}: {
  menu: JQuery<HTMLElement>;
  event: JQuery.TriggeredEvent;
}): void {
  const items = menu.find(MENU_ITEM_SELECTOR).not("[hidden]");
  if (items.length === 0) return;
  const currentIndex = items.index(document.activeElement as HTMLElement);
  switch (event.key) {
    case KEYS.ARROW_DOWN: {
      event.preventDefault();
      const nextIndex =
        currentIndex < 0 ? 0 : (currentIndex + 1) % items.length;
      items.eq(nextIndex).trigger("focus");
      break;
    }
    case KEYS.ARROW_UP: {
      event.preventDefault();
      const prevIndex = currentIndex <= 0 ? items.length - 1 : currentIndex - 1;
      items.eq(prevIndex).trigger("focus");
      break;
    }
    default:
    /* no-op */
  }
}

let _globalHandlersBound = false;

// Bind the document-level closers lazily on the first row bind (rather than at
// module load) so they only exist once a kebab actually renders, and so jQuery's
// plugins are guaranteed installed. offAndOnExact keeps the binding idempotent.
function ensureGlobalHandlers(): void {
  if (_globalHandlersBound) return;
  _globalHandlersBound = true;
  $(document).offAndOnExact("click.memberRowMenu", handleDocumentClick);
  $(document).offAndOnExact("keydown.memberRowMenu", handleDocumentKeydown);
}

// DD-13: the per-row bind entry point, called once by createMemberBadge on the
// freshly-built kebab/menu pair. Wires the kebab toggle and the menu's keyboard
// navigation; the shared document/event-bus closers are set up on first call.
export function bindMemberRowMenu({
  kebab,
  menu,
  memberID,
}: {
  kebab: JQuery<HTMLButtonElement>;
  menu: JQuery<HTMLDivElement>;
  memberID: number;
}): void {
  ensureGlobalHandlers();

  kebab.offAndOnExact(
    "click.memberRowMenu",
    function (event: JQuery.TriggeredEvent) {
      event.preventDefault();
      // Stop the click from reaching the document-level outside closer, which
      // would otherwise immediately re-close a menu opened by this same click.
      event.stopPropagation();
      const isOpen = menu.hasClass("open");
      log("member row kebab toggled", { memberID, willOpen: !isOpen });
      if (isOpen) {
        closeRowMenu({ kebab, menu });
      } else {
        openRowMenu({ kebab, menu });
      }
    },
  );

  menu.offAndOnExact(
    "keydown.memberRowMenu",
    function (event: JQuery.TriggeredEvent) {
      handleMenuKeydown({ menu, event });
    },
  );
}

// DD-25: after the shared #confirmModal opened by a row action closes, return
// focus to that row's kebab trigger. Re-armed on every action (not bound once)
// because the row whose trigger should regain focus differs per open. Namespaced
// distinctly from delete.ts's own .memberAction handler so the two coexist on
// #confirmModal without clobbering each other. The length guard no-ops once the
// row (and its kebab) has been removed from the DOM by a successful removal.
export function bindMemberRowModalFocusRestore(memberID: number): void {
  $("#confirmModal").offAndOnExact(
    "hidden.bs.modal.memberRowFocusRestore",
    function () {
      const trigger = $(`.member[memberid=${memberID}] .memberRowKebab`);
      if (trigger.length > 0) trigger.trigger("focus");
    },
  );
}

// Close any open kebab menu when the visible member-row set changes (DD-5, from
// search.ts) or the add-member combobox opens (DD-6, from member-combobox.ts).
// Registered at module load — the event bus is pure JS and always available.
on(AppEvents.MEMBER_FILTER_CHANGED, closeAllMemberRowMenus);
on(AppEvents.MEMBER_ADD_OPENED, closeAllMemberRowMenus);
