import { createOwnerBadge, createMemberBadge } from "../members.js";
import { createMemberRemoveBtn } from "../delete.js";

vi.mock("../delete.js", () => ({
  createMemberRemoveBtn: vi.fn(() =>
    window.jQuery('<button class="memberOtherBtnDelete"></button>'),
  ),
  removeMemberShowModal: vi.fn(),
}));
vi.mock("../../btns-forms.js", () => ({ hideInputs: vi.fn() }));
vi.mock("../../urls/cards/selection.js", () => ({ deselectAllURLs: vi.fn() }));

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
