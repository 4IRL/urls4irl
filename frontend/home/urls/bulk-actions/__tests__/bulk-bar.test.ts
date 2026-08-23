import { initBulkBar } from "../bulk-bar.js";
import { APP_CONFIG } from "../../../../lib/config.js";
import { AppEvents, emit } from "../../../../lib/event-bus.js";
import { resetStore, setState } from "../../../../store/app-store.js";
import {
  registerBulkAction,
  resetBulkActionRegistryForTest,
} from "../bulk-action-registry.js";
import {
  clearURLSelection,
  invertVisibleSelection,
  selectAllVisibleURLCards,
} from "../bulk-selection.js";
import { exitMultiSelectMode } from "../bulk-mode.js";
import { onPickerOpenChange } from "../picker-guard.js";
import { isBulkTagPickerOpen, setBulkTagPickerOpen } from "../bulk-tag.js";
import { setBulkCopyPickerOpen } from "../bulk-copy.js";

vi.mock("../bulk-selection.js", () => ({
  selectAllVisibleURLCards: vi.fn(),
  clearURLSelection: vi.fn(),
  invertVisibleSelection: vi.fn(),
}));

vi.mock("../bulk-mode.js", () => ({
  exitMultiSelectMode: vi.fn(),
}));

// PARTIAL mock (Pass2-DD-2): keep isAnyBulkPickerOpen / setPickerOpen /
// registerPickerClose / closeAllPickers REAL so the existing picker-guard-driven
// assertions in this file (and bulk-bar.ts's own guards) keep working, and wrap
// ONLY onPickerOpenChange with a vi.fn() to capture the callback bulk-bar.ts
// registers. A wholesale mock would undefine the rest for every importer.
vi.mock("../picker-guard.js", async () => {
  const actual =
    await vi.importActual<typeof import("../picker-guard.js")>(
      "../picker-guard.js",
    );
  return { ...actual, onPickerOpenChange: vi.fn() };
});

const $ = window.jQuery;

// The bar partial's spans/buttons plus a small URL list. Rows 1-3 are visible;
// individual tests mark a row searchable="false" to exercise the hidden-count.
// Includes an empty #URLContentSearch because bulk-bar.ts transitively imports
// search.ts, whose module-level URL_TAG_FILTER_APPLIED subscriber
// (reapplyURLSearchFilter) reads that input; with an empty value it returns
// early (term too short), so it stays inert during these bar tests.
const HTML = `
  <div id="URLDeck" tabindex="-1">
    <input id="URLContentSearch" value="" />
    <button id="urlBtnMultiSelect" aria-pressed="false"></button>
    <div id="bulkActionBar" class="hidden">
      <span id="bulkSelectCount">0</span>
      <span class="bulkLabel">selected</span>
      <span id="bulkSelectHiddenHint" class="hidden" aria-hidden="true"></span>
      <div id="bulkActionButtons"></div>
      <button id="bulkSelectAll" type="button">Select All</button>
      <button id="bulkSelectClear" type="button">Clear</button>
      <button id="bulkSelectExit" type="button">Exit</button>
      <span id="URLBulkSelectionAnnouncement" aria-live="polite"></span>
    </div>
    <div id="bulkSelectRangeStrip" class="bulkSelectRangeStrip" role="group"
         aria-label="Selection controls">
      <button id="bulkRangeSelectAll" type="button" class="barBtn">Select all</button>
      <button id="bulkRangeInvert" type="button" class="barBtn">Invert</button>
      <button id="bulkRangeClear" type="button" class="barBtn clear" aria-disabled="true">Clear</button>
    </div>
    <div id="listURLs">
      <div class="urlRow" utuburlid="1" filterable="true"></div>
      <div class="urlRow" utuburlid="2" filterable="true"></div>
      <div class="urlRow" utuburlid="3" filterable="true"></div>
    </div>
  </div>
`;

