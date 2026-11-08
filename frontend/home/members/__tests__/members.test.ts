import {
  createMockJqXHRChainable,
  createMockXhr,
} from "../../../__tests__/helpers/mock-jquery.js";
import {
  createOwnerBadge,
  createMemberBadge,
  swapMemberRoleInRow,
} from "../members.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { removeMemberShowModal } from "../delete.js";
import { createMemberHideInput } from "../create.js";
import { updateMemberDeck } from "../deck.js";
import { ajaxCall, is429Handled } from "../../../lib/ajax.js";
import { applyDeckDiff } from "../../../logic/apply-deck-diff.js";
import { getState } from "../../../store/app-store.js";
import { getNumOfUTubs } from "../../utubs/utils.js";
import {
  hideInputsAndUpdateUTubDeck,
  resetUTubDeckIfNoUTubs,
} from "../../utubs/deck.js";
import { bootstrap } from "../../../lib/globals.js";

// The ambient test-setup Bootstrap mock returns null from getInstance(), which
// would make the tooltip-hide guard a silent no-op. Override lib/globals.js with
// a shared tooltip instance so the guard can be asserted on.
const { tooltipInstance, globalsMock } = await vi.hoisted(async () => {
  const { mockGlobalsWithTooltipInstance } =
    await import("../../../__tests__/helpers/mock-globals.js");
  return await mockGlobalsWithTooltipInstance();
});

vi.mock("../../../lib/globals.js", () => globalsMock);

