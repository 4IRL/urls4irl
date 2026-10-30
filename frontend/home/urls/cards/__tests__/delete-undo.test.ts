import type { SuccessResponse } from "../../../../types/api-helpers.d.ts";
import type { UtubTag, UtubUrlItem } from "../../../../types/url.js";

import { APP_CONFIG } from "../../../../lib/config.js";
import { ajaxCall, is429Handled } from "../../../../lib/ajax.js";
import { emit } from "../../../../lib/metrics-client.js";
import { getState } from "../../../../store/app-store.js";
import { UI_EVENTS } from "../../../../types/metrics-events.js";
import { isUtubLockedHandled } from "../../../utub-locked.js";
import { refreshTrashCount } from "../../../trash/count.js";
import { insertURLCardIntoDeck } from "../card-deck.js";
import { applyRowCountDelta } from "../../../utubs/row-counts.js";
import { enterMultiSelectMode } from "../../bulk-actions/bulk-mode.js";
import { clearURLOutcomeBanner } from "../../outcome-banner.js";
import {
  isURLDeleteToastShowing,
  isURLDeleteUndoInFlight,
  showURLDeletedToast,
  showURLDeletionFailedToast,
} from "../delete-undo.js";

const { mockMetricsClient } = await vi.hoisted(
  async () =>
    await import("../../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../../lib/metrics-client.js", () => mockMetricsClient());
vi.mock("../../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));
vi.mock("../../../utub-locked.js", () => ({
  isUtubLockedHandled: vi.fn(() => false),
}));
vi.mock("../../../trash/count.js", () => ({
  refreshTrashCount: vi.fn(() => Promise.resolve()),
}));
vi.mock("../card-deck.js", () => ({
  insertURLCardIntoDeck: vi.fn(),
}));
vi.mock("../../../utubs/row-counts.js", () => ({
  applyRowCountDelta: vi.fn(),
}));
vi.mock("../selection.js", () => ({
  deselectAllURLs: vi.fn(),
}));
vi.mock("../../deck.js", () => ({ showURLDeckBannerError: vi.fn() }));
vi.mock("../get.js", () => ({ deleteURLOnStale: vi.fn() }));
vi.mock("../apply-url-string.js", () => ({
  applyUpdatedURLString: vi.fn(),
}));
vi.mock("../../../../store/app-store.js", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../../../store/app-store.js")>()),
  getState: vi.fn(() => ({ activeUTubID: 1 })),
}));

const $ = window.jQuery;

type RestoreResponse = SuccessResponse<"restoreUrls">;

const PAGE_HTML = `
  <div id="URLDeck" tabindex="-1">
    <div id="URLDeckOutcomeBanner" class="urlOutcomeBanner hidden" role="status"></div>
    <div id="listURLs"></div>
  </div>
  <button id="elsewhere">elsewhere</button>
`;

const TAG_A: UtubTag = { id: 1, tagString: "alpha", tagApplied: 1 };
const TAG_B: UtubTag = { id: 2, tagString: "beta", tagApplied: 1 };

function strings(): Record<string, string> {
  return APP_CONFIG.strings;
}

function banner(): JQuery {
  return $("#URLDeckOutcomeBanner");
}

function bannerMessage(): string {
  return banner().find(".urlOutcomeBannerMessage").text();
}

function bannerDetails(): string[] {
  return banner()
    .find(".urlOutcomeBannerDetail")
    .map((_index, element) => $(element).text())
    .get();
}

function undoButton(): JQuery {
  return banner().find(".urlOutcomeBannerAction");
}

function restoredUrl({
  id,
  tagIDs = [],
}: {
  id: number;
  tagIDs?: number[];
}): UtubUrlItem {
  return {
    utubUrlID: id,
    urlString: `https://example.com/${id}`,
    utubUrlTagIDs: tagIDs,
    urlTitle: `Title ${id}`,
    canDelete: true,
    shortLinkExpiresAt: null,
    canRevokeShortLink: false,
    addedAt: "2026-10-17T00:00:00",
    addedByUserID: 1,
  };
}