describe("bulk-bar", () => {
  beforeEach(() => {
    resetStore();
    resetBulkActionRegistryForTest();
    document.body.innerHTML = HTML;
    vi.mocked(selectAllVisibleURLCards).mockClear();
    vi.mocked(clearURLSelection).mockClear();
    vi.mocked(invertVisibleSelection).mockClear();
    vi.mocked(exitMultiSelectMode).mockClear();
    // Reset the (module-scoped) picker flags so a prior test's open picker never
    // leaks into this one's action-button rebuild guard. Both mirror into the
    // shared picker-guard registry that the bar now reads via isAnyBulkPickerOpen.
    setBulkTagPickerOpen(false);
    setBulkCopyPickerOpen(false);
    initBulkBar();
  });

  describe("selection-changed repaint", () => {
    it("sets the count, the SR announcement, and enables Clear for a non-empty selection", () => {
      emit(AppEvents.URL_MULTISELECT_CHANGED, {
        selectedURLCardIDs: [1, 2, 3],
      });

      expect($("#bulkSelectCount").text()).toBe("3");
      expect($("#URLBulkSelectionAnnouncement").text()).toBe(
        APP_CONFIG.strings.URL_BULK_SELECTED_COUNT.replace("{n}", "3"),
      );
      expect($("#bulkSelectClear").attr("aria-disabled")).toBe("false");
      expect($("#bulkSelectHiddenHint").hasClass("hidden")).toBe(true);
    });

    it("uses the singular announcement for exactly one selection", () => {
      emit(AppEvents.URL_MULTISELECT_CHANGED, { selectedURLCardIDs: [1] });

      expect($("#bulkSelectCount").text()).toBe("1");
      expect($("#URLBulkSelectionAnnouncement").text()).toBe(
        APP_CONFIG.strings.URL_BULK_SELECTED_COUNT_ONE,
      );
    });

    it("shows zero, disables Clear, and announces the empty string for []", () => {
      emit(AppEvents.URL_MULTISELECT_CHANGED, { selectedURLCardIDs: [] });

      expect($("#bulkSelectCount").text()).toBe("0");
      expect($("#bulkSelectClear").attr("aria-disabled")).toBe("true");
      expect($("#URLBulkSelectionAnnouncement").text()).toBe(
        APP_CONFIG.strings.URL_BULK_NONE_SELECTED,
      );
      expect($("#bulkSelectHiddenHint").hasClass("hidden")).toBe(true);
    });

    it("shows the hidden hint AND appends the hidden clause to the one shared announcement when a selected row is filtered out", () => {
      // Row 3 hidden by search/filter → selected [1,2,3] has 1 hidden.
      $(".urlRow[utuburlid=3]").attr("searchable", "false");

      emit(AppEvents.URL_MULTISELECT_CHANGED, {
        selectedURLCardIDs: [1, 2, 3],
      });

      const hiddenClause = APP_CONFIG.strings.URL_BULK_N_HIDDEN.replace(
        "{n}",
        "1",
      );
      expect($("#bulkSelectHiddenHint").hasClass("hidden")).toBe(false);
      expect($("#bulkSelectHiddenHint").text()).toBe(hiddenClause);
      expect($("#URLBulkSelectionAnnouncement").text()).toBe(
        `${APP_CONFIG.strings.URL_BULK_SELECTED_COUNT.replace(
          "{n}",
          "3",
        )}, ${hiddenClause}`,
      );
    });

    it("clears the hidden hint (no second live region) when nothing is hidden", () => {
      emit(AppEvents.URL_MULTISELECT_CHANGED, { selectedURLCardIDs: [1, 2] });

      expect($("#bulkSelectHiddenHint").hasClass("hidden")).toBe(true);
      expect($("#bulkSelectHiddenHint").text()).toBe("");
      expect($("#URLBulkSelectionAnnouncement").text()).toBe(
        APP_CONFIG.strings.URL_BULK_SELECTED_COUNT.replace("{n}", "2"),
      );
    });
  });

  describe("visible-set change repaint (filter / search)", () => {
    it("recomputes the hidden hint on URL_TAG_FILTER_APPLIED without a selection change", () => {
      // Seed a 3-row selection with nothing hidden yet.
      setState({ selectedURLCardIDs: [1, 2, 3] });
      emit(AppEvents.URL_MULTISELECT_CHANGED, {
        selectedURLCardIDs: [1, 2, 3],
      });
      expect($("#bulkSelectHiddenHint").hasClass("hidden")).toBe(true);

      // A tag filter now hides row 3; the selection is unchanged (hidden rows
      // stay selected), so only URL_TAG_FILTER_APPLIED fires.
      $(".urlRow[utuburlid=3]").attr("filterable", "false");
      emit(AppEvents.URL_TAG_FILTER_APPLIED);

      const hiddenClause = APP_CONFIG.strings.URL_BULK_N_HIDDEN.replace(
        "{n}",
        "1",
      );
      expect($("#bulkSelectCount").text()).toBe("3");
      expect($("#bulkSelectHiddenHint").hasClass("hidden")).toBe(false);
      expect($("#bulkSelectHiddenHint").text()).toBe(hiddenClause);
      expect($("#URLBulkSelectionAnnouncement").text()).toBe(
        `${APP_CONFIG.strings.URL_BULK_SELECTED_COUNT.replace(
          "{n}",
          "3",
        )}, ${hiddenClause}`,
      );
    });

    it("clears the hidden hint on URL_SEARCH_VISIBILITY_CHANGED when the row becomes visible again", () => {
      setState({ selectedURLCardIDs: [1, 2, 3] });
      $(".urlRow[utuburlid=3]").attr("searchable", "false");
      emit(AppEvents.URL_MULTISELECT_CHANGED, {
        selectedURLCardIDs: [1, 2, 3],
      });
      expect($("#bulkSelectHiddenHint").hasClass("hidden")).toBe(false);

      // Clearing the search reveals row 3; no selection change fires, only the
      // search-visibility event.
      $(".urlRow[utuburlid=3]").attr("searchable", "true");
      emit(AppEvents.URL_SEARCH_VISIBILITY_CHANGED);

      expect($("#bulkSelectHiddenHint").hasClass("hidden")).toBe(true);
      expect($("#URLBulkSelectionAnnouncement").text()).toBe(
        APP_CONFIG.strings.URL_BULK_SELECTED_COUNT.replace("{n}", "3"),
      );
    });
  });

  describe("bar buttons", () => {
    it("calls selectAllVisibleURLCards() when Select All is clicked", () => {
      $("#bulkSelectAll").trigger("click");
      expect(vi.mocked(selectAllVisibleURLCards)).toHaveBeenCalledTimes(1);
    });

    it("calls clearURLSelection() when Clear is clicked with a live selection", () => {
      // Enable Clear first (empty selection leaves it aria-disabled and inert).
      emit(AppEvents.URL_MULTISELECT_CHANGED, { selectedURLCardIDs: [1] });

      $("#bulkSelectClear").trigger("click");

      expect(vi.mocked(clearURLSelection)).toHaveBeenCalledTimes(1);
    });

    it("no-ops Clear while it is aria-disabled (empty selection)", () => {
      emit(AppEvents.URL_MULTISELECT_CHANGED, { selectedURLCardIDs: [] });

      $("#bulkSelectClear").trigger("click");

      expect(vi.mocked(clearURLSelection)).not.toHaveBeenCalled();
    });

    it("calls exitMultiSelectMode() when Exit is clicked", () => {
      $("#bulkSelectExit").trigger("click");
      expect(vi.mocked(exitMultiSelectMode)).toHaveBeenCalledTimes(1);
    });

    it("no-ops Select All and Clear while the bulk tag picker is open (DD-8)", () => {
      // Enable Clear (non-empty selection) so a no-op proves the picker guard —
      // not the aria-disabled guard — is what blocks the click.
      emit(AppEvents.URL_MULTISELECT_CHANGED, { selectedURLCardIDs: [1] });
      setBulkTagPickerOpen(true);

      $("#bulkSelectAll").trigger("click");
      $("#bulkSelectClear").trigger("click");

      expect(vi.mocked(selectAllVisibleURLCards)).not.toHaveBeenCalled();
      expect(vi.mocked(clearURLSelection)).not.toHaveBeenCalled();

      setBulkTagPickerOpen(false);
    });

    it("no-ops Select All and Clear while the bulk COPY picker is open (isAnyBulkPickerOpen covers both)", () => {
      emit(AppEvents.URL_MULTISELECT_CHANGED, { selectedURLCardIDs: [1] });
      setBulkCopyPickerOpen(true);

      $("#bulkSelectAll").trigger("click");
      $("#bulkSelectClear").trigger("click");

      expect(vi.mocked(selectAllVisibleURLCards)).not.toHaveBeenCalled();
      expect(vi.mocked(clearURLSelection)).not.toHaveBeenCalled();

      setBulkCopyPickerOpen(false);
    });
  });

  describe("desktop range strip", () => {
    describe("button clicks", () => {
      it("calls selectAllVisibleURLCards() when the strip Select all is clicked", () => {
        $("#bulkRangeSelectAll").trigger("click");
        expect(vi.mocked(selectAllVisibleURLCards)).toHaveBeenCalledTimes(1);
      });

      it("calls invertVisibleSelection() when the strip Invert is clicked with a live selection", () => {
        // Invert is aria-disabled at 0 selected (DD-6); enable it first.
        setState({ selectedURLCardIDs: [1] });
        emit(AppEvents.URL_MULTISELECT_CHANGED, { selectedURLCardIDs: [1] });

        $("#bulkRangeInvert").trigger("click");

        expect(vi.mocked(invertVisibleSelection)).toHaveBeenCalledTimes(1);
      });

      it("calls clearURLSelection() when the strip Clear is clicked with a live selection", () => {
        setState({ selectedURLCardIDs: [1] });
        emit(AppEvents.URL_MULTISELECT_CHANGED, { selectedURLCardIDs: [1] });

        $("#bulkRangeClear").trigger("click");

        expect(vi.mocked(clearURLSelection)).toHaveBeenCalledTimes(1);
      });

      it("no-ops the strip Clear while it is aria-disabled (empty selection)", () => {
        setState({ selectedURLCardIDs: [] });
        emit(AppEvents.URL_MULTISELECT_CHANGED, { selectedURLCardIDs: [] });

        $("#bulkRangeClear").trigger("click");

        expect(vi.mocked(clearURLSelection)).not.toHaveBeenCalled();
      });

      it("no-ops the strip Invert while it is aria-disabled (0 selected)", () => {
        setState({ selectedURLCardIDs: [] });
        emit(AppEvents.URL_MULTISELECT_CHANGED, { selectedURLCardIDs: [] });

        $("#bulkRangeInvert").trigger("click");

        expect(vi.mocked(invertVisibleSelection)).not.toHaveBeenCalled();
      });

      it("no-ops all three strip controls while the bulk tag picker is open (isAnyBulkPickerOpen guard)", () => {
        // Live selection so a no-op proves the picker guard — not the
        // aria-disabled guard — is what blocks the clicks.
        setState({ selectedURLCardIDs: [1] });
        emit(AppEvents.URL_MULTISELECT_CHANGED, { selectedURLCardIDs: [1] });
        setBulkTagPickerOpen(true);

        $("#bulkRangeSelectAll").trigger("click");
        $("#bulkRangeInvert").trigger("click");
        $("#bulkRangeClear").trigger("click");

        expect(vi.mocked(selectAllVisibleURLCards)).not.toHaveBeenCalled();
        expect(vi.mocked(invertVisibleSelection)).not.toHaveBeenCalled();
        expect(vi.mocked(clearURLSelection)).not.toHaveBeenCalled();

        setBulkTagPickerOpen(false);
      });

      it("no-ops all three strip controls while the bulk COPY picker is open (guard covers both pickers)", () => {
        setState({ selectedURLCardIDs: [1] });
        emit(AppEvents.URL_MULTISELECT_CHANGED, { selectedURLCardIDs: [1] });
        setBulkCopyPickerOpen(true);

        $("#bulkRangeSelectAll").trigger("click");
        $("#bulkRangeInvert").trigger("click");
        $("#bulkRangeClear").trigger("click");

        expect(vi.mocked(selectAllVisibleURLCards)).not.toHaveBeenCalled();
        expect(vi.mocked(invertVisibleSelection)).not.toHaveBeenCalled();
        expect(vi.mocked(clearURLSelection)).not.toHaveBeenCalled();

        setBulkCopyPickerOpen(false);
      });
    });

    describe("aria-disabled sync (syncRangeButtonStates)", () => {
      it("disables Clear AND Invert at 0 selected while rows are visible, keeping Select all enabled (DD-6)", () => {
        // 3 visible rows in the fixture, nothing selected.
        setState({ selectedURLCardIDs: [] });
        emit(AppEvents.URL_MULTISELECT_CHANGED, { selectedURLCardIDs: [] });

        expect($("#bulkRangeClear").attr("aria-disabled")).toBe("true");
        // DD-6: Invert disables at 0 selected even though rows are visible —
        // inverting from empty == Select All, so it is a redundant control.
        expect($("#bulkRangeInvert").attr("aria-disabled")).toBe("true");
        expect($("#bulkRangeSelectAll").attr("aria-disabled")).toBe("false");
      });

      it("enables Clear and Invert once at least one row is selected", () => {
        setState({ selectedURLCardIDs: [1] });
        emit(AppEvents.URL_MULTISELECT_CHANGED, { selectedURLCardIDs: [1] });

        expect($("#bulkRangeClear").attr("aria-disabled")).toBe("false");
        expect($("#bulkRangeInvert").attr("aria-disabled")).toBe("false");
        expect($("#bulkRangeSelectAll").attr("aria-disabled")).toBe("false");
      });

      it("disables Select all AND Invert when a search leaves 0 visible rows (visibleCount === 0 arm)", () => {
        // Seed a live selection, then search-hide every row so nothing matches
        // VISIBLE_URL_SELECTOR (.urlRow[filterable=true]:not([searchable=false])).
        setState({ selectedURLCardIDs: [1] });
        $(".urlRow").attr("searchable", "false");
        emit(AppEvents.URL_SEARCH_VISIBILITY_CHANGED);

        expect($("#bulkRangeSelectAll").attr("aria-disabled")).toBe("true");
        expect($("#bulkRangeInvert").attr("aria-disabled")).toBe("true");
      });

      it("disables Select all AND Invert on URL_TAG_FILTER_APPLIED that yields 0 visible rows", () => {
        setState({ selectedURLCardIDs: [1] });
        $(".urlRow").attr("filterable", "false");
        emit(AppEvents.URL_TAG_FILTER_APPLIED);

        expect($("#bulkRangeSelectAll").attr("aria-disabled")).toBe("true");
        expect($("#bulkRangeInvert").attr("aria-disabled")).toBe("true");
      });
    });

    describe("picker-open inert sync (onPickerOpenChange subscriber)", () => {
      // bulk-bar.ts registers exactly one onPickerOpenChange callback (the
      // subscription block is behind a module-level once-guard), so calls[0][0]
      // is the callback for the whole file. It is intentionally NOT cleared
      // between tests — this block relies on vitest.config.ts leaving clearMocks
      // false; the length assertion below fails loudly (with intent) if that
      // ever changes rather than silently reading an undefined callback.
      function pickerOpenCallback(): (open: boolean) => void {
        const calls = vi.mocked(onPickerOpenChange).mock.calls;
        expect(calls.length).toBeGreaterThan(0);
        return calls[0][0];
      }

      it("forces the container and all three buttons aria-disabled when a picker opens", () => {
        pickerOpenCallback()(true);

        expect($("#bulkSelectRangeStrip").attr("aria-disabled")).toBe("true");
        expect($("#bulkRangeSelectAll").attr("aria-disabled")).toBe("true");
        expect($("#bulkRangeInvert").attr("aria-disabled")).toBe("true");
        expect($("#bulkRangeClear").attr("aria-disabled")).toBe("true");
      });

      it("on picker close re-derives each button from current selection/visibility (not a blind clear)", () => {
        // 0 selected, 3 visible rows: after close, Clear + Invert must STAY
        // disabled (re-derived), while Select all + the container re-enable —
        // proving the close path re-syncs rather than blindly clearing.
        setState({ selectedURLCardIDs: [] });
        const callback = pickerOpenCallback();

        callback(true);
        callback(false);

        expect($("#bulkSelectRangeStrip").attr("aria-disabled")).toBe("false");
        expect($("#bulkRangeSelectAll").attr("aria-disabled")).toBe("false");
        expect($("#bulkRangeInvert").attr("aria-disabled")).toBe("true");
        expect($("#bulkRangeClear").attr("aria-disabled")).toBe("true");
      });

      it("on picker close re-enables all three when a live selection is present", () => {
        setState({ selectedURLCardIDs: [1] });
        const callback = pickerOpenCallback();

        callback(true);
        callback(false);

        expect($("#bulkSelectRangeStrip").attr("aria-disabled")).toBe("false");
        expect($("#bulkRangeSelectAll").attr("aria-disabled")).toBe("false");
        expect($("#bulkRangeInvert").attr("aria-disabled")).toBe("false");
        expect($("#bulkRangeClear").attr("aria-disabled")).toBe("false");
      });

      it("on picker close keeps Select all + Invert disabled when the close-path re-derive finds 0 visible rows", () => {
        // A live selection but every row hidden: after close, the container
        // re-enables while Select all + Invert STAY disabled via the
        // visibleCount === 0 arm of syncRangeButtonStates (close-path re-derive).
        setState({ selectedURLCardIDs: [1] });
        $(".urlRow").attr("filterable", "false");
        const callback = pickerOpenCallback();

        callback(true);
        callback(false);

        expect($("#bulkSelectRangeStrip").attr("aria-disabled")).toBe("false");
        expect($("#bulkRangeSelectAll").attr("aria-disabled")).toBe("true");
        expect($("#bulkRangeInvert").attr("aria-disabled")).toBe("true");
        // Clear gates on selection only, so a live selection keeps it enabled.
        expect($("#bulkRangeClear").attr("aria-disabled")).toBe("false");
      });
    });
  });

  describe("mode-changed show/hide + focus", () => {
    it("shows the bar and moves focus to the header Exit control on mode enter", () => {
      emit(AppEvents.URL_MULTISELECT_MODE_CHANGED, { active: true });

      expect($("#bulkActionBar").hasClass("hidden")).toBe(false);
      // Exit (now the header's primary in-mode control) is the initial focus
      // target, not Clear.
      expect(document.activeElement).toBe($("#bulkSelectExit")[0]);
    });

    it("hides the bar and returns focus to the toggle on mode exit", () => {
      emit(AppEvents.URL_MULTISELECT_MODE_CHANGED, { active: true });
      emit(AppEvents.URL_MULTISELECT_MODE_CHANGED, { active: false });

      expect($("#bulkActionBar").hasClass("hidden")).toBe(true);
      expect(document.activeElement).toBe($("#urlBtnMultiSelect")[0]);
    });

    it("falls back to #URLDeck when the toggle is hidden at exit (DD-23)", () => {
      emit(AppEvents.URL_MULTISELECT_MODE_CHANGED, { active: true });
      $("#urlBtnMultiSelect").addClass("hidden");

      emit(AppEvents.URL_MULTISELECT_MODE_CHANGED, { active: false });

      expect(document.activeElement).toBe($("#URLDeck")[0]);
    });
  });

  describe("mobile drawer height reservation (--bulk-bar-height)", () => {
    // jsdom always reports offsetHeight 0, so stub the rendered height of the
    // #bulkActionBar drawer to a realistic multi-row value and assert the deck's
    // reserved bottom-padding var tracks it.
    function stubBarHeight(px: number): void {
      const bar = document.querySelector("#bulkActionBar");
      if (bar === null) throw new Error("missing #bulkActionBar fixture");
      Object.defineProperty(bar, "offsetHeight", {
        configurable: true,
        get: () => px,
      });
    }

    function reservedHeight(): string {
      return (
        document
          .querySelector<HTMLElement>("#URLDeck")
          ?.style.getPropertyValue("--bulk-bar-height") ?? ""
      );
    }

    it("reserves the measured bar height on the deck when mode is entered", () => {
      stubBarHeight(200);

      emit(AppEvents.URL_MULTISELECT_MODE_CHANGED, { active: true });

      expect(reservedHeight()).toBe("200px");
    });

    it("keeps the reservation in sync on a selection change while the bar is visible", () => {
      stubBarHeight(200);
      emit(AppEvents.URL_MULTISELECT_MODE_CHANGED, { active: true });
      expect(reservedHeight()).toBe("200px");

      // A selection change can add/remove drawer rows; the repaint re-measures.
      emit(AppEvents.URL_MULTISELECT_CHANGED, { selectedURLCardIDs: [1, 2] });

      expect(reservedHeight()).toBe("200px");
    });

    it("does NOT reserve a height while the bar is hidden (mode inactive)", () => {
      stubBarHeight(200);

      // No mode-enter: the bar keeps its initial `hidden` class, so a bare
      // selection repaint must leave the reservation unset.
      emit(AppEvents.URL_MULTISELECT_CHANGED, { selectedURLCardIDs: [1] });

      expect(reservedHeight()).toBe("");
    });

    it("clears the reservation when mode is exited", () => {
      stubBarHeight(200);
      emit(AppEvents.URL_MULTISELECT_MODE_CHANGED, { active: true });
      expect(reservedHeight()).toBe("200px");

      emit(AppEvents.URL_MULTISELECT_MODE_CHANGED, { active: false });

      expect(reservedHeight()).toBe("");
    });
  });

  describe("action registry rendering", () => {
    it("renders no action buttons when nothing is registered", () => {
      emit(AppEvents.URL_MULTISELECT_CHANGED, { selectedURLCardIDs: [1] });
      expect($("#bulkActionButtons").children().length).toBe(0);
    });

    it("renders one button per available registered action", () => {
      registerBulkAction({
        id: "fake",
        label: "Fake Action",
        isAvailable: () => true,
        onActivate: vi.fn(),
      });

      emit(AppEvents.URL_MULTISELECT_CHANGED, { selectedURLCardIDs: [1] });

      const buttons = $("#bulkActionButtons button");
      expect(buttons.length).toBe(1);
      expect(buttons.text()).toBe("Fake Action");
    });

    it("tags the rendered button with the action id, renders its iconHtml, and fires onActivate on click", () => {
      const onActivate = vi.fn();
      registerBulkAction({
        id: "fake",
        label: "Fake Action",
        iconHtml: '<i class="fakeIcon"></i>',
        isAvailable: () => true,
        onActivate,
      });
      // onActivate's context comes from buildContext() (reads the store), which
      // mirrors production where setState precedes the emit — seed it so the
      // rendered button's click carries the real selection.
      setState({ selectedURLCardIDs: [1] });

      emit(AppEvents.URL_MULTISELECT_CHANGED, { selectedURLCardIDs: [1] });

      const button = $("#bulkActionButtons button");
      expect(button.attr("data-bulk-action-id")).toBe("fake");
      expect(button.find("i.fakeIcon").length).toBe(1);

      button.trigger("click");
      expect(onActivate).toHaveBeenCalledTimes(1);
      expect(onActivate).toHaveBeenCalledWith(
        expect.objectContaining({ selectedURLCardIDs: [1] }),
      );
    });

    it("does NOT rebuild the action buttons while the bulk tag picker is open", () => {
      registerBulkAction({
        id: "fake",
        label: "Fake Action",
        isAvailable: () => true,
        onActivate: vi.fn(),
      });
      setState({ selectedURLCardIDs: [1] });

      // First paint (picker closed) renders the action button.
      emit(AppEvents.URL_MULTISELECT_CHANGED, { selectedURLCardIDs: [1] });
      expect($("#bulkActionButtons button").length).toBe(1);

      // Drop a sentinel; a rebuild empties() the container, removing it.
      $("#bulkActionButtons").append('<span id="rebuildSentinel"></span>');

      setBulkTagPickerOpen(true);
      expect(isBulkTagPickerOpen()).toBe(true);
      emit(AppEvents.URL_MULTISELECT_CHANGED, { selectedURLCardIDs: [1, 2] });

      // No rebuild: the sentinel survives (renderBulkActionButtons was skipped),
      // while the count still repaints (it runs before the picker guard).
      expect($("#rebuildSentinel").length).toBe(1);
      expect($("#bulkSelectCount").text()).toBe("2");

      setBulkTagPickerOpen(false);
    });

    it("does NOT rebuild the action buttons while the bulk COPY picker is open", () => {
      registerBulkAction({
        id: "fake",
        label: "Fake Action",
        isAvailable: () => true,
        onActivate: vi.fn(),
      });
      setState({ selectedURLCardIDs: [1] });

      emit(AppEvents.URL_MULTISELECT_CHANGED, { selectedURLCardIDs: [1] });
      expect($("#bulkActionButtons button").length).toBe(1);

      $("#bulkActionButtons").append('<span id="rebuildSentinel"></span>');

      setBulkCopyPickerOpen(true);
      emit(AppEvents.URL_MULTISELECT_CHANGED, { selectedURLCardIDs: [1, 2] });

      expect($("#rebuildSentinel").length).toBe(1);
      expect($("#bulkSelectCount").text()).toBe("2");

      setBulkCopyPickerOpen(false);
    });
  });
});
