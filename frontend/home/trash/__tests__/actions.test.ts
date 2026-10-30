import type {
  TrashList,
  TrashedUrlItem,
  TrashedUtubItem,
} from "../../../types/trash.js";

import {
  createMockJqXHRChainable,
  createMockXhr,
} from "../../../__tests__/helpers/mock-jquery.js";
import { $ } from "../../../lib/globals.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { ajaxCall, is429Handled } from "../../../lib/ajax.js";
import { getState, resetStore, setState } from "../../../store/app-store.js";
import { makeUtubSummaryItem } from "../../../__tests__/helpers/utub-summary.js";
import { buildUTubDeck } from "../../utubs/deck.js";
import { getAllUTubs } from "../../utubs/utils.js";
import {
  getPrefsVersion,
  reseedListPreferences,
  syncDeckOrderToStoreSort,
} from "../../utubs/list-preferences.js";
import { showOutcomeBanner } from "../../urls/outcome-banner.js";
import { TRASH_BANNER_MOUNT } from "../banner.js";
import { refreshTrashCount, renderTrashCount } from "../count.js";
import { loadTrashList } from "../list.js";
import { isTrashOpen } from "../panel.js";
import { renderTrashList, updateEmptyTrashButton } from "../render.js";
import {
  handleTrashTabClick,
  onTrashTabChanged,
  _resetTrashTabsForTests,
} from "../tabs.js";
import {
  confirmAndEmptyTrash,
  focusAfterRowRemoval,
  handleTrashActionFailure,
  initTrashActions,
  restoreTrashedURL,
  restoreTrashedUTub,
} from "../actions.js";
import {
  armTrashClickSuppression,
  clearTrashClickSuppression,
} from "../swipe-click-guard.js";