function restoreResponse(
  overrides: Partial<Omit<RestoreResponse, "status">>,
): RestoreResponse {
  const restored = overrides.restored ?? [];
  const skipped = overrides.skipped ?? [];
  return {
    status: "Success",
    utubID: 1,
    restored,
    skipped,
    lostTagCount: 0,
    totalRestored: restored.length,
    totalSkipped: skipped.length,
    ...overrides,
  };
}

// A request that stays pending until the test settles it.
function pendingRequest(): {
  resolve: (response: RestoreResponse) => void;
  reject: (xhr: Partial<JQuery.jqXHR>) => void;
} {
  const callbacks: {
    done: Array<(response: RestoreResponse) => void>;
    fail: Array<(xhr: JQuery.jqXHR) => void>;
    always: Array<() => void>;
  } = { done: [], fail: [], always: [] };
  const xhr: Record<string, unknown> = {};
  xhr.done = vi.fn((callback: (response: RestoreResponse) => void) => {
    callbacks.done.push(callback);
    return xhr;
  });
  xhr.fail = vi.fn((callback: (xhrArg: JQuery.jqXHR) => void) => {
    callbacks.fail.push(callback);
    return xhr;
  });
  xhr.always = vi.fn((callback: () => void) => {
    callbacks.always.push(callback);
    return xhr;
  });
  vi.mocked(ajaxCall).mockReturnValue(xhr as unknown as JQuery.jqXHR);
  return {
    resolve: (response) => {
      callbacks.done.forEach((callback) => callback(response));
      callbacks.always.forEach((callback) => callback());
    },
    reject: (xhrArg) => {
      callbacks.fail.forEach((callback) =>
        callback(xhrArg as unknown as JQuery.jqXHR),
      );
      callbacks.always.forEach((callback) => callback());
    },
  };
}

function showToast({
  deletedIDs = [11],
  skippedCount = 0,
  hiddenCount = 0,
  returnFocusTo = $(),
}: {
  deletedIDs?: number[];
  skippedCount?: number;
  hiddenCount?: number;
  returnFocusTo?: JQuery;
} = {}): void {
  showURLDeletedToast({
    utubID: 1,
    deletedIDs,
    skippedCount,
    hiddenCount,
    returnFocusTo,
  });
}

function clickUndo(): ReturnType<typeof pendingRequest> {
  const request = pendingRequest();
  undoButton().trigger("click");
  return request;
}

