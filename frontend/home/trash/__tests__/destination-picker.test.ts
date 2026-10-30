import type { TrashList, TrashedUrlItem } from "../../../types/trash.js";
import type { UtubSummaryItem } from "../../../types/utub.js";

import { makeUtubSummaryItem } from "../../../__tests__/helpers/utub-summary.js";
import {
  createMockJqXHRChainable,
  createMockXhr,
} from "../../../__tests__/helpers/mock-jquery.js";
import { $ } from "../../../lib/globals.js";
import { ajaxCall, is429Handled } from "../../../lib/ajax.js";
import { resetStore, setState } from "../../../store/app-store.js";
import { showOutcomeBanner } from "../../urls/outcome-banner.js";
import { refreshTrashCount } from "../count.js";
import { loadTrashList } from "../list.js";
import { renderTrashList } from "../render.js";
import { handleTrashTabClick, _resetTrashTabsForTests } from "../tabs.js";
import { initTrashActions } from "../actions.js";
import {
  closeDestinationPicker,
  isDestinationPickerOpen,
} from "../destination-picker.js";

vi.mock("../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));
vi.mock("../../utubs/deck.js", () => ({ buildUTubDeck: vi.fn() }));
vi.mock("../../utubs/utils.js", () => ({ getAllUTubs: vi.fn() }));
vi.mock("../count.js", () => ({
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
  buildReviveMessage: vi.fn(() => "revived"),
  buildLostTagNamesDetail: vi.fn(() => undefined),
}));

const NOW = Date.parse("2026-10-16T12:00:00Z");
const DAY = 86_400_000;

function makeUrlItem(overrides: Partial<TrashedUrlItem> = {}): TrashedUrlItem {
  return {
    utubUrlID: 21,
    urlString: "https://example.com/a",
    urlTitle: "Example",
    utubID: 3,
    utubName: "Gone",
    originUtubTrashed: true,
    originUtubLocked: false,
    trashedWithUtub: true,
    deletedAt: new Date(NOW - DAY).toISOString(),
    expiresAt: new Date(NOW + 20 * DAY).toISOString(),
    deletedByUserID: 9,
    deletedByUsername: "mcarter",
    addedByUserID: 9,
    addedByUsername: "mcarter",
    canRestore: true,
    canDelete: true,
    ...overrides,
  } as TrashedUrlItem;
}

function makeUtub(overrides: Partial<UtubSummaryItem>): UtubSummaryItem {
  return makeUtubSummaryItem({ name: "Alpha", ...overrides });
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
`;

function renderRows(items: TrashedUrlItem[]): void {
  renderTrashList({
    list: {
      urls: items,
      utubs: [],
      currentUser: 5,
      retentionDays: 30,
      listedAt: new Date(NOW).toISOString(),
    } as TrashList,
  });
}

function rowFor(utubUrlID: number): JQuery {
  return $(`#listTrashURLs .trashRow[data-utub-url-id="${utubUrlID}"]`);
}

function openPickerOn(utubUrlID: number): void {
  rowFor(utubUrlID).find(".trashBtnRestore").trigger("click");
}

function options(): JQuery {
  return $(".trashDestinationOption");
}

function key({
  target,
  type,
  name,
}: {
  target: Element;
  type: "keydown" | "keyup";
  name: string;
}): void {
  target.dispatchEvent(
    new KeyboardEvent(type, { key: name, bubbles: true, cancelable: true }),
  );
}

function settled({ done, fail }: { done?: unknown; fail?: unknown }) {
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

describe("trash destination picker", () => {
  beforeEach(() => {
    document.body.innerHTML = HTML;
    resetStore();
    vi.clearAllMocks();
    vi.mocked(is429Handled).mockReturnValue(false);
    setState({
      utubs: [
        makeUtub({ id: 1, name: "Alpha" }),
        makeUtub({ id: 2, name: "Locked one", isLocked: true }),
        makeUtub({ id: 5, name: "Gamma" }),
      ],
    });
    initTrashActions();
    renderRows([
      makeUrlItem({ utubUrlID: 21 }),
      makeUrlItem({ utubUrlID: 22, urlTitle: "Second" }),
    ]);
  });

  afterEach(() => {
    closeDestinationPicker({ returnFocus: false });
    $("#listTrashURLs, #listTrashUTubs, #TrashBtnEmpty").off(".trashActions");
    _resetTrashTabsForTests();
    vi.restoreAllMocks();
  });

  describe("options", () => {
    it("renders a labelled listbox of live UTubs in deck order, below the actions", () => {
      openPickerOn(21);

      const picker = rowFor(21).find(".trashDestinationPicker");
      expect(picker).toHaveLength(1);
      expect(picker.attr("role")).toBe("listbox");
      expect(picker.attr("aria-label")).toBe("Restore to which UTub?");
      expect(
        options()
          .map((_, el) => $(el).attr("data-dest-utub-id"))
          .get(),
      ).toEqual(["1", "2", "5"]);
      expect(options().attr("role")).toBe("option");
      expect(rowFor(21).find(".actions").next()[0]).toBe(picker[0]);
      expect(rowFor(21).find(".trashBtnRestore").attr("aria-expanded")).toBe(
        "true",
      );
    });

    it("never uses the markup the left-panel UTub search queries", () => {
      openPickerOn(21);

      expect($(".trashDestinationPicker .UTubSelector")).toHaveLength(0);
      expect($(".trashDestinationPicker [utubid]")).toHaveLength(0);
      expect($(".trashDestinationPicker .UTubName")).toHaveLength(0);
    });

    it("excludes the origin UTub", () => {
      setState({
        utubs: [makeUtub({ id: 3, name: "Origin" }), makeUtub({ id: 1 })],
      });
      openPickerOn(21);

      expect(options()).toHaveLength(1);
    });

    it("marks locked UTubs disabled and focuses the first enabled option", () => {
      openPickerOn(21);

      const locked = options().eq(1);
      expect(locked.hasClass("disabled")).toBe(true);
      expect(locked.attr("aria-disabled")).toBe("true");
      expect(locked.text()).toContain("Locked");
      expect(options().eq(0).attr("tabindex")).toBe("0");
      expect(document.activeElement).toBe(options()[0]);
    });

    it("shows a status message instead of options when every UTub is locked", () => {
      setState({ utubs: [makeUtub({ id: 2, isLocked: true })] });
      openPickerOn(21);

      expect(options()).toHaveLength(0);
      const status = $(".trashDestinationNone");
      expect(status.attr("role")).toBe("status");
      expect(status.text()).toBe("You have no unlocked UTub to restore into.");
    });
  });

  describe("keyboard", () => {
    it("arrows skip the disabled option and Home/End jump to the ends", () => {
      openPickerOn(21);
      const picker = $(".trashDestinationPicker")[0];

      key({ target: options()[0], type: "keydown", name: "ArrowDown" });
      expect(document.activeElement).toBe(options()[2]);

      key({ target: options()[2], type: "keydown", name: "Home" });
      expect(document.activeElement).toBe(options()[0]);

      key({ target: picker, type: "keydown", name: "End" });
      expect(document.activeElement).toBe(options()[2]);
    });

    it("Enter on an enabled option restores into it", () => {
      vi.mocked(ajaxCall).mockReturnValue(createMockJqXHRChainable());
      openPickerOn(21);
      const option = options()[2];

      key({ target: option, type: "keydown", name: "Enter" });
      key({ target: option, type: "keyup", name: "Enter" });

      expect(ajaxCall).toHaveBeenCalledTimes(1);
      expect(vi.mocked(ajaxCall).mock.calls[0][2]).toEqual({ destUtubId: 5 });
    });

    it("ignores the keyup of the Enter that opened the picker", () => {
      openPickerOn(21);

      key({ target: options()[0], type: "keyup", name: "Enter" });

      expect(ajaxCall).not.toHaveBeenCalled();
    });

    it("a click on a disabled option does nothing", () => {
      openPickerOn(21);

      options().eq(1).trigger("click");

      expect(ajaxCall).not.toHaveBeenCalled();
    });

    it("Escape closes the picker, toggles aria-expanded and refocuses Restore", () => {
      openPickerOn(21);

      key({ target: options()[0], type: "keydown", name: "Escape" });

      expect(isDestinationPickerOpen()).toBe(false);
      const restore = rowFor(21).find(".trashBtnRestore");
      expect(restore.attr("aria-expanded")).toBe("false");
      expect(document.activeElement).toBe(restore[0]);
    });
  });

  describe("lifecycle", () => {
    it("opening a second picker closes the first", () => {
      openPickerOn(21);
      openPickerOn(22);

      expect($(".trashDestinationPicker")).toHaveLength(1);
      expect(rowFor(22).find(".trashDestinationPicker")).toHaveLength(1);
      expect(rowFor(21).find(".trashBtnRestore").attr("aria-expanded")).toBe(
        "false",
      );
    });

    it("clicking Restore again closes the picker", () => {
      openPickerOn(21);
      openPickerOn(21);

      expect(isDestinationPickerOpen()).toBe(false);
    });

    it("a tab switch closes an open picker", () => {
      openPickerOn(21);

      handleTrashTabClick({ tabId: "TrashTabUtubs" });

      expect(isDestinationPickerOpen()).toBe(false);
    });

    it("a tab switch with no picker open is a no-op", () => {
      expect(() =>
        handleTrashTabClick({ tabId: "TrashTabUtubs" }),
      ).not.toThrow();
      expect(isDestinationPickerOpen()).toBe(false);
    });
  });

  describe("outcomes", () => {
    it("200 removes the row, announces the destination and refreshes the count", async () => {
      vi.mocked(ajaxCall).mockReturnValue(
        settled({
          done: {
            lostTagCount: 4,
            restoredToDestination: true,
            utubName: "Gamma",
          },
        }),
      );
      openPickerOn(21);

      options().eq(2).trigger("click");
      await Promise.resolve();

      expect(rowFor(21)).toHaveLength(0);
      const call = vi.mocked(showOutcomeBanner).mock.calls[0][0] as {
        message: string;
        variant: string;
      };
      expect(call.message).toBe("Restored to Gamma.");
      expect(call.variant).toBe("success");
      expect(refreshTrashCount).toHaveBeenCalledTimes(1);
    });

    it("409 already-in-destination keeps the row, warns and refocuses the picker", async () => {
      vi.mocked(ajaxCall).mockReturnValue(
        settled({
          fail: createMockXhr({
            status: 409,
            responseJSON: { errorCode: 14 },
          }),
        }),
      );
      openPickerOn(21);

      options().eq(2).trigger("click");
      await Promise.resolve();

      expect(rowFor(21)).toHaveLength(1);
      expect(isDestinationPickerOpen()).toBe(true);
      const call = vi.mocked(showOutcomeBanner).mock.calls[0][0] as {
        message: string;
        variant: string;
      };
      expect(call.variant).toBe("partial");
      expect(call.message).toBe("That UTub already has this URL.");
      expect(document.activeElement).toBe(options()[0]);
    });

    it.each([12, 13])(
      "400 with error code %i reloads the list",
      async (code) => {
        vi.mocked(ajaxCall).mockReturnValue(
          settled({
            fail: createMockXhr({
              status: 400,
              responseJSON: { errorCode: code },
            }),
          }),
        );
        openPickerOn(21);

        options().eq(0).trigger("click");
        await Promise.resolve();

        expect(loadTrashList).toHaveBeenCalledTimes(1);
        expect(isDestinationPickerOpen()).toBe(false);
      },
    );
  });
});
