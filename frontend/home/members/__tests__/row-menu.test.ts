import { createMemberBadge } from "../members.js";
import {
  bindMemberRowModalFocusRestore,
  closeMemberRowMenuInRow,
  disarmMemberRowModalFocusRestore,
} from "../row-menu.js";
import { removeMemberShowModal } from "../delete.js";
import { modifyMemberRoleShowModal } from "../role.js";
import { emit, AppEvents } from "../../../lib/event-bus.js";

// createMemberBadge (members.js) builds the kebab + menu and wires the real
// row-menu.js behavior; only removeMemberShowModal / modifyMemberRoleShowModal
// are stubbed so the "Remove member" / role-toggle items' calls can be asserted
// without opening the real modals.
vi.mock("../delete.js", () => ({
  removeMemberShowModal: vi.fn(),
}));
vi.mock("../role.js", () => ({
  modifyMemberRoleShowModal: vi.fn(),
}));
vi.mock("../../btns-forms.js", () => ({ hideInputs: vi.fn() }));
vi.mock("../../urls/cards/selection.js", () => ({ deselectAllURLs: vi.fn() }));

const $ = window.jQuery;

function buildOwnerRow(
  memberID: number,
  username = "Bob",
): JQuery<HTMLSpanElement> {
  return createMemberBadge({
    memberID,
    username,
    memberRole: "member",
    viewerRole: "owner",
    utubID: 10,
  });
}

function buildCoOwnerRow(memberID: number): JQuery<HTMLSpanElement> {
  return createMemberBadge({
    memberID,
    username: "Bob",
    memberRole: "member",
    viewerRole: "co_owner",
    utubID: 10,
  });
}

