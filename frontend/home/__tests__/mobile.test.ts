import { TABLET_WIDTH } from "../../lib/constants.js";
import {
  isMobile,
  isCoarsePointer,
  initMobileLayout,
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

// Simulated manual-collapse intent, controlled per-test, that the mocked
// reapply function reads to mirror the real resolver's viewport behavior:
// mobile clears `.lhs-collapsed`; desktop re-applies it when intent is set.
const mockLeftPanelToggleState = { userCollapsedLHS: false };
const mockReapplyLeftPanelVisibilityForViewport = vi.fn(() => {
  const mainPanel = window.jQuery("#mainPanel");
  if ((window.jQuery(window).width() ?? 0) < TABLET_WIDTH) {
    mainPanel.removeClass("lhs-collapsed");
    return;
  }
  mainPanel.toggleClass(
    "lhs-collapsed",
    mockLeftPanelToggleState.userCollapsedLHS,
  );
});

vi.mock("../left-panel-toggle.js", () => ({
  reapplyLeftPanelVisibilityForViewport: () =>
    mockReapplyLeftPanelVisibilityForViewport(),
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

describe("isCoarsePointer", () => {
  it("returns true when a coarse pointer is present", () => {
    const matchMediaSpy = vi
      .spyOn(window, "matchMedia")
      .mockReturnValue({ matches: true } as MediaQueryList);
    expect(isCoarsePointer()).toBe(true);
    expect(matchMediaSpy).toHaveBeenCalledWith("(any-pointer: coarse)");
    matchMediaSpy.mockRestore();
  });

  it("returns false when no coarse pointer is present", () => {
    const matchMediaSpy = vi
      .spyOn(window, "matchMedia")
      .mockReturnValue({ matches: false } as MediaQueryList);
    expect(isCoarsePointer()).toBe(false);
    matchMediaSpy.mockRestore();
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

describe("initMobileLayout viewport-crossing reconciliation", () => {
  let breakpointChangeHandler: () => void;
  let matchMediaSpy: ReturnType<typeof vi.spyOn>;
  let widthSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    vi.clearAllMocks();
    mockLeftPanelToggleState.userCollapsedLHS = false;
    document.body.innerHTML = `
      <main id="mainPanel">
        <div class="panel" id="leftPanel"></div>
        <div class="panel" id="centerPanel"></div>
      </main>
      <div class="deck" id="UTubDeck"></div>
      <div class="deck" id="MemberDeck"></div>
      <div class="deck" id="TagDeck"></div>
      <button id="toUTubs" class="hidden"></button>
      <button id="toMembers" class="hidden"></button>
      <button id="toTags" class="hidden"></button>
      <button id="toURLs" class="hidden"></button>
    `;

    matchMediaSpy = vi.spyOn(window, "matchMedia").mockReturnValue({
      addEventListener: (
        _event: string,
        listener: EventListenerOrEventListenerObject,
      ) => {
        breakpointChangeHandler = listener as () => void;
      },
      removeEventListener: vi.fn(),
    } as unknown as MediaQueryList);

    initMobileLayout();
  });

  afterEach(() => {
    matchMediaSpy.mockRestore();
    widthSpy?.mockRestore();
  });

  it("removes lhs-collapsed from mainPanel when crossing into mobile", () => {
    $("#mainPanel").addClass("lhs-collapsed");
    widthSpy = vi.spyOn($.fn, "width").mockReturnValue(500);

    breakpointChangeHandler();

    expect(mockReapplyLeftPanelVisibilityForViewport).toHaveBeenCalled();
    expect($("#mainPanel").hasClass("lhs-collapsed")).toBe(false);
  });

  it("re-applies lhs-collapsed on desktop re-entry while collapse intent is retained", () => {
    mockLeftPanelToggleState.userCollapsedLHS = true;
    $("#mainPanel").removeClass("lhs-collapsed");
    widthSpy = vi.spyOn($.fn, "width").mockReturnValue(1200);

    breakpointChangeHandler();

    expect(mockReapplyLeftPanelVisibilityForViewport).toHaveBeenCalled();
    expect($("#mainPanel").hasClass("lhs-collapsed")).toBe(true);
  });

  it("leaves mainPanel expanded on desktop re-entry when no collapse intent", () => {
    mockLeftPanelToggleState.userCollapsedLHS = false;
    $("#mainPanel").addClass("lhs-collapsed");
    widthSpy = vi.spyOn($.fn, "width").mockReturnValue(1200);

    breakpointChangeHandler();

    expect($("#mainPanel").hasClass("lhs-collapsed")).toBe(false);
  });
});