vi.mock("../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));

vi.mock("../../utubs/deck.js", () => ({ buildUTubDeck: vi.fn() }));
vi.mock("../../utubs/utils.js", () => ({ getAllUTubs: vi.fn() }));
vi.mock("../../utubs/list-preferences.js", () => ({
  getPrefsVersion: vi.fn(() => 0),
  reseedListPreferences: vi.fn(),
  syncDeckOrderToStoreSort: vi.fn(),
}));
vi.mock("../count.js", () => ({
  beginCountRequest: vi.fn(() => () => true),
  refreshTrashCount: vi.fn(() => Promise.resolve()),
  renderTrashCount: vi.fn(),
}));
vi.mock("../list.js", () => ({
  loadTrashList: vi.fn(() => Promise.resolve()),
}));
vi.mock("../panel.js", () => ({
  isTrashOpen: vi.fn(() => true),
}));
vi.mock("../../urls/outcome-banner.js", () => ({
  showOutcomeBanner: vi.fn(),
  buildReviveMessage: vi.fn(
    ({ lostTagCount }: { lostTagCount: number }) => `revived:${lostTagCount}`,
  ),
  buildLostTagNamesDetail: vi.fn(
    ({ lostTagNames }: { lostTagNames: readonly string[] }) =>
      lostTagNames.length > 0 ? lostTagNames.join(", ") : undefined,
  ),
}));

const NOW = Date.parse("2026-10-16T12:00:00Z");
const DAY = 86_400_000;
const LISTED_AT = new Date(NOW).toISOString();

function isoFromNow({ days }: { days: number }): string {
  return new Date(NOW + days * DAY).toISOString();
}

function makeUrlItem(overrides: Partial<TrashedUrlItem> = {}): TrashedUrlItem {
  return {
    utubUrlID: 11,
    urlString: "https://example.com/a",
    urlTitle: "Example A",
    utubID: 3,
    utubName: "Reading List",
    originUtubTrashed: false,
    originUtubLocked: false,
    trashedWithUtub: false,
    deletedAt: isoFromNow({ days: -2 }),
    expiresAt: isoFromNow({ days: 20 }),
    deletedByUserID: 9,
    deletedByUsername: "mcarter",
    addedByUserID: 9,
    addedByUsername: "mcarter",
    canRestore: true,
    canDelete: true,
    ...overrides,
  } as TrashedUrlItem;
}

function makeUtubItem(
  overrides: Partial<TrashedUtubItem> = {},
): TrashedUtubItem {
  return {
    utubID: 4,
    utubName: "Work Archive",
    utubDescription: null,
    deletedAt: isoFromNow({ days: -5 }),
    expiresAt: isoFromNow({ days: 25 }),
    deletedByUserID: 5,
    deletedByUsername: "me",
    urlCount: 12,
    memberCount: 3,
    isLocked: false,
    canRestore: true,
    canDelete: true,
    ...overrides,
  };
}

function makeList(overrides: Partial<TrashList> = {}): TrashList {
  return {
    urls: [],
    utubs: [],
    currentUser: 5,
    retentionDays: 30,
    listedAt: LISTED_AT,
    ...overrides,
  } as TrashList;
}

const HTML = `
  <div id="TrashPanel" tabindex="-1">
    <div id="TrashTablist" role="tablist">
      <button id="TrashTabUrls" role="tab" aria-selected="true" tabindex="0"></button>
      <button id="TrashTabUtubs" role="tab" aria-selected="false" tabindex="-1"></button>
    </div>
    <button id="TrashBtnEmpty"></button>
    <p id="TrashRetentionNotice" class="hidden"></p>
    <div id="TrashOutcomeBanner"></div>
    <div id="TrashPanelUrls" role="tabpanel">
      <div id="listTrashURLs"></div>
      <p id="TrashUrlsEmptyState" class="hidden" tabindex="-1"></p>
    </div>
    <div id="TrashPanelUtubs" role="tabpanel" hidden>
      <div id="listTrashUTubs"></div>
      <p id="TrashUtubsEmptyState" class="hidden" tabindex="-1"></p>
    </div>
  </div>
  <div id="confirmModal">
    <div id="confirmModalTitle"></div>
    <div id="confirmModalBody"></div>
    <button id="modalDismiss"></button>
    <button id="modalSubmit"></button>
    <button id="modalRedirect"></button>
  </div>
`;

const URL_ITEMS = [
  makeUrlItem({ utubUrlID: 11, urlTitle: "First" }),
  makeUrlItem({ utubUrlID: 12, urlTitle: "Second" }),
  makeUrlItem({ utubUrlID: 13, urlTitle: "Third" }),
];

let modalSpy: ReturnType<typeof vi.fn>;

type MockXhrHandlers = {
  done?: unknown;
  fail?: unknown;
};

/** An already-settled request: runs `done` or `fail` synchronously, then `always`. */
function settled({ done, fail }: MockXhrHandlers): JQuery.jqXHR {
  return createMockJqXHRChainable({
    done: (callback) => {
      if (done !== undefined) (callback as (arg: unknown) => void)(done);
    },
    fail: (callback) => {
      if (fail !== undefined) (callback as (arg: unknown) => void)(fail);
    },
    always: (callback) => (callback as () => void)(),
  });
}

function pending(): JQuery.jqXHR {
  return createMockJqXHRChainable();
}

function renderRows(overrides: Partial<TrashList> = {}): void {
  renderTrashList({ list: makeList({ urls: URL_ITEMS, ...overrides }) });
}

function rowFor(utubUrlID: number): JQuery {
  return $(`#listTrashURLs .trashRow[data-utub-url-id="${utubUrlID}"]`);
}

function bannerCall(): Record<string, unknown> {
  const calls = vi.mocked(showOutcomeBanner).mock.calls;
  return calls[calls.length - 1][0] as Record<string, unknown>;
}

function failXhr(props: Record<string, unknown>): JQuery.jqXHR {
  return createMockXhr({
    getResponseHeader: vi.fn(() => "application/json"),
    ...props,
  });
}

describe("trash actions", () => {
  beforeEach(() => {
    document.body.innerHTML = HTML;
    resetStore();
    vi.clearAllMocks();
    vi.mocked(is429Handled).mockReturnValue(false);
    vi.mocked(isTrashOpen).mockReturnValue(true);
    modalSpy = vi.fn().mockReturnThis();
    ($.fn as unknown as Record<string, unknown>).modal = modalSpy;
    initTrashActions();
  });

  afterEach(() => {
    $("#listTrashURLs, #listTrashUTubs, #TrashBtnEmpty").off(".trashActions");
    $("#modalSubmit, #modalDismiss, #confirmModal").off();
    _resetTrashTabsForTests();
    clearTrashClickSuppression();
    vi.restoreAllMocks();
  });

  describe("in-place URL restore", () => {
    it("posts the destUtubId key with no confirm modal, removes the row and announces it", async () => {
      renderRows();
      vi.mocked(ajaxCall).mockReturnValue(
        settled({ done: { lostTagCount: 0, restoredToDestination: false } }),
      );

      rowFor(12).find(".trashBtnRestore").trigger("click");
      await Promise.resolve();

      expect(ajaxCall).toHaveBeenCalledTimes(1);
      const [method, url, data] = vi.mocked(ajaxCall).mock.calls[0];
      expect(method).toBe("post");
      expect(url).toBe(APP_CONFIG.routes.restoreURL(3, 12));
      // The key must be present even when undefined: a literal {} would make
      // ajaxCall send no JSON body at all.
      expect(Object.keys(data as object)).toEqual(["destUtubId"]);
      expect((data as { destUtubId?: number }).destUtubId).toBeUndefined();
      expect(modalSpy).not.toHaveBeenCalled();

      expect(rowFor(12)).toHaveLength(0);
      expect($("#TrashTabUrls").text()).toBe("URLs (2)");
      expect(showOutcomeBanner).toHaveBeenCalledWith({
        mount: TRASH_BANNER_MOUNT,
        variant: "success",
        message: "revived:0",
        detail: undefined,
        returnFocusTo: expect.anything(),
      });
      expect(refreshTrashCount).toHaveBeenCalledTimes(1);
    });

    it("raises the row URL count by one when restored into the open UTub", async () => {
      renderRows();
      setState({
        activeUTubID: 3,
        utubs: [makeUtubSummaryItem({ id: 3, urlCount: 4 })],
      });
      vi.mocked(ajaxCall).mockReturnValue(
        settled({ done: { lostTagCount: 0, restoredToDestination: false } }),
      );

      await restoreTrashedURL({ utubID: 3, utubUrlID: 11 });

      expect(getState().utubs[0].urlCount).toBe(5);
    });

    it("raises the row URL count even though Trash cleared the active UTub", async () => {
      renderRows();
      setState({
        activeUTubID: null,
        utubs: [makeUtubSummaryItem({ id: 3, urlCount: 4 })],
      });
      vi.mocked(ajaxCall).mockReturnValue(
        settled({ done: { lostTagCount: 0, restoredToDestination: false } }),
      );

      await restoreTrashedURL({ utubID: 3, utubUrlID: 11 });

      expect(getState().utubs[0].urlCount).toBe(5);
    });

    it("raises only the destination row when destUtubID is given", async () => {
      renderRows();
      setState({
        activeUTubID: 4,
        utubs: [
          makeUtubSummaryItem({ id: 3, urlCount: 4 }),
          makeUtubSummaryItem({ id: 4, urlCount: 6 }),
        ],
      });
      vi.mocked(ajaxCall).mockReturnValue(
        settled({
          done: {
            lostTagCount: 0,
            restoredToDestination: true,
            utubName: "Work Archive",
          },
        }),
      );

      await restoreTrashedURL({ utubID: 3, utubUrlID: 11, destUtubID: 4 });

      expect(getState().utubs.map((utub) => utub.urlCount)).toEqual([4, 7]);
    });

    it("raises the destination row, not the origin, when destUtubID is not the open UTub", async () => {
      renderRows();
      setState({
        activeUTubID: 3,
        utubs: [
          makeUtubSummaryItem({ id: 3, urlCount: 4 }),
          makeUtubSummaryItem({ id: 4, urlCount: 6 }),
        ],
      });
      vi.mocked(ajaxCall).mockReturnValue(
        settled({
          done: {
            lostTagCount: 0,
            restoredToDestination: true,
            utubName: "Work Archive",
          },
        }),
      );

      await restoreTrashedURL({ utubID: 3, utubUrlID: 11, destUtubID: 4 });

      expect(getState().utubs.map((utub) => utub.urlCount)).toEqual([4, 7]);
    });

    it("uses the partial variant when tags were lost", async () => {
      renderRows();
      vi.mocked(ajaxCall).mockReturnValue(
        settled({ done: { lostTagCount: 2, restoredToDestination: false } }),
      );

      await restoreTrashedURL({ utubID: 3, utubUrlID: 11 });

      expect(bannerCall().variant).toBe("partial");
      expect(bannerCall().message).toBe("revived:2");
      expect(bannerCall().detail).toBeUndefined();
    });

    it("names the lost tags on a second line", async () => {
      renderRows();
      vi.mocked(ajaxCall).mockReturnValue(
        settled({
          done: {
            lostTagCount: 2,
            lostTagNames: ["Tool", "Art"],
            restoredToDestination: false,
          },
        }),
      );

      await restoreTrashedURL({ utubID: 3, utubUrlID: 11 });

      expect(bannerCall().variant).toBe("partial");
      expect(bannerCall().detail).toBe("Tool, Art");
    });

    it("shows no detail when no tags were lost", async () => {
      renderRows();
      vi.mocked(ajaxCall).mockReturnValue(
        settled({
          done: {
            lostTagCount: 0,
            lostTagNames: [],
            restoredToDestination: false,
          },
        }),
      );

      await restoreTrashedURL({ utubID: 3, utubUrlID: 11 });

      expect(bannerCall().detail).toBeUndefined();
    });

    it("says where a destination restore landed and never reports lost tags", async () => {
      renderRows();
      vi.mocked(ajaxCall).mockReturnValue(
        settled({
          done: {
            lostTagCount: 3,
            lostTagNames: ["Tool"],
            restoredToDestination: true,
            utubName: "Inbox",
          },
        }),
      );

      await restoreTrashedURL({ utubID: 3, utubUrlID: 11, destUtubID: 8 });

      expect(vi.mocked(ajaxCall).mock.calls[0][2]).toEqual({ destUtubId: 8 });
      expect(bannerCall().message).toBe("Restored to Inbox.");
      expect(bannerCall().variant).toBe("success");
      expect(bannerCall().detail).toBeUndefined();
    });

    it("opens the destination picker instead of posting for an origin-trashed row", () => {
      renderRows({
        urls: [makeUrlItem({ utubUrlID: 21, originUtubTrashed: true })],
      });

      rowFor(21).find(".trashBtnRestore").trigger("click");

      expect(ajaxCall).not.toHaveBeenCalled();
      expect($("#listTrashURLs .trashDestinationPicker")).toHaveLength(1);
    });
  });

  describe("UTub restore", () => {
    it("posts, rebuilds the deck from one GET /utubs and reloads the list", async () => {
      renderTrashList({ list: makeList({ utubs: [makeUtubItem()] }) });
      vi.mocked(ajaxCall).mockReturnValue(
        settled({ done: { utubName: "Work Archive" } }),
      );
      const utubs = [{ id: 4, name: "Work Archive" }];
      vi.mocked(getAllUTubs).mockReturnValue(
        settled({ done: { utubs, trashCount: 7 } }) as never,
      );

      $("#listTrashUTubs .trashBtnRestore").trigger("click");
      await vi.waitFor(() => expect(loadTrashList).toHaveBeenCalled());

      expect(ajaxCall).toHaveBeenCalledWith(
        "post",
        APP_CONFIG.routes.restoreUTub(4),
        null,
      );
      expect(bannerCall().message).toBe("Restored Work Archive.");
      expect(buildUTubDeck).toHaveBeenCalledWith(utubs);
      expect(getState().trashCount).toBe(7);
      expect(renderTrashCount).toHaveBeenCalledTimes(1);
      expect(refreshTrashCount).not.toHaveBeenCalled();
    });

    it("captures the prefs version before the GET, reseeds before the build and syncs the order after", async () => {
      renderTrashList({ list: makeList({ utubs: [makeUtubItem()] }) });
      vi.mocked(ajaxCall).mockReturnValue(
        settled({ done: { utubName: "Work Archive" } }),
      );
      vi.mocked(getPrefsVersion).mockReturnValue(3);
      const preferences = { utubSort: "name_az" };
      vi.mocked(getAllUTubs).mockReturnValue(
        settled({
          done: { utubs: [], trashCount: 1, preferences },
        }) as never,
      );

      $("#listTrashUTubs .trashBtnRestore").trigger("click");
      await vi.waitFor(() =>
        expect(syncDeckOrderToStoreSort).toHaveBeenCalled(),
      );

      expect(
        vi.mocked(getPrefsVersion).mock.invocationCallOrder[0],
      ).toBeLessThan(vi.mocked(getAllUTubs).mock.invocationCallOrder[0]);
      expect(reseedListPreferences).toHaveBeenCalledWith({
        preferences,
        capturedVersion: 3,
      });
      expect(
        vi.mocked(reseedListPreferences).mock.invocationCallOrder[0],
      ).toBeLessThan(vi.mocked(buildUTubDeck).mock.invocationCallOrder[0]);
      expect(vi.mocked(buildUTubDeck).mock.invocationCallOrder[0]).toBeLessThan(
        vi.mocked(syncDeckOrderToStoreSort).mock.invocationCallOrder[0],
      );
      expect(syncDeckOrderToStoreSort).toHaveBeenCalledWith({
        responseSort: "name_az",
      });
    });
  });

  describe("Delete forever", () => {
    it("URL: confirms in the shared modal, then deletes and announces", async () => {
      renderRows();
      vi.mocked(ajaxCall).mockReturnValue(
        settled({ done: { utubID: 3, utubUrlID: 12 } }),
      );

      rowFor(12).find(".trashBtnPurge").trigger("click");

      expect(ajaxCall).not.toHaveBeenCalled();
      expect($("#confirmModalTitle").text()).toBe(
        APP_CONFIG.strings.TRASH_CONFIRM_PURGE_TITLE,
      );
      expect($("#confirmModalBody").text()).toContain("Second");
      expect(modalSpy).toHaveBeenCalledWith("show");

      $("#modalSubmit").trigger("click");

      expect(ajaxCall).toHaveBeenCalledWith(
        "delete",
        APP_CONFIG.routes.purgeURL(3, 12),
        [],
      );
      expect(modalSpy).toHaveBeenCalledWith("hide");
      expect(rowFor(12)).toHaveLength(0);
      expect(bannerCall().message).toBe(APP_CONFIG.strings.TRASH_URL_PURGED);
      expect(refreshTrashCount).toHaveBeenCalledTimes(1);
    });

    it("URL: cancel sends nothing", () => {
      renderRows();

      rowFor(11).find(".trashBtnPurge").trigger("click");
      $("#modalDismiss").trigger("click");

      expect(ajaxCall).not.toHaveBeenCalled();
      expect(modalSpy).toHaveBeenLastCalledWith("hide");
    });

    it("UTub: names the URL count, deletes, then reloads the list", async () => {
      renderTrashList({ list: makeList({ utubs: [makeUtubItem()] }) });
      vi.mocked(ajaxCall).mockReturnValue(
        settled({ done: { utubName: "Work Archive" } }),
      );

      $("#listTrashUTubs .trashBtnPurge").trigger("click");
      expect($("#confirmModalBody").text()).toContain("12 URLs");
      $("#modalSubmit").trigger("click");
      await vi.waitFor(() => expect(loadTrashList).toHaveBeenCalled());

      expect(ajaxCall).toHaveBeenCalledWith(
        "delete",
        APP_CONFIG.routes.purgeUTub(4),
        [],
      );
      expect(bannerCall().message).toBe("Deleted Work Archive forever.");
      expect(refreshTrashCount).toHaveBeenCalledTimes(1);
    });
  });

  describe("Purge UTub singular copy", () => {
    it("says '1 URL' when the UTub holds exactly one URL", () => {
      renderTrashList({
        list: makeList({ utubs: [makeUtubItem({ urlCount: 1 })] }),
      });

      $("#listTrashUTubs .trashBtnPurge").trigger("click");

      expect($("#confirmModalBody").text()).toContain("its 1 URL will be");
    });
  });

  describe("Empty trash", () => {
    it("counts only deletable rows, forwards listedAt verbatim and reports skipped locks", async () => {
      renderRows({
        urls: [...URL_ITEMS, makeUrlItem({ utubUrlID: 14, canDelete: false })],
      });
      vi.mocked(ajaxCall).mockReturnValue(
        settled({ done: { totalPurged: 3, totalSkippedLocked: 1 } }),
      );

      confirmAndEmptyTrash();
      expect($("#confirmModalBody").text()).toBe(
        "Permanently delete 3 URLs? This can't be undone.",
      );
      $("#modalSubmit").trigger("click");
      await vi.waitFor(() => expect(loadTrashList).toHaveBeenCalled());

      expect(ajaxCall).toHaveBeenCalledWith(
        "post",
        APP_CONFIG.routes.emptyTrash,
        { scope: "urls", listedAt: LISTED_AT },
        expect.any(Number),
      );
      expect(bannerCall().variant).toBe("partial");
      expect(bannerCall().message).toBe("3 items deleted forever.");
      expect(bannerCall().detail).toBe("1 locked item was kept.");
      expect(refreshTrashCount).toHaveBeenCalledTimes(1);
    });

    it("uses the UTubs body and scope on the UTubs tab, and success when nothing was skipped", async () => {
      renderTrashList({ list: makeList({ utubs: [makeUtubItem()] }) });
      // The panel registers this in production; the button is native-disabled
      // (nothing to empty on the URLs tab) until the tab change re-evaluates it.
      onTrashTabChanged(() => updateEmptyTrashButton());
      handleTrashTabClick({ tabId: "TrashTabUtubs" });
      vi.mocked(ajaxCall).mockReturnValue(
        settled({ done: { totalPurged: 1, totalSkippedLocked: 0 } }),
      );

      $("#TrashBtnEmpty").trigger("click");
      expect($("#confirmModalBody").text()).toBe(
        "Permanently delete 1 UTub and its URLs? This can't be undone.",
      );
      $("#modalSubmit").trigger("click");
      await vi.waitFor(() => expect(loadTrashList).toHaveBeenCalled());

      expect(vi.mocked(ajaxCall).mock.calls[0][2]).toEqual({
        scope: "utubs",
        listedAt: LISTED_AT,
      });
      expect(bannerCall().variant).toBe("success");
      expect(bannerCall().message).toBe("1 item deleted forever.");
      expect(bannerCall().detail).toBeUndefined();
    });

    it("uses singular copy for exactly one deletable URL and one purged item", async () => {
      renderRows({ urls: [makeUrlItem({ utubUrlID: 11 })] });
      vi.mocked(ajaxCall).mockReturnValue(
        settled({ done: { totalPurged: 1, totalSkippedLocked: 1 } }),
      );

      confirmAndEmptyTrash();
      expect($("#confirmModalBody").text()).toBe(
        "Permanently delete 1 URL? This can't be undone.",
      );
      $("#modalSubmit").trigger("click");
      await vi.waitFor(() => expect(loadTrashList).toHaveBeenCalled());

      expect(bannerCall().message).toBe("1 item deleted forever.");
      expect(bannerCall().detail).toBe("1 locked item was kept.");
    });
  });

  describe("focus after a row leaves", () => {
    beforeEach(() => renderRows());

    it("focuses the row that took the removed row's place", () => {
      rowFor(12).remove();
      focusAfterRowRemoval({ scope: "urls", removedIndex: 1 });
      expect(document.activeElement).toBe(rowFor(13)[0]);
    });

    it("focuses the previous row when the last one left", () => {
      rowFor(13).remove();
      focusAfterRowRemoval({ scope: "urls", removedIndex: 2 });
      expect(document.activeElement).toBe(rowFor(12)[0]);
    });

    it("focuses the empty-state container when none remain", () => {
      $("#listTrashURLs").empty();
      focusAfterRowRemoval({ scope: "urls", removedIndex: 0 });
      expect(document.activeElement).toBe($("#TrashUrlsEmptyState")[0]);
    });

    it("moves focus on a successful row restore", async () => {
      vi.mocked(ajaxCall).mockReturnValue(
        settled({ done: { lostTagCount: 0, restoredToDestination: false } }),
      );
      await restoreTrashedURL({ utubID: 3, utubUrlID: 11 });
      expect(document.activeElement).toBe(rowFor(12)[0]);
    });
  });

  describe("failures", () => {
    it("returns early for a handled 429", () => {
      vi.mocked(is429Handled).mockReturnValue(true);
      const assign = vi.fn();
      vi.spyOn(window, "location", "get").mockReturnValue({
        assign,
      } as unknown as Location);

      handleTrashActionFailure({
        xhr: failXhr({ status: 429 }),
        domain: "url",
      });

      expect(assign).not.toHaveBeenCalled();
      expect(showOutcomeBanner).not.toHaveBeenCalled();
    });

    it("a locked UTub hides the modal, warns, and reloads so the row renders disabled", () => {
      handleTrashActionFailure({
        xhr: failXhr({
          status: 403,
          responseJSON: { message: APP_CONFIG.strings.UTUB_IS_LOCKED },
        }),
        domain: "url",
      });

      expect(modalSpy).toHaveBeenCalledWith("hide");
      expect(bannerCall().variant).toBe("partial");
      expect(bannerCall().message).toBe(APP_CONFIG.strings.TRASH_LOCKED);
      expect(loadTrashList).toHaveBeenCalledTimes(1);
    });

    it.each([
      { domain: "url" as const, errorCode: 11 },
      { domain: "utub" as const, errorCode: 4 },
    ])(
      "a $domain not-in-trash 404 warns, reloads and refreshes the count",
      ({ domain, errorCode }) => {
        handleTrashActionFailure({
          xhr: failXhr({ status: 404, responseJSON: { errorCode } }),
          domain,
        });

        expect(bannerCall().message).toBe(
          APP_CONFIG.strings.TRASH_NOT_IN_TRASH,
        );
        expect(loadTrashList).toHaveBeenCalledTimes(1);
        expect(refreshTrashCount).toHaveBeenCalledTimes(1);
      },
    );

    it("redirects to the error page for a bare 404 and for other failures", () => {
      const assign = vi.fn();
      vi.spyOn(window, "location", "get").mockReturnValue({
        assign,
      } as unknown as Location);

      handleTrashActionFailure({
        xhr: failXhr({ status: 404 }),
        domain: "url",
      });
      handleTrashActionFailure({
        xhr: failXhr({ status: 404, responseJSON: { errorCode: 4 } }),
        domain: "url",
      });
      handleTrashActionFailure({
        xhr: failXhr({ status: 500 }),
        domain: "utub",
      });

      expect(assign).toHaveBeenCalledTimes(3);
      expect(assign).toHaveBeenCalledWith(APP_CONFIG.routes.errorPage);
    });

    it("replaces the page for a CSRF 403 html response", () => {
      handleTrashActionFailure({
        xhr: failXhr({
          status: 403,
          responseText: "<p>csrf</p>",
          getResponseHeader: vi.fn(() => "text/html; charset=utf-8"),
        }),
        domain: "url",
      });

      expect(document.body.innerHTML).toContain("csrf");
    });

    it("re-enables the row after a failed restore", async () => {
      renderRows();
      vi.mocked(ajaxCall).mockReturnValue(
        settled({ fail: failXhr({ status: 429 }) }),
      );
      vi.mocked(is429Handled).mockReturnValue(true);

      await restoreTrashedURL({ utubID: 3, utubUrlID: 11 });

      const button = rowFor(11).find(".trashBtnRestore");
      expect(button.attr("aria-disabled")).toBeUndefined();
      expect(button.hasClass("disabled")).toBe(false);
    });
  });

  describe("restoreTrashedURL resolution", () => {
    beforeEach(() => renderRows());

    it("resolves true when the row was removed", async () => {
      vi.mocked(ajaxCall).mockReturnValue(
        settled({ done: { lostTagCount: 0, restoredToDestination: false } }),
      );

      await expect(
        restoreTrashedURL({ utubID: 3, utubUrlID: 11 }),
      ).resolves.toBe(true);
      expect(rowFor(11)).toHaveLength(0);
    });

    it.each([
      { name: "403 locked", status: 403, responseJSON: undefined },
      {
        name: "404 not in Trash",
        status: 404,
        responseJSON: { errorCode: 11 },
      },
      { name: "network failure", status: 0, responseJSON: undefined },
    ])("resolves false on $name and keeps the row", async (fixture) => {
      vi.spyOn(window, "location", "get").mockReturnValue({
        assign: vi.fn(),
      } as unknown as Location);
      vi.mocked(ajaxCall).mockReturnValue(
        settled({
          fail: failXhr({
            status: fixture.status,
            responseJSON:
              fixture.status === 403
                ? { message: APP_CONFIG.strings.UTUB_IS_LOCKED }
                : fixture.responseJSON,
          }),
        }),
      );

      await expect(
        restoreTrashedURL({ utubID: 3, utubUrlID: 11 }),
      ).resolves.toBe(false);
      expect(rowFor(11)).toHaveLength(1);
    });
  });

  describe("400 URL_DESTINATION_REQUIRED on an in-place restore", () => {
    beforeEach(() => renderRows());

    it.each([
      { name: "swipe call shape", viaSwipe: true },
      { name: "plain tap call shape", viaSwipe: false },
    ])(
      "reloads the list, warns with the origin-unavailable copy and resolves false ($name)",
      async ({ viaSwipe }) => {
        const assign = vi.fn();
        vi.spyOn(window, "location", "get").mockReturnValue({
          assign,
        } as unknown as Location);
        vi.mocked(ajaxCall).mockReturnValue(
          settled({
            fail: failXhr({ status: 400, responseJSON: { errorCode: 12 } }),
          }),
        );

        const restored = await restoreTrashedURL({
          utubID: 3,
          utubUrlID: 11,
          destUtubID: undefined,
          viaSwipe,
        });

        expect(restored).toBe(false);
        expect(loadTrashList).toHaveBeenCalledTimes(1);
        expect(bannerCall().variant).toBe("partial");
        expect(bannerCall().message).toBe(
          APP_CONFIG.strings.TRASH_ORIGIN_UNAVAILABLE,
        );
        expect(assign).not.toHaveBeenCalled();
      },
    );

    it("a desktop tap on the Restore button takes the same path", async () => {
      const assign = vi.fn();
      vi.spyOn(window, "location", "get").mockReturnValue({
        assign,
      } as unknown as Location);
      vi.mocked(ajaxCall).mockReturnValue(
        settled({
          fail: failXhr({ status: 400, responseJSON: { errorCode: 12 } }),
        }),
      );

      rowFor(11).find(".trashBtnRestore").trigger("click");
      await Promise.resolve();

      expect(loadTrashList).toHaveBeenCalledTimes(1);
      expect(assign).not.toHaveBeenCalled();
    });

    it("a 400 with a different errorCode still redirects to the error page", async () => {
      const assign = vi.fn();
      vi.spyOn(window, "location", "get").mockReturnValue({
        assign,
      } as unknown as Location);
      vi.mocked(ajaxCall).mockReturnValue(
        settled({
          fail: failXhr({ status: 400, responseJSON: { errorCode: 99 } }),
        }),
      );

      await expect(
        restoreTrashedURL({ utubID: 3, utubUrlID: 11, viaSwipe: true }),
      ).resolves.toBe(false);

      expect(assign).toHaveBeenCalledWith(APP_CONFIG.routes.errorPage);
      expect(loadTrashList).not.toHaveBeenCalled();
    });
  });

  describe("stale completion after Trash closed (DD-25)", () => {
    function deferredXhr(): {
      xhr: JQuery.jqXHR;
      resolve: (response: unknown) => void;
      reject: (xhr: JQuery.jqXHR) => void;
    } {
      const handlers: {
        done: Array<(arg: unknown) => void>;
        fail: Array<(arg: unknown) => void>;
        always: Array<() => void>;
      } = { done: [], fail: [], always: [] };
      const xhr = createMockJqXHRChainable({
        done: (callback) => handlers.done.push(callback as never),
        fail: (callback) => handlers.fail.push(callback as never),
        always: (callback) => handlers.always.push(callback as never),
      });
      return {
        xhr,
        resolve: (response) => {
          handlers.done.forEach((callback) => callback(response));
          handlers.always.forEach((callback) => callback());
        },
        reject: (failed) => {
          handlers.fail.forEach((callback) => callback(failed));
          handlers.always.forEach((callback) => callback());
        },
      };
    }

    function expectSilent(): void {
      expect(showOutcomeBanner).not.toHaveBeenCalled();
      expect(document.activeElement).toBe(document.body);
    }

    beforeEach(() => {
      renderRows({ utubs: [makeUtubItem()] });
      (document.activeElement as HTMLElement | null)?.blur();
    });

    it("restoreTrashedURL removes the row and counts, but writes no banner and moves no focus", async () => {
      const request = deferredXhr();
      vi.mocked(ajaxCall).mockReturnValue(request.xhr);

      const pendingRestore = restoreTrashedURL({ utubID: 3, utubUrlID: 11 });
      vi.mocked(isTrashOpen).mockReturnValue(false);
      request.resolve({ lostTagCount: 0, restoredToDestination: false });

      await expect(pendingRestore).resolves.toBe(true);
      expect(rowFor(11)).toHaveLength(0);
      expect(refreshTrashCount).toHaveBeenCalledTimes(1);
      expectSilent();
    });

    it("restoreTrashedUTub skips the list reload but still refreshes the deck and count", async () => {
      const request = deferredXhr();
      vi.mocked(ajaxCall).mockReturnValue(request.xhr);
      vi.mocked(getAllUTubs).mockReturnValue(
        settled({ done: { utubs: [], trashCount: 2 } }) as never,
      );

      const pendingRestore = restoreTrashedUTub({ utubID: 4 });
      vi.mocked(isTrashOpen).mockReturnValue(false);
      request.resolve({ utubName: "Work Archive" });
      await pendingRestore;
      await vi.waitFor(() => expect(getState().trashCount).toBe(2));
      await Promise.resolve();
      await Promise.resolve();

      expect(buildUTubDeck).toHaveBeenCalled();
      expect(getState().trashCount).toBe(2);
      expect(loadTrashList).not.toHaveBeenCalled();
      expectSilent();
    });

    it("purgeURL removes the row and counts, silently", () => {
      const request = deferredXhr();
      vi.mocked(ajaxCall).mockReturnValue(request.xhr);

      rowFor(12).find(".trashBtnPurge").trigger("click");
      $("#modalSubmit").trigger("click");
      vi.mocked(isTrashOpen).mockReturnValue(false);
      request.resolve({ utubID: 3, utubUrlID: 12 });

      expect(rowFor(12)).toHaveLength(0);
      expect(refreshTrashCount).toHaveBeenCalledTimes(1);
      expectSilent();
    });

    it("purgeUTub skips the reload but still counts, silently", async () => {
      const request = deferredXhr();
      vi.mocked(ajaxCall).mockReturnValue(request.xhr);

      $("#listTrashUTubs .trashBtnPurge").trigger("click");
      $("#modalSubmit").trigger("click");
      vi.mocked(isTrashOpen).mockReturnValue(false);
      request.resolve({ utubName: "Work Archive" });
      await Promise.resolve();

      expect(loadTrashList).not.toHaveBeenCalled();
      expect(refreshTrashCount).toHaveBeenCalledTimes(1);
      expectSilent();
    });

    it("emptyTrash skips the reload but still counts, silently", async () => {
      const request = deferredXhr();
      vi.mocked(ajaxCall).mockReturnValue(request.xhr);

      confirmAndEmptyTrash();
      $("#modalSubmit").trigger("click");
      vi.mocked(isTrashOpen).mockReturnValue(false);
      request.resolve({ totalPurged: 3, totalSkippedLocked: 0 });
      await Promise.resolve();

      expect(loadTrashList).not.toHaveBeenCalled();
      expect(refreshTrashCount).toHaveBeenCalledTimes(1);
      expectSilent();
    });

    it("the locked-UTub failure arm shows no banner and skips the reload", () => {
      vi.mocked(isTrashOpen).mockReturnValue(false);

      handleTrashActionFailure({
        xhr: failXhr({
          status: 403,
          responseJSON: { message: APP_CONFIG.strings.UTUB_IS_LOCKED },
        }),
        domain: "url",
      });

      expect(loadTrashList).not.toHaveBeenCalled();
      expectSilent();
    });

    it("the not-in-Trash failure arm shows no banner, skips the reload, still counts", () => {
      vi.mocked(isTrashOpen).mockReturnValue(false);

      handleTrashActionFailure({
        xhr: failXhr({ status: 404, responseJSON: { errorCode: 11 } }),
        domain: "url",
      });

      expect(loadTrashList).not.toHaveBeenCalled();
      expect(refreshTrashCount).toHaveBeenCalledTimes(1);
      expectSilent();
    });

    it("the already-in-destination arm shows no banner", async () => {
      const request = deferredXhr();
      vi.mocked(ajaxCall).mockReturnValue(request.xhr);

      const pendingRestore = restoreTrashedURL({
        utubID: 3,
        utubUrlID: 11,
        destUtubID: 5,
      });
      vi.mocked(isTrashOpen).mockReturnValue(false);
      request.reject(failXhr({ status: 409, responseJSON: { errorCode: 14 } }));

      await expect(pendingRestore).resolves.toBe(false);
      expectSilent();
    });

    it("the 400 stale-list arm shows no banner and skips the reload", async () => {
      const request = deferredXhr();
      vi.mocked(ajaxCall).mockReturnValue(request.xhr);

      const pendingRestore = restoreTrashedURL({ utubID: 3, utubUrlID: 11 });
      vi.mocked(isTrashOpen).mockReturnValue(false);
      request.reject(failXhr({ status: 400, responseJSON: { errorCode: 12 } }));

      await expect(pendingRestore).resolves.toBe(false);
      expect(loadTrashList).not.toHaveBeenCalled();
      expectSilent();
    });
  });

  describe("swipe focus-ring suppression", () => {
    beforeEach(() => renderRows());

    it("viaSwipe hides the ring on the newly focused row, cleared on blur", async () => {
      vi.mocked(ajaxCall).mockReturnValue(
        settled({ done: { lostTagCount: 0, restoredToDestination: false } }),
      );

      await restoreTrashedURL({ utubID: 3, utubUrlID: 11, viaSwipe: true });

      expect(rowFor(12).hasClass("swipe-focus-return")).toBe(true);
      rowFor(12).trigger("blur");
      expect(rowFor(12).hasClass("swipe-focus-return")).toBe(false);
    });

    it("viaSwipe suppression is also cleared by the next pointerdown in the panel", async () => {
      vi.mocked(ajaxCall).mockReturnValue(
        settled({ done: { lostTagCount: 0, restoredToDestination: false } }),
      );

      await restoreTrashedURL({ utubID: 3, utubUrlID: 11, viaSwipe: true });
      $("#TrashPanel").trigger("pointerdown");

      expect(rowFor(12).hasClass("swipe-focus-return")).toBe(false);
    });

    it("a tap or keyboard restore keeps the visible ring", async () => {
      vi.mocked(ajaxCall).mockReturnValue(
        settled({ done: { lostTagCount: 0, restoredToDestination: false } }),
      );

      await restoreTrashedURL({ utubID: 3, utubUrlID: 11 });

      expect(rowFor(12).hasClass("swipe-focus-return")).toBe(false);
    });
  });

  describe("trailing click after a committed swipe", () => {
    beforeEach(() => renderRows());

    it("swallows exactly one click, then acts normally", () => {
      vi.mocked(ajaxCall).mockReturnValue(pending());
      armTrashClickSuppression();

      rowFor(11).find(".trashBtnRestore").trigger("click");
      expect(ajaxCall).not.toHaveBeenCalled();

      rowFor(11).find(".trashBtnRestore").trigger("click");
      expect(ajaxCall).toHaveBeenCalledTimes(1);
      clearTrashClickSuppression();
    });
  });

  describe("double activation", () => {
    it("disables the row's buttons synchronously so a second click sends nothing", () => {
      renderRows();
      vi.mocked(ajaxCall).mockReturnValue(pending());

      const button = rowFor(11).find(".trashBtnRestore");
      button.trigger("click");
      button.trigger("click");
      rowFor(11).find(".trashBtnPurge").trigger("click");

      expect(ajaxCall).toHaveBeenCalledTimes(1);
      expect(button.attr("aria-disabled")).toBe("true");
      expect(modalSpy).not.toHaveBeenCalled();
    });

    it("ignores clicks on a row the user cannot act on", () => {
      renderRows({ urls: [makeUrlItem({ canRestore: false })] });

      rowFor(11).find(".trashBtnRestore").trigger("click");

      expect(ajaxCall).not.toHaveBeenCalled();
    });
  });
});
