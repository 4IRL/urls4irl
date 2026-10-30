import { initBulkDelete, isBulkDeleteSubmitInFlight } from "../bulk-delete.js";
import { getAvailableBulkActions } from "../bulk-action-registry.js";
import type { BulkAction } from "../bulk-action-registry.js";
import { setPickerOpen } from "../picker-guard.js";
import { APP_CONFIG } from "../../../../lib/config.js";
import { ajaxCall, is429Handled } from "../../../../lib/ajax.js";
import { updateVisibleURLsForTagCount } from "../../cards/filtering.js";
import {
  showURLDeletedToast,
  showURLDeletionFailedToast,
} from "../../cards/delete-undo.js";
import { showURLsEmptyState } from "../../empty-state.js";
import { hideURLSearchIcon } from "../../search.js";
import { exitMultiSelectMode } from "../bulk-mode.js";
import { showURLDeckBannerError } from "../../deck.js";
import { createMockJqXHR } from "../../../../__tests__/helpers/mock-jquery.js";
import { refreshTrashCount } from "../../../trash/count.js";
import { applyRowCountDelta } from "../../../utubs/row-counts.js";

vi.mock("../../../trash/count.js", () => ({ refreshTrashCount: vi.fn() }));

vi.mock("../../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));

vi.mock("../../cards/delete-undo.js", () => ({
  showURLDeletedToast: vi.fn(),
  showURLDeletionFailedToast: vi.fn(),
}));

// Partial mock: keep the real AppEvents enum, spying only `emit` so the
// URL_DECK_CHANGED notification fired on a successful bulk delete can be asserted.
vi.mock("../../../../lib/event-bus.js", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("../../../../lib/event-bus.js")>();
  return {
    ...actual,
    emit: vi.fn(),
  };
});

// Partial mock: keep the real writeTagChipDenominator (the DD-2 assertion below
// checks the actual "X / Y" chip DOM write) while stubbing the numerator
// recompute (its call count is asserted in isolation) and the tag-filter refresh
// (stubbed for DOM isolation so it can't rewrite the chip under test).
vi.mock("../../cards/filtering.js", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("../../cards/filtering.js")>();
  return {
    ...actual,
    updateTagFilteringOnURLOrURLTagDeletion: vi.fn(),
    updateVisibleURLsForTagCount: vi.fn(),
  };
});

vi.mock("../../empty-state.js", () => ({
  showURLsEmptyState: vi.fn(),
  hideURLsEmptyState: vi.fn(),
}));

vi.mock("../../search.js", () => ({
  hideURLSearchIcon: vi.fn(),
}));

vi.mock("../bulk-mode.js", () => ({
  exitMultiSelectMode: vi.fn(),
}));

// deck.js is pulled in via the shared lock guard (../../utub-locked.js); mock it
// so the locked-UTub case asserts the inline banner without loading the real deck.
vi.mock("../../deck.js", () => ({
  showURLDeckBannerError: vi.fn(),
}));

interface TestUrl {
  utubUrlID: number;
  canDelete: boolean;
}
const storeState: {
  activeUTubID: number | null;
  urls: TestUrl[];
  selectedURLCardIDs: number[];
} = {
  activeUTubID: 1,
  urls: [],
  selectedURLCardIDs: [],
};
vi.mock("../../../utubs/row-counts.js", () => ({
  applyRowCountDelta: vi.fn(),
}));

vi.mock("../../../../store/app-store.js", () => ({
  getState: vi.fn(() => storeState),
  setState: vi.fn((partial: Partial<typeof storeState>) => {
    Object.assign(storeState, partial);
  }),
}));

const $ = window.jQuery;

const LOCKED_MESSAGE = "This UTub is locked and cannot be modified.";
const URL_UTUB_IS_LOCKED = 8;

const BASE_HTML = `
  <div id="URLDeck">
    <div id="listURLs"></div>
    <div id="bulkActionBar">
      <button id="bulkSelectExit" type="button">Exit</button>
      <div id="bulkActionButtons"></div>
    </div>
    <span id="URLDeckOutcomeAnnouncement" class="visually-hidden" aria-live="polite"></span>
    <div id="noURLsEmptyState" class="hidden"><p id="noURLsSubheader"></p></div>
  </div>
`;

