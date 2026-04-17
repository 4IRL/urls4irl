import {
  isMobile,
  setMobileUIWhenUTubSelectedOrURLNavSelected,
  setMobileUIWhenUTubNotSelectedOrUTubDeleted,
  setMobileUIWhenUTubDeckSelected,
  setMobileUIWhenMemberDeckSelected,
  setMobileUIWhenTagDeckSelected,
  revertMobileUIToFullScreenUI,
} from "../mobile.js";

const mockMakeUTubSelectableAgainIfMobile = vi.fn();

vi.mock("../lib/event-bus.js", () => ({
  on: vi.fn(),
  AppEvents: { UTUB_SELECTED: "utub-selected" },
}));
vi.mock("../navbar.js", () => ({
  NAVBAR_TOGGLER: { toggler: { hide: vi.fn() } },
}));
vi.mock("../collapsible-decks.js", () => ({
  resetAllDecksIfCollapsed: vi.fn(),
  removeCollapsibleClickableHeaderClass: vi.fn(),
  addCollapsibleClickableHeaderClass: vi.fn(),
}));
vi.mock("../../store/app-store.js", () => ({
  getState: vi.fn(() => ({ activeUTubID: null })),
}));
vi.mock("../utubs/selectors.js", () => ({
  makeUTubSelectableAgainIfMobile: (...args: unknown[]) =>
    mockMakeUTubSelectableAgainIfMobile(...args),
}));

const $ = window.jQuery;

const MOBILE_HTML = `
  <div class="panel" id="leftPanel"></div>
  <div class="panel" id="centerPanel"></div>
  <div class="deck" id="UTubDeck"></div>
  <div class="deck" id="MemberDeck"></div>
  <div class="deck" id="TagDeck"></div>
  <button id="toUTubs" class="hidden"></button>
  <button id="toMembers" class="hidden"></button>
  <button id="toTags" class="hidden"></button>
  <button id="toURLs" class="hidden"></button>
  <div id="listUTubs">
    <div class="UTubSelector active" utubid="1"></div>
  </div>
`;

describe("isMobile", () => {
  it("returns true when $(window).width() returns undefined", () => {
    const widthSpy = vi
      .spyOn($.fn, "width")
      .mockReturnValue(undefined as unknown as number);
    expect(isMobile()).toBe(true);
    widthSpy.mockRestore();
  });

  it("returns true when viewport width is below TABLET_WIDTH", () => {
    const widthSpy = vi.spyOn($.fn, "width").mockReturnValue(500);
    expect(isMobile()).toBe(true);
    widthSpy.mockRestore();
  });

  it("returns false when viewport width is at or above TABLET_WIDTH", () => {
    const widthSpy = vi.spyOn($.fn, "width").mockReturnValue(992);
    expect(isMobile()).toBe(false);
    widthSpy.mockRestore();
  });
});

describe("setMobileUIWhenUTubSelectedOrURLNavSelected", () => {
  beforeEach(() => {
    document.body.innerHTML = MOBILE_HTML;
  });

  it("hides left panel and shows center panel with nav buttons", () => {
    setMobileUIWhenUTubSelectedOrURLNavSelected();

    expect($(".panel#leftPanel").hasClass("hidden")).toBe(true);
    expect($(".panel#centerPanel").hasClass("visible-flex")).toBe(true);
    expect($("button#toUTubs").hasClass("hidden")).toBe(false);
    expect($("button#toMembers").hasClass("hidden")).toBe(false);
    expect($("button#toTags").hasClass("hidden")).toBe(false);
    expect($("button#toURLs").hasClass("hidden")).toBe(true);
  });

  it("hides member and tag deck visible-flex states", () => {
    $(".deck#MemberDeck").addClass("visible-flex");
    $(".deck#TagDeck").addClass("visible-flex");

    setMobileUIWhenUTubSelectedOrURLNavSelected();

    expect($(".deck#MemberDeck").hasClass("visible-flex")).toBe(false);
    expect($(".deck#TagDeck").hasClass("visible-flex")).toBe(false);
  });
});

