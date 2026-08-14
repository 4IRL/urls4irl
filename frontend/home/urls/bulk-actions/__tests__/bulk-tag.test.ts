import {
  initBulkTag,
  isBulkTagPickerOpen,
  setBulkTagPickerOpen,
} from "../bulk-tag.js";
import { getAvailableBulkActions } from "../bulk-action-registry.js";
import type { BulkAction, BulkActionContext } from "../bulk-action-registry.js";
import { APP_CONFIG } from "../../../../lib/config.js";
import { ajaxCall, is429Handled } from "../../../../lib/ajax.js";
import { AppEvents, emit } from "../../../../lib/event-bus.js";
import { mergeAppliedTagsIntoStore } from "../../tags/combobox-state.js";
import { createTagBadgeInURL } from "../../tags/tags.js";
import { buildTagFilterInDeck } from "../../../tags/tags.js";
import { isTagInUTubTagDeck } from "../../../tags/utils.js";
import { updateVisibleURLsForTagCount } from "../../cards/filtering.js";
import { createMockJqXHR } from "../../../../__tests__/helpers/mock-jquery.js";

// --- Combobox mock: bulk-tag.ts drives the real BULK combobox in production, but
// this suite isolates bulk-tag's own lifecycle. Fake createTagComboboxBlock builds
// a minimal wrap with the elements bulk-tag queries and captures the onSubmit
// callback (production wires it to the submit button / Enter key) so tests can
// invoke a "user submit" directly. The real combobox BULK mode is covered by
// tags/__tests__/combobox-bulk.test.ts.
const comboboxState = vi.hoisted(() => ({
  lastOnSubmit: null as ((stagedStrings: string[]) => void) | null,
  lastSelectedCount: 0,
  lastResetSpy: null as ReturnType<typeof vi.fn> | null,
}));

vi.mock("../../tags/combobox.js", () => {
  const BULK_RESET_KEY = "urlTagComboboxResetBulk";
  const ComboboxMode = Object.freeze({
    URL: "url",
    CREATE: "create",
    BULK: "bulk",
  } as const);
  return {
    BULK_RESET_KEY,
    ComboboxMode,
    createTagComboboxBlock: vi.fn(
      (args: {
        onSubmit?: (stagedStrings: string[]) => void;
        selectedCount?: number;
      }) => {
        comboboxState.lastOnSubmit = args.onSubmit ?? null;
        comboboxState.lastSelectedCount = args.selectedCount ?? 0;
        const jq = window.jQuery;
        const wrap = jq(
          '<div class="urlTagComboboxWrap hidden">' +
            '<input class="urlTagComboboxInput" />' +
            '<div class="urlTagListbox hidden"></div>' +
            '<div class="urlTagComboboxMsg"></div>' +
            '<div class="urlTagComboboxFooter">' +
            '<div class="urlTagComboboxActions">' +
            '<button class="urlTagComboboxSubmitBtn" type="button"></button>' +
            "</div>" +
            "</div>" +
            "</div>",
        );
        // Mirror the real BULK_RESET_KEY closure's card-independent DOM reset so
        // teardown clears the transient message/input/chips realistically.
        const resetSpy = vi.fn(() => {
          wrap.find(".urlTagComboboxInput").val("").prop("disabled", false);
          wrap.find(".urlTagStagedChip").remove();
          wrap.find(".urlTagListbox").empty().addClass("hidden");
          wrap.find(".urlTagComboboxMsg").text("").removeClass("warn");
        });
        comboboxState.lastResetSpy = resetSpy;
        wrap.data(BULK_RESET_KEY, resetSpy);
        return wrap;
      },
    ),
  };
});

