/**
 * Refresh-on-focus trigger: debounce clock, busy gate, coalescing and cleanup.
 *
 * CRITICAL: `vi.useFakeTimers()` is installed in `beforeEach` BEFORE
 * `initUTubRefreshOnFocus()` so the init-time clock seed
 * (`performance.now()`) is controlled by the fake clock.
 */

const mocks = vi.hoisted(() => ({
  updateUTubOnFindingStaleData: vi.fn(),
  isUTubSelected: vi.fn(() => true),
  getOpenForm: vi.fn((): string | null => null),
  isAnyBulkPickerOpen: vi.fn(() => false),
  isTransferPickerOpen: vi.fn(() => false),
  isTagSheetOpen: vi.fn(() => false),
  isURLTitleSubmitInFlight: vi.fn(() => false),
  isURLStringSubmitInFlight: vi.fn(() => false),
  isUTubNameSubmitInFlight: vi.fn(() => false),
  isUTubDescriptionSubmitInFlight: vi.fn(() => false),
  isBulkTagSubmitInFlight: vi.fn(() => false),
  isBulkDeleteSubmitInFlight: vi.fn(() => false),
  isURLDeleteInFlight: vi.fn(() => false),
  isURLDeleteUndoInFlight: vi.fn(() => false),
  isURLDeleteToastShowing: vi.fn(() => false),
  isBulkCopySubmitInFlight: vi.fn(() => false),
  isCrossUtubSearchActive: vi.fn(() => false),
  log: vi.fn(),
  storeState: {
    activeUTubID: 7 as number | null,
    multiSelectMode: false,
  },
}));

vi.mock("../stale-data.js", () => ({
  updateUTubOnFindingStaleData: mocks.updateUTubOnFindingStaleData,
}));
vi.mock("../utils.js", () => ({ isUTubSelected: mocks.isUTubSelected }));
vi.mock("../../../store/app-store.js", () => ({
  getState: () => mocks.storeState,
}));
vi.mock("../../../lib/debug.js", () => ({ debug: () => mocks.log }));
vi.mock("../../../lib/modal-tracking.js", () => ({
  getOpenForm: mocks.getOpenForm,
}));
vi.mock("../../urls/bulk-actions/picker-guard.js", () => ({
  isAnyBulkPickerOpen: mocks.isAnyBulkPickerOpen,
}));
vi.mock("../../members/transfer-picker.js", () => ({
  isTransferPickerOpen: mocks.isTransferPickerOpen,
}));
vi.mock("../../tags/sheet.js", () => ({
  isTagSheetOpen: mocks.isTagSheetOpen,
}));
vi.mock("../../urls/cards/update-title.js", () => ({
  isURLTitleSubmitInFlight: mocks.isURLTitleSubmitInFlight,
}));
vi.mock("../../urls/cards/update-string.js", () => ({
  isURLStringSubmitInFlight: mocks.isURLStringSubmitInFlight,
}));
vi.mock("../../urls/update-name.js", () => ({
  isUTubNameSubmitInFlight: mocks.isUTubNameSubmitInFlight,
}));
vi.mock("../../urls/update-description.js", () => ({
  isUTubDescriptionSubmitInFlight: mocks.isUTubDescriptionSubmitInFlight,
}));
vi.mock("../../urls/bulk-actions/bulk-tag.js", () => ({
  isBulkTagSubmitInFlight: mocks.isBulkTagSubmitInFlight,
}));
vi.mock("../../urls/bulk-actions/bulk-delete.js", () => ({
  isBulkDeleteSubmitInFlight: mocks.isBulkDeleteSubmitInFlight,
}));
vi.mock("../../urls/cards/delete.js", () => ({
  isURLDeleteInFlight: mocks.isURLDeleteInFlight,
}));
vi.mock("../../urls/cards/delete-undo.js", () => ({
  isURLDeleteUndoInFlight: mocks.isURLDeleteUndoInFlight,
  isURLDeleteToastShowing: mocks.isURLDeleteToastShowing,
}));
vi.mock("../../urls/bulk-actions/bulk-copy.js", () => ({
  isBulkCopySubmitInFlight: mocks.isBulkCopySubmitInFlight,
}));
vi.mock("../../search/cross-utub-search.js", () => ({
  isCrossUtubSearchActive: mocks.isCrossUtubSearchActive,
}));