describe("setMobileUIWhenUTubNotSelectedOrUTubDeleted", () => {
  beforeEach(() => {
    document.body.innerHTML = MOBILE_HTML;
  });

  it("hides all navigation buttons and shows UTub deck", () => {
    setMobileUIWhenUTubNotSelectedOrUTubDeleted();

    expect($("button#toUTubs").hasClass("hidden")).toBe(true);
    expect($("button#toMembers").hasClass("hidden")).toBe(true);
    expect($("button#toTags").hasClass("hidden")).toBe(true);
    expect($("button#toURLs").hasClass("hidden")).toBe(true);
    expect($(".deck#UTubDeck").hasClass("hidden")).toBe(false);
  });

  it("removes visible-flex from center panel and side decks", () => {
    $(".panel#centerPanel").addClass("visible-flex");
    $(".deck#MemberDeck").addClass("visible-flex");

    setMobileUIWhenUTubNotSelectedOrUTubDeleted();

    expect($(".panel#centerPanel").hasClass("visible-flex")).toBe(false);
    expect($(".deck#MemberDeck").hasClass("visible-flex")).toBe(false);
  });
});

describe("setMobileUIWhenUTubDeckSelected", () => {
  beforeEach(() => {
    document.body.innerHTML = MOBILE_HTML;
    vi.clearAllMocks();
  });

  it("shows left panel and hides center panel", () => {
    setMobileUIWhenUTubDeckSelected();

    expect($(".panel#leftPanel").hasClass("hidden")).toBe(false);
    expect($(".panel#centerPanel").hasClass("visible-flex")).toBe(false);
    expect($("button#toUTubs").hasClass("hidden")).toBe(true);
  });

  it("calls makeUTubSelectableAgainIfMobile when a UTub is active", () => {
    setMobileUIWhenUTubDeckSelected();

    expect(mockMakeUTubSelectableAgainIfMobile).toHaveBeenCalled();
  });
});

describe("setMobileUIWhenMemberDeckSelected", () => {
  beforeEach(() => {
    document.body.innerHTML = MOBILE_HTML;
  });

  it("shows member deck and hides UTub deck", () => {
    setMobileUIWhenMemberDeckSelected();

    expect($(".deck#MemberDeck").hasClass("visible-flex")).toBe(true);
    expect($(".deck#UTubDeck").hasClass("hidden")).toBe(true);
    expect($("button#toMembers").hasClass("hidden")).toBe(true);
  });
});

describe("setMobileUIWhenTagDeckSelected", () => {
  beforeEach(() => {
    document.body.innerHTML = MOBILE_HTML;
  });

  it("shows tag deck and hides UTub deck", () => {
    setMobileUIWhenTagDeckSelected();

    expect($(".deck#TagDeck").hasClass("visible-flex")).toBe(true);
    expect($(".deck#UTubDeck").hasClass("hidden")).toBe(true);
    expect($("button#toTags").hasClass("hidden")).toBe(true);
  });
});

describe("revertMobileUIToFullScreenUI", () => {
  beforeEach(() => {
    document.body.innerHTML = MOBILE_HTML;
  });

  it("removes hidden from all panels and decks, hides nav buttons", () => {
    $(".panel#centerPanel").addClass("hidden");
    $(".deck#UTubDeck").addClass("hidden");
    $(".deck#MemberDeck").addClass("hidden");

    revertMobileUIToFullScreenUI();

    expect($(".panel#centerPanel").hasClass("hidden")).toBe(false);
    expect($(".panel#leftPanel").hasClass("hidden")).toBe(false);
    expect($(".deck#UTubDeck").hasClass("hidden")).toBe(false);
    expect($(".deck#MemberDeck").hasClass("hidden")).toBe(false);
    expect($(".deck#TagDeck").hasClass("hidden")).toBe(false);
    expect($("button#toUTubs").hasClass("hidden")).toBe(true);
    expect($("button#toMembers").hasClass("hidden")).toBe(true);
    expect($("button#toTags").hasClass("hidden")).toBe(true);
    expect($("button#toURLs").hasClass("hidden")).toBe(true);
  });

  it("is a no-op when panels are already in full-screen state", () => {
    // Remove hidden from everything first
    $(".panel").removeClass("hidden");
    $(".deck").removeClass("hidden");

    revertMobileUIToFullScreenUI();

    // Nav buttons should still be hidden
    expect($("button#toUTubs").hasClass("hidden")).toBe(true);
  });
});