vi.mock("../../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));

vi.mock("../../../../lib/modal-tracking.js", () => ({
  setOpenForm: vi.fn(),
  clearOpenForm: vi.fn(),
}));

const { mockMetricsClient } = await vi.hoisted(
  async () =>
    await import("../../../../__tests__/helpers/mock-metrics-client.js"),
);
vi.mock("../../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../../tags/combobox-state.js", () => ({
  mergeAppliedTagsIntoStore: vi.fn(),
}));

vi.mock("../../tags/tags.js", () => ({
  createTagBadgeInURL: vi.fn(() =>
    window.jQuery('<span class="tagBadge"></span>'),
  ),
}));

vi.mock("../../../tags/tags.js", () => ({
  buildTagFilterInDeck: vi.fn(() =>
    window.jQuery('<div class="tagFilter"></div>'),
  ),
}));

vi.mock("../../../tags/utils.js", () => ({
  isTagInUTubTagDeck: vi.fn(() => false),
}));

vi.mock("../../../tags/search.js", () => ({
  reapplyTagFilter: vi.fn(),
}));

vi.mock("../../cards/filtering.js", () => ({
  updateVisibleURLsForTagCount: vi.fn(),
}));

interface StoreUrl {
  utubUrlID: number;
  utubUrlTagIDs: number[];
  urlTitle: string;
}
const storeState: { activeUTubID: number | null; urls: StoreUrl[] } = {
  activeUTubID: 1,
  urls: [],
};
vi.mock("../../../../store/app-store.js", () => ({
  getState: vi.fn(() => storeState),
  setState: vi.fn((partial: Partial<typeof storeState>) => {
    Object.assign(storeState, partial);
  }),
}));

const $ = window.jQuery;

interface AppliedEntry {
  utubUrlID: number;
  utubUrlTagIDs: number[];
  appliedTags: { id: number; tagString: string; tagApplied: number }[];
}
interface SkippedEntry {
  utubUrlID: number;
  reason: string;
}

/** Minimal bar/deck scaffold bulk-tag queries during the open/submit lifecycle. */
const BASE_HTML = `
  <div id="URLDeck">
    <div id="listURLs"></div>
    <div id="bulkActionBar">
      <span id="bulkSelectCount">0</span>
      <button id="bulkSelectExit" type="button">Exit</button>
      <div id="bulkTagPickerMount" class="hidden"></div>
      <div id="bulkTagResultBanner" class="hidden" role="status"></div>
    </div>
    <div id="listTags"></div>
    <div id="unselectAllTagFilters" class="hidden"></div>
    <div id="utubTagBtnUpdateAllOpen" class="hidden"></div>
  </div>
`;

function seedUrlRows(ids: number[]): void {
  const listURLs = $("#listURLs");
  ids.forEach((id) => {
    listURLs.append(
      `<div class="urlRow" utuburlid="${id}"><div class="urlTagsContainer"></div></div>`,
    );
  });
}

function getBulkAction(): BulkAction {
  const context: BulkActionContext = {
    selectedURLCardIDs: [1],
    urls: [],
  };
  const action = getAvailableBulkActions(context).find(
    (candidate) => candidate.id === "bulk-add-tags",
  );
  if (!action) throw new Error("bulk-add-tags action not registered");
  return action;
}

function pickerWrap(): JQuery {
  return $("#bulkTagPickerMount").find(".urlTagComboboxWrap");
}

/** Open the picker for a selection, returning the mounted wrap. */
function openPickerFor(selectedURLCardIDs: number[]): JQuery {
  // The context's `urls` is the full UtubUrlItem[]; this suite only needs the
  // fields bulk-tag actually reads (utubUrlID/utubUrlTagIDs/urlTitle), so the
  // minimal StoreUrl[] is cast at the boundary.
  getBulkAction().onActivate({
    selectedURLCardIDs,
    urls: storeState.urls as unknown as BulkActionContext["urls"],
  });
  return pickerWrap();
}

beforeAll(() => {
  // Registers the bulk-add-tags action + the mode-exit teardown subscription.
  // Idempotent (guarded) so a single call is enough for the whole file.
  document.body.innerHTML = BASE_HTML;
  initBulkTag();
});

beforeEach(() => {
  document.body.innerHTML = BASE_HTML;
  storeState.activeUTubID = 1;
  storeState.urls = [];
  comboboxState.lastOnSubmit = null;
  comboboxState.lastSelectedCount = 0;
  comboboxState.lastResetSpy = null;
  vi.clearAllMocks();
  vi.mocked(is429Handled).mockReturnValue(false);
  vi.mocked(isTagInUTubTagDeck).mockReturnValue(false);
});

afterEach(() => {
  // Close any still-open picker so module-scoped lifecycle state never leaks.
  if (isBulkTagPickerOpen()) {
    emit(AppEvents.URL_MULTISELECT_MODE_CHANGED, { active: false });
  }
  setBulkTagPickerOpen(false);
  document.body.innerHTML = "";
});

describe("bulk-tag action registration + availability", () => {
  it("registers the bulk-add-tags action with the Add-tags label", () => {
    const action = getBulkAction();
    expect(action.label).toBe(APP_CONFIG.strings.ADD_TAGS_SUBMIT);
  });

  it("isAvailable is true only for a non-empty selection", () => {
    const action = getBulkAction();
    expect(action.isAvailable({ selectedURLCardIDs: [1], urls: [] })).toBe(
      true,
    );
    expect(action.isAvailable({ selectedURLCardIDs: [], urls: [] })).toBe(
      false,
    );
  });
});

describe("openBulkTagPicker (onActivate)", () => {
  it("mounts the picker in #bulkTagPickerMount and locks the selection", () => {
    openPickerFor([10, 20]);

    expect(pickerWrap().length).toBe(1);
    expect(isBulkTagPickerOpen()).toBe(true);
    // The deck lock cue is applied while the picker is open.
    expect($("#URLDeck").hasClass("bulkTagPickerOpen")).toBe(true);
    // A Cancel button was prepended into the combobox action row.
    expect(pickerWrap().find(".urlTagComboboxCancelBtn").length).toBe(1);
  });

  it("is a no-op re-entrant activation (never double-mounts)", () => {
    openPickerFor([10, 20]);
    openPickerFor([10, 20]);

    expect($("#bulkTagPickerMount").find(".urlTagComboboxWrap").length).toBe(1);
  });
});

describe("submitBulkTags — success", () => {
  function successResponse(
    applied: AppliedEntry[],
    skipped: SkippedEntry[],
  ): { applied: AppliedEntry[]; skipped: SkippedEntry[] } {
    return { applied, skipped };
  }

  it("merges applied tags, appends a badge to each applied card, and closes the picker", () => {
    seedUrlRows([10, 20]);
    storeState.urls = [
      { utubUrlID: 10, utubUrlTagIDs: [], urlTitle: "Alpha" },
      { utubUrlID: 20, utubUrlTagIDs: [], urlTitle: "Beta" },
    ];
    openPickerFor([10, 20]);

    const deferred = createMockJqXHR();
    vi.mocked(ajaxCall).mockReturnValue(deferred);

    comboboxState.lastOnSubmit!(["python"]);
    deferred.resolve(
      successResponse(
        [
          {
            utubUrlID: 10,
            utubUrlTagIDs: [1],
            appliedTags: [{ id: 1, tagString: "python", tagApplied: 3 }],
          },
          {
            utubUrlID: 20,
            utubUrlTagIDs: [1],
            appliedTags: [{ id: 1, tagString: "python", tagApplied: 3 }],
          },
        ],
        [],
      ),
      "success",
      { status: 200 },
    );

    expect(vi.mocked(mergeAppliedTagsIntoStore)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(createTagBadgeInURL)).toHaveBeenCalledTimes(2);
    expect($('.urlRow[utuburlid="10"] .tagBadge').length).toBe(1);
    expect($('.urlRow[utuburlid="20"] .tagBadge').length).toBe(1);
    expect(isBulkTagPickerOpen()).toBe(false);
  });

  it("renders the all-succeeded banner (plural) with success styling", () => {
    seedUrlRows([10, 20]);
    storeState.urls = [
      { utubUrlID: 10, utubUrlTagIDs: [], urlTitle: "Alpha" },
      { utubUrlID: 20, utubUrlTagIDs: [], urlTitle: "Beta" },
    ];
    openPickerFor([10, 20]);

    const deferred = createMockJqXHR();
    vi.mocked(ajaxCall).mockReturnValue(deferred);
    comboboxState.lastOnSubmit!(["python"]);
    deferred.resolve(
      successResponse(
        [
          {
            utubUrlID: 10,
            utubUrlTagIDs: [1],
            appliedTags: [{ id: 1, tagString: "python", tagApplied: 3 }],
          },
          {
            utubUrlID: 20,
            utubUrlTagIDs: [1],
            appliedTags: [{ id: 1, tagString: "python", tagApplied: 3 }],
          },
        ],
        [],
      ),
      "success",
      { status: 200 },
    );

    const banner = $("#bulkTagResultBanner");
    expect(banner.hasClass("hidden")).toBe(false);
    expect(banner.hasClass("success")).toBe(true);
    expect(banner.text()).toContain(
      APP_CONFIG.strings.URL_BULK_TAGS_APPLIED.replace("{n}", "2"),
    );
    expect(banner.attr("aria-live")).toBe("polite");
  });

  it("renders the partial banner naming the skipped URL and skips that card", () => {
    seedUrlRows([10, 30]);
    storeState.urls = [
      { utubUrlID: 10, utubUrlTagIDs: [], urlTitle: "Alpha" },
      { utubUrlID: 30, utubUrlTagIDs: [], urlTitle: "Gamma" },
    ];
    openPickerFor([10, 30]);

    const deferred = createMockJqXHR();
    vi.mocked(ajaxCall).mockReturnValue(deferred);
    comboboxState.lastOnSubmit!(["python"]);
    deferred.resolve(
      successResponse(
        [
          {
            utubUrlID: 10,
            utubUrlTagIDs: [1],
            appliedTags: [{ id: 1, tagString: "python", tagApplied: 3 }],
          },
        ],
        [{ utubUrlID: 30, reason: "overLimit" }],
      ),
      "success",
      { status: 200 },
    );

    const banner = $("#bulkTagResultBanner");
    expect(banner.hasClass("partial")).toBe(true);
    expect(banner.text()).toContain("Gamma");
    // The skipped card gains no badge.
    expect($('.urlRow[utuburlid="30"] .tagBadge').length).toBe(0);
    expect($('.urlRow[utuburlid="10"] .tagBadge').length).toBe(1);
  });

  it("HTML-escapes a hostile skipped URL title in the partial banner", () => {
    const hostileTitle = '<img src=x onerror="alert(1)">';
    seedUrlRows([10, 30]);
    storeState.urls = [
      { utubUrlID: 10, utubUrlTagIDs: [], urlTitle: "Alpha" },
      { utubUrlID: 30, utubUrlTagIDs: [], urlTitle: hostileTitle },
    ];
    openPickerFor([10, 30]);

    const deferred = createMockJqXHR();
    vi.mocked(ajaxCall).mockReturnValue(deferred);
    comboboxState.lastOnSubmit!(["python"]);
    deferred.resolve(
      successResponse(
        [
          {
            utubUrlID: 10,
            utubUrlTagIDs: [1],
            appliedTags: [{ id: 1, tagString: "python", tagApplied: 3 }],
          },
        ],
        [{ utubUrlID: 30, reason: "overLimit" }],
      ),
      "success",
      { status: 200 },
    );

    const banner = $("#bulkTagResultBanner");
    // The title is rendered as escaped TEXT, never parsed into a live element.
    expect(banner.find("img").length).toBe(0);
    expect(banner.text()).toContain(hostileTitle);
  });

  it("renders the all-over-limit banner (assertive) and applies no badges", () => {
    seedUrlRows([10, 20]);
    storeState.urls = [
      { utubUrlID: 10, utubUrlTagIDs: [], urlTitle: "Alpha" },
      { utubUrlID: 20, utubUrlTagIDs: [], urlTitle: "Beta" },
    ];
    openPickerFor([10, 20]);

    const deferred = createMockJqXHR();
    vi.mocked(ajaxCall).mockReturnValue(deferred);
    comboboxState.lastOnSubmit!(["python"]);
    deferred.resolve(
      successResponse(
        [],
        [
          { utubUrlID: 10, reason: "overLimit" },
          { utubUrlID: 20, reason: "overLimit" },
        ],
      ),
      "success",
      { status: 200 },
    );

    const banner = $("#bulkTagResultBanner");
    expect(banner.hasClass("fail")).toBe(true);
    expect(banner.attr("aria-live")).toBe("assertive");
    expect(banner.text()).toContain(
      APP_CONFIG.strings.URL_BULK_TAGS_NONE.replace("{n}", "2").replace(
        "{max}",
        String(APP_CONFIG.constants.TAGS_MAX_ON_URLS),
      ),
    );
    expect(vi.mocked(createTagBadgeInURL)).not.toHaveBeenCalled();
  });
});

describe("submitBulkTags — failure handling", () => {
  it("short-circuits (no inline warn) when is429Handled returns true", () => {
    seedUrlRows([10]);
    storeState.urls = [{ utubUrlID: 10, utubUrlTagIDs: [], urlTitle: "Alpha" }];
    const wrap = openPickerFor([10]);

    vi.mocked(is429Handled).mockReturnValueOnce(true);
    const deferred = createMockJqXHR();
    vi.mocked(ajaxCall).mockReturnValue(deferred);
    comboboxState.lastOnSubmit!(["python"]);
    deferred.reject({ status: 429 });

    // The 400 field/message branch never ran, so no warn styling was applied.
    expect(wrap.find(".urlTagComboboxMsg").hasClass("warn")).toBe(false);
  });

  it("renders a 400 field error inline in the combobox message", () => {
    seedUrlRows([10]);
    storeState.urls = [{ utubUrlID: 10, utubUrlTagIDs: [], urlTitle: "Alpha" }];
    const wrap = openPickerFor([10]);

    const deferred = createMockJqXHR();
    vi.mocked(ajaxCall).mockReturnValue(deferred);
    comboboxState.lastOnSubmit!(["python"]);
    deferred.reject({
      status: 400,
      responseJSON: { errors: { tagStrings: ["Too many tags"] } },
    });

    expect(wrap.find(".urlTagComboboxMsg").text()).toBe("Too many tags");
    expect(wrap.find(".urlTagComboboxMsg").hasClass("warn")).toBe(true);
  });

  it("renders the stale-selection copy for a message-level 400 (URL_NOT_IN_UTUB)", () => {
    seedUrlRows([10]);
    storeState.urls = [{ utubUrlID: 10, utubUrlTagIDs: [], urlTitle: "Alpha" }];
    const wrap = openPickerFor([10]);

    const deferred = createMockJqXHR();
    vi.mocked(ajaxCall).mockReturnValue(deferred);
    comboboxState.lastOnSubmit!(["python"]);
    deferred.reject({
      status: 400,
      responseJSON: { message: "One or more URLs are not in this UTub." },
    });

    expect(wrap.find(".urlTagComboboxMsg").text()).toBe(
      APP_CONFIG.strings.URL_BULK_TAGS_STALE_SELECTION,
    );
  });
});

describe("submitBulkTags — in-flight button + message state (DD-19, DD-20)", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("disables submit + Cancel and posts the transient message, re-enabling on success", () => {
    seedUrlRows([10]);
    storeState.urls = [{ utubUrlID: 10, utubUrlTagIDs: [], urlTitle: "Alpha" }];
    const wrap = openPickerFor([10]);
    const submitBtn = wrap.find(".urlTagComboboxSubmitBtn");
    const cancelBtn = wrap.find(".urlTagComboboxCancelBtn");

    const deferred = createMockJqXHR();
    vi.mocked(ajaxCall).mockReturnValue(deferred);
    comboboxState.lastOnSubmit!(["python"]);

    // In flight: both buttons disabled, transient live-region message posted.
    expect(submitBtn.prop("disabled")).toBe(true);
    expect(cancelBtn.prop("disabled")).toBe(true);
    expect(wrap.find(".urlTagComboboxMsg").text()).toBe(
      APP_CONFIG.strings.URL_BULK_TAGS_SUBMITTING,
    );

    // The loading spinner class appears after the delay threshold.
    vi.advanceTimersByTime(60);
    expect(submitBtn.hasClass("bulkTagSubmitLoading")).toBe(true);

    deferred.resolve(
      {
        applied: [
          {
            utubUrlID: 10,
            utubUrlTagIDs: [1],
            appliedTags: [{ id: 1, tagString: "python", tagApplied: 3 }],
          },
        ],
        skipped: [],
      },
      "success",
      { status: 200 },
    );

    // Settled: buttons re-enabled, spinner gone, transient message cleared by
    // the reset (the outcome now lives in the result banner).
    expect(submitBtn.prop("disabled")).toBe(false);
    expect(cancelBtn.prop("disabled")).toBe(false);
    expect(submitBtn.hasClass("bulkTagSubmitLoading")).toBe(false);
    expect(wrap.find(".urlTagComboboxMsg").text()).toBe("");
  });

  it("re-enables submit + Cancel and hides the spinner on failure too", () => {
    seedUrlRows([10]);
    storeState.urls = [{ utubUrlID: 10, utubUrlTagIDs: [], urlTitle: "Alpha" }];
    const wrap = openPickerFor([10]);
    const submitBtn = wrap.find(".urlTagComboboxSubmitBtn");
    const cancelBtn = wrap.find(".urlTagComboboxCancelBtn");

    const deferred = createMockJqXHR();
    vi.mocked(ajaxCall).mockReturnValue(deferred);
    comboboxState.lastOnSubmit!(["python"]);
    vi.advanceTimersByTime(60);
    expect(submitBtn.hasClass("bulkTagSubmitLoading")).toBe(true);

    deferred.reject({
      status: 400,
      responseJSON: { errors: { tagStrings: ["Too many tags"] } },
    });

    expect(submitBtn.prop("disabled")).toBe(false);
    expect(cancelBtn.prop("disabled")).toBe(false);
    expect(submitBtn.hasClass("bulkTagSubmitLoading")).toBe(false);
  });
});

