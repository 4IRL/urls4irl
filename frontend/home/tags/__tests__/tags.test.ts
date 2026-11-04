import {
  applyClaimingModeChange,
  buildTagFilterInDeck,
  initTagMatchMode,
  syncTagCapState,
  toggleTagFilterSelected,
} from "../tags.js";
import { readTagCount } from "../utils.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { getState, resetStore, setState } from "../../../store/app-store.js";
import {
  disableUnselectAllButtonAfterTagFilterRemoved,
  enableUnselectAllButtonAfterTagFilterApplied,
} from "../unselect-all.js";
import { updateURLsAndTagSubheaderWhenTagSelected } from "../../urls/cards/filtering.js";
import { announceSettingsStatus } from "../../panel-settings/announce.js";
import { isPanelSettingsOpen } from "../../panel-settings/state.js";

vi.mock("../delete.js", () => ({ deleteUTubTagShowModal: vi.fn() }));
vi.mock("../unselect-all.js", () => ({
  enableUnselectAllButtonAfterTagFilterApplied: vi.fn(),
  disableUnselectAllButtonAfterTagFilterRemoved: vi.fn(),
}));
vi.mock("../../urls/cards/filtering.js", () => ({
  updateURLsAndTagSubheaderWhenTagSelected: vi.fn(),
}));
vi.mock("../../panel-settings/announce.js", () => ({
  announceSettingsStatus: vi.fn(),
}));
vi.mock("../../panel-settings/state.js", () => ({
  isPanelSettingsOpen: vi.fn(() => false),
}));

describe("buildTagFilterInDeck", () => {
  describe("element structure", () => {
    it("returns a jQuery element", () => {
      const el = buildTagFilterInDeck(1, 10, "my-tag");
      expect(el.length).toBe(1);
    });

    it("has tagFilter, pointerable, unselected, col-12 classes", () => {
      const el = buildTagFilterInDeck(1, 10, "my-tag");
      expect(el.hasClass("tagFilter")).toBe(true);
      expect(el.hasClass("pointerable")).toBe(true);
      expect(el.hasClass("unselected")).toBe(true);
      expect(el.hasClass("col-12")).toBe(true);
    });

    it("sets data-utub-tag-id attribute to tagID", () => {
      const el = buildTagFilterInDeck(1, 42, "my-tag");
      expect(el.attr("data-utub-tag-id")).toBe("42");
    });

    it("sets tabindex to 0", () => {
      const el = buildTagFilterInDeck(1, 10, "my-tag");
      expect(el.attr("tabindex")).toBe("0");
    });

    it("contains a span with the tag string as its text content", () => {
      const el = buildTagFilterInDeck(1, 10, "cool-tag");
      expect(el.children("span").first().text()).toBe("cool-tag");
    });

    it("contains a .tagCountWrap container", () => {
      const el = buildTagFilterInDeck(1, 10, "tag");
      expect(el.find(".tagCountWrap").length).toBe(1);
    });

    it("contains a .tagMenuWrap container with the hidden class", () => {
      const el = buildTagFilterInDeck(1, 10, "tag");
      const menuWrap = el.find(".tagMenuWrap");
      expect(menuWrap.length).toBe(1);
      expect(menuWrap.hasClass("hidden")).toBe(true);
    });

    it("contains a .utubTagBtnDelete button", () => {
      const el = buildTagFilterInDeck(1, 10, "tag");
      expect(el.find(".utubTagBtnDelete").length).toBe(1);
    });
  });

  describe("url count display", () => {
    it("counts 0 in view and 0 total when urlCount defaults to 0", () => {
      const el = buildTagFilterInDeck(1, 10, "tag");
      expect(readTagCount(el)).toEqual({ inView: 0, total: 0 });
    });

    it("counts N in view and N total when urlCount is provided", () => {
      const el = buildTagFilterInDeck(1, 10, "tag", 7);
      expect(readTagCount(el)).toEqual({ inView: 7, total: 7 });
    });

    it("uses the same value for both the in-view and total count", () => {
      const el = buildTagFilterInDeck(1, 10, "tag", 3);
      expect(el.find(".tagCountInView").text()).toBe("3");
      expect(el.find(".tagCountTotal").text()).toBe("3");
    });

    it("renders the default style as 'in view / total' text", () => {
      const el = buildTagFilterInDeck(1, 10, "tag", 3);
      expect(el.find(".tagAppliedToUrlsCount").text()).toBe("3 / 3");
      expect(el.find(".tagCountSep").text()).toBe(" / ");
    });
  });
});