vi.mock("../../btns-forms.js", () => ({ hideInputs: vi.fn() }));
vi.mock("../../urls/cards/selection.js", () => ({ deselectAllURLs: vi.fn() }));
vi.mock("../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));
vi.mock("../../../logic/apply-deck-diff.js", () => ({
  applyDeckDiff: vi.fn(),
}));
vi.mock("../../../store/app-store.js", () => ({
  getState: vi.fn(() => ({ members: [], isCurrentUserOwner: true })),
  setState: vi.fn(),
}));
vi.mock("../../utubs/utils.js", () => ({ getNumOfUTubs: vi.fn(() => 1) }));
vi.mock("../../utubs/deck.js", () => ({
  resetUTubDeckIfNoUTubs: vi.fn(),
  hideInputsAndUpdateUTubDeck: vi.fn(),
}));
vi.mock("../../init.js", () => ({ setUIWhenNoUTubSelected: vi.fn() }));

const $ = window.jQuery;

describe("createOwnerBadge", () => {
  it("returns a span element", () => {
    const el = createOwnerBadge(1, "Alice");
    expect(el.tagName.toLowerCase()).toBe("span");
  });

  it("sets memberid attribute to the owner user ID", () => {
    const el = createOwnerBadge(99, "Alice");
    expect($(el).attr("memberid")).toBe("99");
  });

  it("has member, full-width, flex-row, jc-sb, align-center classes", () => {
    const $el = $(createOwnerBadge(1, "Alice"));
    expect($el.hasClass("member")).toBe(true);
    expect($el.hasClass("full-width")).toBe(true);
    expect($el.hasClass("flex-row")).toBe(true);
    expect($el.hasClass("jc-sb")).toBe(true);
    expect($el.hasClass("align-center")).toBe(true);
  });

  it("renders the username inside a bold element", () => {
    const el = createOwnerBadge(1, "Alice");
    expect($(el).find("b").text()).toBe("Alice");
  });

  it("renders the owner diamond marker icon", () => {
    const $el = $(createOwnerBadge(1, "Alice"));
    expect($el.find("svg.bi-diamond-fill.memberRole").length).toBe(1);
  });

  it("sets the username via .text() so adversarial markup is never parsed (XSS regression)", () => {
    // A regression to `.html("<b>" + username + "</b>")` would render identically
    // for benign names but parse this payload into a live <img>. Set via .text()
    // (a text node), the raw string is the <b> textContent and nothing is parsed.
    const payload = '<img src=x onerror="alert(1)">';
    const $el = $(createOwnerBadge(1, payload));
    expect($el.find("b").text()).toBe(payload);
    expect($el.find("img").length).toBe(0);
  });

  it("renders a visually-hidden 'Owner' role label alongside the icon", () => {
    const $el = $(createOwnerBadge(1, "Alice"));
    expect($el.find(".member-role-wrap .visually-hidden").text()).toBe("Owner");
  });
});

describe("createMemberBadge", () => {
  beforeEach(() => vi.clearAllMocks());

  describe("element structure", () => {
    it("sets memberid attribute to the member user ID", () => {
      const el = createMemberBadge({
        memberID: 42,
        username: "Bob",
        memberRole: "member",
        viewerRole: "member",
        utubID: 10,
      });
      expect(el.attr("memberid")).toBe("42");
    });

    it("has member, full-width, flex-row, jc-sb, align-center, flex-start classes", () => {
      const el = createMemberBadge({
        memberID: 1,
        username: "Bob",
        memberRole: "member",
        viewerRole: "member",
        utubID: 10,
      });
      expect(el.hasClass("member")).toBe(true);
      expect(el.hasClass("full-width")).toBe(true);
      expect(el.hasClass("flex-row")).toBe(true);
      expect(el.hasClass("jc-sb")).toBe(true);
      expect(el.hasClass("align-center")).toBe(true);
      expect(el.hasClass("flex-start")).toBe(true);
    });

    it("renders the username inside a bold element", () => {
      const el = createMemberBadge({
        memberID: 1,
        username: "Bob",
        memberRole: "member",
        viewerRole: "member",
        utubID: 10,
      });
      expect(el.find("b").text()).toBe("Bob");
    });

    it("sets the username via .text() so adversarial markup is never parsed (XSS regression)", () => {
      // A regression to `.html("<b>" + username + "</b>")` would render identically
      // for benign names but parse this payload into a live <img>. Set via .text()
      // (a text node), the raw string is the <b> textContent and nothing is parsed.
      const payload = '<img src=x onerror="alert(1)">';
      const el = createMemberBadge({
        memberID: 1,
        username: payload,
        memberRole: "member",
        viewerRole: "member",
        utubID: 10,
      });
      expect(el.find("b").text()).toBe(payload);
      expect(el.find("img").length).toBe(0);
    });

    it("sets the kebab aria-label via .attr() so a double-quote cannot break out (XSS regression)", () => {
      // A regression to interpolating the username into the aria-label's HTML
      // string would let this double-quote close the attribute and inject markup.
      // Set via .attr() + .replace(), the label is the literal resolved string and
      // the username never reaches HTML parsing (so no injected <img> appears).
      const payload = 'Bob" onmouseover="x';
      const el = createMemberBadge({
        memberID: 5,
        username: payload,
        memberRole: "member",
        viewerRole: "owner",
        utubID: 10,
      });
      expect(el.find(".memberRowKebab").attr("aria-label")).toBe(
        `Actions for ${payload}`,
      );
      expect(el.find("img").length).toBe(0);
    });
  });

  describe("per-row role icon (DD-2/DD-10/DD-18)", () => {
    it("renders the co-creator diamond-half icon + 'Co-owner' label", () => {
      const el = createMemberBadge({
        memberID: 3,
        username: "Bob",
        memberRole: "cocreator",
        viewerRole: "member",
        utubID: 10,
      });
      expect(el.find("svg.bi-diamond-half.memberRole").length).toBe(1);
      expect(el.find(".member-role-wrap .visually-hidden").text()).toBe(
        "Co-owner",
      );
    });

    it("renders the creator diamond-fill icon + 'Owner' label", () => {
      const el = createMemberBadge({
        memberID: 3,
        username: "Bob",
        memberRole: "creator",
        viewerRole: "member",
        utubID: 10,
      });
      expect(el.find("svg.bi-diamond-fill.memberRole").length).toBe(1);
      expect(el.find(".member-role-wrap .visually-hidden").text()).toBe(
        "Owner",
      );
    });

    it("renders the plain-member people-fill icon + 'Member' label", () => {
      const el = createMemberBadge({
        memberID: 3,
        username: "Bob",
        memberRole: "member",
        viewerRole: "member",
        utubID: 10,
      });
      expect(el.find("svg.bi-people-fill.memberRole").length).toBe(1);
      expect(el.find(".member-role-wrap .visually-hidden").text()).toBe(
        "Member",
      );
    });
  });

  describe("when the current user is the UTub owner (isCurrentUserOwner=true)", () => {
    it("renders exactly one kebab (overflow) menu trigger", () => {
      const el = createMemberBadge({
        memberID: 5,
        username: "Bob",
        memberRole: "member",
        viewerRole: "owner",
        utubID: 10,
      });
      expect(el.find(".memberRowKebab").length).toBe(1);
    });

    it("folds the remove action into the menu and renders no bare remove button", () => {
      const el = createMemberBadge({
        memberID: 5,
        username: "Bob",
        memberRole: "member",
        viewerRole: "owner",
        utubID: 10,
      });
      // The standalone remove button is folded into the kebab menu.
      expect(el.find(".memberOtherBtnDelete").length).toBe(0);
      const removeItem = el.find(".memberRowMenu .memberRowMenuItem.danger");
      expect(removeItem.length).toBe(1);
      // The item text is sourced from the string bridge, not hardcoded.
      expect(removeItem.find("span").text()).toBe("Remove member");
    });

    it("builds the kebab aria-label from the bridged {{ username }} template", () => {
      const el = createMemberBadge({
        memberID: 5,
        username: "Bob",
        memberRole: "member",
        viewerRole: "owner",
        utubID: 10,
      });
      // MEMBER_ROW_ACTIONS_ARIA_LABEL ("Actions for {{ username }}") is resolved
      // client-side via .replace(), so the row's username lands in the label.
      expect(el.find(".memberRowKebab").attr("aria-label")).toBe(
        "Actions for Bob",
      );
    });

    it('labels the role item "Make co-owner" for a plain member', () => {
      const el = createMemberBadge({
        memberID: 5,
        username: "Bob",
        memberRole: "member",
        viewerRole: "owner",
        utubID: 10,
      });
      const roleItem = el.find(".memberRowMenuItemRole");
      expect(roleItem.length).toBe(1);
      expect(roleItem.find("span").text()).toBe("Make co-owner");
      expect(roleItem.attr("aria-label")).toBe("Make co-owner");
    });

    it('labels the role item "Revoke co-owner" for an existing co-owner', () => {
      const el = createMemberBadge({
        memberID: 6,
        username: "Cara",
        memberRole: "cocreator",
        viewerRole: "owner",
        utubID: 10,
      });
      const roleItem = el.find(".memberRowMenuItemRole");
      expect(roleItem.find("span").text()).toBe("Revoke co-owner");
      expect(roleItem.attr("aria-label")).toBe("Revoke co-owner");
    });
  });

  describe("when the current user is a member (isCurrentUserOwner=false)", () => {
    it("does not render a kebab menu trigger", () => {
      const el = createMemberBadge({
        memberID: 5,
        username: "Bob",
        memberRole: "member",
        viewerRole: "member",
        utubID: 10,
      });
      expect(el.find(".memberRowKebab").length).toBe(0);
    });

    it("does not render a row menu", () => {
      const el = createMemberBadge({
        memberID: 5,
        username: "Bob",
        memberRole: "member",
        viewerRole: "member",
        utubID: 10,
      });
      expect(el.find(".memberRowMenu").length).toBe(0);
    });
  });
});

describe("createMemberBadge - co-owner viewer", () => {
  const MEMBER_ROLE = "member";
  const CO_OWNER_ROLE = "cocreator";

  function coOwnerRow({
    memberRole,
    memberID = 5,
  }: {
    memberRole: string;
    memberID?: number;
  }) {
    return createMemberBadge({
      memberID,
      username: "Bob",
      memberRole,
      viewerRole: "co_owner",
      utubID: 10,
    });
  }

  beforeEach(() => {
    vi.clearAllMocks();
    document.body.innerHTML = REMOVE_MODAL_HTML;
    ($.fn as unknown as Record<string, unknown>).modal = function (
      this: JQuery,
    ) {
      return this;
    };
  });

  it("renders one co-owner kebab on a plain-member row, sharing the owner kebab's base class", () => {
    const el = coOwnerRow({ memberRole: MEMBER_ROLE });
    const kebab = el.find(".memberRowKebab");
    expect(kebab.length).toBe(1);
    expect(kebab.hasClass("memberRowKebab--coOwner")).toBe(true);
    expect(kebab.attr("aria-label")).toBe("Actions for Bob");
  });

  it("builds a menu with exactly one item, Remove member: no role item, no divider", () => {
    const el = coOwnerRow({ memberRole: MEMBER_ROLE });
    const items = el.find(".memberRowMenu .memberRowMenuItem");
    expect(items.length).toBe(1);
    expect(items.hasClass("danger")).toBe(true);
    expect(items.find("span").text()).toBe("Remove member");
    expect(el.find(".memberRowMenuItemRole").length).toBe(0);
    expect(el.find(".memberRowMenuDivider").length).toBe(0);
  });

  it("gives no kebab to another co-owner's row", () => {
    const el = coOwnerRow({ memberRole: CO_OWNER_ROLE });
    expect(el.find(".memberRowKebab").length).toBe(0);
    expect(el.find(".memberRowMenu").length).toBe(0);
  });

  it("gives no kebab to a row with an unknown role (fail closed)", () => {
    for (const memberRole of ["", "admin", "creator", "MEMBER"]) {
      const el = coOwnerRow({ memberRole });
      expect(el.find(".memberRowKebab").length).toBe(0);
    }
  });

  it("keeps the owner's full menu unchanged: role item, divider and Remove", () => {
    const el = createMemberBadge({
      memberID: 5,
      username: "Bob",
      memberRole: MEMBER_ROLE,
      viewerRole: "owner",
      utubID: 10,
    });
    expect(el.find(".memberRowKebab").hasClass("memberRowKebab--coOwner")).toBe(
      false,
    );
    expect(el.find(".memberRowMenuItemRole").length).toBe(1);
    expect(el.find(".memberRowMenuDivider").length).toBe(1);
    expect(el.find(".memberRowMenuItem.danger").length).toBe(1);
  });

  it("a plain-member viewer never gets a kebab", () => {
    const el = createMemberBadge({
      memberID: 5,
      username: "Bob",
      memberRole: MEMBER_ROLE,
      viewerRole: "member",
      utubID: 10,
    });
    expect(el.find(".memberRowKebab").length).toBe(0);
  });

  it("uses the shared kebab classes only: no size override class beyond --coOwner", () => {
    const el = coOwnerRow({ memberRole: MEMBER_ROLE });
    expect(Array.from(el.find(".memberRowKebab")[0].classList).sort()).toEqual([
      "align-center",
      "flex-row",
      "memberRowKebab",
      "memberRowKebab--coOwner",
    ]);
  });

  it("confirming a co-owner's Remove uses the remove copy, removes the row and keeps the viewer in the UTub", () => {
    vi.mocked(getState).mockReturnValue({
      members: [{ id: 5 }],
      utubs: [],
      urls: [],
      isCurrentUserOwner: false,
      isCoCreator: true,
      activeUTubID: 10,
      settings: null,
    } as unknown as ReturnType<typeof getState>);
    ($.fn as unknown as Record<string, unknown>).fadeOut = function (
      this: JQuery,
      _duration: unknown,
      callback?: () => void,
    ) {
      if (typeof callback === "function") callback();
      return this;
    };
    document.body.insertAdjacentHTML(
      "beforeend",
      `<div id="listMembers"></div><button id="memberBtnCreate" class="hidden"></button>`,
    );
    $("#listMembers").append(coOwnerRow({ memberRole: MEMBER_ROLE }));
    vi.mocked(ajaxCall).mockReturnValue(
      createMockJqXHRChainable({
        done: (cb: unknown) => {
          (
            cb as (
              _response: unknown,
              _textStatus: unknown,
              xhr: JQuery.jqXHR,
            ) => void
          )({}, "success", createMockXhr({ status: 200 }));
        },
      }),
    );

    $(".memberRowMenuItem.danger").trigger("click");
    expect($("#confirmModalTitle").text()).toBe(
      "Are you sure you want to remove this member from the UTub?",
    );
    expect($("#modalSubmit").text()).toBe("Remove member");
    $("#modalSubmit").trigger("click");

    expect(ajaxCall).toHaveBeenCalledWith(
      "delete",
      APP_CONFIG.routes.removeMember(10, 5),
      [],
    );
    expect($('.member[memberid="5"]').length).toBe(0);
    expect(vi.mocked(hideInputsAndUpdateUTubDeck)).not.toHaveBeenCalled();
    // The co-owner keeps the add button: it matches canAddMembers for the viewer.
    expect($("#memberBtnCreate").hasClass("hidden")).toBe(false);
  });
});

describe("swapMemberRoleInRow - co-owner viewer kebab sync", () => {
  function seedRow({ memberRole }: { memberRole: string }): void {
    document.body.innerHTML = `<div id="listMembers"></div>`;
    $("#listMembers").append(
      createMemberBadge({
        memberID: 5,
        username: "Bob",
        memberRole,
        viewerRole: "co_owner",
        utubID: 10,
      }),
    );
  }

  function viewerState(patch: Record<string, unknown>) {
    vi.mocked(getState).mockReturnValue({
      members: [],
      activeUTubID: 10,
      isCurrentUserOwner: false,
      isCoCreator: true,
      ...patch,
    } as unknown as ReturnType<typeof getState>);
  }

  it("removes the co-owner kebab when the row is promoted to co-owner", () => {
    viewerState({});
    seedRow({ memberRole: "member" });
    expect($(".member[memberid=5] .memberRowKebab--coOwner").length).toBe(1);

    swapMemberRoleInRow({ memberID: 5, targetRole: "cocreator" });

    expect($(".member[memberid=5] .memberRowKebab").length).toBe(0);
    expect($(".member[memberid=5] .memberRowMenu").length).toBe(0);
  });

  describe("focus on promotion", () => {
    beforeEach(() => {
      // jsdom has no layout: model connected elements as visible.
      Object.defineProperty(HTMLElement.prototype, "offsetParent", {
        configurable: true,
        get() {
          return this.isConnected ? document.body : null;
        },
      });
    });

    afterEach(() => {
      delete (HTMLElement.prototype as unknown as Record<string, unknown>)
        .offsetParent;
    });

    it("moves focus from the removed kebab to the row, never body", () => {
      viewerState({});
      seedRow({ memberRole: "member" });
      (
        $(".member[memberid=5] .memberRowKebab--coOwner")[0] as HTMLElement
      ).focus();

      swapMemberRoleInRow({ memberID: 5, targetRole: "cocreator" });

      expect(document.activeElement).not.toBe(document.body);
      expect(document.activeElement).toBe($(".member[memberid=5]")[0]);
    });

    it("moves focus from a removed open-menu item to the row, never body", () => {
      viewerState({});
      seedRow({ memberRole: "member" });
      ($(".member[memberid=5] .memberRowMenuItem")[0] as HTMLElement).focus();

      swapMemberRoleInRow({ memberID: 5, targetRole: "cocreator" });

      expect(document.activeElement).not.toBe(document.body);
      expect(document.activeElement).toBe($(".member[memberid=5]")[0]);
    });
  });

  it("adds the co-owner kebab when the row is demoted to a plain member", () => {
    viewerState({});
    seedRow({ memberRole: "cocreator" });
    expect($(".member[memberid=5] .memberRowKebab").length).toBe(0);

    swapMemberRoleInRow({ memberID: 5, targetRole: "member" });

    const kebab = $(".member[memberid=5] .memberRowKebab--coOwner");
    expect(kebab.length).toBe(1);
    expect(kebab.attr("aria-label")).toBe("Actions for Bob");
    expect($(".member[memberid=5] .memberRowMenuItem").length).toBe(1);
  });

  it("does not double-add the kebab when the row is already a plain member", () => {
    viewerState({});
    seedRow({ memberRole: "member" });

    swapMemberRoleInRow({ memberID: 5, targetRole: "member" });

    expect($(".member[memberid=5] .memberRowKebab").length).toBe(1);
  });

  it("leaves a plain-member viewer's rows without a kebab", () => {
    viewerState({ isCoCreator: false });
    seedRow({ memberRole: "cocreator" });

    swapMemberRoleInRow({ memberID: 5, targetRole: "member" });

    expect($(".member[memberid=5] .memberRowKebab").length).toBe(0);
  });
});

const REMOVE_MODAL_HTML = `
  <div id="confirmModal">
    <div id="confirmModalTitle"></div>
    <div id="confirmModalBody"></div>
    <button id="modalDismiss"></button>
    <button id="modalSubmit"></button>
    <div id="modalRedirect"></div>
  </div>
`;

describe("removeMemberFail - is429Handled early-return", () => {
  beforeEach(() => {
    document.body.innerHTML = REMOVE_MODAL_HTML;
    vi.clearAllMocks();
    // Stub jQuery bootstrap-modal plugin used by removeMemberShowModal/hideModal
    ($.fn as unknown as Record<string, unknown>).modal = function (
      this: JQuery,
    ) {
      return this;
    };
  });

  it("returns early without redirecting to error page when is429Handled is true", () => {
    const locationAssignSpy = vi
      .spyOn(window.location, "assign")
      .mockImplementation(() => {});

    vi.mocked(is429Handled).mockReturnValueOnce(true);

    const rateLimitedXhr = createMockXhr({ status: 429 });
    const chainable = createMockJqXHRChainable({
      fail: (cb: unknown) =>
        (cb as (xhr: JQuery.jqXHR) => void)(rateLimitedXhr),
    });
    vi.mocked(ajaxCall).mockReturnValue(chainable);

    removeMemberShowModal({ memberID: 5, utubID: 1, intent: "remove" });
    $("#modalSubmit").trigger("click");

    expect(vi.mocked(is429Handled)).toHaveBeenCalledWith(rateLimitedXhr);
    expect(locationAssignSpy).not.toHaveBeenCalled();
  });
});

const CREATE_MEMBER_FORM_HTML = `
  <div>
    <div id="createMemberWrap" class="visible-flex">
      <div class="memberAddComboboxWrap"></div>
    </div>
    <div id="displayMemberWrap"></div>
    <button id="memberBtnCreate"></button>
  </div>
`;

describe("createMemberHideInput tears down the add-member combobox", () => {
  beforeEach(() => {
    document.body.innerHTML = CREATE_MEMBER_FORM_HTML;
    vi.clearAllMocks();
  });

  it("empties and hides #createMemberWrap", () => {
    expect($("#createMemberWrap").find(".memberAddComboboxWrap").length).toBe(
      1,
    );

    createMemberHideInput();

    expect($("#createMemberWrap").hasClass("hidden")).toBe(true);
    expect($("#createMemberWrap").children().length).toBe(0);
  });
});

describe("updateMemberDeck - applyDeckDiff config", () => {
  beforeEach(() => {
    document.body.innerHTML = `<div id="listMembers"></div>`;
    vi.clearAllMocks();
    vi.mocked(getState).mockReturnValue({
      members: [
        { id: 1, username: "Alice", memberRole: "member", joinedAt: null },
      ],
      isCurrentUserOwner: true,
      preferences: { memberSort: "name_az" },
    } as unknown as ReturnType<typeof getState>);
  });

  it("calls applyDeckDiff once with oldItems matching getState().members and newItems matching newMembers", () => {
    const existingMember = {
      id: 1,
      username: "Alice",
      memberRole: "member",
      joinedAt: null,
    };
    const newMember = {
      id: 2,
      username: "Bob",
      memberRole: "member",
      joinedAt: null,
    };
    const newMembers = [existingMember, newMember];

    updateMemberDeck(newMembers, true, 42);

    expect(vi.mocked(applyDeckDiff)).toHaveBeenCalledTimes(1);
    const config = vi.mocked(applyDeckDiff).mock.calls[0][0];
    expect(config.oldItems).toEqual([existingMember]);
    expect(config.newItems).toEqual(newMembers);
    expect(config.getID(existingMember)).toBe(1);
    expect(config.getID(newMember)).toBe(2);
    expect(typeof config.removeElement).toBe("function");
    expect(typeof config.addElement).toBe("function");
  });

  it("removeElement callback removes the member badge from the DOM", () => {
    document.body.innerHTML = `
      <div id="listMembers">
        <span class="member" memberid="7"><b>Charlie</b></span>
      </div>
    `;

    updateMemberDeck([], true, 42);
    const config = vi.mocked(applyDeckDiff).mock.calls[0][0];

    config.removeElement(7);

    expect(document.querySelector('.member[memberid="7"]')).toBeNull();
  });

  it("addElement callback appends a new member badge to #listMembers", () => {
    const newMember = {
      id: 9,
      username: "Dana",
      memberRole: "member",
      joinedAt: null,
    };

    updateMemberDeck([newMember], true, 42);
    const config = vi.mocked(applyDeckDiff).mock.calls[0][0];

    config.addElement(newMember);

    const appendedBadge = document.querySelector(
      '#listMembers .member[memberid="9"]',
    );
    expect(appendedBadge).not.toBeNull();
    expect(appendedBadge!.querySelector("b")!.textContent).toBe("Dana");
  });
});

const LEAVE_UTUB_HTML = `
  <div id="confirmModal">
    <div id="confirmModalTitle"></div>
    <div id="confirmModalBody"></div>
    <button id="modalDismiss"></button>
    <button id="modalSubmit"></button>
    <div id="modalRedirect"></div>
  </div>
  <button id="memberSelfBtnDelete"></button>
  <div id="listUTubs">
    <div class="UTubSelector" utubid="42"></div>
  </div>
`;

describe("leaveUTubSuccess - UTub deck dispatch on successful leave", () => {
  beforeEach(() => {
    document.body.innerHTML = LEAVE_UTUB_HTML;
    vi.clearAllMocks();
    ($.fn as unknown as Record<string, unknown>).modal = function (
      this: JQuery,
    ) {
      return this;
    };
    // Override fadeOut so the post-fade callback fires synchronously
    ($.fn as unknown as Record<string, unknown>).fadeOut = function (
      this: JQuery,
      _duration: unknown,
      callback?: () => void,
    ) {
      if (typeof callback === "function") callback();
      return this;
    };
    vi.mocked(is429Handled).mockReturnValue(false);
  });

  function triggerLeaveSubmit(utubID: number): void {
    const successXhr = createMockXhr({ status: 200 });
    const chainable = createMockJqXHRChainable({
      done: (cb: unknown) => {
        (
          cb as (
            _response: unknown,
            _textStatus: unknown,
            xhr: JQuery.jqXHR,
          ) => void
        )({}, "success", successXhr);
      },
    });
    vi.mocked(ajaxCall).mockReturnValue(chainable);

    // Pass isCreator=false to route the done callback through leaveUTubSuccess
    removeMemberShowModal({ memberID: 5, utubID: utubID, intent: "leave" });
    $("#modalSubmit").trigger("click");
  }

  it("calls resetUTubDeckIfNoUTubs and skips hideInputsAndUpdateUTubDeck when no UTubs remain", () => {
    vi.mocked(getNumOfUTubs).mockReturnValue(0);

    triggerLeaveSubmit(42);

    expect(vi.mocked(resetUTubDeckIfNoUTubs)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(hideInputsAndUpdateUTubDeck)).not.toHaveBeenCalled();
  });

  it("calls hideInputsAndUpdateUTubDeck and skips resetUTubDeckIfNoUTubs when UTubs remain", () => {
    vi.mocked(getNumOfUTubs).mockReturnValue(2);

    triggerLeaveSubmit(42);

    expect(vi.mocked(hideInputsAndUpdateUTubDeck)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(resetUTubDeckIfNoUTubs)).not.toHaveBeenCalled();
  });
});

describe("createMemberBadge - leaves #memberSelfBtnDelete to createLeaveUTubAsMemberIcon", () => {
  beforeEach(() => {
    document.body.innerHTML = `<button id="memberSelfBtnDelete" data-bs-toggle="tooltip"></button>`;
    vi.clearAllMocks();
  });

  it("binds nothing on the leave button when building a non-owner viewer's member row", () => {
    createMemberBadge({
      memberID: 5,
      username: "Bob",
      memberRole: "member",
      viewerRole: "member",
      utubID: 10,
    });

    const jqueryInternals = $ as unknown as {
      _data: (element: Element, name: string) => unknown;
    };
    expect(
      jqueryInternals._data($("#memberSelfBtnDelete")[0], "events"),
    ).toBeUndefined();
    $("#memberSelfBtnDelete").trigger("click.removeMember");
    expect(tooltipInstance.hide).not.toHaveBeenCalled();
    expect(vi.mocked(bootstrap.Tooltip.getInstance)).not.toHaveBeenCalled();
  });
});