describe("Escape precedence (container capture-phase listener) — DD", () => {
  // Fake timers so the in-flight test's never-settled submit leaves no real
  // pending spinner timeout on the runner.
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("first Escape closes only the dropdown; second discards + closes + stops propagation", () => {
    const wrap = openPickerFor([10]);
    // Simulate an open dropdown for the first Escape.
    wrap.find(".urlTagListbox").removeClass("hidden");

    const docSpy = vi.fn();
    document.addEventListener("keydown", docSpy);

    try {
      const input = wrap.find(".urlTagComboboxInput")[0];
      input.dispatchEvent(
        new KeyboardEvent("keydown", {
          key: "Escape",
          bubbles: true,
          cancelable: true,
        }),
      );
      // Dropdown closed, picker still open.
      expect(wrap.find(".urlTagListbox").hasClass("hidden")).toBe(true);
      expect(isBulkTagPickerOpen()).toBe(true);

      input.dispatchEvent(
        new KeyboardEvent("keydown", {
          key: "Escape",
          bubbles: true,
          cancelable: true,
        }),
      );
      // Second Escape discards + closes the whole picker.
      expect(isBulkTagPickerOpen()).toBe(false);
      // The capture-phase handler stopped propagation both times, so the
      // document-level (multi-select-exit) handler never saw the event.
      expect(docSpy).not.toHaveBeenCalled();
    } finally {
      // Always detach so a native keydown listener never leaks onto the
      // persistent `document` into later tests, even on an assertion throw.
      document.removeEventListener("keydown", docSpy);
    }
  });

  it("second Escape is a no-op while a submit is in flight (still swallowed)", () => {
    const wrap = openPickerFor([10]);
    storeState.urls = [{ utubUrlID: 10, utubUrlTagIDs: [], urlTitle: "Alpha" }];

    // Start a submit but never settle it → in flight.
    const deferred = createMockJqXHR();
    vi.mocked(ajaxCall).mockReturnValue(deferred);
    comboboxState.lastOnSubmit!(["python"]);

    const input = wrap.find(".urlTagComboboxInput")[0];
    // Listbox already hidden → this is the "second Escape" branch.
    input.dispatchEvent(
      new KeyboardEvent("keydown", {
        key: "Escape",
        bubbles: true,
        cancelable: true,
      }),
    );

    // In flight: the picker is NOT torn down by Escape.
    expect(isBulkTagPickerOpen()).toBe(true);
  });
});

