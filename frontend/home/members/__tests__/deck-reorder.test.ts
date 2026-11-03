import {
  reorderMemberDeck,
  setMemberDeckOnUTubSelected,
  updateMemberDeck,
} from "../deck.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { getState, resetStore, setState } from "../../../store/app-store.js";
import type { MemberItem } from "../../../types/member.js";
import type { MemberSortValue } from "../../../types/preferences.js";

const { CREATOR, CO_CREATOR, MEMBER } = APP_CONFIG.constants.MEMBER_ROLES;
const $ = window.jQuery;

function buildRowHTML({
  memberID,
  username,
}: {
  memberID: number;
  username: string;
}): string {
  return (
    `<span class="member" memberid="${memberID}"><b>${username}</b>` +
    `<span class="member-right">` +
    `<button type="button" class="memberRowKebab" aria-expanded="false"></button>` +
    `<button type="button" class="memberOtherBtnDelete"></button>` +
    `<div class="memberRowMenu" hidden><button type="button" class="memberRowMenuItem"></button></div>` +
    `</span></span>`
  );
}

vi.mock("../members.js", () => ({
  createMemberBadge: vi.fn(
    ({ memberID, username }: { memberID: number; username: string }) =>
      window.jQuery(buildRowHTML({ memberID, username })),
  ),
  createOwnerBadge: vi.fn((memberID: number, username: string) =>
    window.jQuery(buildRowHTML({ memberID, username })),
  ),
  swapMemberRoleInRow: vi.fn(),
}));
vi.mock("../create.js", () => ({
  setupShowCreateMemberFormEventListeners: vi.fn(),
}));
vi.mock("../delete.js", () => ({
  createLeaveUTubAsMemberIcon: vi.fn(),
  removeMemberShowModal: vi.fn(),
}));

const DECK_HTML = `
  <div id="MemberDeck">
    <button type="button" id="MemberDeckHeaderAndCaret"></button>
    <span id="MemberDeckCount"></span>
    <button id="memberNameFilterBtn" class="hidden"></button>
    <button id="memberNameFilterBtnClose" class="hidden"></button>
    <button id="memberBtnCreate" class="hidden"></button>
    <input id="MemberNameSearch" type="search" value="" />
    <p id="MemberSearchNoResults" class="hidden"></p>
    <span id="MemberSearchAnnouncement"></span>
    <span id="MemberRowActionAnnouncement" aria-live="polite"></span>
    <button id="outsideButton" type="button"></button>
    <div id="displayMemberWrap">
      <div id="UTubOwner"></div>
      <div id="listMembers"></div>
    </div>
  </div>
`;

const OWNER: MemberItem = {
  id: 1,
  username: "owner",
  memberRole: CREATOR,
  joinedAt: null,
};

function member({
  id,
  username,
  memberRole = MEMBER,
  joinedAt = null,
}: {
  id: number;
  username: string;
  memberRole?: string;
  joinedAt?: string | null;
}): MemberItem {
  return { id, username, memberRole, joinedAt };
}

// Paints the rows in the given (possibly wrong) order, the way an in-place
// append or role swap leaves the deck before a reorder.
function paintRows(usernamesInOrder: MemberItem[]): void {
  $("#UTubOwner").append(
    buildRowHTML({ memberID: OWNER.id, username: OWNER.username }),
  );
  usernamesInOrder.forEach((entry) => {
    $("#listMembers").append(
      buildRowHTML({ memberID: entry.id, username: entry.username }),
    );
  });
}

function listedIDs(): number[] {
  return $("#listMembers > .member")
    .toArray()
    .map((row) => Number(row.getAttribute("memberid")));
}

function rowOf(memberID: number): HTMLElement {
  return $(`.member[memberid="${memberID}"]`)[0];
}

function setSort(memberSort: MemberSortValue): void {
  setState({ preferences: { ...getState().preferences, memberSort } });
}

// Tests assign HTMLElement.prototype.scrollIntoView spies; restore it so they
// never leak into other tests in this file.
const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;
afterEach(() => {
  HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
});

