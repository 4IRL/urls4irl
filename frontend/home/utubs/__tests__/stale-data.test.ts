import { updateUTubOnFindingStaleData } from "../stale-data.js";
import {
  fetchUTubForRefresh,
  buildSelectedUTub,
  makeUTubRoleIcon,
  applyUTubDescriptionVisibility,
} from "../selectors.js";
import type { RefreshResult } from "../selectors.js";
import { removeUTubLocally } from "../remove-local.js";
import { showURLDeckBannerError } from "../../urls/deck.js";
import { showCreateDescriptionButtonAlways } from "../../urls/update-description.js";
import { setState } from "../../../store/app-store.js";
import { emit, AppEvents } from "../../../lib/event-bus.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { isBackgroundRefreshActive } from "../background-refresh-flag.js";
import type { UtubDetail } from "../../../types/utub.js";

import {
  isMobile,
  isCoarsePointer,
  getCurrentMobilePanel,
  setCurrentMobilePanel,
  setMobileUIWhenUTubDeckSelected,
  setMobileUIWhenMemberDeckSelected,
  setMobileUIWhenUTubSelectedOrURLNavSelected,
} from "../../mobile.js";
import {
  bindUTubEditPanelDirtyState,
  unbindUTubEditPanelDirtyState,
} from "../../urls/utub-edit-panel-dirty.js";