function url(utubUrlID: number, canDelete: boolean): TestUrl {
  return { utubUrlID, canDelete };
}

/** Seed visible, removable URL rows into #listURLs. */
function seedUrlRows(ids: number[]): void {
  const listURLs = $("#listURLs");
  ids.forEach((id) => {
    listURLs.append(
      `<div class="urlRow" utuburlid="${id}" filterable="true" data-utub-url-tag-ids=""></div>`,
    );
  });
}

/** Resolve the registered bulk-delete action (via a known-available context). */
function resolveDeleteAction(): BulkAction {
  const action = getAvailableBulkActions({
    selectedURLCardIDs: [10],
    urls: [url(10, true)] as never,
  }).find((candidate) => candidate.id === "bulk-delete");
  if (!action) throw new Error("bulk-delete action not registered");
  return action;
}

/** Activate bulk delete for a selection/url-list (no modal: submits directly). */
function activateFor(selectedURLCardIDs: number[], urls: TestUrl[]): void {
  resolveDeleteAction().onActivate({
    selectedURLCardIDs,
    urls: urls as never,
  });
}

/** Activate with a pending request and return its deferred. */
function activateAndPend(
  selectedURLCardIDs: number[],
  urls: TestUrl[],
): ReturnType<typeof createMockJqXHR> {
  const deferred = createMockJqXHR();
  vi.mocked(ajaxCall).mockReturnValue(deferred);
  activateFor(selectedURLCardIDs, urls);
  return deferred;
}

/** Build a bulk-delete success response envelope. */
function deleteResponse({
  deletedIds,
  tagCountsInUtub = {},
}: {
  deletedIds: number[];
  tagCountsInUtub?: Record<string, number>;
}): Record<string, unknown> {
  return {
    deleted: deletedIds.map((id) => ({
      utubUrlID: id,
      urlString: `https://example.com/${id}`,
      urlTitle: `Title ${id}`,
    })),
    skipped: [],
    tagCountsInUtub,
    totalDeleted: deletedIds.length,
    totalSkipped: 0,
  };
}

beforeAll(() => {
  document.body.innerHTML = BASE_HTML;
  initBulkDelete();
});

beforeEach(() => {
  document.body.innerHTML = BASE_HTML;
  // The shared lock guard (utub-locked.js) hides any open Bootstrap modal.
  $.fn.modal = vi.fn().mockReturnThis();
  $.fx.off = true;
  storeState.activeUTubID = 1;
  storeState.urls = [];
  storeState.selectedURLCardIDs = [];
  vi.clearAllMocks();
  vi.mocked(is429Handled).mockReturnValue(false);
  setPickerOpen("bulk-tag", false);
  setPickerOpen("bulk-copy", false);
});

afterEach(() => {
  $.fx.off = false;
  setPickerOpen("bulk-tag", false);
  setPickerOpen("bulk-copy", false);
  document.body.innerHTML = "";
});

describe("bulk-delete action registration + availability", () => {
  it("registers the bulk-delete action with the Delete label", () => {
    expect(resolveDeleteAction().label).toBe(
      APP_CONFIG.strings.URL_BULK_DELETE_LABEL,
    );
  });

  it("declares the destructive 'danger' variant class (rendered onto the .barBtn)", () => {
    expect(resolveDeleteAction().className).toBe("danger");
  });

  it("isAvailable is false with no selection", () => {
    expect(
      resolveDeleteAction().isAvailable({ selectedURLCardIDs: [], urls: [] }),
    ).toBe(false);
  });

  it("isAvailable is true whenever something is selected, even if nothing is deletable", () => {
    // Availability now only gates on a non-empty selection; the destructive
    // button stays visible-but-disabled when nothing is deletable (isEnabled).
    expect(
      resolveDeleteAction().isAvailable({
        selectedURLCardIDs: [10, 20],
        urls: [url(10, false), url(20, false)] as never,
      }),
    ).toBe(true);
  });

  it("isEnabled is false with no selection", () => {
    expect(
      resolveDeleteAction().isEnabled!({ selectedURLCardIDs: [], urls: [] }),
    ).toBe(false);
  });

  it("isEnabled is false when no selected URL is deletable", () => {
    expect(
      resolveDeleteAction().isEnabled!({
        selectedURLCardIDs: [10, 20],
        urls: [url(10, false), url(20, false)] as never,
      }),
    ).toBe(false);
  });

  it("isEnabled is true when at least one selected URL is deletable", () => {
    expect(
      resolveDeleteAction().isEnabled!({
        selectedURLCardIDs: [10, 20],
        urls: [url(10, false), url(20, true)] as never,
      }),
    ).toBe(true);
  });

  it("carries the bridged disabledReason shown while disabled", () => {
    expect(resolveDeleteAction().disabledReason).toBe(
      APP_CONFIG.strings.URL_BULK_DELETE_DISABLED_REASON,
    );
  });
});