describe("reorderMemberDeck", () => {
  const amy = member({ id: 2, username: "amy" });
  const bob = member({ id: 3, username: "bob" });
  const cat = member({ id: 4, username: "cat" });

  beforeEach(() => {
    document.body.innerHTML = DECK_HTML;
    resetStore();
  });

  it("moves rows into sort order and returns the moved ids", () => {
    paintRows([cat, amy, bob]);

    const moved = reorderMemberDeck({
      members: [OWNER, amy, bob, cat],
      memberSort: "name_az",
    });

    expect(listedIDs()).toEqual([2, 3, 4]);
    expect(moved.sort()).toEqual([2, 3, 4]);
  });

  it("is a no-op that touches no DOM and returns no ids when already ordered", () => {
    paintRows([amy, bob, cat]);
    const before = rowOf(3);
    const observer = new MutationObserver(() => {});
    observer.observe($("#listMembers")[0], { childList: true });

    const moved = reorderMemberDeck({
      members: [OWNER, amy, bob, cat],
      memberSort: "name_az",
    });

    expect(moved).toEqual([]);
    expect(observer.takeRecords()).toEqual([]);
    expect(rowOf(3)).toBe(before);
    expect(listedIDs()).toEqual([2, 3, 4]);
  });

  it("never writes to the store", () => {
    paintRows([cat, amy]);
    const membersBefore = getState().members;

    reorderMemberDeck({ members: [OWNER, amy, cat], memberSort: "name_az" });

    expect(getState().members).toBe(membersBefore);
  });

  it("keeps the owner in #UTubOwner and never moves it into the list", () => {
    paintRows([cat, amy]);

    reorderMemberDeck({
      members: [OWNER, amy, cat],
      memberSort: "recently_joined",
    });

    expect($("#UTubOwner > .member").attr("memberid")).toBe("1");
    expect(listedIDs()).not.toContain(1);
  });

  it("orders by role under role_then_name and by recency under recently_joined", () => {
    const coOwner = member({ id: 5, username: "zed", memberRole: CO_CREATOR });
    const older = member({
      id: 2,
      username: "amy",
      joinedAt: "2026-01-01T00:00:00.000Z",
    });
    const newer = member({
      id: 3,
      username: "bob",
      joinedAt: "2026-02-01T00:00:00.000Z",
    });
    paintRows([older, newer, coOwner]);

    reorderMemberDeck({
      members: [OWNER, older, newer, coOwner],
      memberSort: "role_then_name",
    });
    expect(listedIDs()).toEqual([5, 2, 3]);

    reorderMemberDeck({
      members: [OWNER, older, newer, coOwner],
      memberSort: "recently_joined",
    });
    expect(listedIDs()).toEqual([3, 2, 5]);
  });

  it("keeps each row node, its handlers and its attributes", () => {
    paintRows([cat, amy, bob]);
    const clicked = vi.fn();
    $(rowOf(4)).on("click", clicked);
    rowOf(4).setAttribute("data-staged-suppressed", "true");
    const catRow = rowOf(4);

    reorderMemberDeck({
      members: [OWNER, amy, bob, cat],
      memberSort: "name_az",
    });

    expect(rowOf(4)).toBe(catRow);
    expect(catRow.getAttribute("data-staged-suppressed")).toBe("true");
    $(catRow).trigger("click");
    expect(clicked).toHaveBeenCalledTimes(1);
  });

  it("restripes the visible rows after a reorder and keeps a filter-hidden row hidden", () => {
    paintRows([amy, bob, cat]);
    rowOf(3).classList.add("hidden");
    const newest = member({
      id: 2,
      username: "amy",
      joinedAt: "2026-01-01T00:00:00.000Z",
    });
    const newer = member({
      id: 4,
      username: "cat",
      joinedAt: "2026-03-01T00:00:00.000Z",
    });

    reorderMemberDeck({
      members: [OWNER, newest, bob, newer],
      memberSort: "recently_joined",
    });

    expect(listedIDs()).toEqual([4, 2, 3]);
    expect(rowOf(3).classList.contains("hidden")).toBe(true);
    // Owner takes parity 0; the visible rows are cat (1: striped) then amy (2).
    expect(rowOf(4).classList.contains("member-stripe")).toBe(true);
    expect(rowOf(2).classList.contains("member-stripe")).toBe(false);
  });

  it("keeps the staged-add sibling suppression on the delete buttons across a reorder", () => {
    paintRows([cat, amy, bob]);
    $("#MemberDeck").addClass("member-add-open");
    $(".memberOtherBtnDelete")
      .prop("disabled", true)
      .attr("aria-disabled", "true");

    reorderMemberDeck({
      members: [OWNER, amy, bob, cat],
      memberSort: "name_az",
    });

    expect(listedIDs()).toEqual([2, 3, 4]);
    expect($("#MemberDeck").hasClass("member-add-open")).toBe(true);
    $(".memberOtherBtnDelete").each((_index, button) => {
      expect((button as HTMLButtonElement).disabled).toBe(true);
      expect(button.getAttribute("aria-disabled")).toBe("true");
    });
  });

  describe("focus", () => {
    it("keeps a focused resting kebab in an unmoved row while a moved row's open menu closes", () => {
      // bob and amy swap; cat is unmoved at the end.
      paintRows([bob, amy, cat]);
      const menu = $(rowOf(3)).find(".memberRowMenu");
      menu.addClass("open").removeAttr("hidden");
      const catKebab = $(rowOf(4)).find(".memberRowKebab")[0];
      catKebab.focus();

      reorderMemberDeck({
        members: [OWNER, amy, bob, cat],
        memberSort: "name_az",
      });

      expect(menu.hasClass("open")).toBe(false);
      expect(document.activeElement).toBe(catKebab);
    });

    it("keeps focus on a moved row's kebab with no open menu while another moved row's menu closes", () => {
      paintRows([bob, amy, cat]);
      const amyMenu = $(rowOf(2)).find(".memberRowMenu");
      amyMenu.addClass("open").removeAttr("hidden");
      const bobKebab = $(rowOf(3)).find(".memberRowKebab")[0];
      bobKebab.focus();

      reorderMemberDeck({
        members: [OWNER, amy, bob, cat],
        memberSort: "name_az",
      });

      expect(amyMenu.hasClass("open")).toBe(false);
      expect(document.activeElement).toBe(bobKebab);
    });

    it("refocuses a kebab inside a moved row without scrolling", () => {
      paintRows([cat, amy]);
      const kebab = $(rowOf(4)).find(".memberRowKebab")[0];
      kebab.focus();

      reorderMemberDeck({ members: [OWNER, amy, cat], memberSort: "name_az" });

      expect(document.activeElement).toBe(kebab);
    });

    it("keeps focus on a kebab in an unmoved row", () => {
      // amy and bob swap; cat stays at the end.
      paintRows([bob, amy, cat]);
      const kebab = $(rowOf(4)).find(".memberRowKebab")[0];
      kebab.focus();

      reorderMemberDeck({
        members: [OWNER, amy, bob, cat],
        memberSort: "name_az",
      });

      expect(listedIDs()).toEqual([2, 3, 4]);
      expect(document.activeElement).toBe(kebab);
    });

    it("never moves focus that is outside #listMembers", () => {
      paintRows([cat, amy]);
      const outside = $("#outsideButton")[0];
      outside.focus();

      reorderMemberDeck({ members: [OWNER, amy, cat], memberSort: "name_az" });

      expect(document.activeElement).toBe(outside);
    });

    it("leaves an open menu and focus alone when no row moves", () => {
      paintRows([amy, bob]);
      const menu = $(rowOf(2)).find(".memberRowMenu");
      menu.addClass("open").removeAttr("hidden");
      const item = menu.find(".memberRowMenuItem")[0];
      item.focus();

      const moved = reorderMemberDeck({
        members: [OWNER, amy, bob],
        memberSort: "name_az",
      });

      expect(moved).toEqual([]);
      expect(menu.hasClass("open")).toBe(true);
      expect(document.activeElement).toBe(item);
    });
  });

  describe("open row menus", () => {
    it("closes the menu of a moved row and refocuses its kebab", () => {
      paintRows([cat, amy]);
      const menu = $(rowOf(4)).find(".memberRowMenu");
      const kebab = $(rowOf(4)).find(".memberRowKebab");
      menu.addClass("open").removeAttr("hidden");
      kebab.attr("aria-expanded", "true");
      menu.find(".memberRowMenuItem")[0].focus();

      reorderMemberDeck({ members: [OWNER, amy, cat], memberSort: "name_az" });

      expect(menu.hasClass("open")).toBe(false);
      expect(menu.attr("hidden")).toBeDefined();
      expect(kebab.attr("aria-expanded")).toBe("false");
      expect(document.activeElement).toBe(kebab[0]);
    });

    it("keeps the menu of an unmoved row open when another row moves", () => {
      // amy and bob swap; cat is untouched at the end.
      paintRows([bob, amy, cat]);
      const menu = $(rowOf(4)).find(".memberRowMenu");
      menu.addClass("open").removeAttr("hidden");

      reorderMemberDeck({
        members: [OWNER, amy, bob, cat],
        memberSort: "name_az",
      });

      expect(listedIDs()).toEqual([2, 3, 4]);
      expect(menu.hasClass("open")).toBe(true);
    });
  });
});

