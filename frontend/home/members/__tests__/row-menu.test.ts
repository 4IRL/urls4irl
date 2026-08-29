import { createMemberBadge } from "../members.js";
import { bindMemberRowModalFocusRestore } from "../row-menu.js";
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
    isCurrentUserOwner: true,
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

    expect(vi.mocked(removeMemberShowModal)).toHaveBeenCalledWith(5, true, 10);
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
});