describe("activateBulkDelete (onActivate)", () => {
  it("posts only the deletable snapshot immediately, with no modal", () => {
    // 2 deletable (10, 20) + 1 non-deletable (30) + 1 filter-hidden (40: no row).
    seedUrlRows([10, 20, 30]);
    const deferred = activateAndPend(
      [10, 20, 30, 40],
      [url(10, true), url(20, true), url(30, false), url(40, true)],
    );

    expect(vi.mocked(ajaxCall)).toHaveBeenCalledTimes(1);
    const [method, requestUrl, body] = vi.mocked(ajaxCall).mock.calls[0];
    expect(method).toBe("post");
    expect(requestUrl).toBe(APP_CONFIG.routes.bulkDeleteURLs(1));
    // id 30 (not deletable) is skipped client-side; hidden id 40 is still sent.
    expect(body).toEqual({ utubUrlIds: [10, 20, 40] });

    // Settle the request so the module-private submitInFlight flag does not leak.
    deferred.resolve(deleteResponse({ deletedIds: [10, 20] }), "success", {
      status: 200,
    });
  });

  it("disables the bar's Delete button while pending and restores it after", () => {
    $("#bulkActionButtons").append(
      '<button data-bulk-action-id="bulk-delete">',
    );
    seedUrlRows([10]);
    storeState.urls = [url(10, true)];
    const deferred = activateAndPend([10], storeState.urls);
    expect($('[data-bulk-action-id="bulk-delete"]').attr("aria-disabled")).toBe(
      "true",
    );
    deferred.resolve(deleteResponse({ deletedIds: [10] }), "success", {
      status: 200,
    });
    expect(
      $('[data-bulk-action-id="bulk-delete"]').attr("aria-disabled"),
    ).toBeUndefined();
  });

  it("does not re-enable a Delete button that was re-rendered while pending", () => {
    $("#bulkActionButtons").append(
      '<button data-bulk-action-id="bulk-delete">',
    );
    seedUrlRows([10]);
    storeState.urls = [url(10, true)];
    const deferred = activateAndPend([10], storeState.urls);
    // The bar re-renders: the captured button is detached, a new disabled one
    // takes its place (e.g. the remaining selection has nothing deletable).
    $("#bulkActionButtons").html(
      '<button data-bulk-action-id="bulk-delete" aria-disabled="true">',
    );
    deferred.resolve(deleteResponse({ deletedIds: [10] }), "success", {
      status: 200,
    });
    expect($('[data-bulk-action-id="bulk-delete"]').attr("aria-disabled")).toBe(
      "true",
    );
  });

  it("no-ops while another bulk picker is open", () => {
    setPickerOpen("bulk-tag", true);
    activateFor([10], [url(10, true)]);
    expect(vi.mocked(ajaxCall)).not.toHaveBeenCalled();
  });

  it("no-ops while a submit is already in flight", () => {
    seedUrlRows([10]);
    storeState.urls = [url(10, true)];
    const deferred = activateAndPend([10], storeState.urls);
    activateFor([10], [url(10, true)]);
    expect(vi.mocked(ajaxCall)).toHaveBeenCalledTimes(1);
    deferred.resolve(deleteResponse({ deletedIds: [10] }), "success", {
      status: 200,
    });
  });

  it("no-ops when there is no active UTub", () => {
    storeState.activeUTubID = null;
    activateFor([10], [url(10, true)]);
    expect(vi.mocked(ajaxCall)).not.toHaveBeenCalled();
  });

  it("no-ops when nothing selected is deletable", () => {
    activateFor([10], [url(10, false)]);
    expect(vi.mocked(ajaxCall)).not.toHaveBeenCalled();
  });
});