describe("tag selection, cap and match mode", () => {
  const $ = window.jQuery;
  const MAX = APP_CONFIG.constants.TAGS_MAX_ON_URLS;
  const ANNOUNCEMENT = "#URLTagFilterAnnouncement";

  function chip(tagID: number): JQuery {
    return $(`.tagFilter[data-utub-tag-id="${tagID}"]`);
  }

  function mountChips({
    count,
    visibleUrls,
  }: {
    count: number;
    visibleUrls: number;
  }) {
    const urls = Array.from(
      { length: visibleUrls },
      () => '<div class="urlRow" filterable="true"></div>',
    ).join("");
    document.body.innerHTML =
      '<div id="listTags"></div><span id="URLTagFilterAnnouncement"></span>' +
      urls;
    for (let tagID = 1; tagID <= count; tagID++) {
      $("#listTags").append(buildTagFilterInDeck(1, tagID, `t${tagID}`));
    }
  }

  function setMode(mode: "all" | "any") {
    setState({
      preferences: { ...getState().preferences, tagMatchMode: mode },
    });
  }

  function selectFirst(count: number) {
    for (let tagID = 1; tagID <= count; tagID++) {
      toggleTagFilterSelected(chip(tagID));
    }
  }

  const disabledCount = () => $(".tagFilter.unselected.disabled").length;

  beforeEach(() => {
    resetStore();
    vi.clearAllMocks();
    vi.mocked(isPanelSettingsOpen).mockReturnValue(false);
    vi.mocked(updateURLsAndTagSubheaderWhenTagSelected).mockReset();
    mountChips({ count: MAX + 2, visibleUrls: 3 });
    initTagMatchMode();
  });

  describe("selection order", () => {
    it("records click order, not DOM order, and unselect removes in place", () => {
      toggleTagFilterSelected(chip(5));
      toggleTagFilterSelected(chip(2));
      toggleTagFilterSelected(chip(9));
      expect(getState().selectedTagIDs).toEqual([5, 2, 9]);

      toggleTagFilterSelected(chip(2));
      expect(getState().selectedTagIDs).toEqual([5, 9]);
      expect(chip(2).hasClass("unselected")).toBe(true);
    });

    it("toggles the unselect-all button on the first select and last unselect", () => {
      toggleTagFilterSelected(chip(1));
      expect(
        enableUnselectAllButtonAfterTagFilterApplied,
      ).toHaveBeenCalledTimes(1);
      toggleTagFilterSelected(chip(2));
      expect(
        enableUnselectAllButtonAfterTagFilterApplied,
      ).toHaveBeenCalledTimes(1);

      toggleTagFilterSelected(chip(1));
      expect(
        disableUnselectAllButtonAfterTagFilterRemoved,
      ).not.toHaveBeenCalled();
      toggleTagFilterSelected(chip(2));
      expect(
        disableUnselectAllButtonAfterTagFilterRemoved,
      ).toHaveBeenCalledTimes(1);
    });
  });

  describe("syncTagCapState", () => {
    it.each([
      { mode: "all" as const, selected: MAX - 1, disabled: false },
      { mode: "all" as const, selected: MAX, disabled: true },
      { mode: "any" as const, selected: MAX - 1, disabled: false },
      { mode: "any" as const, selected: MAX, disabled: false },
      { mode: "all" as const, selected: MAX + 1, disabled: true },
      { mode: "any" as const, selected: MAX + 1, disabled: false },
    ])(
      "$mode with $selected selected: disabled=$disabled",
      ({ mode, selected, disabled }) => {
        setMode(mode);
        selectFirst(selected);
        syncTagCapState();
        syncTagCapState();
        expect(disabledCount() > 0).toBe(disabled);
      },
    );

    it("blocks a 21st selection under all but allows it under any", () => {
      selectFirst(MAX);
      toggleTagFilterSelected(chip(MAX + 1));
      expect(getState().selectedTagIDs).toHaveLength(MAX);

      setMode("any");
      toggleTagFilterSelected(chip(MAX + 1));
      expect(getState().selectedTagIDs).toHaveLength(MAX + 1);
      expect(disabledCount()).toBe(0);
    });

    it("any -> all at the cap disables the rest, and all -> any re-enables", () => {
      setMode("any");
      selectFirst(MAX);
      expect(disabledCount()).toBe(0);
      setMode("all");
      expect(disabledCount()).toBe(2);
      setMode("any");
      expect(disabledCount()).toBe(0);
    });

    it("does not stack click handlers across repeated enables", () => {
      selectFirst(MAX);
      setMode("any");
      setMode("all");
      setMode("any");
      vi.mocked(updateURLsAndTagSubheaderWhenTagSelected).mockClear();
      chip(MAX + 1).trigger("click");
      expect(getState().selectedTagIDs).toHaveLength(MAX + 1);
    });
  });

  describe("any -> all trim", () => {
    it("keeps the first MAX in selection order and runs the pipeline once after sync", () => {
      setMode("any");
      // Click order differs from DOM order: 22 first, then the rest.
      toggleTagFilterSelected(chip(MAX + 2));
      selectFirst(MAX + 1);
      expect(getState().selectedTagIDs).toHaveLength(MAX + 2);

      const observed: Array<{ selected: number; disabled: number }> = [];
      vi.mocked(updateURLsAndTagSubheaderWhenTagSelected).mockImplementation(
        () => {
          observed.push({
            selected: getState().selectedTagIDs.length,
            disabled: disabledCount(),
          });
        },
      );
      setMode("all");

      expect(getState().selectedTagIDs).toHaveLength(MAX);
      expect(getState().selectedTagIDs[0]).toBe(MAX + 2);
      expect(chip(MAX).hasClass("unselected")).toBe(true);
      // Run once, over the trimmed selection, after the cap state was synced.
      expect(observed).toEqual([{ selected: MAX, disabled: 2 }]);
    });

    it("does nothing when the mode change is not a mode change", () => {
      setState({
        preferences: { ...getState().preferences, tagSort: "name_az" },
      });
      expect(updateURLsAndTagSubheaderWhenTagSelected).not.toHaveBeenCalled();
    });

    it("does not treat a UTub switch as a mode change", () => {
      setState({
        activeUTubID: 7,
        memberSettings: null,
        preferences: { ...getState().preferences, tagMatchMode: "any" },
      });
      expect(updateURLsAndTagSubheaderWhenTagSelected).not.toHaveBeenCalled();
    });
  });

  describe("announcement routing", () => {
    it("writes the filter result to the page region when unclaimed and the panel is closed", () => {
      selectFirst(2);
      setMode("any");
      expect($(ANNOUNCEMENT).text()).toBe(
        "3 URLs shown, matching any selected tags",
      );
      expect(announceSettingsStatus).not.toHaveBeenCalled();
    });

    it("uses the settings status region when the panel is open", () => {
      vi.mocked(isPanelSettingsOpen).mockReturnValue(true);
      selectFirst(2);
      setMode("any");
      expect(announceSettingsStatus).toHaveBeenCalledWith({
        message: "3 URLs shown, matching any selected tags",
      });
      expect($(ANNOUNCEMENT).text()).toBe("");
    });

    it("joins the trim and filter sentences with '. '", () => {
      setMode("any");
      selectFirst(MAX + 1);
      setMode("all");
      expect($(ANNOUNCEMENT).text()).toBe(
        `3 URLs shown, matching all selected tags. ${APP_CONFIG.strings.TAG_FILTER_TRIM_ANNOUNCEMENT}`,
      );
    });

    it("announces nothing with fewer than two tags selected", () => {
      selectFirst(1);
      setMode("any");
      expect($(ANNOUNCEMENT).text()).toBe("");
      expect(announceSettingsStatus).not.toHaveBeenCalled();
    });

    it("returns the outcome and announces nothing when claimed", () => {
      selectFirst(2);
      const outcome = applyClaimingModeChange(() => setMode("any"));
      expect(outcome).toEqual({
        filterResult: "3 URLs shown, matching any selected tags",
        trimNotice: null,
      });
      expect($(ANNOUNCEMENT).text()).toBe("");
      expect(announceSettingsStatus).not.toHaveBeenCalled();
    });

    it("returns no filter result for a claimed write that is not a mode change", () => {
      selectFirst(2);
      const outcome = applyClaimingModeChange(() =>
        setState({
          preferences: { ...getState().preferences, tagSort: "name_az" },
        }),
      );
      expect(outcome).toEqual({ filterResult: null, trimNotice: null });
    });

    it("leaves no record behind after a claim: the next unclaimed change announces", () => {
      selectFirst(2);
      applyClaimingModeChange(() => setMode("any"));
      setMode("all");
      expect($(ANNOUNCEMENT).text()).toBe(
        "3 URLs shown, matching all selected tags",
      );
    });

    it("reports the final mode once when a claimed save flips twice", () => {
      selectFirst(2);
      const outcome = applyClaimingModeChange(() => {
        setMode("any");
        setMode("all");
        setMode("any");
      });
      expect(outcome.filterResult).toBe(
        "3 URLs shown, matching any selected tags",
      );
    });

    it("drops the filter result but keeps the trim notice when a claim returns to its start", () => {
      setMode("any");
      selectFirst(MAX + 1);
      const outcome = applyClaimingModeChange(() => {
        setMode("all");
        setMode("any");
      });
      expect(outcome).toEqual({
        filterResult: null,
        trimNotice: APP_CONFIG.strings.TAG_FILTER_TRIM_ANNOUNCEMENT,
      });
    });

    it("returns an empty outcome from a later claim after an unclaimed change", () => {
      selectFirst(2);
      setMode("any");
      expect(applyClaimingModeChange(() => {})).toEqual({
        filterResult: null,
        trimNotice: null,
      });
    });

    it("clears the claim when fn throws", () => {
      selectFirst(2);
      expect(() =>
        applyClaimingModeChange(() => {
          throw new Error("boom");
        }),
      ).toThrow("boom");
      setMode("any");
      expect($(ANNOUNCEMENT).text()).toBe(
        "3 URLs shown, matching any selected tags",
      );
    });
  });
});
