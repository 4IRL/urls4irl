import {
  createMockJqXHRChainable,
  createMockXhr,
} from "../../../__tests__/helpers/mock-jquery.js";
import { createOwnerBadge, createMemberBadge } from "../members.js";
import { createMemberRemoveBtn, removeMemberShowModal } from "../delete.js";
import { createMemberHideInput } from "../create.js";
import { updateMemberDeck } from "../deck.js";
import { ajaxCall, is429Handled } from "../../../lib/ajax.js";
import { diffIDLists } from "../../../logic/deck-diffing.js";
import { getState } from "../../../store/app-store.js";
import { getNumOfUTubs } from "../../utubs/utils.js";
import {
  hideInputsAndUpdateUTubDeck,
  resetUTubDeckIfNoUTubs,
} from "../../utubs/deck.js";

vi.mock("../delete.js", async () => {
  const actual =
    await vi.importActual<typeof import("../delete.js")>("../delete.js");
  return {
    ...actual,
    createMemberRemoveBtn: vi.fn(() =>
      window.jQuery('<button class="memberOtherBtnDelete"></button>'),
    ),
  };
});
vi.mock("../../btns-forms.js", () => ({ hideInputs: vi.fn() }));
vi.mock("../../urls/cards/selection.js", () => ({ deselectAllURLs: vi.fn() }));
vi.mock("../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));
vi.mock("../../../logic/deck-diffing.js", () => ({
  diffIDLists: vi.fn(() => ({ toRemove: [], toAdd: [], toUpdate: [] })),
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

  it("has member, full-width, flex-row, flex-start, align-center classes", () => {
    const $el = $(createOwnerBadge(1, "Alice"));
    expect($el.hasClass("member")).toBe(true);
    expect($el.hasClass("full-width")).toBe(true);
    expect($el.hasClass("flex-row")).toBe(true);
    expect($el.hasClass("flex-start")).toBe(true);
    expect($el.hasClass("align-center")).toBe(true);
  });

  it("renders the username inside a bold element", () => {
    const el = createOwnerBadge(1, "Alice");
    expect($(el).find("b").text()).toBe("Alice");
  });
});

describe("createMemberBadge", () => {
  beforeEach(() => vi.clearAllMocks());

  describe("element structure", () => {
    it("sets memberid attribute to the member user ID", () => {
      const el = createMemberBadge(42, "Bob", false, 10);
      expect(el.attr("memberid")).toBe("42");
    });

    it("has member, full-width, flex-row, jc-sb, align-center, flex-start classes", () => {
      const el = createMemberBadge(1, "Bob", false, 10);
      expect(el.hasClass("member")).toBe(true);
      expect(el.hasClass("full-width")).toBe(true);
      expect(el.hasClass("flex-row")).toBe(true);
      expect(el.hasClass("jc-sb")).toBe(true);
      expect(el.hasClass("align-center")).toBe(true);
      expect(el.hasClass("flex-start")).toBe(true);
    });

    it("renders the username inside a bold element", () => {
      const el = createMemberBadge(1, "Bob", false, 10);
      expect(el.find("b").text()).toBe("Bob");
    });
  });

  describe("when the current user is the UTub owner (isCurrentUserOwner=true)", () => {
    it("calls createMemberRemoveBtn to create a remove button", () => {
      createMemberBadge(5, "Bob", true, 10);
      expect(vi.mocked(createMemberRemoveBtn)).toHaveBeenCalledOnce();
    });

    it("appends the remove button to the member span", () => {
      const el = createMemberBadge(5, "Bob", true, 10);
      expect(el.find(".memberOtherBtnDelete").length).toBe(1);
    });
  });

  describe("when the current user is a member (isCurrentUserOwner=false)", () => {
    it("does not call createMemberRemoveBtn", () => {
      createMemberBadge(5, "Bob", false, 10);
      expect(vi.mocked(createMemberRemoveBtn)).not.toHaveBeenCalled();
    });

    it("does not append a remove button to the span", () => {
      const el = createMemberBadge(5, "Bob", false, 10);
      expect(el.find(".memberOtherBtnDelete").length).toBe(0);
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
    <div id="createMemberWrap"></div>
    <div id="displayMemberWrap"></div>
    <button id="memberBtnCreate"></button>
    <input id="memberCreate" type="text" value="existing-text" />
    <div id="memberCreate-error" class="visible"></div>
  </div>
`;

describe("resetNewMemberForm via createMemberHideInput", () => {
  beforeEach(() => {
    document.body.innerHTML = CREATE_MEMBER_FORM_HTML;
    vi.clearAllMocks();
  });

  it("resets the #memberCreate input value to the empty string (not null)", () => {
    $("#memberCreate").val("some-username");
    expect($("#memberCreate").val()).toBe("some-username");

    createMemberHideInput();

    expect($("#memberCreate").val()).toBe("");
  });
});

describe("updateMemberDeck - null-guard for missing member data", () => {
  beforeEach(() => {
    document.body.innerHTML = `<div id="listMembers"></div>`;
    vi.clearAllMocks();
    vi.mocked(getState).mockReturnValue({
      members: [],
      isCurrentUserOwner: true,
    } as unknown as ReturnType<typeof getState>);
  });

  it("skips appending a badge when the member ID in toAdd is not found in newMembers", () => {
    // Force diffIDLists to return a toAdd ID that is not present in newMembers,
    // exercising the `if (!memberData) return;` null-guard branch.
    vi.mocked(diffIDLists).mockReturnValueOnce({
      toRemove: [],
      toAdd: [999],
      toUpdate: [],
    });

    updateMemberDeck([{ id: 1, username: "Alice" }], true, 42);

    expect($("#listMembers").children().length).toBe(0);
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