describe("submit + success (active-deck mutation)", () => {
  it("isBulkDeleteSubmitInFlight is true while the delete is pending and false after it settles", () => {
    seedUrlRows([10]);
    storeState.urls = [url(10, true)];
    expect(isBulkDeleteSubmitInFlight()).toBe(false);
    const deferred = activateAndPend([10], storeState.urls);
    expect(isBulkDeleteSubmitInFlight()).toBe(true);
    deferred.resolve(deleteResponse({ deletedIds: [10] }), "success", {
      status: 200,
    });
    expect(isBulkDeleteSubmitInFlight()).toBe(false);
  });

  it("clean delete → deleted toast with server ids, survivors remain, numerators recomputed once", async () => {
    seedUrlRows([10, 20, 99]);
    storeState.urls = [url(10, true), url(20, true), url(99, false)];
    const deferred = activateAndPend(
      [10, 20],
      [url(10, true), url(20, true), url(99, false)],
    );

    deferred.resolve(deleteResponse({ deletedIds: [10, 20] }), "success", {
      status: 200,
    });

    expect(vi.mocked(showURLDeletedToast)).toHaveBeenCalledTimes(1);
    const args = vi.mocked(showURLDeletedToast).mock.calls[0][0];
    expect(args).toMatchObject({
      utubID: 1,
      deletedIDs: [10, 20],
      skippedCount: 0,
      hiddenCount: 0,
    });
    expect(args.returnFocusTo[0]).toBe(
      document.getElementById("bulkSelectExit"),
    );
    expect(vi.mocked(showURLDeletionFailedToast)).not.toHaveBeenCalled();

    await vi.waitFor(() => {
      expect($("#listURLs .urlRow[utuburlid=10]").length).toBe(0);
    });
    // Numerator half recomputed exactly once, unconditionally (mirrors bulk-tag).
    expect(vi.mocked(updateVisibleURLsForTagCount)).toHaveBeenCalledTimes(1);
    // Survivors remain → mode is NOT exited, focus returns to the Exit control.
    expect(vi.mocked(exitMultiSelectMode)).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(
      document.getElementById("bulkSelectExit"),
    );
    expect(refreshTrashCount).toHaveBeenCalledTimes(1);
  });

  it("applyTagCountsInUtub writes the server denominator onto the affected tag chip", () => {
    seedUrlRows([10, 20, 99]);
    storeState.urls = [url(10, true), url(20, true), url(99, false)];
    // Tag 5 lives in the deck showing a STALE "2 / 4". The server-reported
    // UTub-wide total (7) is unreachable by any per-card ±1 of the stale base, so
    // the "2 / 7" assertion genuinely discriminates the direct server-set path
    // (the numerator recompute is stubbed, so it can't have moved the digit).
    $("#URLDeck").append(
      '<div class="tagFilter" data-utub-tag-id="5">' +
        '<span class="tagAppliedToUrlsCount">2 / 4</span>' +
        "</div>",
    );
    const deferred = activateAndPend(
      [10, 20],
      [url(10, true), url(20, true), url(99, false)],
    );

    deferred.resolve(
      deleteResponse({ deletedIds: [10, 20], tagCountsInUtub: { "5": 7 } }),
      "success",
      { status: 200 },
    );

    // Denominator half set directly to the authoritative server count (7); the
    // numerator half ("2") is left untouched for the (stubbed) later recompute.
    expect(
      $('.tagFilter[data-utub-tag-id="5"] .tagAppliedToUrlsCount').text(),
    ).toBe("2 / 7");
  });

  it("partial (skip + filter-hidden) → toast carries the skipped and hidden counts, amber cue on the survivor", () => {
    // id 10 deletable + visible; id 20 not deletable + visible (skipped);
    // id 30 deletable but NO row (hidden by filter).
    seedUrlRows([10, 20]);
    storeState.urls = [url(10, true), url(20, false)];
    const deferred = activateAndPend(
      [10, 20, 30],
      [url(10, true), url(20, false), url(30, true)],
    );

    deferred.resolve(deleteResponse({ deletedIds: [10, 30] }), "success", {
      status: 200,
    });

    expect(vi.mocked(showURLDeletedToast)).toHaveBeenCalledWith(
      expect.objectContaining({
        utubID: 1,
        deletedIDs: [10, 30],
        skippedCount: 1,
        hiddenCount: 1,
      }),
    );
    // The non-deletable survivor (id 20) flashes an amber "Can't delete" cue.
    const cue = $('.urlRow[utuburlid="20"] .bulkCardResultCue--skipped');
    expect(cue.length).toBe(1);
    expect(cue.text()).toBe(APP_CONFIG.strings.URL_BULK_CARD_CANT_DELETE);
  });

  it("dedupes a server-reported skipped id already in the client-side skipped partition", () => {
    seedUrlRows([10, 20]);
    storeState.urls = [url(10, true), url(20, false)];
    const deferred = activateAndPend([10, 20], [url(10, true), url(20, false)]);

    deferred.resolve(
      {
        ...deleteResponse({ deletedIds: [10] }),
        skipped: [{ utubUrlID: 20 }],
        totalSkipped: 1,
      },
      "success",
      { status: 200 },
    );

    expect(vi.mocked(showURLDeletedToast)).toHaveBeenCalledWith(
      expect.objectContaining({ deletedIDs: [10], skippedCount: 1 }),
    );
  });

  it("all-skipped success → failed toast (no Undo), forceFail false", () => {
    seedUrlRows([10]);
    storeState.urls = [url(10, true)];
    const deferred = activateAndPend([10], [url(10, true)]);

    // Server skipped the only id (permission drift): nothing deleted.
    deferred.resolve(
      {
        ...deleteResponse({ deletedIds: [] }),
        skipped: [{ utubUrlID: 10 }],
        totalSkipped: 1,
      },
      "success",
      { status: 200 },
    );

    expect(vi.mocked(showURLDeletedToast)).not.toHaveBeenCalled();
    expect(vi.mocked(showURLDeletionFailedToast)).toHaveBeenCalledWith({
      forceFail: false,
    });
    // Nothing was deleted, so the row's count must not move.
    expect(applyRowCountDelta).not.toHaveBeenCalled();
  });

  it("deck empties → outcome announced in the deck live region, toast still shows, mode exits", async () => {
    seedUrlRows([10, 20]);
    storeState.urls = [url(10, true), url(20, true)];
    const deferred = activateAndPend([10, 20], [url(10, true), url(20, true)]);

    deferred.resolve(deleteResponse({ deletedIds: [10, 20] }), "success", {
      status: 200,
    });

    expect($("#URLDeckOutcomeAnnouncement").text()).toContain(
      APP_CONFIG.strings.URL_MOVED_TO_TRASH.replace("{n}", "2"),
    );
    // The toast lives outside the bulk bar, so it still shows.
    expect(vi.mocked(showURLDeletedToast)).toHaveBeenCalledTimes(1);

    await vi.waitFor(() => {
      expect(vi.mocked(showURLsEmptyState)).toHaveBeenCalled();
    });
    expect(vi.mocked(hideURLSearchIcon)).toHaveBeenCalled();
    expect(vi.mocked(exitMultiSelectMode)).toHaveBeenCalled();
  });

  it("emits AppEvents.URL_DECK_CHANGED after a successful bulk delete", async () => {
    const { emit, AppEvents } = await import("../../../../lib/event-bus.js");
    seedUrlRows([10, 20]);
    storeState.urls = [url(10, true), url(20, true)];
    const deferred = activateAndPend([10, 20], [url(10, true), url(20, true)]);

    deferred.resolve(deleteResponse({ deletedIds: [10, 20] }), "success", {
      status: 200,
    });

    // The store-mutating bulk-delete site notifies the onboarding nudge system
    // (and any future url-deck consumer) that the deck's URL set changed.
    expect(emit).toHaveBeenCalledWith(AppEvents.URL_DECK_CHANGED);
  });

  it("lowers the selected row's URL count by the number actually deleted", () => {
    seedUrlRows([10, 20, 30]);
    storeState.urls = [url(10, true), url(20, true), url(30, true)];
    const deferred = activateAndPend(
      [10, 20, 30],
      [url(10, true), url(20, true), url(30, true)],
    );

    deferred.resolve(deleteResponse({ deletedIds: [10, 20] }), "success", {
      status: 200,
    });

    expect(applyRowCountDelta).toHaveBeenCalledTimes(1);
    expect(applyRowCountDelta).toHaveBeenCalledWith({
      utubID: 1,
      urlDelta: -2,
      memberDelta: 0,
    });
  });

  it("stale activeUTubID race → nothing rendered when the active UTub changes mid-flight", () => {
    seedUrlRows([10]);
    storeState.urls = [url(10, true)];
    const deferred = activateAndPend([10], [url(10, true)]);

    storeState.activeUTubID = 999;
    deferred.resolve(deleteResponse({ deletedIds: [10] }), "success", {
      status: 200,
    });

    expect(vi.mocked(showURLDeletedToast)).not.toHaveBeenCalled();
    expect($("#URLDeckOutcomeAnnouncement").text()).toBe("");
  });
});