import { AppEvents, emit } from "../../../lib/event-bus.js";
import type { UtubSelectedPayload } from "../../../lib/event-bus.js";
import {
  UTUB_REFRESH_MIN_INTERVAL_MS,
  _resetUTubRefreshOnFocusForTests,
  initUTubRefreshOnFocus,
  isUserBusyOnHome,
} from "../refresh-on-focus.js";

const $ = window.jQuery;

// The frontend tsconfig carries no Node types; vitest still runs on Node.
const nodeProcess = (
  globalThis as unknown as {
    process: {
      on: (event: string, handler: () => void) => void;
      off: (event: string, handler: () => void) => void;
    };
  }
).process;

// jsdom has no layout, so every element reports a zero offset size. The busy
// gate treats a non-zero offsetWidth as rendered; drive that from a data
// attribute instead.
beforeAll(() => {
  Object.defineProperty(HTMLElement.prototype, "offsetWidth", {
    configurable: true,
    get(this: HTMLElement) {
      return this.hasAttribute("data-test-visible") ? 100 : 0;
    },
  });
});
afterAll(() => {
  Reflect.deleteProperty(HTMLElement.prototype, "offsetWidth");
});

const BASE_HTML = `
  <h2 id="URLDeckHeader"></h2>
  <div id="URLDeckSubheader"></div>
  <button id="utubEditPanelClose" class="hidden"></button>
  <div id="confirmModal"></div>
  <div id="MemberDeck"></div>
  <div id="urlDeckSlot"></div>
`;

function setDocumentVisibility(state: "visible" | "hidden"): void {
  Object.defineProperty(document, "visibilityState", {
    value: state,
    configurable: true,
  });
}

// A full return to the tab: hidden -> visible.
function returnToTab(): void {
  setDocumentVisibility("hidden");
  document.dispatchEvent(new Event("visibilitychange"));
  setDocumentVisibility("visible");
  document.dispatchEvent(new Event("visibilitychange"));
}

function focusWindow(): void {
  $(window).trigger("focus.utubRefresh");
}

type ShouldApplyArgs = {
  utubID: number;
  isBackgroundRefresh: boolean;
  shouldApply: () => boolean;
};

function lastCallArgs(): ShouldApplyArgs {
  const calls = mocks.updateUTubOnFindingStaleData.mock.calls;
  return calls[calls.length - 1]![0] as ShouldApplyArgs;
}

// vi.clearAllMocks keeps implementations, so reset every busy signal explicitly.
function clearBusySignals(): void {
  mocks.getOpenForm.mockReturnValue(null);
  mocks.isAnyBulkPickerOpen.mockReturnValue(false);
  mocks.isTransferPickerOpen.mockReturnValue(false);
  mocks.isTagSheetOpen.mockReturnValue(false);
  mocks.isURLTitleSubmitInFlight.mockReturnValue(false);
  mocks.isURLStringSubmitInFlight.mockReturnValue(false);
  mocks.isUTubNameSubmitInFlight.mockReturnValue(false);
  mocks.isUTubDescriptionSubmitInFlight.mockReturnValue(false);
  mocks.isBulkTagSubmitInFlight.mockReturnValue(false);
  mocks.isBulkDeleteSubmitInFlight.mockReturnValue(false);
  mocks.isURLDeleteInFlight.mockReturnValue(false);
  mocks.isURLDeleteUndoInFlight.mockReturnValue(false);
  mocks.isURLDeleteToastShowing.mockReturnValue(false);
  mocks.isBulkCopySubmitInFlight.mockReturnValue(false);
  mocks.isCrossUtubSearchActive.mockReturnValue(false);
  mocks.storeState.multiSelectMode = false;
}

function pendingRefresh(): { resolve: () => void; reject: (e: Error) => void } {
  let resolve!: () => void;
  let reject!: (e: Error) => void;
  const promise = new Promise<void>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  mocks.updateUTubOnFindingStaleData.mockReturnValueOnce(promise);
  return { resolve, reject };
}

