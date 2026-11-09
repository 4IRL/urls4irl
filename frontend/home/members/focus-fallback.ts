import { $ } from "../../lib/globals.js";

// Members-local hidden-control focus fallback. `withHiddenControlFocusFallback`
// in urls/deck-view-attrs.ts is URL-deck specific and is not used here.

const HEADER_SELECTOR = "#MemberDeckHeaderAndCaret";
const ADD_BUTTON_SELECTOR = "#memberBtnCreate";
const ADD_WRAP_SELECTOR = "#createMemberWrap";
const INVITE_TRIGGER_SELECTOR = "#memberBtnInviteLink";
const INVITE_PANEL_SELECTOR = "#MemberInvitePanel";
// The co-owner kebab is the only kebab a policy flip hides.
// Owner kebabs are covered by `coverList` on a rebuild write.
const KEBAB_SELECTOR = ".memberRowKebab--coOwner";
const MENU_SELECTOR = ".memberRowMenu";
const LIST_SELECTOR = "#listMembers";
const ROW_SELECTOR = ".member[memberid]";

// Mirrors `isFocusable` in row-menu.ts (private there, duplicated here on
// purpose): `offsetParent` is `null` for a hidden element or a hidden ancestor.
function isFocusable(element: Element | null | undefined): boolean {
  return (
    element instanceof HTMLElement &&
    element.isConnected &&
    element.offsetParent !== null &&
    getComputedStyle(element).visibility !== "hidden"
  );
}

type FocusKind = "add" | "list" | "kebab";

function classifyFocus({
  active,
  coverList,
}: {
  active: HTMLElement;
  coverList: boolean;
}): FocusKind | null {
  if (
    active.matches(ADD_BUTTON_SELECTOR) ||
    active.closest(ADD_WRAP_SELECTOR) ||
    active.matches(INVITE_TRIGGER_SELECTOR) ||
    active.closest(INVITE_PANEL_SELECTOR)
  )
    return "add";
  // The kebab itself, or an item of its open menu (a sibling in the same cluster).
  if (
    active.matches(KEBAB_SELECTOR) ||
    active.closest(MENU_SELECTOR)?.parentElement?.querySelector(KEBAB_SELECTOR)
  )
    return "kebab";
  if (coverList && active.closest(LIST_SELECTOR)) return "list";
  return null;
}

// Runs a DOM write, then, when focus sat on the add button (or inside the add
// combobox) or a row kebab and that control is no longer focusable, moves focus
// to a place that still exists: the deck header for the add button, the kebab's
// own row when the row survives, otherwise the deck header. With `coverList`
// any focused element inside #listMembers is guarded (a rebuild write). Focus
// anywhere else is left alone.
export function withMemberControlFocusFallback({
  write,
  coverList = false,
}: {
  write: () => void;
  coverList?: boolean;
}): void {
  const active = document.activeElement;
  const kind =
    active instanceof HTMLElement ? classifyFocus({ active, coverList }) : null;
  // Resolved before the write: a removed control no longer has an ancestor row.
  const row =
    active instanceof HTMLElement
      ? active.closest<HTMLElement>(ROW_SELECTOR)
      : null;
  write();
  if (kind === null || !(active instanceof HTMLElement)) return;
  if (isFocusable(active)) return;

  if (kind !== "add") {
    if (row !== null && isFocusable(row)) {
      row.setAttribute("tabindex", "-1");
      row.focus({ preventScroll: true });
      return;
    }
  }
  $(HEADER_SELECTOR)[0]?.focus({ preventScroll: true });
}