describe("submit — failure paths", () => {
  it("is429Handled short-circuits the failure path", () => {
    vi.mocked(is429Handled).mockReturnValueOnce(true);
    const deferred = activateAndPend([10], [url(10, true)]);
    deferred.reject({ status: 429 });
    expect(vi.mocked(showURLDeletionFailedToast)).not.toHaveBeenCalled();
  });

  it("locked UTub 403 → inline deck banner, no error-page redirect", () => {
    const locationAssignSpy = vi
      .spyOn(window.location, "assign")
      .mockImplementation(() => {});
    try {
      const deferred = activateAndPend([10], [url(10, true)]);
      deferred.reject({
        status: 403,
        responseJSON: {
          errorCode: URL_UTUB_IS_LOCKED,
          message: LOCKED_MESSAGE,
        },
      });
      expect(vi.mocked(showURLDeckBannerError)).toHaveBeenCalledWith(
        LOCKED_MESSAGE,
      );
      expect(locationAssignSpy).not.toHaveBeenCalled();
    } finally {
      locationAssignSpy.mockRestore();
    }
  });

  it("message-level 400 → failed toast with forceFail", () => {
    const deferred = activateAndPend([10], [url(10, true)]);
    deferred.reject({
      status: 400,
      responseJSON: { message: "One or more URLs are not in this UTub." },
    });

    expect(vi.mocked(showURLDeletionFailedToast)).toHaveBeenCalledWith({
      forceFail: true,
    });
    expect(vi.mocked(showURLDeletedToast)).not.toHaveBeenCalled();
    expect(refreshTrashCount).not.toHaveBeenCalled();
  });

  it("400 after the active UTub changed mid-flight → no failed toast", () => {
    const deferred = activateAndPend([10], [url(10, true)]);
    storeState.activeUTubID = 999;
    deferred.reject({
      status: 400,
      responseJSON: { message: "One or more URLs are not in this UTub." },
    });

    expect(vi.mocked(showURLDeletionFailedToast)).not.toHaveBeenCalled();
  });

  it("redirects to the error page on a JSON 403 (non-locked)", () => {
    const locationAssignSpy = vi
      .spyOn(window.location, "assign")
      .mockImplementation(() => {});
    try {
      const deferred = activateAndPend([10], [url(10, true)]);
      deferred.reject({ status: 403, responseJSON: { message: "Forbidden" } });
      expect(locationAssignSpy).toHaveBeenCalledWith(
        APP_CONFIG.routes.errorPage,
      );
    } finally {
      locationAssignSpy.mockRestore();
    }
  });

  it("redirects to the error page on a JSON 404", () => {
    const locationAssignSpy = vi
      .spyOn(window.location, "assign")
      .mockImplementation(() => {});
    try {
      const deferred = activateAndPend([10], [url(10, true)]);
      deferred.reject({ status: 404, responseJSON: { message: "Not found" } });
      expect(locationAssignSpy).toHaveBeenCalledWith(
        APP_CONFIG.routes.errorPage,
      );
    } finally {
      locationAssignSpy.mockRestore();
    }
  });

  it("replaces the body with server HTML on a non-JSON 403 (CSRF expired)", () => {
    const deferred = activateAndPend([10], [url(10, true)]);
    const forbiddenHtml = '<div id="forbiddenPage">Forbidden</div>';
    deferred.reject({
      status: 403,
      responseText: forbiddenHtml,
      getResponseHeader: (name: string) =>
        name === "Content-Type" ? "text/html; charset=utf-8" : null,
    });
    expect($("#forbiddenPage").length).toBe(1);
  });
});
