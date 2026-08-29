import {
  createMockJqXHRChainable,
  createMockXhr,
} from "../../../__tests__/helpers/mock-jquery.js";
import { createOwnerBadge, createMemberBadge } from "../members.js";
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
        isCurrentUserOwner: false,
        utubID: 10,
      });
      expect(el.attr("memberid")).toBe("42");
    });

    it("has member, full-width, flex-row, jc-sb, align-center, flex-start classes", () => {
      const el = createMemberBadge({
        memberID: 1,
        username: "Bob",
        memberRole: "member",
        isCurrentUserOwner: false,
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
        isCurrentUserOwner: false,
        utubID: 10,
      });
      expect(el.find("b").text()).toBe("Bob");
    });
  });

  describe("per-row role icon (DD-2/DD-10/DD-18)", () => {
    it("renders the co-creator diamond-half icon + 'Co-owner' label", () => {
      const el = createMemberBadge({
        memberID: 3,
        username: "Bob",
        memberRole: "cocreator",
        isCurrentUserOwner: false,
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
        isCurrentUserOwner: false,
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
        isCurrentUserOwner: false,
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
        isCurrentUserOwner: true,
        utubID: 10,
      });
      expect(el.find(".memberRowKebab").length).toBe(1);
    });

    it("folds the remove action into the menu and renders no bare remove button", () => {
      const el = createMemberBadge({
        memberID: 5,
        username: "Bob",
        memberRole: "member",
        isCurrentUserOwner: true,
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
        isCurrentUserOwner: true,
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
        isCurrentUserOwner: true,
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
        isCurrentUserOwner: true,
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
        isCurrentUserOwner: false,
        utubID: 10,
      });
      expect(el.find(".memberRowKebab").length).toBe(0);
    });

    it("does not render a row menu", () => {
      const el = createMemberBadge({
        memberID: 5,
        username: "Bob",
        memberRole: "member",
        isCurrentUserOwner: false,
        utubID: 10,
      });
      expect(el.find(".memberRowMenu").length).toBe(0);
    });
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

    removeMemberShowModal(5, true, 1);
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
      members: [{ id: 1, username: "Alice", memberRole: "member" }],
      isCurrentUserOwner: true,
    } as unknown as ReturnType<typeof getState>);
  });

  it("calls applyDeckDiff once with oldItems matching getState().members and newItems matching newMembers", () => {
    const existingMember = { id: 1, username: "Alice", memberRole: "member" };
    const newMember = { id: 2, username: "Bob", memberRole: "member" };
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
    const newMember = { id: 9, username: "Dana", memberRole: "member" };

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
    removeMemberShowModal(5, false, utubID);
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
