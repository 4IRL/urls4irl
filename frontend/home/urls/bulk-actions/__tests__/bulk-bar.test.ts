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
  selectAllVisibleURLCards,
} from "../bulk-selection.js";
import { exitMultiSelectMode } from "../bulk-mode.js";
import { isBulkTagPickerOpen, setBulkTagPickerOpen } from "../bulk-tag.js";
import { setBulkCopyPickerOpen } from "../bulk-copy.js";

vi.mock("../bulk-selection.js", () => ({
  selectAllVisibleURLCards: vi.fn(),
  clearURLSelection: vi.fn(),
}));

vi.mock("../bulk-mode.js", () => ({
  exitMultiSelectMode: vi.fn(),
}));

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