describe("refresh-on-focus trigger", () => {
  beforeEach(() => {
    document.body.innerHTML = BASE_HTML;
    setDocumentVisibility("visible");
    vi.clearAllMocks();
    mocks.updateUTubOnFindingStaleData.mockResolvedValue(undefined);
    mocks.isUTubSelected.mockReturnValue(true);
    clearBusySignals();
    mocks.storeState.activeUTubID = 7;
    vi.useFakeTimers();
    initUTubRefreshOnFocus();
  });

  afterEach(() => {
    _resetUTubRefreshOnFocusForTests();
    vi.useRealTimers();
    document.body.innerHTML = "";
  });

  it("exports a 30s minimum interval", () => {
    expect(UTUB_REFRESH_MIN_INTERVAL_MS).toBe(30_000);
  });

  it("fires once after the interval, with the background-refresh arguments", async () => {
    await vi.advanceTimersByTimeAsync(31_000);
    returnToTab();

    expect(mocks.updateUTubOnFindingStaleData).toHaveBeenCalledTimes(1);
    expect(mocks.updateUTubOnFindingStaleData).toHaveBeenCalledWith({
      utubID: 7,
      isBackgroundRefresh: true,
      shouldApply: expect.any(Function),
    });
  });

  it("coalesces a visibilitychange and a window focus in the same return", async () => {
    await vi.advanceTimersByTimeAsync(31_000);
    returnToTab();
    focusWindow();

    expect(mocks.updateUTubOnFindingStaleData).toHaveBeenCalledTimes(1);
  });

  it("does nothing while the document is hidden", async () => {
    await vi.advanceTimersByTimeAsync(31_000);
    setDocumentVisibility("hidden");
    document.dispatchEvent(new Event("visibilitychange"));

    expect(mocks.updateUTubOnFindingStaleData).not.toHaveBeenCalled();
  });

  it("debounces a second return within 30s", async () => {
    await vi.advanceTimersByTimeAsync(31_000);
    returnToTab();
    await vi.advanceTimersByTimeAsync(0);
    await vi.advanceTimersByTimeAsync(10_000);
    returnToTab();

    expect(mocks.updateUTubOnFindingStaleData).toHaveBeenCalledTimes(1);
  });

  it("does not fire within 30s of init (clock seeded at init)", async () => {
    await vi.advanceTimersByTimeAsync(1_000);
    returnToTab();

    expect(mocks.updateUTubOnFindingStaleData).not.toHaveBeenCalled();
  });

  it("blocks a return 31s later while the first refresh is still pending (refreshInFlight, not the clock), then fires after it settles", async () => {
    await vi.advanceTimersByTimeAsync(31_000);
    const first = pendingRefresh();
    returnToTab();
    expect(mocks.updateUTubOnFindingStaleData).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(31_000);
    returnToTab();
    expect(mocks.updateUTubOnFindingStaleData).toHaveBeenCalledTimes(1);

    first.resolve();
    await vi.advanceTimersByTimeAsync(0);
    returnToTab();
    expect(mocks.updateUTubOnFindingStaleData).toHaveBeenCalledTimes(2);
  });

  it("also fires after a pending refresh settles by rejecting", async () => {
    await vi.advanceTimersByTimeAsync(31_000);
    const first = pendingRefresh();
    returnToTab();

    await vi.advanceTimersByTimeAsync(31_000);
    first.reject(new Error("boom"));
    await vi.advanceTimersByTimeAsync(0);
    returnToTab();

    expect(mocks.updateUTubOnFindingStaleData).toHaveBeenCalledTimes(2);
  });

  it("sets the clock at dispatch, not at completion (settle +20s, blocked +25s, fires +31s)", async () => {
    await vi.advanceTimersByTimeAsync(31_000);
    const first = pendingRefresh();
    returnToTab(); // dispatch at t0
    expect(mocks.updateUTubOnFindingStaleData).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(20_000);
    first.resolve(); // settles at t0 + 20s; refreshInFlight clears
    await vi.advanceTimersByTimeAsync(0);

    await vi.advanceTimersByTimeAsync(5_000); // t0 + 25s
    returnToTab();
    expect(mocks.updateUTubOnFindingStaleData).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(6_000); // t0 + 31s
    returnToTab();
    expect(mocks.updateUTubOnFindingStaleData).toHaveBeenCalledTimes(2);
  });

  it("swallows a rejection (logged, no unhandled rejection) and clears refreshInFlight", async () => {
    const unhandled = vi.fn();
    nodeProcess.on("unhandledRejection", unhandled);
    try {
      await vi.advanceTimersByTimeAsync(31_000);
      mocks.updateUTubOnFindingStaleData.mockRejectedValueOnce(
        new Error("boom"),
      );
      returnToTab();
      await vi.runAllTimersAsync();

      expect(unhandled).not.toHaveBeenCalled();
      expect(mocks.log).toHaveBeenCalledWith(
        expect.stringContaining("background refresh failed"),
        expect.objectContaining({ utubID: 7 }),
      );

      await vi.advanceTimersByTimeAsync(31_000);
      returnToTab();
      expect(mocks.updateUTubOnFindingStaleData).toHaveBeenCalledTimes(2);
    } finally {
      nodeProcess.off("unhandledRejection", unhandled);
    }
  });

  it("does nothing with no UTub selected and does not advance the clock", async () => {
    await vi.advanceTimersByTimeAsync(31_000);
    mocks.isUTubSelected.mockReturnValue(false);
    returnToTab();
    expect(mocks.updateUTubOnFindingStaleData).not.toHaveBeenCalled();

    mocks.isUTubSelected.mockReturnValue(true);
    returnToTab();
    expect(mocks.updateUTubOnFindingStaleData).toHaveBeenCalledTimes(1);
  });

  it("fails closed on a null activeUTubID without advancing the clock", async () => {
    await vi.advanceTimersByTimeAsync(31_000);
    mocks.storeState.activeUTubID = null;
    returnToTab();
    expect(mocks.updateUTubOnFindingStaleData).not.toHaveBeenCalled();

    mocks.storeState.activeUTubID = 7;
    returnToTab();
    expect(mocks.updateUTubOnFindingStaleData).toHaveBeenCalledTimes(1);
  });

  it("reseeds the clock on every UTUB_SELECTED emit", async () => {
    await vi.advanceTimersByTimeAsync(31_000);
    emit(AppEvents.UTUB_SELECTED, {} as UtubSelectedPayload);
    returnToTab();
    expect(mocks.updateUTubOnFindingStaleData).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(31_000);
    returnToTab();
    expect(mocks.updateUTubOnFindingStaleData).toHaveBeenCalledTimes(1);
  });

  it("skips while the user is busy and does not advance the clock", async () => {
    await vi.advanceTimersByTimeAsync(31_000);
    mocks.getOpenForm.mockReturnValue("utub_name_edit");
    returnToTab();
    expect(mocks.updateUTubOnFindingStaleData).not.toHaveBeenCalled();

    mocks.getOpenForm.mockReturnValue(null);
    returnToTab();
    expect(mocks.updateUTubOnFindingStaleData).toHaveBeenCalledTimes(1);
  });

  it("shouldApply while busy returns false and restores the pre-dispatch clock", async () => {
    await vi.advanceTimersByTimeAsync(31_000);
    returnToTab();
    await vi.advanceTimersByTimeAsync(0);
    const { shouldApply } = lastCallArgs();

    mocks.getOpenForm.mockReturnValue("utub_name_edit");
    expect(shouldApply()).toBe(false);
    mocks.getOpenForm.mockReturnValue(null);

    // Clock rolled back to the init seed, so an immediate return fires again.
    returnToTab();
    expect(mocks.updateUTubOnFindingStaleData).toHaveBeenCalledTimes(2);
  });

  it("shouldApply while not busy returns true and keeps the dispatch time", async () => {
    await vi.advanceTimersByTimeAsync(31_000);
    returnToTab();
    await vi.advanceTimersByTimeAsync(0);
    const { shouldApply } = lastCallArgs();

    expect(shouldApply()).toBe(true);

    returnToTab();
    expect(mocks.updateUTubOnFindingStaleData).toHaveBeenCalledTimes(1);
  });

  it("skips during a cross-UTub search and does not advance the clock", async () => {
    await vi.advanceTimersByTimeAsync(31_000);
    mocks.isCrossUtubSearchActive.mockReturnValue(true);
    returnToTab();
    expect(mocks.updateUTubOnFindingStaleData).not.toHaveBeenCalled();

    mocks.isCrossUtubSearchActive.mockReturnValue(false);
    returnToTab();
    expect(mocks.updateUTubOnFindingStaleData).toHaveBeenCalledTimes(1);
  });

  it("the disposer removes every listener", async () => {
    const dispose = initUTubRefreshOnFocus();
    await vi.advanceTimersByTimeAsync(31_000);
    dispose();

    returnToTab();
    focusWindow();
    emit(AppEvents.UTUB_SELECTED, {} as UtubSelectedPayload);

    expect(mocks.updateUTubOnFindingStaleData).not.toHaveBeenCalled();
  });

  it("re-init replaces the previous binding instead of stacking listeners", async () => {
    initUTubRefreshOnFocus();
    await vi.advanceTimersByTimeAsync(31_000);
    returnToTab();

    expect(mocks.updateUTubOnFindingStaleData).toHaveBeenCalledTimes(1);
  });
});