describe("picker/flag teardown on mode exit (DD-17)", () => {
  it("URL_MULTISELECT_MODE_CHANGED active:false runs the reset and clears the flag", () => {
    openPickerFor([10, 20]);
    expect(isBulkTagPickerOpen()).toBe(true);

    emit(AppEvents.URL_MULTISELECT_MODE_CHANGED, { active: false });

    expect(isBulkTagPickerOpen()).toBe(false);
    expect(comboboxState.lastResetSpy).toHaveBeenCalledTimes(1);
    expect($("#bulkTagPickerMount").hasClass("hidden")).toBe(true);
    expect($("#URLDeck").hasClass("bulkTagPickerOpen")).toBe(false);
  });
});

describe("once-per-distinct-tag deck sync (DD-23)", () => {
  it("writes the authoritative total once for an already-in-deck tag applied to 2+ URLs", () => {
    seedUrlRows([10, 20]);
    storeState.urls = [
      { utubUrlID: 10, utubUrlTagIDs: [], urlTitle: "Alpha" },
      { utubUrlID: 20, utubUrlTagIDs: [], urlTitle: "Beta" },
    ];
    // Tag 5 already lives in the deck showing "2 / 4". The authoritative total
    // (9) is chosen so it CANNOT be reached by incrementing the base (4) once per
    // applied card (4 -> 5 -> 6): a per-card ±1 path would yield "2 / 6", so the
    // "2 / 9" assertion below genuinely discriminates the direct-set-once path.
    $("#listTags").html(
      '<div class="tagFilter" data-utub-tag-id="5">' +
        '<span class="tagAppliedToUrlsCount">2 / 4</span>' +
        "</div>",
    );
    vi.mocked(isTagInUTubTagDeck).mockImplementation((tagId) => tagId === 5);

    openPickerFor([10, 20]);
    const deferred = createMockJqXHR();
    vi.mocked(ajaxCall).mockReturnValue(deferred);
    comboboxState.lastOnSubmit!(["shared"]);
    // The same tag id 5 is named on BOTH applied entries (applied to 2 URLs).
    deferred.resolve(
      {
        applied: [
          {
            utubUrlID: 10,
            utubUrlTagIDs: [5],
            appliedTags: [{ id: 5, tagString: "shared", tagApplied: 9 }],
          },
          {
            utubUrlID: 20,
            utubUrlTagIDs: [5],
            appliedTags: [{ id: 5, tagString: "shared", tagApplied: 9 }],
          },
        ],
        skipped: [],
      },
      "success",
      { status: 200 },
    );

    // Total digit set directly to the authoritative UTub-wide count (9), ONCE —
    // not the two base+1 increments (which would land on "2 / 6") a per-card
    // deck-sync path would have produced.
    expect(
      $('.tagFilter[data-utub-tag-id="5"] .tagAppliedToUrlsCount').text(),
    ).toBe("2 / 9");
    // Already-in-deck → no new deck filter built; a single visible-count recompute.
    expect(vi.mocked(buildTagFilterInDeck)).not.toHaveBeenCalled();
    expect(vi.mocked(updateVisibleURLsForTagCount)).toHaveBeenCalledTimes(1);
  });
});
