import {
  initBulkDelete,
  isBulkDeleteConfirmOpen,
  setBulkDeleteConfirmOpen,
} from "../bulk-delete.js";
import { getAvailableBulkActions } from "../bulk-action-registry.js";
import type { BulkAction } from "../bulk-action-registry.js";
import { setPickerOpen } from "../picker-guard.js";
import { APP_CONFIG } from "../../../../lib/config.js";
import { ajaxCall, is429Handled } from "../../../../lib/ajax.js";
import { updateVisibleURLsForTagCount } from "../../cards/filtering.js";
import { showURLsEmptyState } from "../../empty-state.js";
import { hideURLSearchIcon } from "../../search.js";
import { exitMultiSelectMode } from "../bulk-mode.js";
import { showURLDeckBannerError } from "../../deck.js";
import { createMockJqXHR } from "../../../../__tests__/helpers/mock-jquery.js";

vi.mock("../../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));

// Partial mock: keep the real AppEvents enum AND the real `on` wiring that
// initBulkDelete relies on (URL_MULTISELECT_MODE_CHANGED subscription) functional,
// spying only `emit` so the URL_DECK_CHANGED notification fired on a successful
// bulk delete can be asserted.
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
vi.mock("../../../../store/app-store.js", () => ({
  getState: vi.fn(() => storeState),
  setState: vi.fn((partial: Partial<typeof storeState>) => {
    Object.assign(storeState, partial);
  }),
}));

const $ = window.jQuery;

const LOCKED_MESSAGE = "This UTub is locked and cannot be modified.";
const URL_UTUB_IS_LOCKED = 8;

// #confirmModal carries the CORRECTED aria-labelledby (the real homeModalBase.html
// fix). This is a hand-authored fixture check only — the authoritative regression
// coverage for the template is the Playwright assertion in Step 6.
const BASE_HTML = `
  <div id="URLDeck">
    <div id="listURLs"></div>
    <div id="bulkActionBar">
      <button id="bulkSelectExit" type="button">Exit</button>
      <div id="bulkActionButtons"></div>
      <div id="bulkDeleteResultBanner" class="bulkTagBanner hidden" role="status"></div>
    </div>
    <span id="URLDeckOutcomeAnnouncement" class="visually-hidden" aria-live="polite"></span>
    <div id="noURLsEmptyState" class="hidden"><p id="noURLsSubheader"></p></div>
  </div>
  <div id="confirmModal" class="modal fade" aria-labelledby="confirmModalTitle">
    <h4 id="confirmModalTitle"></h4>
    <div id="confirmModalBody"></div>
    <button id="modalDismiss" type="button"></button>
    <button id="modalRedirect" type="button"></button>
    <button id="modalSubmit" type="submit" class="btn btn-danger"></button>
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

/** Open the confirm modal for a selection/url-list. */
function openConfirmFor(selectedURLCardIDs: number[], urls: TestUrl[]): void {
  resolveDeleteAction().onActivate({
    selectedURLCardIDs,
    urls: urls as never,
  });
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
  $.fn.modal = vi.fn().mockReturnThis();
  $.fx.off = true;
  storeState.activeUTubID = 1;
  storeState.urls = [];
  storeState.selectedURLCardIDs = [];
  vi.clearAllMocks();
  vi.mocked(is429Handled).mockReturnValue(false);
  setBulkDeleteConfirmOpen(false);
  setPickerOpen("bulk-tag", false);
  setPickerOpen("bulk-copy", false);
});

afterEach(() => {
  $.fx.off = false;
  setBulkDeleteConfirmOpen(false);
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

describe("openBulkDeleteConfirm (onActivate)", () => {
  it("opens the confirm with a count-aware title and a deletable-count submit label", () => {
    openConfirmFor(
      [10, 20, 30],
      [url(10, true), url(20, true), url(30, false)],
    );

    expect(isBulkDeleteConfirmOpen()).toBe(true);
    expect($("#confirmModalTitle").text()).toBe(
      APP_CONFIG.strings.URL_BULK_DELETE_CONFIRM_TITLE.replace("{n}", "3"),
    );
    // 2 of the 3 selected are deletable → "Delete 2 URLs".
    expect($("#modalSubmit").text()).toBe(
      APP_CONFIG.strings.URL_BULK_DELETE_SUBMIT.replace("{n}", "2"),
    );
  });

  it("discloses the not-deletable skip scope in the confirm body", () => {
    openConfirmFor([10, 20], [url(10, true), url(20, false)]);
    // One selected URL is not deletable → skip warning shown.
    expect($("#confirmModalBody").text()).toContain(
      APP_CONFIG.strings.URL_BULK_DELETE_SKIPPED_WARNING_ONE,
    );
  });

  it("discloses the hidden-by-filter scope when a selected URL is not visible", () => {
    // id 10 has a visible row; id 20 has NO row (hidden by filter).
    seedUrlRows([10]);
    openConfirmFor([10, 20], [url(10, true), url(20, true)]);
    expect($("#confirmModalBody").text()).toContain(
      APP_CONFIG.strings.URL_BULK_DELETE_HIDDEN_WARNING_ONE,
    );
  });

  it("renders the plural {n}-interpolated hidden + skipped warnings (not the _ONE variants) for 2+ of each", () => {
    // id 10 → deletable + visible (the required deletable survivor).
    // ids 20, 30 → deletable but NO row → hidden by filter (2 hidden).
    // ids 40, 50 → not deletable but visible → skipped (2 skipped).
    seedUrlRows([10, 40, 50]);
    openConfirmFor(
      [10, 20, 30, 40, 50],
      [
        url(10, true),
        url(20, true),
        url(30, true),
        url(40, false),
        url(50, false),
      ],
    );

    const bodyText = $("#confirmModalBody").text();
    // Plural templates render with the correct interpolated counts…
    expect(bodyText).toContain(
      APP_CONFIG.strings.URL_BULK_DELETE_HIDDEN_WARNING.replace("{n}", "2"),
    );
    expect(bodyText).toContain(
      APP_CONFIG.strings.URL_BULK_DELETE_SKIPPED_WARNING.replace("{n}", "2"),
    );
    // …and the singular _ONE variants are NOT used when the count is > 1.
    expect(bodyText).not.toContain(
      APP_CONFIG.strings.URL_BULK_DELETE_HIDDEN_WARNING_ONE,
    );
    expect(bodyText).not.toContain(
      APP_CONFIG.strings.URL_BULK_DELETE_SKIPPED_WARNING_ONE,
    );
  });

  it("opening the confirm does NOT fire a request (confirm gates the AJAX)", () => {
    openConfirmFor([10], [url(10, true)]);
    expect(vi.mocked(ajaxCall)).not.toHaveBeenCalled();
  });

  it("cancel (Just kidding) closes the confirm without firing a request", () => {
    openConfirmFor([10], [url(10, true)]);
    $("#modalDismiss").trigger("click");
    expect(isBulkDeleteConfirmOpen()).toBe(false);
    expect(vi.mocked(ajaxCall)).not.toHaveBeenCalled();
  });

  it("no-ops (re-entrant) when another bulk picker is already open", () => {
    setPickerOpen("bulk-tag", true);
    openConfirmFor([10], [url(10, true)]);
    expect(isBulkDeleteConfirmOpen()).toBe(false);
    expect(vi.mocked(ajaxCall)).not.toHaveBeenCalled();
  });

  it("does not open when there is no active UTub", () => {
    storeState.activeUTubID = null;
    openConfirmFor([10], [url(10, true)]);
    expect(isBulkDeleteConfirmOpen()).toBe(false);
  });

  it("uses the aria-labelledby=confirmModalTitle contract on the shared modal (fixture smoke)", () => {
    expect($("#confirmModal").attr("aria-labelledby")).toBe(
      "confirmModalTitle",
    );
  });
});

describe("confirm submit + success (active-deck mutation)", () => {
  function openAndSubmit(
    selectedURLCardIDs: number[],
    urls: TestUrl[],
  ): ReturnType<typeof createMockJqXHR> {
    const deferred = createMockJqXHR();
    vi.mocked(ajaxCall).mockReturnValue(deferred);
    openConfirmFor(selectedURLCardIDs, urls);
    $("#modalSubmit").trigger("click");
    return deferred;
  }

  it("posts only the deletable snapshot to bulkDeleteURLs(activeUTubID)", () => {
    seedUrlRows([10, 20, 30]);
    storeState.urls = [url(10, true), url(20, true), url(30, false)];
    openAndSubmit([10, 20, 30], storeState.urls);

    expect(vi.mocked(ajaxCall)).toHaveBeenCalledTimes(1);
    const [method, requestUrl, body] = vi.mocked(ajaxCall).mock.calls[0];
    expect(method).toBe("post");
    expect(requestUrl).toBe(APP_CONFIG.routes.bulkDeleteURLs(1));
    // Only the two deletable ids travel; id 30 (not deletable) is skipped client-side.
    expect(body).toEqual({ utubUrlIds: [10, 20] });
  });

  it("clean delete → success banner, survivors remain, tag numerators recomputed once", async () => {
    seedUrlRows([10, 20, 99]);
    storeState.urls = [url(10, true), url(20, true), url(99, false)];
    const deferred = openAndSubmit(
      [10, 20],
      [url(10, true), url(20, true), url(99, false)],
    );

    deferred.resolve(deleteResponse({ deletedIds: [10, 20] }), "success", {
      status: 200,
    });

    const banner = $("#bulkDeleteResultBanner");
    expect(banner.hasClass("success")).toBe(true);
    expect(banner.attr("aria-live")).toBe("polite");
    expect(banner.text()).toContain(
      APP_CONFIG.strings.URL_BULK_DELETED.replace("{n}", "2"),
    );

    await vi.waitFor(() => {
      expect($("#listURLs .urlRow[utuburlid=10]").length).toBe(0);
    });
    // Numerator half recomputed exactly once, unconditionally (mirrors bulk-tag).
    expect(vi.mocked(updateVisibleURLsForTagCount)).toHaveBeenCalledTimes(1);
    // Survivors remain → mode is NOT exited.
    expect(vi.mocked(exitMultiSelectMode)).not.toHaveBeenCalled();
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
    const deferred = openAndSubmit(
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

  it("partial (client-side skip) → partial banner + amber Can't-delete cue on the survivor", () => {
    seedUrlRows([10, 20]);
    storeState.urls = [url(10, true), url(20, false)];
    const deferred = openAndSubmit([10, 20], [url(10, true), url(20, false)]);

    deferred.resolve(deleteResponse({ deletedIds: [10] }), "success", {
      status: 200,
    });

    const banner = $("#bulkDeleteResultBanner");
    expect(banner.hasClass("partial")).toBe(true);
    expect(banner.attr("aria-live")).toBe("assertive");
    expect(banner.text()).toContain(APP_CONFIG.strings.URL_BULK_DELETED_ONE);
    // The non-deletable survivor (id 20) flashes an amber "Can't delete" cue.
    const cue = $('.urlRow[utuburlid="20"] .bulkCardResultCue--skipped');
    expect(cue.length).toBe(1);
    expect(cue.text()).toBe(APP_CONFIG.strings.URL_BULK_CARD_CANT_DELETE);
  });

  it("deck empties → outcome announced in the deck live region, bulk banner stays empty, mode exits", async () => {
    seedUrlRows([10, 20]);
    storeState.urls = [url(10, true), url(20, true)];
    const deferred = openAndSubmit([10, 20], [url(10, true), url(20, true)]);

    deferred.resolve(deleteResponse({ deletedIds: [10, 20] }), "success", {
      status: 200,
    });

    // The deck-level announcer carries the outcome; the bulk-bar banner does NOT.
    expect($("#URLDeckOutcomeAnnouncement").text()).toContain(
      APP_CONFIG.strings.URL_BULK_DELETED.replace("{n}", "2"),
    );
    expect($("#bulkDeleteResultBanner").text()).toBe("");

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
    const deferred = openAndSubmit([10, 20], [url(10, true), url(20, true)]);

    deferred.resolve(deleteResponse({ deletedIds: [10, 20] }), "success", {
      status: 200,
    });

    // The store-mutating bulk-delete site notifies the onboarding nudge system
    // (and any future url-deck consumer) that the deck's URL set changed.
    expect(emit).toHaveBeenCalledWith(AppEvents.URL_DECK_CHANGED);
  });

  it("stale activeUTubID race → nothing rendered when the active UTub changes mid-flight", () => {
    seedUrlRows([10]);
    storeState.urls = [url(10, true)];
    const deferred = openAndSubmit([10], [url(10, true)]);

    storeState.activeUTubID = 999;
    deferred.resolve(deleteResponse({ deletedIds: [10] }), "success", {
      status: 200,
    });

    expect($("#bulkDeleteResultBanner").hasClass("hidden")).toBe(true);
    expect($("#URLDeckOutcomeAnnouncement").text()).toBe("");
  });
});

describe("confirm submit — failure paths", () => {
  function openAndSubmit(
    selectedURLCardIDs: number[],
    urls: TestUrl[],
  ): ReturnType<typeof createMockJqXHR> {
    const deferred = createMockJqXHR();
    vi.mocked(ajaxCall).mockReturnValue(deferred);
    openConfirmFor(selectedURLCardIDs, urls);
    $("#modalSubmit").trigger("click");
    return deferred;
  }

  it("is429Handled short-circuits the failure path", () => {
    vi.mocked(is429Handled).mockReturnValueOnce(true);
    const deferred = openAndSubmit([10], [url(10, true)]);
    deferred.reject({ status: 429 });
    expect($("#bulkDeleteResultBanner").hasClass("fail")).toBe(false);
  });

  it("locked UTub 403 → inline deck banner, no error-page redirect", () => {
    const locationAssignSpy = vi
      .spyOn(window.location, "assign")
      .mockImplementation(() => {});
    try {
      const deferred = openAndSubmit([10], [url(10, true)]);
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

  it("message-level 400 → fail banner (UNABLE_TO_DELETE_URLS) and the modal closes", () => {
    const deferred = openAndSubmit([10], [url(10, true)]);
    deferred.reject({
      status: 400,
      responseJSON: { message: "One or more URLs are not in this UTub." },
    });

    const banner = $("#bulkDeleteResultBanner");
    expect(banner.hasClass("fail")).toBe(true);
    expect(banner.attr("aria-live")).toBe("assertive");
    expect(banner.text()).toContain(APP_CONFIG.strings.UNABLE_TO_DELETE_URLS);
    expect(isBulkDeleteConfirmOpen()).toBe(false);
  });

  it("redirects to the error page on a JSON 403 (non-locked)", () => {
    const locationAssignSpy = vi
      .spyOn(window.location, "assign")
      .mockImplementation(() => {});
    try {
      const deferred = openAndSubmit([10], [url(10, true)]);
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
      const deferred = openAndSubmit([10], [url(10, true)]);
      deferred.reject({ status: 404, responseJSON: { message: "Not found" } });
      expect(locationAssignSpy).toHaveBeenCalledWith(
        APP_CONFIG.routes.errorPage,
      );
    } finally {
      locationAssignSpy.mockRestore();
    }
  });

  it("replaces the body with server HTML on a non-JSON 403 (CSRF expired)", () => {
    const deferred = openAndSubmit([10], [url(10, true)]);
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