describe("member row kebab menu (row-menu.ts)", () => {
  beforeEach(() => {
    document.body.innerHTML = `<div id="listMembers"></div>`;
    vi.clearAllMocks();
  });

  it("opening the menu sets aria-expanded=true, adds .open, and removes hidden", () => {
    const row = buildOwnerRow(5);
    $("#listMembers").append(row);
    const kebab = row.find(".memberRowKebab");
    const menu = row.find(".memberRowMenu");

    expect(kebab.attr("aria-expanded")).toBe("false");
    expect(menu.hasClass("open")).toBe(false);
    expect(menu.attr("hidden")).toBe("hidden");

    kebab.trigger("click");

    expect(kebab.attr("aria-expanded")).toBe("true");
    expect(menu.hasClass("open")).toBe(true);
    expect(menu.attr("hidden")).toBeUndefined();
  });

  it("focuses the first menu item on open (DD-15)", () => {
    const row = buildOwnerRow(5);
    $("#listMembers").append(row);
    const kebab = row.find(".memberRowKebab");
    const menu = row.find(".memberRowMenu");

    kebab.trigger("click");

    const firstItem = menu.find(".memberRowMenuItem").first().get(0);
    expect(document.activeElement).toBe(firstItem);
  });

  it("Escape closes the menu, restores hidden, and returns focus to the kebab", () => {
    const row = buildOwnerRow(5);
    $("#listMembers").append(row);
    const kebab = row.find(".memberRowKebab");
    const menu = row.find(".memberRowMenu");

    kebab.trigger("click");
    // Deterministically place focus inside the menu (DD-15 does this on open).
    (menu.find(".memberRowMenuItem").first().get(0) as HTMLElement).focus();
    expect(menu.hasClass("open")).toBe(true);

    $(document).trigger($.Event("keydown", { key: "Escape" }));

    expect(menu.hasClass("open")).toBe(false);
    expect(menu.attr("hidden")).toBe("hidden");
    expect(kebab.attr("aria-expanded")).toBe("false");
    expect(document.activeElement).toBe(kebab.get(0));
  });

  it("does not act on Escape when focus is outside the menu/trigger (DD-3 gate)", () => {
    document.body.innerHTML = `<div id="listMembers"></div><input id="elsewhere" />`;
    const row = buildOwnerRow(5);
    $("#listMembers").append(row);
    const kebab = row.find(".memberRowKebab");
    const menu = row.find(".memberRowMenu");

    kebab.trigger("click");
    // Move focus away from the menu — the gated Escape handler must NOT fire.
    (document.getElementById("elsewhere") as HTMLElement).focus();

    $(document).trigger($.Event("keydown", { key: "Escape" }));

    expect(menu.hasClass("open")).toBe(true);
  });

  it("clicking 'Remove member' calls removeMemberShowModal with the row's args", () => {
    const row = buildOwnerRow(5);
    $("#listMembers").append(row);
    const kebab = row.find(".memberRowKebab");

    kebab.trigger("click");
    row.find(".memberRowMenuItem.danger").trigger("click");

    expect(vi.mocked(removeMemberShowModal)).toHaveBeenCalledWith({
      memberID: 5,
      utubID: 10,
      intent: "remove",
    });
  });

  it("closes the menu before opening the remove modal (DD-16)", () => {
    const row = buildOwnerRow(5);
    $("#listMembers").append(row);
    const kebab = row.find(".memberRowKebab");
    const menu = row.find(".memberRowMenu");

    kebab.trigger("click");
    row.find(".memberRowMenuItem.danger").trigger("click");

    expect(menu.hasClass("open")).toBe(false);
    expect(kebab.attr("aria-expanded")).toBe("false");
  });

  it("clicking the role item closes the menu (DD-16) and calls modifyMemberRoleShowModal with the row's args", () => {
    const row = buildOwnerRow(5);
    $("#listMembers").append(row);
    const kebab = row.find(".memberRowKebab");
    const menu = row.find(".memberRowMenu");

    kebab.trigger("click");
    row.find(".memberRowMenuItemRole").trigger("click");

    // DD-16: the menu closes before the (mocked) role modal would open.
    expect(menu.hasClass("open")).toBe(false);
    expect(kebab.attr("aria-expanded")).toBe("false");
    // currentRole is sourced at click time; the store is empty here so it falls
    // back to the row's creation-time role ("member"), the grant direction.
    expect(vi.mocked(modifyMemberRoleShowModal)).toHaveBeenCalledWith({
      memberID: 5,
      currentRole: "member",
      utubID: 10,
    });
  });

  it("opening one row's menu closes any other open row menu (DD-4a)", () => {
    const rowA = buildOwnerRow(1, "Alice");
    const rowB = buildOwnerRow(2, "Bob");
    $("#listMembers").append(rowA).append(rowB);
    const kebabA = rowA.find(".memberRowKebab");
    const menuA = rowA.find(".memberRowMenu");
    const kebabB = rowB.find(".memberRowKebab");
    const menuB = rowB.find(".memberRowMenu");

    kebabA.trigger("click");
    expect(menuA.hasClass("open")).toBe(true);

    kebabB.trigger("click");
    expect(menuB.hasClass("open")).toBe(true);
    expect(menuA.hasClass("open")).toBe(false);
    expect(kebabA.attr("aria-expanded")).toBe("false");
    expect(kebabB.attr("aria-expanded")).toBe("true");
  });

  it("an outside click closes the open menu (DD-4b/DD-3)", () => {
    document.body.innerHTML = `<div id="listMembers"></div><button id="outside">x</button>`;
    const row = buildOwnerRow(5);
    $("#listMembers").append(row);
    const kebab = row.find(".memberRowKebab");
    const menu = row.find(".memberRowMenu");

    kebab.trigger("click");
    expect(menu.hasClass("open")).toBe(true);

    $("#outside").trigger("click");

    expect(menu.hasClass("open")).toBe(false);
    expect(menu.attr("hidden")).toBe("hidden");
  });

  it("MEMBER_FILTER_CHANGED closes the open menu (DD-14/DD-5)", () => {
    const row = buildOwnerRow(5);
    $("#listMembers").append(row);
    const kebab = row.find(".memberRowKebab");
    const menu = row.find(".memberRowMenu");

    kebab.trigger("click");
    expect(menu.hasClass("open")).toBe(true);

    emit(AppEvents.MEMBER_FILTER_CHANGED);

    expect(menu.hasClass("open")).toBe(false);
    expect(kebab.attr("aria-expanded")).toBe("false");
  });

  it("restores focus to the row's kebab after the confirm modal closes (DD-25)", () => {
    document.body.innerHTML = `<div id="listMembers"></div><div id="confirmModal"></div>`;
    const row = buildOwnerRow(5);
    $("#listMembers").append(row);
    const kebab = row.find(".memberRowKebab");

    bindMemberRowModalFocusRestore(5);
    // Simulate Bootstrap firing hidden.bs.modal when the confirm modal closes.
    $("#confirmModal").trigger("hidden.bs.modal");

    expect(document.activeElement).toBe(kebab.get(0));
  });

  // Sad path: the kebab lives inside the Member deck's `.content`, which is
  // visibility:hidden while the deck is collapsed — the row still exists, so
  // the old length-only guard would have focused an unfocusable button and
  // dropped focus to <body>.
  it("falls back to the deck header button when the row's kebab is not focusable", () => {
    document.body.innerHTML = `<div id="listMembers"></div><div id="confirmModal"></div><button type="button" id="MemberDeckHeaderAndCaret"></button>`;
    const row = buildOwnerRow(5);
    $("#listMembers").append(row);
    // decks.css never loads into happy-dom — stand the collapsed deck's
    // inherited visibility:hidden up directly on the kebab.
    // CSS visibility inherits, so the row is hidden together with its kebab.
    (row.get(0) as HTMLElement).style.visibility = "hidden";
    (row.find(".memberRowKebab").get(0) as HTMLElement).style.visibility =
      "hidden";

    bindMemberRowModalFocusRestore(5);
    $("#confirmModal").trigger("hidden.bs.modal");

    expect(document.activeElement).toBe(
      document.getElementById("MemberDeckHeaderAndCaret"),
    );
  });

  // The same fallback covers a row removed by a successful removal, which the
  // old guard left focus-less.
  it("falls back to the deck header button when the row is gone entirely", () => {
    document.body.innerHTML = `<div id="listMembers"></div><div id="confirmModal"></div><button type="button" id="MemberDeckHeaderAndCaret"></button>`;

    bindMemberRowModalFocusRestore(5);
    $("#confirmModal").trigger("hidden.bs.modal");

    expect(document.activeElement).toBe(
      document.getElementById("MemberDeckHeaderAndCaret"),
    );
  });

  it("a hidden co-owner kebab lands focus on its surviving row (tabindex=-1), not the header", () => {
    document.body.innerHTML = `<div id="listMembers"></div><div id="confirmModal"></div><button type="button" id="MemberDeckHeaderAndCaret"></button>`;
    const row = buildCoOwnerRow(5);
    $("#listMembers").append(row);
    // The CSS hide rule is display:none, so the kebab is not focusable; the row is.
    (row.find(".memberRowKebab").get(0) as HTMLElement).style.visibility =
      "hidden";

    bindMemberRowModalFocusRestore(5);
    $("#confirmModal").trigger("hidden.bs.modal");

    expect(document.activeElement).toBe(row.get(0));
    expect(row.attr("tabindex")).toBe("-1");
  });

  it("is one-shot: a second hidden.bs.modal does not move focus", () => {
    document.body.innerHTML = `<div id="listMembers"></div><div id="confirmModal"></div><button type="button" id="MemberDeckHeaderAndCaret"></button><button type="button" id="elsewhere"></button>`;
    const row = buildOwnerRow(5);
    $("#listMembers").append(row);

    bindMemberRowModalFocusRestore(5);
    $("#confirmModal").trigger("hidden.bs.modal");
    expect(document.activeElement).toBe(row.find(".memberRowKebab").get(0));

    document.getElementById("elsewhere")!.focus();
    $("#confirmModal").trigger("hidden.bs.modal");

    expect(document.activeElement).toBe(document.getElementById("elsewhere"));
  });

  it("disarmMemberRowModalFocusRestore drops a pending restore (Leave after a cancelled Remove)", () => {
    document.body.innerHTML = `<div id="listMembers"></div><div id="confirmModal"></div><button type="button" id="MemberDeckHeaderAndCaret"></button><button type="button" id="leaveBtn"></button>`;
    $("#listMembers").append(buildOwnerRow(5));

    bindMemberRowModalFocusRestore(5);
    disarmMemberRowModalFocusRestore();
    document.getElementById("leaveBtn")!.focus();
    $("#confirmModal").trigger("hidden.bs.modal");

    expect(document.activeElement).toBe(document.getElementById("leaveBtn"));
  });

  it("a co-owner's Remove closes the menu, arms the focus restore and requests the remove intent", () => {
    document.body.innerHTML = `<div id="listMembers"></div><div id="confirmModal"></div><button type="button" id="MemberDeckHeaderAndCaret"></button>`;
    const row = buildCoOwnerRow(5);
    $("#listMembers").append(row);
    row.find(".memberRowKebab").trigger("click");
    expect(row.find(".memberRowMenu").hasClass("open")).toBe(true);

    row.find(".memberRowMenuItem.danger").trigger("click");

    expect(row.find(".memberRowMenu").hasClass("open")).toBe(false);
    expect(vi.mocked(removeMemberShowModal)).toHaveBeenCalledWith({
      memberID: 5,
      utubID: 10,
      intent: "remove",
    });
    $("#confirmModal").trigger("hidden.bs.modal");
    expect(document.activeElement).toBe(row.find(".memberRowKebab").get(0));
  });

  it("ArrowUp from the first menu item wraps focus to the last item", () => {
    const row = buildOwnerRow(5);
    $("#listMembers").append(row);
    const kebab = row.find(".memberRowKebab");
    const menu = row.find(".memberRowMenu");

    // Opening lands focus on the first item (DD-15).
    kebab.trigger("click");
    const items = menu.find(".memberRowMenuItem");
    expect(document.activeElement).toBe(items.first().get(0));

    menu.trigger($.Event("keydown", { key: "ArrowUp" }));

    // ARROW_UP from index 0 wraps to items.length - 1 (the last item).
    expect(document.activeElement).toBe(items.last().get(0));
  });

  it("ArrowDown from the last menu item wraps focus back to the first item", () => {
    const row = buildOwnerRow(5);
    $("#listMembers").append(row);
    const kebab = row.find(".memberRowKebab");
    const menu = row.find(".memberRowMenu");

    kebab.trigger("click");
    const items = menu.find(".memberRowMenuItem");
    // Land focus on the last item first.
    (items.last().get(0) as HTMLElement).focus();
    expect(document.activeElement).toBe(items.last().get(0));

    menu.trigger($.Event("keydown", { key: "ArrowDown" }));

    // ARROW_DOWN from the last index wraps modulo items.length back to 0.
    expect(document.activeElement).toBe(items.first().get(0));
  });

  it("MEMBER_ADD_OPENED closes the open menu (DD-14/DD-6)", () => {
    const row = buildOwnerRow(5);
    $("#listMembers").append(row);
    const kebab = row.find(".memberRowKebab");
    const menu = row.find(".memberRowMenu");

    kebab.trigger("click");
    expect(menu.hasClass("open")).toBe(true);

    emit(AppEvents.MEMBER_ADD_OPENED);

    expect(menu.hasClass("open")).toBe(false);
    expect(kebab.attr("aria-expanded")).toBe("false");
  });

  describe("closeMemberRowMenuInRow", () => {
    it("closes the row's open menu and returns its kebab", () => {
      const row = buildOwnerRow(5);
      $("#listMembers").append(row);
      const kebab = row.find(".memberRowKebab");
      const menu = row.find(".memberRowMenu");
      kebab.trigger("click");
      expect(menu.hasClass("open")).toBe(true);

      const result = closeMemberRowMenuInRow({ row: row.get(0)! });

      expect(result?.get(0)).toBe(kebab.get(0));
      expect(menu.hasClass("open")).toBe(false);
      expect(menu.attr("hidden")).toBe("hidden");
      expect(kebab.attr("aria-expanded")).toBe("false");
    });

    it("returns null when the row has no open menu", () => {
      const row = buildOwnerRow(5);
      $("#listMembers").append(row);

      expect(closeMemberRowMenuInRow({ row: row.get(0)! })).toBeNull();
    });
  });
});