const { mockMetricsClient } = await vi.hoisted(
  async () => await import("../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../../mobile.js", () => ({
  isMobile: vi.fn(() => false),
  isCoarsePointer: vi.fn(() => false),
  getCurrentMobilePanel: vi.fn(() => "urls"),
  setCurrentMobilePanel: vi.fn(),
  replaceMobilePanelHistoryState: vi.fn(),
  setMobileUIWhenUTubDeckSelected: vi.fn(),
  setMobileUIWhenMemberDeckSelected: vi.fn(),
  setMobileUIWhenUTubSelectedOrURLNavSelected: vi.fn(),
}));

// The real description helper runs (spied) so the visibility cases exercise it.
vi.mock("../selectors.js", async () => {
  const actual =
    await vi.importActual<typeof import("../selectors.js")>("../selectors.js");
  return {
    ...actual,
    fetchUTubForRefresh: vi.fn(),
    buildSelectedUTub: vi.fn(),
    makeUTubRoleIcon: vi.fn(
      ({ memberRole, isLocked }: { memberRole: string; isLocked: boolean }) =>
        `<svg class="memberRole" data-role="${memberRole}" data-locked="${isLocked}"></svg>`,
    ),
    applyUTubDescriptionVisibility: vi.fn(
      actual.applyUTubDescriptionVisibility,
    ),
  };
});

vi.mock("../deck.js", () => ({
  showUTubLoadingIconAndSetTimeout: vi.fn(() => 0),
  hideUTubLoadingIconAndClearTimeout: vi.fn(),
  setUTubDeckOnUTubSelected: vi.fn(),
}));

vi.mock("../remove-local.js", () => ({ removeUTubLocally: vi.fn() }));

vi.mock("../../urls/deck.js", () => ({ showURLDeckBannerError: vi.fn() }));

vi.mock("../../urls/update-description.js", () => ({
  removeEventListenersForShowCreateUTubDescIfEmptyDesc: vi.fn(),
  showCreateDescriptionButtonAlways: vi.fn(),
}));

vi.mock("../header-fit.js", () => ({ fitUTubHeaderAndSubheader: vi.fn() }));

const storeState = vi.hoisted(() => ({
  value: {} as Record<string, unknown>,
}));

vi.mock("../../../store/app-store.js", () => ({
  getState: vi.fn(() => ({ ...storeState.value })),
  setState: vi.fn((partial: Record<string, unknown>) => {
    Object.assign(storeState.value, partial);
  }),
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

const UTUB_ID = 1;
const CURRENT_USER_ID = 1000;

function makeUrl(
  utubUrlID: number,
  overrides: Partial<UtubDetail["urls"][number]> = {},
): UtubDetail["urls"][number] {
  return {
    utubUrlID,
    urlString: `https://example${utubUrlID}.com`,
    utubUrlTagIDs: [100],
    urlTitle: `Example ${utubUrlID}`,
    canDelete: true,
    addedAt: "2024-01-01T00:00:00+00:00",
    addedByUserID: CURRENT_USER_ID,
    ...overrides,
  };
}

function makeDetail(overrides: Partial<UtubDetail> = {}): UtubDetail {
  return {
    status: "Success",
    id: UTUB_ID,
    name: "My UTub",
    createdByUserID: CURRENT_USER_ID,
    createdAt: "2026-01-01T00:00:00Z",
    description: "Sample description",
    members: [
      { id: CURRENT_USER_ID, username: "alice", memberRole: "creator" },
    ],
    urls: [makeUrl(10)],
    tags: [{ id: 100, tagString: "tag-a", tagApplied: 1 }],
    isCreator: true,
    isCoCreator: false,
    isLocked: false,
    currentUser: CURRENT_USER_ID,
    ...overrides,
  } as UtubDetail;
}

// Seeds the store with content deep-equal to `detail` but distinct references
// (the mid-flight guard compares array references).
function seedStore(
  detail: UtubDetail,
  overrides: Record<string, unknown> = {},
): void {
  storeState.value = {
    activeUTubID: detail.id,
    activeUTubName: detail.name,
    activeUTubDescription: detail.description,
    isCurrentUserOwner: detail.isCreator,
    isCoCreator: detail.isCoCreator,
    isCurrentUTubLocked: detail.isLocked,
    utubOwnerID: detail.createdByUserID,
    urls: structuredClone(detail.urls),
    tags: structuredClone(detail.tags),
    members: structuredClone(detail.members),
    utubs: [
      {
        id: detail.id,
        name: detail.name,
        memberRole: "creator",
        isLocked: detail.isLocked,
      },
    ],
    selectedTagIDs: [],
    ...overrides,
  };
}

function ok(data: UtubDetail): RefreshResult {
  return { kind: "ok", data };
}

async function refreshWith(
  result: RefreshResult,
  options: { isBackgroundRefresh?: boolean; shouldApply?: () => boolean } = {},
): Promise<void> {
  vi.mocked(fetchUTubForRefresh).mockResolvedValue(result);
  await updateUTubOnFindingStaleData({ utubID: UTUB_ID, ...options });
}

function emitsOf(eventName: string): unknown[][] {
  return vi.mocked(emit).mock.calls.filter(([name]) => name === eventName);
}

const DOM = `
  <div id="URLDeckHeader">My UTub</div>
  <div id="URLDeckSubheader">Sample description</div>
  <div id="UTubDescriptionSubheaderWrap" class="hidden"></div>
  <div id="URLDeckNoDescription" class="hidden"></div>
  <button id="URLDeckSubheaderCreateDescription"></button>
  <input id="utubDescriptionUpdate" />
  <span id="URLDeckLockIcon" class="hidden"></span>
  <div id="URLDeckOutcomeAnnouncement"></div>
  <div id="MobilePanelAnnouncement"></div>
  <span class="UTubSelector" utubid="1"><b class="UTubName">My UTub</b><svg class="memberRole" data-role="old"></svg></span>
`;

describe("updateUTubOnFindingStaleData", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(isMobile).mockReturnValue(false);
    vi.mocked(isCoarsePointer).mockReturnValue(false);
    vi.mocked(getCurrentMobilePanel).mockReturnValue("urls");
    document.body.innerHTML = DOM;
    document.body.className = "";
    seedStore(makeDetail());
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe("stale guard, busy re-check and error", () => {
    it.each([
      ["ok", ok(makeDetail({ name: "Renamed" }))],
      ["gone", { kind: "gone" } as RefreshResult],
      ["error", { kind: "error" } as RefreshResult],
    ])(
      "discards a %s outcome when the active UTub changed (guard runs first)",
      async (_label, result) => {
        for (const activeUTubID of [99, null]) {
          vi.clearAllMocks();
          seedStore(makeDetail(), { activeUTubID });
          const shouldApply = vi.fn(() => true);

          await refreshWith(result, { shouldApply });

          expect(removeUTubLocally).not.toHaveBeenCalled();
          expect(showURLDeckBannerError).not.toHaveBeenCalled();
          expect(emit).not.toHaveBeenCalled();
          expect(setState).not.toHaveBeenCalled();
          expect(shouldApply).not.toHaveBeenCalled();
        }
      },
    );

    it("shouldApply returning false discards both ok and gone", async () => {
      await refreshWith(ok(makeDetail({ name: "Renamed" })), {
        shouldApply: () => false,
      });
      await refreshWith({ kind: "gone" }, { shouldApply: () => false });

      expect(emit).not.toHaveBeenCalled();
      expect(removeUTubLocally).not.toHaveBeenCalled();
      expect(setState).not.toHaveBeenCalled();
    });

    it("applies the response when shouldApply is omitted", async () => {
      await refreshWith(ok(makeDetail({ name: "Renamed" })));

      expect(emitsOf(AppEvents.STALE_DATA_DETECTED)).toHaveLength(1);
    });

    it("calls shouldApply only after the stale guard passes", async () => {
      const shouldApply = vi.fn(() => true);

      await refreshWith(ok(makeDetail({ name: "Renamed" })), { shouldApply });

      expect(shouldApply).toHaveBeenCalledTimes(1);
    });

    it("does nothing on error", async () => {
      await expect(refreshWith({ kind: "error" })).resolves.toBeUndefined();

      expect(emit).not.toHaveBeenCalled();
      expect(setState).not.toHaveBeenCalled();
      expect(removeUTubLocally).not.toHaveBeenCalled();
    });
  });

  describe("gone", () => {
    it.each([
      ["desktop", false],
      ["mobile", true],
    ])(
      "removes locally, shows the banner and announces on the next tick (%s)",
      async (_label, mobile) => {
        vi.useFakeTimers();
        vi.mocked(isMobile).mockReturnValue(mobile);

        await refreshWith({ kind: "gone" });

        expect(removeUTubLocally).toHaveBeenCalledWith({ utubID: UTUB_ID });
        expect(showURLDeckBannerError).toHaveBeenCalledWith(
          APP_CONFIG.strings.UTUB_NO_LONGER_AVAILABLE,
        );
        expect(
          vi.mocked(removeUTubLocally).mock.invocationCallOrder[0],
        ).toBeLessThan(
          vi.mocked(showURLDeckBannerError).mock.invocationCallOrder[0],
        );
        expect($("#MobilePanelAnnouncement").text()).toBe("");
        vi.advanceTimersByTime(0);
        expect($("#MobilePanelAnnouncement").text()).toBe(
          APP_CONFIG.strings.UTUB_NO_LONGER_AVAILABLE,
        );
        expect(emit).not.toHaveBeenCalled();
      },
    );

    it("re-announces a second consecutive gone by clearing then re-setting the text", async () => {
      vi.useFakeTimers();
      $("#MobilePanelAnnouncement").text(
        APP_CONFIG.strings.UTUB_NO_LONGER_AVAILABLE,
      );

      await refreshWith({ kind: "gone" });

      expect($("#MobilePanelAnnouncement").text()).toBe("");
      vi.advanceTimersByTime(0);
      expect($("#MobilePanelAnnouncement").text()).toBe(
        APP_CONFIG.strings.UTUB_NO_LONGER_AVAILABLE,
      );
    });
  });

  describe("mid-flight guards", () => {
    function startPendingRefresh(data: UtubDetail): {
      pending: Promise<void>;
      resolveFetch: () => void;
    } {
      let resolveFetch!: () => void;
      vi.mocked(fetchUTubForRefresh).mockReturnValue(
        new Promise<RefreshResult>((resolve) => {
          resolveFetch = () => resolve(ok(data));
        }),
      );
      const pending = updateUTubOnFindingStaleData({ utubID: UTUB_ID });
      return { pending, resolveFetch };
    }

    it.each(["urls", "tags", "members"])(
      "discards an ok when the %s array reference changed mid-flight",
      async (key) => {
        const { pending, resolveFetch } = startPendingRefresh(
          makeDetail({ name: "Renamed" }),
        );
        storeState.value[key] = [...(storeState.value[key] as unknown[])];

        resolveFetch();
        await pending;

        expect(emit).not.toHaveBeenCalled();
        expect(setState).not.toHaveBeenCalled();
      },
    );

    it.each([
      ["activeUTubName", "Renamed locally"],
      ["activeUTubDescription", "Edited locally"],
      ["isCurrentUTubLocked", true],
    ])(
      "discards an ok when %s changed mid-flight (desktop rename race)",
      async (key, value) => {
        const { pending, resolveFetch } = startPendingRefresh(
          makeDetail({ name: "From server" }),
        );
        storeState.value[key] = value;
        $("#URLDeckHeader").text("SENTINEL");

        resolveFetch();
        await pending;

        expect(emit).not.toHaveBeenCalled();
        expect(setState).not.toHaveBeenCalled();
        expect($("#URLDeckHeader").text()).toBe("SENTINEL");
      },
    );
  });

  describe("no-op short-circuit", () => {
    function expectNoOp(): void {
      expect(emit).not.toHaveBeenCalled();
      expect(setState).not.toHaveBeenCalled();
      expect($("#URLDeckHeader").text()).toBe("SENTINEL");
      expect(applyUTubDescriptionVisibility).not.toHaveBeenCalled();
    }

    it("does nothing for a payload deep-equal to the store", async () => {
      $("#URLDeckHeader").text("SENTINEL");

      await refreshWith(ok(makeDetail()));

      expectNoOp();
    });

    it("still short-circuits when keys, arrays and tag IDs are in a different order", async () => {
      const urlA = makeUrl(10, { utubUrlTagIDs: [1, 2, 3] });
      const urlB = makeUrl(11, { utubUrlTagIDs: [4, 5] });
      const tags = [
        { id: 1, tagString: "a", tagApplied: 1 },
        { id: 2, tagString: "b", tagApplied: 1 },
      ];
      const members = [
        { id: 1000, username: "alice", memberRole: "creator" },
        { id: 1001, username: "bob", memberRole: "member" },
      ];
      const payload = makeDetail({ urls: [urlA, urlB], tags, members });
      seedStore(payload, {
        urls: [
          {
            addedByUserID: urlB.addedByUserID,
            addedAt: urlB.addedAt,
            canDelete: urlB.canDelete,
            utubUrlTagIDs: [5, 4],
            urlTitle: urlB.urlTitle,
            urlString: urlB.urlString,
            utubUrlID: urlB.utubUrlID,
          },
          {
            addedByUserID: urlA.addedByUserID,
            addedAt: urlA.addedAt,
            canDelete: urlA.canDelete,
            utubUrlTagIDs: [3, 1, 2],
            urlTitle: urlA.urlTitle,
            urlString: urlA.urlString,
            utubUrlID: urlA.utubUrlID,
          },
        ],
        tags: [...tags].reverse(),
        members: [...members].reverse(),
      });
      $("#URLDeckHeader").text("SENTINEL");

      await refreshWith(ok(payload));

      expectNoOp();
    });

    it("treats a payload whose only difference is URL order as a no-op", async () => {
      const urlA = makeUrl(10);
      const urlB = makeUrl(11);
      seedStore(makeDetail({ urls: [urlA, urlB] }));
      $("#URLDeckHeader").text("SENTINEL");

      await refreshWith(ok(makeDetail({ urls: [urlB, urlA] })));

      expectNoOp();
    });
  });

  describe("diff path", () => {
    it("emits STALE_DATA_DETECTED with urls, tags, members and then calls setState", async () => {
      const payload = makeDetail({
        name: "Renamed",
        urls: [makeUrl(10), makeUrl(11)],
      });

      await refreshWith(ok(payload));

      expect(emit).toHaveBeenCalledWith(AppEvents.STALE_DATA_DETECTED, {
        utubID: UTUB_ID,
        urls: payload.urls,
        tags: payload.tags,
        members: payload.members,
      });
      expect(setState).toHaveBeenCalledWith({
        urls: payload.urls,
        tags: payload.tags,
        members: payload.members,
        activeUTubName: "Renamed",
        activeUTubDescription: payload.description,
      });
      expect(vi.mocked(emit).mock.invocationCallOrder[0]).toBeLessThan(
        vi.mocked(setState).mock.invocationCallOrder[0],
      );
    });

    it("updates #URLDeckHeader and the sidebar .UTubName on a span.UTubSelector", async () => {
      await refreshWith(ok(makeDetail({ name: "Renamed" })));

      expect($("#URLDeckHeader").text()).toBe("Renamed");
      expect($(".UTubSelector[utubid=1] > .UTubName").text()).toBe("Renamed");
    });

    it("syncs the sidebar name and utubs store entry even when the header already matches", async () => {
      $("#URLDeckHeader").text("Renamed");

      await refreshWith(ok(makeDetail({ name: "Renamed" })));

      expect($(".UTubSelector[utubid=1] .UTubName").text()).toBe("Renamed");
      expect(
        (storeState.value.utubs as { id: number; name: string }[])[0].name,
      ).toBe("Renamed");
    });
  });

  describe("description visibility", () => {
    it("empty to non-empty shows the wrap and hides the no-description text", async () => {
      seedStore(makeDetail({ description: "" }));
      $("#UTubDescriptionSubheaderWrap").addClass("hidden");
      $("#URLDeckNoDescription").removeClass("hidden");

      await refreshWith(ok(makeDetail({ description: "Now described" })));

      expect($("#URLDeckSubheader").text()).toBe("Now described");
      expect($("#UTubDescriptionSubheaderWrap").hasClass("hidden")).toBe(false);
      expect($("#URLDeckNoDescription").hasClass("hidden")).toBe(true);
    });

    it("non-empty to empty hides the wrap and shows the no-description text for a non-owner", async () => {
      seedStore(makeDetail({ isCreator: false }));
      $("#UTubDescriptionSubheaderWrap").removeClass("hidden");
      $("#URLDeckNoDescription").addClass("hidden");

      await refreshWith(ok(makeDetail({ isCreator: false, description: "" })));

      expect($("#UTubDescriptionSubheaderWrap").hasClass("hidden")).toBe(true);
      expect($("#URLDeckNoDescription").hasClass("hidden")).toBe(false);
      expect(showCreateDescriptionButtonAlways).not.toHaveBeenCalled();
    });

    it("non-empty to empty shows the create-description button for the owner", async () => {
      await refreshWith(ok(makeDetail({ description: "" })));

      expect(showCreateDescriptionButtonAlways).toHaveBeenCalledWith(UTUB_ID);
      expect($("#UTubDescriptionSubheaderWrap").hasClass("hidden")).toBe(true);
    });

    it("does not call applyUTubDescriptionVisibility when the description is unchanged", async () => {
      await refreshWith(
        ok(makeDetail({ name: "Renamed", urls: [makeUrl(10), makeUrl(11)] })),
      );

      expect(applyUTubDescriptionVisibility).not.toHaveBeenCalled();
    });

    it("calls applyUTubDescriptionVisibility exactly once when the description changed", async () => {
      await refreshWith(ok(makeDetail({ description: "Different" })));

      expect(applyUTubDescriptionVisibility).toHaveBeenCalledTimes(1);
      expect(applyUTubDescriptionVisibility).toHaveBeenCalledWith({
        utubID: UTUB_ID,
        utubDescription: "Different",
        isCurrentUserOwner: true,
      });
    });
  });

  describe("background flag", () => {
    function flagDuringEmit(): { seen: boolean[] } {
      const seen: boolean[] = [];
      vi.mocked(emit).mockImplementation((eventName: string) => {
        if (eventName === AppEvents.STALE_DATA_DETECTED) {
          seen.push(isBackgroundRefreshActive());
        }
      });
      return { seen };
    }

    afterEach(() => {
      vi.mocked(emit).mockReset();
    });

    it("is true during the emit and false after for a background refresh", async () => {
      const { seen } = flagDuringEmit();

      await refreshWith(ok(makeDetail({ name: "Renamed" })), {
        isBackgroundRefresh: true,
      });

      expect(seen).toEqual([true]);
      expect(isBackgroundRefreshActive()).toBe(false);
    });

    it("is false during the emit for a conflict-handler-style call", async () => {
      const { seen } = flagDuringEmit();

      await refreshWith(ok(makeDetail({ name: "Renamed" })));

      expect(seen).toEqual([false]);
    });

    it("is cleared even when a listener throws", async () => {
      vi.mocked(emit).mockImplementation(() => {
        throw new Error("listener boom");
      });

      await expect(
        refreshWith(ok(makeDetail({ name: "Renamed" })), {
          isBackgroundRefresh: true,
        }),
      ).rejects.toThrow("listener boom");

      expect(isBackgroundRefreshActive()).toBe(false);
    });
  });

  describe("lock change", () => {
    beforeEach(() => {
      vi.useFakeTimers();
    });

    it("patches store, body class, lock icon, sidebar entry and icon, and announces the lock", async () => {
      await refreshWith(ok(makeDetail({ isLocked: true })));

      expect(setState).toHaveBeenCalledWith({ isCurrentUTubLocked: true });
      expect($("body").hasClass("utub-locked")).toBe(true);
      expect($("#URLDeckLockIcon").hasClass("hidden")).toBe(false);
      expect(storeState.value.utubs).toEqual([
        { id: UTUB_ID, name: "My UTub", memberRole: "creator", isLocked: true },
      ]);
      expect(makeUTubRoleIcon).toHaveBeenCalledWith({
        memberRole: "creator",
        isLocked: true,
      });
      expect($(".UTubSelector[utubid=1] .memberRole").attr("data-locked")).toBe(
        "true",
      );
      expect($("#URLDeckOutcomeAnnouncement").text()).toBe("");
      vi.advanceTimersByTime(0);
      expect($("#URLDeckOutcomeAnnouncement").text()).toBe(
        APP_CONFIG.strings.UTUB_IS_LOCKED,
      );
    });

    it("announces the unlock with the unlock string", async () => {
      seedStore(makeDetail({ isLocked: true }));
      $("body").addClass("utub-locked");
      $("#URLDeckLockIcon").removeClass("hidden");

      await refreshWith(ok(makeDetail({ isLocked: false })));

      expect($("body").hasClass("utub-locked")).toBe(false);
      expect($("#URLDeckLockIcon").hasClass("hidden")).toBe(true);
      vi.advanceTimersByTime(0);
      expect($("#URLDeckOutcomeAnnouncement").text()).toBe(
        APP_CONFIG.strings.UTUB_UNLOCKED_ANNOUNCEMENT,
      );
    });

    it("re-announces a repeated lock by clearing then re-setting the text", async () => {
      $("#URLDeckOutcomeAnnouncement").text(APP_CONFIG.strings.UTUB_IS_LOCKED);

      await refreshWith(ok(makeDetail({ isLocked: true })));

      expect($("#URLDeckOutcomeAnnouncement").text()).toBe("");
      vi.advanceTimersByTime(0);
      expect($("#URLDeckOutcomeAnnouncement").text()).toBe(
        APP_CONFIG.strings.UTUB_IS_LOCKED,
      );
    });

    it("applies the lock patch and the diff together when a new URL arrives in the same payload", async () => {
      const payload = makeDetail({
        isLocked: true,
        urls: [makeUrl(10), makeUrl(11)],
      });

      await refreshWith(ok(payload));

      expect(setState).toHaveBeenCalledWith({ isCurrentUTubLocked: true });
      expect(emit).toHaveBeenCalledWith(
        AppEvents.STALE_DATA_DETECTED,
        expect.objectContaining({ urls: payload.urls }),
      );
      expect(setState).toHaveBeenCalledWith(
        expect.objectContaining({ urls: payload.urls }),
      );
    });
  });

  describe("onboarding re-evaluation", () => {
    function finalSetStateOrder(): number {
      const index = vi
        .mocked(setState)
        .mock.calls.findIndex(([partial]) => "urls" in partial);
      return vi.mocked(setState).mock.invocationCallOrder[index];
    }

    function emitOrder(eventName: string): number[] {
      return vi
        .mocked(emit)
        .mock.calls.flatMap(([name], index) =>
          name === eventName
            ? [vi.mocked(emit).mock.invocationCallOrder[index]]
            : [],
        );
    }

    it("emits URL_DECK_CHANGED after the final setState when the URL count changed", async () => {
      await refreshWith(ok(makeDetail({ urls: [makeUrl(10), makeUrl(11)] })));

      expect(emitsOf(AppEvents.URL_DECK_CHANGED)).toHaveLength(1);
      expect(emitsOf(AppEvents.MEMBER_DECK_CHANGED)).toHaveLength(0);
      expect(emitsOf(AppEvents.TAG_DECK_CHANGED)).toHaveLength(0);
      expect(emitOrder(AppEvents.URL_DECK_CHANGED)[0]).toBeGreaterThan(
        finalSetStateOrder(),
      );
    });

    it("emits MEMBER_DECK_CHANGED when the member count changed", async () => {
      await refreshWith(
        ok(
          makeDetail({
            members: [
              { id: CURRENT_USER_ID, username: "alice", memberRole: "creator" },
              { id: 1001, username: "bob", memberRole: "member" },
            ],
          }),
        ),
      );

      expect(emitsOf(AppEvents.MEMBER_DECK_CHANGED)).toHaveLength(1);
      expect(emitsOf(AppEvents.URL_DECK_CHANGED)).toHaveLength(0);
      expect(emitOrder(AppEvents.MEMBER_DECK_CHANGED)[0]).toBeGreaterThan(
        finalSetStateOrder(),
      );
    });

    it("emits TAG_DECK_CHANGED when the tag count changed", async () => {
      await refreshWith(
        ok(
          makeDetail({
            tags: [
              { id: 100, tagString: "tag-a", tagApplied: 1 },
              { id: 101, tagString: "tag-b", tagApplied: 0 },
            ],
          }),
        ),
      );

      expect(emitsOf(AppEvents.TAG_DECK_CHANGED)).toHaveLength(1);
      expect(emitOrder(AppEvents.TAG_DECK_CHANGED)[0]).toBeGreaterThan(
        finalSetStateOrder(),
      );
    });

    it("emits all three when all three counts changed", async () => {
      await refreshWith(
        ok(
          makeDetail({
            urls: [makeUrl(10), makeUrl(11)],
            members: [],
            tags: [],
          }),
        ),
      );

      expect(emitsOf(AppEvents.URL_DECK_CHANGED)).toHaveLength(1);
      expect(emitsOf(AppEvents.MEMBER_DECK_CHANGED)).toHaveLength(1);
      expect(emitsOf(AppEvents.TAG_DECK_CHANGED)).toHaveLength(1);
    });

    it("emits none for a content change with equal lengths", async () => {
      await refreshWith(
        ok(makeDetail({ urls: [makeUrl(10, { urlTitle: "Edited title" })] })),
      );

      expect(emitsOf(AppEvents.URL_DECK_CHANGED)).toHaveLength(0);
      expect(emitsOf(AppEvents.MEMBER_DECK_CHANGED)).toHaveLength(0);
      expect(emitsOf(AppEvents.TAG_DECK_CHANGED)).toHaveLength(0);
    });

    it("emits URL_DECK_CHANGED exactly once for a lock-only change", async () => {
      vi.useFakeTimers();

      await refreshWith(ok(makeDetail({ isLocked: true })));

      expect(emitsOf(AppEvents.URL_DECK_CHANGED)).toHaveLength(1);
    });

    it("emits URL_DECK_CHANGED exactly once when lock and URL count both change", async () => {
      vi.useFakeTimers();

      await refreshWith(
        ok(makeDetail({ isLocked: true, urls: [makeUrl(10), makeUrl(11)] })),
      );

      expect(emitsOf(AppEvents.URL_DECK_CHANGED)).toHaveLength(1);
    });

    it("emits none of the three on the permission fallback or on gone", async () => {
      await refreshWith(ok(makeDetail({ isCoCreator: true })));
      await refreshWith({ kind: "gone" });

      expect(emitsOf(AppEvents.URL_DECK_CHANGED)).toHaveLength(0);
      expect(emitsOf(AppEvents.MEMBER_DECK_CHANGED)).toHaveLength(0);
      expect(emitsOf(AppEvents.TAG_DECK_CHANGED)).toHaveLength(0);
    });
  });

  describe("permission change", () => {
    it.each([
      ["isCoCreator", { isCoCreator: true }],
      ["isCreator", { isCreator: false }],
      ["createdByUserID", { createdByUserID: 4242 }],
    ])(
      "falls back to buildSelectedUTub when %s differs from the store",
      async (_label, overrides) => {
        const payload = makeDetail(overrides);

        await refreshWith(ok(payload));

        expect(buildSelectedUTub).toHaveBeenCalledWith(payload);
        expect(emitsOf(AppEvents.STALE_DATA_DETECTED)).toHaveLength(0);
        expect(storeState.value.utubs).toEqual([
          expect.objectContaining({ id: UTUB_ID, isLocked: false }),
        ]);
        expect(makeUTubRoleIcon).toHaveBeenCalled();
      },
    );

    it("falls back when a URL's canDelete flipped", async () => {
      const payload = makeDetail({ urls: [makeUrl(10, { canDelete: false })] });

      await refreshWith(ok(payload));

      expect(buildSelectedUTub).toHaveBeenCalledWith(payload);
      expect(emitsOf(AppEvents.STALE_DATA_DETECTED)).toHaveLength(0);
    });

    it("derives the sidebar role from the current user's member entry", async () => {
      const payload = makeDetail({
        isCreator: false,
        isCoCreator: true,
        createdByUserID: 4242,
        members: [
          { id: CURRENT_USER_ID, username: "alice", memberRole: "co-creator" },
        ],
      });

      await refreshWith(ok(payload));

      expect(makeUTubRoleIcon).toHaveBeenCalledWith({
        memberRole: "co-creator",
        isLocked: false,
      });
    });

    it.each([
      ["members", setMobileUIWhenMemberDeckSelected],
      ["urls", setMobileUIWhenUTubSelectedOrURLNavSelected],
      ["utubs", setMobileUIWhenUTubDeckSelected],
    ] as const)(
      "restores the %s mobile panel after buildSelectedUTub on mobile",
      async (panel, setter) => {
        vi.mocked(isMobile).mockReturnValue(true);
        vi.mocked(getCurrentMobilePanel).mockReturnValue(panel);

        await refreshWith(ok(makeDetail({ isCoCreator: true })));

        expect(setCurrentMobilePanel).toHaveBeenCalledWith({
          mobilePanel: panel,
        });
        expect(setter).toHaveBeenCalledTimes(1);
        expect(
          vi.mocked(buildSelectedUTub).mock.invocationCallOrder[0],
        ).toBeLessThan(
          vi.mocked(setCurrentMobilePanel).mock.invocationCallOrder[0],
        );
      },
    );

    it("calls no mobile setter on desktop", async () => {
      await refreshWith(ok(makeDetail({ isCoCreator: true })));

      expect(setCurrentMobilePanel).not.toHaveBeenCalled();
      expect(setMobileUIWhenMemberDeckSelected).not.toHaveBeenCalled();
      expect(setMobileUIWhenUTubDeckSelected).not.toHaveBeenCalled();
      expect(
        setMobileUIWhenUTubSelectedOrURLNavSelected,
      ).not.toHaveBeenCalled();
    });

    it("takes the diff path for an added URL with canDelete false", async () => {
      const payload = makeDetail({
        urls: [makeUrl(10), makeUrl(11, { canDelete: false })],
      });

      await refreshWith(ok(payload));

      expect(emitsOf(AppEvents.STALE_DATA_DETECTED)).toHaveLength(1);
      expect(buildSelectedUTub).not.toHaveBeenCalled();
    });
  });

  describe("with the mobile UTub edit panel open", () => {
    beforeEach(() => {
      vi.mocked(isCoarsePointer).mockReturnValue(true);
      document.body.innerHTML = `
        ${DOM}
        <input id="utubNameUpdate" value="Old name" />
        <button id="utubNameSubmitBtnUpdate"></button>
        <button id="utubDescriptionSubmitBtnUpdate"></button>
      `;
      // #utubDescriptionUpdate already exists in DOM (no duplicate id).
      $("#utubDescriptionUpdate").val("Old description");
      $("#URLDeckHeader").text("Old name");
      $("#URLDeckSubheader").text("Old description");
      seedStore(
        makeDetail({
          name: "Old name",
          description: "Old description",
          isCreator: false,
        }),
      );
      bindUTubEditPanelDirtyState();
    });

    afterEach(() => {
      unbindUTubEditPanelDirtyState();
    });

    const refreshedUtub = (): UtubDetail =>
      makeDetail({
        name: "Refreshed name",
        description: "Refreshed description",
        isCreator: false,
      });

    it("re-enables the checks when the refreshed stored values now differ from the inputs", async () => {
      expect($("#utubNameSubmitBtnUpdate").attr("aria-disabled")).toBe("true");
      expect($("#utubDescriptionSubmitBtnUpdate").attr("aria-disabled")).toBe(
        "true",
      );

      await refreshWith(ok(refreshedUtub()));

      expect(
        $("#utubNameSubmitBtnUpdate").attr("aria-disabled"),
      ).toBeUndefined();
      expect(
        $("#utubDescriptionSubmitBtnUpdate").attr("aria-disabled"),
      ).toBeUndefined();
    });

    it("disables a check when the refreshed stored value now matches the typed input", async () => {
      $("#utubNameUpdate").val("Refreshed name").trigger("input");
      expect(
        $("#utubNameSubmitBtnUpdate").attr("aria-disabled"),
      ).toBeUndefined();

      await refreshWith(ok(refreshedUtub()));

      expect($("#utubNameSubmitBtnUpdate").attr("aria-disabled")).toBe("true");
    });
  });
});
