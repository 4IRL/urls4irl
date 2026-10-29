import type { UtubDetail } from "../../../types/utub.js";

import {
  buildSelectedUTub,
  captureSettingsVersions,
  shouldKeepSettings,
} from "../selectors.js";
import { getState, resetStore, setState } from "../../../store/app-store.js";
import { makeUtubSummaryItem } from "../../../__tests__/helpers/utub-summary.js";

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
    isCoCreator: false,
    isLocked: false,
    currentUser: 1,
    createdByUserID: 2,
    urls: [],
    tags: [],
    members: [],
    ...overrides,
  } as UtubDetail;
}

describe("buildSelectedUTub — row counts and order", () => {
  const ROW_HTML = `${SELECTED_UTUB_HTML}
    <div id="listUTubs">
      <span class="UTubSelector" utubid="5"><span class="UTubRowCounts"><span class="visually-hidden"></span><span class="UTubRowCountNum">9</span><span class="UTubRowCountNum">9</span></span></span>
      <span class="UTubSelector" utubid="42"><span class="UTubRowCounts"><span class="visually-hidden"></span><span class="UTubRowCountNum">9</span><span class="UTubRowCountNum">9</span></span></span>
    </div>`;

  beforeEach(() => {
    document.body.innerHTML = ROW_HTML;
    resetStore();
    vi.clearAllMocks();
    window.history.replaceState(null, "", "/");
    mockIsMobile.mockReturnValue(false);
  });

  afterEach(() => {
    document.body.innerHTML = "";
    resetStore();
  });

  it("corrects a stale summary count from the loaded decks on select", () => {
    setState({
      utubs: [
        makeUtubSummaryItem({ id: 5, urlCount: 9, memberCount: 9 }),
        makeUtubSummaryItem({ id: 42, urlCount: 9, memberCount: 9 }),
      ],
    });

    buildSelectedUTub({
      selectedUTub: makeUtubDetail({
        urls: [{ utubUrlID: 1 }, { utubUrlID: 2 }] as UtubDetail["urls"],
        members: [{ id: 1 }] as UtubDetail["members"],
      }),
    });

    const selected = getState().utubs.find((utub) => utub.id === 42);
    expect(selected?.urlCount).toBe(2);
    expect(selected?.memberCount).toBe(1);
    expect($('.UTubSelector[utubid="42"] .UTubRowCountNum').eq(0).text()).toBe(
      "2",
    );
    // Other rows are untouched.
    expect(getState().utubs.find((utub) => utub.id === 5)?.urlCount).toBe(9);
  });

  it.each(["recent_activity", "last_opened"] as const)(
    "leaves store and DOM order unchanged when selecting under %s",
    (utubSort) => {
      setState({
        preferences: { ...getState().preferences, utubSort },
        utubs: [
          makeUtubSummaryItem({ id: 5 }),
          makeUtubSummaryItem({ id: 42 }),
        ],
      });

      buildSelectedUTub({ selectedUTub: makeUtubDetail() });

      expect(getState().utubs.map((utub) => utub.id)).toEqual([5, 42]);
      expect(
        $("#listUTubs > .UTubSelector")
          .map((_, element) => Number($(element).attr("utubid")))
          .get(),
      ).toEqual([5, 42]);
    },
  );
});

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
    buildSelectedUTub({ selectedUTub: makeUtubDetail({ isLocked: true }) });

    expect(document.body.classList.contains("utub-locked")).toBe(true);
    expect($("#URLDeckLockIcon").hasClass("hidden")).toBe(false);
    expect(getState().isCurrentUTubLocked).toBe(true);
  });

  it("clears the locked body class, hides the lock icon, and stores unlocked state for an unlocked UTub", () => {
    buildSelectedUTub({ selectedUTub: makeUtubDetail({ isLocked: false }) });

    expect(document.body.classList.contains("utub-locked")).toBe(false);
    expect($("#URLDeckLockIcon").hasClass("hidden")).toBe(true);
    expect(getState().isCurrentUTubLocked).toBe(false);
  });

  describe("settings slice", () => {
    const populated = { utubs: { sample: 1 } } as never;
    const emptyShape = {
      utubs: {},
      members: {},
      tags: {},
      urls: {
        default_url_scheme: "https",
        hide_scheme_selector: false,
        allow_short_links: true,
      },
    };

    it("sets settings from the payload and replaces the previous UTub's", () => {
      buildSelectedUTub({
        selectedUTub: makeUtubDetail({ id: 1, settings: populated }),
      });
      expect(getState().settings).toEqual({
        ...emptyShape,
        utubs: { sample: 1 },
      });

      buildSelectedUTub({ selectedUTub: makeUtubDetail({ id: 2 }) });
      expect(getState().settings).toEqual(emptyShape);
    });

    it("stores the empty resolved shape (not the previous value) for a payload without settings", () => {
      buildSelectedUTub({
        selectedUTub: makeUtubDetail({ id: 1, settings: populated }),
      });
      buildSelectedUTub({ selectedUTub: makeUtubDetail({ id: 1 }) });

      expect(getState().settings).toEqual(emptyShape);
    });

    it("keepSettings preserves the stored settings", () => {
      buildSelectedUTub({
        selectedUTub: makeUtubDetail({ id: 1, settings: populated }),
      });
      buildSelectedUTub({
        selectedUTub: makeUtubDetail({ id: 1 }),
        keepSettings: true,
      });

      expect(getState().settings).toEqual({
        ...emptyShape,
        utubs: { sample: 1 },
      });
    });

    it("captureSettingsVersions returns all current versions", () => {
      setState({
        settingsVersion: 4,
        memberSettingsVersion: 7,
        policyLearnedVersion: 2,
      });

      expect(captureSettingsVersions()).toEqual({
        settingsVersion: 4,
        memberSettingsVersion: 7,
        policyLearnedVersion: 2,
      });
    });

    it("shouldKeepSettings truth table covers keepSettings, keepMemberSettings and forceShortLinksOff independently", () => {
      setState({
        activeUTubID: 1,
        settingsVersion: 3,
        memberSettingsVersion: 6,
        policyLearnedVersion: 5,
      });
      const sameID = makeUtubDetail({ id: 1 });
      const otherID = makeUtubDetail({ id: 9 });
      const decide = (
        selectedUTub: UtubDetail,
        settingsVersion: number,
        policyLearnedVersion: number,
        memberSettingsVersion = 6,
      ) =>
        shouldKeepSettings({
          selectedUTub,
          captured: {
            settingsVersion,
            memberSettingsVersion,
            policyLearnedVersion,
          },
        });

      expect(decide(sameID, 2, 5)).toEqual({
        keepSettings: true,
        keepMemberSettings: false,
        forceShortLinksOff: false,
      });
      expect(decide(sameID, 3, 4)).toEqual({
        keepSettings: false,
        keepMemberSettings: false,
        forceShortLinksOff: true,
      });
      expect(decide(sameID, 2, 4)).toEqual({
        keepSettings: true,
        keepMemberSettings: false,
        forceShortLinksOff: true,
      });
      expect(decide(sameID, 3, 5)).toEqual({
        keepSettings: false,
        keepMemberSettings: false,
        forceShortLinksOff: false,
      });
      // A member-settings bump alone keeps only the member slice.
      expect(decide(sameID, 3, 5, 5)).toEqual({
        keepSettings: false,
        keepMemberSettings: true,
        forceShortLinksOff: false,
      });
      // Both bumped: each is kept independently.
      expect(decide(sameID, 2, 5, 5)).toEqual({
        keepSettings: true,
        keepMemberSettings: true,
        forceShortLinksOff: false,
      });
      // A different UTub keeps neither.
      expect(decide(otherID, 2, 4, 5)).toEqual({
        keepSettings: false,
        keepMemberSettings: false,
        forceShortLinksOff: false,
      });
    });

    it("seeds memberSettings from the payload in the same setState as settings", () => {
      buildSelectedUTub({
        selectedUTub: makeUtubDetail({
          id: 1,
          memberSettings: { urls: { hide_copy_button: true } } as never,
        }),
      });

      expect(getState().memberSettings?.urls.hide_copy_button).toBe(true);
      expect(getState().memberSettings?.urls.sort).toBeNull();
    });

    it("resolves a payload without memberSettings to the empty shape", () => {
      buildSelectedUTub({ selectedUTub: makeUtubDetail({ id: 1 }) });

      expect(getState().memberSettings).toEqual({
        urls: {
          hide_copy_button: false,
          hide_short_link_button: false,
          hide_date_added: false,
          sort: null,
          view_mode: null,
          density: null,
          disable_swipe_delete: false,
        },
      });
    });

    it("keepMemberSettings preserves the stored slice while settings still apply", () => {
      buildSelectedUTub({
        selectedUTub: makeUtubDetail({
          id: 1,
          memberSettings: { urls: { hide_copy_button: true } } as never,
        }),
      });
      buildSelectedUTub({
        selectedUTub: makeUtubDetail({ id: 1 }),
        keepMemberSettings: true,
      });

      expect(getState().memberSettings?.urls.hide_copy_button).toBe(true);
    });

    it("a UTub switch nulls memberSettings unless the same setState supplies them", () => {
      buildSelectedUTub({
        selectedUTub: makeUtubDetail({
          id: 1,
          memberSettings: { urls: { hide_copy_button: true } } as never,
        }),
      });
      setState({ activeUTubID: 2 });

      expect(getState().memberSettings).toBeNull();
    });

    it("forceShortLinksOff applies incoming settings with allow_short_links false", () => {
      buildSelectedUTub({
        selectedUTub: makeUtubDetail({
          id: 1,
          settings: { urls: { allow_short_links: true } } as never,
        }),
        forceShortLinksOff: true,
      });

      expect(getState().settings?.urls.allow_short_links).toBe(false);
      expect(getState().settings?.urls.default_url_scheme).toBe("https");
    });

    it("without forceShortLinksOff the incoming allow_short_links is adopted", () => {
      buildSelectedUTub({
        selectedUTub: makeUtubDetail({
          id: 1,
          settings: { urls: { allow_short_links: true } } as never,
        }),
      });

      expect(getState().settings?.urls.allow_short_links).toBe(true);
    });
  });

  describe("multi-select store clear (UTub switch, defense-in-depth)", () => {
    it("resets multiSelectMode to false and clears selectedURLCardIDs on build", () => {
      // Production behavior lives at utubs/selectors.ts buildSelectedUTub's
      // setState — a defense-in-depth backstop to the UTUB_SELECTED event
      // subscriber (emit is mocked in this suite, so only the setState clear
      // runs here). Seed a live selection first so the assertion actually
      // proves the clear rather than re-confirming resetStore()'s defaults.
      setState({ multiSelectMode: true, selectedURLCardIDs: [1, 2] });
      expect(getState().multiSelectMode).toBe(true);

      buildSelectedUTub({ selectedUTub: makeUtubDetail({ id: 55 }) });

      expect(getState().multiSelectMode).toBe(false);
      expect(getState().selectedURLCardIDs).toEqual([]);
    });
  });

  describe("co-creator signal and member roles are threaded into the store", () => {
    it("writes isCoCreator from the response and preserves each member's memberRole", () => {
      buildSelectedUTub({
        selectedUTub: makeUtubDetail({
          id: 61,
          isCoCreator: true,
          members: [
            { id: 2, username: "owner", memberRole: "creator" },
            { id: 3, username: "cofriend", memberRole: "cocreator" },
            { id: 4, username: "regular", memberRole: "member" },
          ],
        }),
      });

      expect(getState().isCoCreator).toBe(true);
      expect(getState().members.map((member) => member.memberRole)).toEqual([
        "creator",
        "cocreator",
        "member",
      ]);
    });

    it("keeps isCoCreator false when the response is not co-creator", () => {
      buildSelectedUTub({
        selectedUTub: makeUtubDetail({ id: 62, isCoCreator: false }),
      });

      expect(getState().isCoCreator).toBe(false);
    });
  });

  describe("mobile landing-panel history", () => {
    it("on mobile, pushes bare { UTubID } then replaces with { UTubID, mobilePanel: 'urls' }", () => {
      mockIsMobile.mockReturnValue(true);
      const pushStateSpy = vi.spyOn(window.history, "pushState");

      buildSelectedUTub({ selectedUTub: makeUtubDetail({ id: 77 }) });

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

      buildSelectedUTub({ selectedUTub: makeUtubDetail({ id: 88 }) });

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