describe("updateMemberDeck reorder (stale refresh)", () => {
  const amy = member({ id: 2, username: "amy" });
  const cat = member({ id: 4, username: "cat" });
  const bob = member({ id: 3, username: "bob" });

  beforeEach(() => {
    document.body.innerHTML = DECK_HTML;
    resetStore();
  });

  it("places an added member using the incoming members, not the pre-update store", () => {
    paintRows([amy, cat]);
    setState({ members: [OWNER, amy, cat] });

    updateMemberDeck([OWNER, amy, bob, cat], true, 42);

    expect(listedIDs()).toEqual([2, 3, 4]);
  });

  it("lands an added member on top under recently_joined", () => {
    const old = member({
      id: 2,
      username: "amy",
      joinedAt: "2026-01-01T00:00:00.000Z",
    });
    const added = member({
      id: 3,
      username: "bob",
      joinedAt: "2026-03-01T00:00:00.000Z",
    });
    paintRows([old]);
    setState({ members: [OWNER, old] });
    setSort("recently_joined");

    updateMemberDeck([OWNER, old, added], true, 42);

    expect(listedIDs()).toEqual([3, 2]);
  });

  it("keepMemberSort: follows the store's resolved sort, so a kept local sort wins over the payload", () => {
    const coOwner = member({ id: 3, username: "zed", memberRole: CO_CREATOR });
    paintRows([amy, cat]);
    setState({ members: [OWNER, amy, cat] });
    // The store holds the kept local edit; the payload's sort is irrelevant here.
    setSort("role_then_name");

    updateMemberDeck([OWNER, amy, cat, coOwner], true, 42);

    expect(listedIDs()).toEqual([3, 2, 4]);
  });

  it("keeps a filter-hidden row hidden and restripes the visible rows after an add under recently_joined", () => {
    const amyJoined = member({
      id: 2,
      username: "ben",
      joinedAt: "2026-01-01T00:00:00.000Z",
    });
    const bobJoined = member({
      id: 3,
      username: "bob",
      joinedAt: "2026-02-01T00:00:00.000Z",
    });
    const abe = member({
      id: 5,
      username: "abe",
      joinedAt: "2026-03-01T00:00:00.000Z",
    });
    paintRows([amyJoined, bobJoined]);
    setState({ members: [OWNER, amyJoined, bobJoined] });
    setSort("recently_joined");
    // "e" matches the owner, ben and abe (the owner row counts for striping);
    // bob is filtered out.
    $("#MemberNameSearch").val("e");

    updateMemberDeck([OWNER, amyJoined, bobJoined, abe], true, 42);

    expect(listedIDs()).toEqual([5, 3, 2]);
    expect(rowOf(3).classList.contains("hidden")).toBe(true);
    // Owner takes parity 0; the visible rows are abe (1: striped) then ben (2).
    expect(rowOf(5).classList.contains("member-stripe")).toBe(true);
    expect(rowOf(2).classList.contains("member-stripe")).toBe(false);
  });

  describe("adds land in sort order and never scroll", () => {
    const first = member({
      id: 2,
      username: "amy",
      joinedAt: "2026-01-01T00:00:00.000Z",
    });
    const second = member({
      id: 4,
      username: "cat",
      joinedAt: "2026-01-02T00:00:00.000Z",
    });
    const added = member({
      id: 3,
      username: "bob",
      joinedAt: "2026-03-01T00:00:00.000Z",
    });
    const addedCoOwner = member({
      id: 5,
      username: "zed",
      memberRole: CO_CREATOR,
      joinedAt: "2026-04-01T00:00:00.000Z",
    });

    it.each([
      ["name_az", [2, 3, 4], [2, 3, 4, 5]],
      ["role_then_name", [2, 3, 4], [5, 2, 3, 4]],
      ["recently_joined", [3, 4, 2], [5, 3, 4, 2]],
    ] as const)(
      "%s: single add and batch of two",
      (memberSort, singleOrder, batchOrder) => {
        const scrollSpy = vi.fn();
        HTMLElement.prototype.scrollIntoView = scrollSpy;
        paintRows([first, second]);
        setState({ members: [OWNER, first, second] });
        setSort(memberSort);

        updateMemberDeck([OWNER, first, second, added], true, 42);
        expect(listedIDs()).toEqual(singleOrder);
        expect(scrollSpy).not.toHaveBeenCalled();

        // Rebuild the baseline, then add both members in one payload.
        document.body.innerHTML = DECK_HTML;
        paintRows([first, second]);
        setState({ members: [OWNER, first, second] });

        updateMemberDeck([OWNER, first, second, added, addedCoOwner], true, 42);
        expect(listedIDs()).toEqual(batchOrder);
        expect(scrollSpy).not.toHaveBeenCalled();
      },
    );
  });

  it("reorders a role flip silently: no scroll and no announcement", () => {
    const scrollSpy = vi.fn();
    HTMLElement.prototype.scrollIntoView = scrollSpy;
    paintRows([amy, bob, cat]);
    setState({ members: [OWNER, amy, bob, cat] });
    setSort("role_then_name");
    const flipped = member({ id: 4, username: "cat", memberRole: CO_CREATOR });

    updateMemberDeck([OWNER, amy, bob, flipped], true, 42);

    expect(listedIDs()).toEqual([4, 2, 3]);
    expect(scrollSpy).not.toHaveBeenCalled();
    expect($("#MemberRowActionAnnouncement").text()).toBe("");
  });
});

