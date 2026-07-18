import type { UtubDetail } from "../../../types/utub.js";

import { buildSelectedUTub } from "../selectors.js";
import { getState, resetStore } from "../../../store/app-store.js";

const { mockMetricsClient } = await vi.hoisted(
  async () => await import("../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../header-fit.js", () => ({ fitUTubHeaderAndSubheader: vi.fn() }));

vi.mock("../deck.js", () => ({
  showUTubLoadingIconAndSetTimeout: vi.fn(() => 0),
  hideUTubLoadingIconAndClearTimeout: vi.fn(),
  setUTubDeckOnUTubSelected: vi.fn(),
}));

vi.mock("../../urls/update-description.js", () => ({
  removeEventListenersForShowCreateUTubDescIfEmptyDesc: vi.fn(),
  showCreateDescriptionButtonAlways: vi.fn(),
}));

vi.mock("../../../lib/event-bus.js", async () => {
  const actual = await vi.importActual<
    typeof import("../../../lib/event-bus.js")
  >("../../../lib/event-bus.js");
  return {
    ...actual,
    emit: vi.fn(),
  };
});

const mockIsMobile = vi.fn(() => false);
const mockReplaceMobilePanelHistoryState = vi.fn();

vi.mock("../../mobile.js", () => ({
  isMobile: () => mockIsMobile(),
  replaceMobilePanelHistoryState: (...args: unknown[]) =>
    mockReplaceMobilePanelHistoryState(...args),
}));

const $ = window.jQuery;

const SELECTED_UTUB_HTML = `
  <span id="URLDeckLockIcon" class="hidden"></span>
  <h1 id="URLDeckHeader"></h1>
  <h2 id="URLDeckSubheader"></h2>
  <div id="UTubDescriptionSubheaderWrap"></div>
  <button id="URLDeckSubheaderCreateDescription"></button>
  <div id="URLDeckNoDescription"></div>
  <input id="utubDescriptionUpdate" />
`;

function makeUtubDetail(overrides: Partial<UtubDetail> = {}): UtubDetail {
  return {
    id: 42,
    name: "Sample UTub",
    description: "",
    isCreator: false,
    isLocked: false,
    currentUser: 1,
    createdByUserID: 2,
    urls: [],
    tags: [],
    members: [],
    ...overrides,
  } as UtubDetail;
}

describe("buildSelectedUTub — locked-UTub affordances", () => {
  beforeEach(() => {
    document.body.innerHTML = SELECTED_UTUB_HTML;
    resetStore();
    vi.clearAllMocks();
    // Null the history entry so the push-guard fires a fresh push each test.
    window.history.replaceState(null, "", "/");
    mockIsMobile.mockReturnValue(false);
  });

  afterEach(() => {
    document.body.className = "";
    document.body.innerHTML = "";
    resetStore();
  });

  it("marks the body locked, reveals the lock icon, and stores lock state for a locked UTub", () => {
    buildSelectedUTub(makeUtubDetail({ isLocked: true }));

    expect(document.body.classList.contains("utub-locked")).toBe(true);
    expect($("#URLDeckLockIcon").hasClass("hidden")).toBe(false);
    expect(getState().isCurrentUTubLocked).toBe(true);
  });

  it("clears the locked body class, hides the lock icon, and stores unlocked state for an unlocked UTub", () => {
    buildSelectedUTub(makeUtubDetail({ isLocked: false }));

    expect(document.body.classList.contains("utub-locked")).toBe(false);
    expect($("#URLDeckLockIcon").hasClass("hidden")).toBe(true);
    expect(getState().isCurrentUTubLocked).toBe(false);
  });

  describe("mobile landing-panel history", () => {
    it("on mobile, pushes bare { UTubID } then replaces with { UTubID, mobilePanel: 'urls' }", () => {
      mockIsMobile.mockReturnValue(true);
      const pushStateSpy = vi.spyOn(window.history, "pushState");

      buildSelectedUTub(makeUtubDetail({ id: 77 }));

      // The bare-{UTubID} push shape is unchanged (shared with desktop).
      expect(pushStateSpy).toHaveBeenCalledTimes(1);
      expect(pushStateSpy).toHaveBeenCalledWith(
        { UTubID: 77 },
        "",
        expect.any(String),
      );
      // Immediately overwritten with the merged mobile-panel shape.
      expect(mockReplaceMobilePanelHistoryState).toHaveBeenCalledTimes(1);
      expect(mockReplaceMobilePanelHistoryState).toHaveBeenCalledWith({
        mobilePanel: "urls",
        UTubID: 77,
      });
      // Push must precede the replace so the merged entry wins.
      expect(pushStateSpy.mock.invocationCallOrder[0]).toBeLessThan(
        mockReplaceMobilePanelHistoryState.mock.invocationCallOrder[0],
      );

      pushStateSpy.mockRestore();
    });

    it("on desktop, only pushes bare { UTubID } — no mobile replace", () => {
      mockIsMobile.mockReturnValue(false);
      const pushStateSpy = vi.spyOn(window.history, "pushState");

      buildSelectedUTub(makeUtubDetail({ id: 88 }));

      expect(pushStateSpy).toHaveBeenCalledTimes(1);
      expect(pushStateSpy).toHaveBeenCalledWith(
        { UTubID: 88 },
        "",
        expect.any(String),
      );
      expect(mockReplaceMobilePanelHistoryState).not.toHaveBeenCalled();

      pushStateSpy.mockRestore();
    });
  });
});