describe("isUserBusyOnHome", () => {
  beforeEach(() => {
    document.body.innerHTML = BASE_HTML;
    vi.clearAllMocks();
    clearBusySignals();
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("is false when no signal is set", () => {
    expect(isUserBusyOnHome()).toBe(false);
  });

  const mockSignals: Array<[string, () => void]> = [
    ["an open form", () => mocks.getOpenForm.mockReturnValue("utub_name_edit")],
    ["a bulk picker", () => mocks.isAnyBulkPickerOpen.mockReturnValue(true)],
    [
      "the transfer picker",
      () => mocks.isTransferPickerOpen.mockReturnValue(true),
    ],
    ["multi-select mode", () => (mocks.storeState.multiSelectMode = true)],
    ["the tag sheet", () => mocks.isTagSheetOpen.mockReturnValue(true)],
    [
      "a URL title submit",
      () => mocks.isURLTitleSubmitInFlight.mockReturnValue(true),
    ],
    [
      "a URL string submit",
      () => mocks.isURLStringSubmitInFlight.mockReturnValue(true),
    ],
    [
      "a UTub name submit",
      () => mocks.isUTubNameSubmitInFlight.mockReturnValue(true),
    ],
    [
      "a UTub description submit",
      () => mocks.isUTubDescriptionSubmitInFlight.mockReturnValue(true),
    ],
    [
      "a bulk tag submit",
      () => mocks.isBulkTagSubmitInFlight.mockReturnValue(true),
    ],
    [
      "a bulk delete submit",
      () => mocks.isBulkDeleteSubmitInFlight.mockReturnValue(true),
    ],
    [
      "a URL delete request",
      () => mocks.isURLDeleteInFlight.mockReturnValue(true),
    ],
    [
      "a URL delete-undo request",
      () => mocks.isURLDeleteUndoInFlight.mockReturnValue(true),
    ],
    [
      "a URL delete-undo toast showing",
      () => mocks.isURLDeleteToastShowing.mockReturnValue(true),
    ],
    [
      "a bulk copy submit",
      () => mocks.isBulkCopySubmitInFlight.mockReturnValue(true),
    ],
    [
      "a cross-UTub search",
      () => mocks.isCrossUtubSearchActive.mockReturnValue(true),
    ],
  ];

  const domSignals: Array<[string, () => void]> = [
    ["the confirm modal", () => $("#confirmModal").addClass("show")],
    ["the member add form", () => $("#MemberDeck").addClass("member-add-open")],
    [
      "a URL title edit",
      () => $("#urlDeckSlot").append('<div class="updateUrlTitleWrap"></div>'),
    ],
    [
      "a URL string edit",
      () => $("#urlDeckSlot").append('<div class="updateUrlStringWrap"></div>'),
    ],
    [
      "a visible URL tag combobox",
      () =>
        $("#urlDeckSlot").append(
          '<div class="urlTagComboboxWrap" data-test-visible></div>',
        ),
    ],
    [
      "a visible create-URL form",
      () =>
        $("#urlDeckSlot").append(
          '<div id="createURLWrap" data-test-visible></div>',
        ),
    ],
    [
      "a visible create-tag form",
      () =>
        $("#urlDeckSlot").append(
          '<div id="createUTubTagWrap" data-test-visible></div>',
        ),
    ],
    ["a hidden deck header", () => $("#URLDeckHeader").addClass("hidden")],
    [
      "a hidden deck subheader",
      () => $("#URLDeckSubheader").addClass("hidden"),
    ],
    [
      "the open edit panel",
      () => $("#utubEditPanelClose").removeClass("hidden"),
    ],
  ];

  it.each([...mockSignals, ...domSignals])("is true for %s", (_name, set) => {
    set();
    expect(isUserBusyOnHome()).toBe(true);
  });

  it("ignores hidden create/combobox wrappers and a hidden-class title wrap", () => {
    $("#urlDeckSlot").append(
      '<div class="urlTagComboboxWrap"></div><div id="createURLWrap"></div><div id="createUTubTagWrap"></div><div class="updateUrlTitleWrap hidden"></div><div class="updateUrlStringWrap hidden"></div>',
    );
    expect(isUserBusyOnHome()).toBe(false);
  });
});