describe("delete-undo", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    document.body.innerHTML = PAGE_HTML;
    vi.mocked(is429Handled).mockReturnValue(false);
    vi.mocked(isUtubLockedHandled).mockReturnValue(false);
    vi.mocked(getState).mockReturnValue({
      activeUTubID: 1,
    } as ReturnType<typeof getState>);
    // jsdom has no layout, so ":visible" is always false; declare cards rendered.
    const originalIs = $.fn.is;
    vi.spyOn($.fn, "is").mockImplementation(function (
      this: JQuery,
      selector: unknown,
    ) {
      if (selector === ":visible") return true;
      return originalIs.call(this, selector as string);
    });
    vi.mocked(insertURLCardIntoDeck).mockImplementation(({ newUrl }) => {
      const card = $("<div>", {
        class: "urlRow",
        tabindex: "-1",
        utuburlid: String(newUrl.utubUrlID),
      });
      $("#listURLs").prepend(card);
      return card;
    });
    clearURLOutcomeBanner();
    expect(isURLDeleteUndoInFlight()).toBe(false);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  describe("showURLDeletedToast", () => {
    it("1 id: success with the singular message and no detail", () => {
      showToast({ deletedIDs: [11] });
      expect(banner().hasClass("success")).toBe(true);
      expect(bannerMessage()).toBe(strings().URL_MOVED_TO_TRASH_ONE);
      expect(bannerDetails()).toEqual([]);
    });

    it("4 ids, 1 skipped, 2 hidden: partial, count filled, skipped then hidden detail", () => {
      showToast({ deletedIDs: [1, 2, 3, 4], skippedCount: 1, hiddenCount: 2 });
      expect(banner().hasClass("partial")).toBe(true);
      expect(bannerMessage()).toBe("Moved 4 URLs to Trash.");
      expect(bannerDetails()).toEqual([
        strings().URL_BULK_DELETE_SKIPPED_SUFFIX_ONE,
        "Includes 2 URLs hidden by your filters.",
      ]);
    });

    it("hidden only: success, with the hidden detail", () => {
      showToast({ deletedIDs: [1, 2], hiddenCount: 1 });
      expect(banner().hasClass("success")).toBe(true);
      expect(bannerDetails()).toEqual([strings().URL_DELETE_HIDDEN_DETAIL_ONE]);
    });

    it("labels Undo for assistive tech: singular for 1 id, filled template for N", () => {
      showToast({ deletedIDs: [11] });
      expect(undoButton().attr("aria-label")).toBe(
        strings().URL_UNDO_DELETE_ARIA_ONE,
      );
      showToast({ deletedIDs: [1, 2, 3] });
      expect(undoButton().attr("aria-label")).toBe("Undo delete of 3 URLs");
      expect(undoButton().text()).toBe(strings().URL_TRIM_UNDO);
    });
  });

  describe("showURLDeletionFailedToast", () => {
    it("nothing deleted, some skipped: assertive partial NONE copy with no Undo", () => {
      showURLDeletionFailedToast({ forceFail: false });
      expect(banner().hasClass("partial")).toBe(true);
      expect(bannerMessage()).toBe(strings().URL_BULK_DELETE_NONE);
      expect(banner().attr("aria-live")).toBe("assertive");
      expect(undoButton().length).toBe(0);
    });

    it("forceFail: UNABLE_TO_DELETE_URLS", () => {
      showURLDeletionFailedToast({ forceFail: true });
      expect(bannerMessage()).toBe(strings().UNABLE_TO_DELETE_URLS);
      expect(undoButton().length).toBe(0);
    });
  });

  describe("Undo request", () => {
    it("posts once to the bulk restore route with every id and emits the metric once", () => {
      showToast({ deletedIDs: [11, 12] });
      const request = clickUndo();
      undoButton().trigger("click"); // aria-disabled single-flight guard
      // Settle it so the module's in-flight flag does not leak into later tests.
      request.resolve(restoreResponse({}));

      expect(ajaxCall).toHaveBeenCalledTimes(1);
      expect(ajaxCall).toHaveBeenCalledWith(
        "post",
        APP_CONFIG.routes.restoreURLs(1),
        { utubUrlIds: [11, 12] },
        35000,
      );
      expect(emit).toHaveBeenCalledTimes(1);
      expect(emit).toHaveBeenCalledWith({
        event: UI_EVENTS.UI_URL_DELETE_UNDONE,
      });
    });

    it("isURLDeleteUndoInFlight is true between click and settle", () => {
      showToast();
      expect(isURLDeleteUndoInFlight()).toBe(false);
      const request = clickUndo();
      expect(isURLDeleteUndoInFlight()).toBe(true);
      request.resolve(restoreResponse({ restored: [restoredUrl({ id: 11 })] }));
      expect(isURLDeleteUndoInFlight()).toBe(false);
    });

    it("isURLDeleteToastShowing tracks whether this module's toast is the banner", () => {
      expect(isURLDeleteToastShowing()).toBe(false);
      showToast();
      expect(isURLDeleteToastShowing()).toBe(true);
      clearURLOutcomeBanner();
      expect(isURLDeleteToastShowing()).toBe(false);
    });
  });

  describe("Undo done", () => {
    it("1 id restored: inserts once with only that URL's tags, success banner, no Undo, trash count refreshed", () => {
      showToast();
      const url = restoredUrl({ id: 11, tagIDs: [1] });
      clickUndo().resolve(
        restoreResponse({ restored: [url], appliedTags: [TAG_A, TAG_B] }),
      );

      expect(insertURLCardIntoDeck).toHaveBeenCalledTimes(1);
      expect(insertURLCardIntoDeck).toHaveBeenCalledWith({
        newUrl: url,
        utubID: 1,
        appliedTags: [TAG_A],
        announce: false,
        select: false,
      });
      expect(banner().hasClass("success")).toBe(true);
      expect(bannerMessage()).toBe(strings().URL_REVIVED_FROM_TRASH);
      expect(undoButton().length).toBe(0);
      expect(banner().attr("aria-live")).toBe("polite");
      expect(refreshTrashCount).toHaveBeenCalled();
    });

    it("1 id with 2 lost tags: partial revive message with a tag-name detail", () => {
      showToast();
      clickUndo().resolve(
        restoreResponse({
          restored: [restoredUrl({ id: 11 })],
          lostTagCount: 2,
          lostTagNames: ["Art", "Tool"],
        }),
      );
      expect(banner().hasClass("partial")).toBe(true);
      expect(bannerMessage()).toBe(
        "Restored from trash. 2 tags no longer exist.",
      );
      expect(bannerDetails()).toEqual(["Art, Tool"]);
      expect(banner().attr("aria-live")).toBe("polite");
    });

    it("4 ids all restored with 2 lost tags: one banner, every insert is select:false", () => {
      showToast({ deletedIDs: [1, 2, 3, 4] });
      clickUndo().resolve(
        restoreResponse({
          restored: [1, 2, 3, 4].map((id) => restoredUrl({ id })),
          lostTagCount: 2,
          lostTagNames: ["Art", "Tool"],
        }),
      );
      expect(insertURLCardIntoDeck).toHaveBeenCalledTimes(4);
      for (const [params] of vi.mocked(insertURLCardIntoDeck).mock.calls) {
        expect(params.select).toBe(false);
      }
      expect(banner().hasClass("partial")).toBe(true);
      expect(bannerMessage()).toBe(
        "Restored 4 URLs from trash. 2 tags no longer exist.",
      );
      expect(banner().attr("aria-live")).toBe("polite");
    });

    it("3 of 4 restored, the skip is not_in_trash: RESTORED_SOME with a not-in-Trash detail", () => {
      showToast({ deletedIDs: [1, 2, 3, 4] });
      clickUndo().resolve(
        restoreResponse({
          restored: [1, 2, 3].map((id) => restoredUrl({ id })),
          skipped: [{ utubUrlID: 4, reason: "not_in_trash" }],
        }),
      );
      expect(banner().hasClass("partial")).toBe(true);
      expect(bannerMessage()).toBe("Restored 3 of 4 URLs from trash.");
      expect(bannerDetails()).toEqual([strings().URL_UNDO_NOT_IN_TRASH_ONE]);
      expect(banner().attr("aria-live")).toBe("assertive");
    });

    it("3 of 4 restored, the skip is destination_required: its own detail, never not-in-Trash", () => {
      showToast({ deletedIDs: [1, 2, 3, 4] });
      clickUndo().resolve(
        restoreResponse({
          restored: [1, 2, 3].map((id) => restoredUrl({ id })),
          skipped: [{ utubUrlID: 4, reason: "destination_required" }],
        }),
      );
      expect(bannerMessage()).toBe("Restored 3 of 4 URLs from trash.");
      expect(bannerDetails()).toEqual([
        strings().URL_UNDO_DESTINATION_REQUIRED_ONE,
      ]);
      expect(banner().attr("aria-live")).toBe("assertive");
    });

    it("2 of 4 restored, one skip of each reason: both details", () => {
      showToast({ deletedIDs: [1, 2, 3, 4] });
      clickUndo().resolve(
        restoreResponse({
          restored: [1, 2].map((id) => restoredUrl({ id })),
          skipped: [
            { utubUrlID: 3, reason: "not_in_trash" },
            { utubUrlID: 4, reason: "destination_required" },
          ],
        }),
      );
      expect(bannerMessage()).toBe("Restored 2 of 4 URLs from trash.");
      expect(bannerDetails()).toEqual([
        strings().URL_UNDO_NOT_IN_TRASH_ONE,
        strings().URL_UNDO_DESTINATION_REQUIRED_ONE,
      ]);
    });

    it("0 restored, all not_in_trash: partial TRASH_NOT_IN_TRASH, no insert", () => {
      showToast({ deletedIDs: [1, 2] });
      clickUndo().resolve(
        restoreResponse({
          skipped: [
            { utubUrlID: 1, reason: "not_in_trash" },
            { utubUrlID: 2, reason: "not_in_trash" },
          ],
        }),
      );
      expect(insertURLCardIntoDeck).not.toHaveBeenCalled();
      expect(banner().hasClass("partial")).toBe(true);
      expect(bannerMessage()).toBe(strings().TRASH_NOT_IN_TRASH);
      expect(banner().attr("aria-live")).toBe("assertive");
    });

    it("0 restored, all destination_required: the destination message (filled), never TRASH_NOT_IN_TRASH", () => {
      showToast({ deletedIDs: [1, 2] });
      clickUndo().resolve(
        restoreResponse({
          skipped: [
            { utubUrlID: 1, reason: "destination_required" },
            { utubUrlID: 2, reason: "destination_required" },
          ],
        }),
      );
      expect(insertURLCardIntoDeck).not.toHaveBeenCalled();
      expect(bannerMessage()).toBe(
        "2 are still in Trash — pick a destination in the Trash panel.",
      );
      expect(bannerMessage()).not.toBe(strings().TRASH_NOT_IN_TRASH);
      expect(banner().attr("aria-live")).toBe("assertive");

      showToast({ deletedIDs: [1] });
      clickUndo().resolve(
        restoreResponse({
          skipped: [{ utubUrlID: 1, reason: "destination_required" }],
        }),
      );
      expect(bannerMessage()).toBe(strings().URL_UNDO_DESTINATION_REQUIRED_ONE);
    });

    it("after the active UTub changed: no insert and no banner, trash count still refreshed", () => {
      showToast();
      const request = clickUndo();
      vi.mocked(getState).mockReturnValue({
        activeUTubID: 2,
      } as ReturnType<typeof getState>);
      request.resolve(restoreResponse({ restored: [restoredUrl({ id: 11 })] }));
      expect(insertURLCardIntoDeck).not.toHaveBeenCalled();
      expect(bannerMessage()).toBe("Moved 1 URL to Trash.");
      expect(refreshTrashCount).toHaveBeenCalled();
      expect(applyRowCountDelta).toHaveBeenCalledTimes(1);
      expect(applyRowCountDelta).toHaveBeenCalledWith({
        utubID: 1,
        urlDelta: 1,
        memberDelta: 0,
      });
    });

    it("active UTub unchanged: row count is left to insertURLCardIntoDeck (no double count)", () => {
      showToast();
      clickUndo().resolve(
        restoreResponse({ restored: [restoredUrl({ id: 11 })] }),
      );
      expect(insertURLCardIntoDeck).toHaveBeenCalledTimes(1);
      expect(applyRowCountDelta).not.toHaveBeenCalled();
    });

    it("a second delete's toast replaced the first while Undo was in flight: re-inserts but never overwrites the newer banner or focus", () => {
      showToast({ deletedIDs: [11] });
      const request = clickUndo();
      showToast({ deletedIDs: [21, 22] });
      $("#elsewhere").trigger("focus");

      request.resolve(restoreResponse({ restored: [restoredUrl({ id: 11 })] }));

      expect(insertURLCardIntoDeck).toHaveBeenCalledTimes(1);
      expect(vi.mocked(insertURLCardIntoDeck).mock.calls[0][0].select).toBe(
        false,
      );
      expect(refreshTrashCount).toHaveBeenCalled();
      expect(bannerMessage()).toBe("Moved 2 URLs to Trash.");
      expect(undoButton().length).toBe(1);
      expect(document.activeElement).toBe($("#elsewhere")[0]);
    });

    it("multi-select mode entered while Undo was in flight: re-inserts but renders no completion banner", () => {
      showToast({ deletedIDs: [11] });
      const request = clickUndo();
      enterMultiSelectMode();

      request.resolve(restoreResponse({ restored: [restoredUrl({ id: 11 })] }));

      expect(insertURLCardIntoDeck).toHaveBeenCalledTimes(1);
      expect(vi.mocked(insertURLCardIntoDeck).mock.calls[0][0].select).toBe(
        false,
      );
      expect(refreshTrashCount).toHaveBeenCalled();
      expect(banner().hasClass("hidden")).toBe(true);
      expect(banner().children().length).toBe(0);
    });

    it("returns focus to the last inserted card after the completion banner", () => {
      showToast({ deletedIDs: [1, 2] });
      clickUndo().resolve(
        restoreResponse({
          restored: [1, 2].map((id) => restoredUrl({ id })),
        }),
      );
      const lastCard = vi.mocked(insertURLCardIntoDeck).mock.results[1]
        .value as JQuery;
      expect(document.activeElement).toBe(lastCard[0]);
    });

    it("falls back to the deck when nothing was restored", () => {
      showToast();
      clickUndo().resolve(
        restoreResponse({
          skipped: [{ utubUrlID: 11, reason: "not_in_trash" }],
        }),
      );
      expect(document.activeElement).toBe($("#URLDeck")[0]);
    });
  });

  describe("Undo fail", () => {
    it("429: re-renders the toast with Undo enabled and focuses the new Undo button", () => {
      showToast({ deletedIDs: [11, 12] });
      const staleButton = undoButton()[0];
      const request = clickUndo();
      vi.mocked(is429Handled).mockReturnValue(true);
      request.reject({ status: 429 });

      expect(undoButton().length).toBe(1);
      expect(undoButton()[0]).not.toBe(staleButton);
      expect(undoButton().attr("aria-disabled")).toBeUndefined();
      expect(bannerMessage()).toBe("Moved 2 URLs to Trash.");
      expect(document.activeElement).toBe(undoButton()[0]);
      expect(isURLDeleteToastShowing()).toBe(true);
    });

    it("locked: clears the banner and returns focus to returnFocusTo", () => {
      const row = $("<div>", { class: "urlRow", tabindex: "-1" });
      $("#listURLs").append(row);
      showToast({ returnFocusTo: row });
      const request = clickUndo();
      vi.mocked(isUtubLockedHandled).mockReturnValue(true);
      request.reject({ status: 403 });

      expect(banner().hasClass("hidden")).toBe(true);
      expect(banner().children().length).toBe(0);
      expect(document.activeElement).toBe(row[0]);
    });

    it("stale 429 (a newer toast replaced the banner): leaves the newer banner and focus untouched", () => {
      showToast({ deletedIDs: [11] });
      const request = clickUndo();
      showToast({ deletedIDs: [21, 22] });
      $("#elsewhere").trigger("focus");
      vi.mocked(is429Handled).mockReturnValue(true);
      request.reject({ status: 429 });

      expect(bannerMessage()).toBe("Moved 2 URLs to Trash.");
      expect(undoButton().length).toBe(1);
      expect(document.activeElement).toBe($("#elsewhere")[0]);
    });

    it("stale locked (a newer toast replaced the banner): does not clear the newer banner", () => {
      showToast({ deletedIDs: [11] });
      const request = clickUndo();
      showToast({ deletedIDs: [21, 22] });
      $("#elsewhere").trigger("focus");
      vi.mocked(isUtubLockedHandled).mockReturnValue(true);
      request.reject({ status: 403 });

      expect(banner().hasClass("hidden")).toBe(false);
      expect(bannerMessage()).toBe("Moved 2 URLs to Trash.");
      expect(document.activeElement).toBe($("#elsewhere")[0]);
    });

    it("403 with an HTML Content-Type swaps in the CSRF body", () => {
      showToast();
      const request = clickUndo();
      request.reject({
        status: 403,
        getResponseHeader: () => "text/html; charset=utf-8",
        responseText: "<p id='csrf'>csrf</p>",
      });
      expect($("#csrf").length).toBe(1);
    });

    it("any other status goes to the error page", () => {
      const assign = vi.fn();
      vi.stubGlobal("location", { ...window.location, assign });
      showToast();
      const request = clickUndo();
      request.reject({
        status: 500,
        getResponseHeader: () => "application/json",
      });
      expect(assign).toHaveBeenCalledWith(APP_CONFIG.routes.errorPage);
    });
  });
});