describe("setMemberDeckOnUTubSelected sorting", () => {
  beforeEach(() => {
    document.body.innerHTML = DECK_HTML;
    resetStore();
  });

  it("paints in the store's sort", () => {
    const amy = member({ id: 2, username: "amy" });
    const zed = member({ id: 3, username: "zed", memberRole: CO_CREATOR });
    setSort("role_then_name");

    setMemberDeckOnUTubSelected([OWNER, amy, zed], 1, true, 1, 42);

    expect(listedIDs()).toEqual([3, 2]);
  });

  it("follows the store sort when a kept local value differs from the payload's", () => {
    const old = member({
      id: 2,
      username: "amy",
      joinedAt: "2026-01-01T00:00:00.000Z",
    });
    const fresh = member({
      id: 3,
      username: "bob",
      joinedAt: "2026-02-01T00:00:00.000Z",
    });
    // buildSelectedUTub wrote the kept local sort; the UTUB_SELECTED payload
    // carries no sort of its own.
    setSort("recently_joined");

    setMemberDeckOnUTubSelected([OWNER, old, fresh], 1, true, 1, 42);

    expect(listedIDs()).toEqual([3, 2]);
  });

  it("rebuilds a transferred UTub in sort order with the new owner in #UTubOwner", () => {
    const scrollSpy = vi.fn();
    HTMLElement.prototype.scrollIntoView = scrollSpy;
    const formerOwner = member({
      id: 1,
      username: "owner",
      memberRole: CO_CREATOR,
    });
    const newOwner = member({ id: 3, username: "bob", memberRole: CREATOR });
    const amy = member({ id: 2, username: "amy" });
    setSort("name_az");

    setMemberDeckOnUTubSelected([formerOwner, amy, newOwner], 3, false, 1, 42);

    expect($("#UTubOwner > .member").attr("memberid")).toBe("3");
    expect(listedIDs()).toEqual([2, 1]);
    expect(scrollSpy).not.toHaveBeenCalled();
    expect($("#MemberRowActionAnnouncement").text()).toBe("");
  });
});
