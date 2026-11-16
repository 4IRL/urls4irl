import { resetStore, setState } from "../../../../store/app-store.js";
import { resolveUtubSettings } from "../../../../types/settings.js";
import { isCoarsePointer } from "../../../mobile.js";
import { initBulkBar, refreshBulkActionButtons } from "../bulk-bar.js";
import { initBulkTag, isBulkTagPickerOpen } from "../bulk-tag.js";

vi.mock("../../../mobile.js", () => ({
  isMobile: vi.fn(() => false),
  isCoarsePointer: vi.fn(() => false),
}));

vi.mock("../../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));

vi.mock("../../../../lib/modal-tracking.js", () => ({
  setOpenForm: vi.fn(),
  clearOpenForm: vi.fn(),
}));

vi.mock("../../tags/combobox-state.js", () => ({
  mergeAppliedTagsIntoStore: vi.fn(),
}));
vi.mock("../../tags/tags.js", () => ({ createTagBadgeInURL: vi.fn() }));
vi.mock("../../../tags/tags.js", () => ({
  syncTagCapState: vi.fn(),
  buildTagFilterInDeck: vi.fn(),
}));
vi.mock("../../../tags/deck.js", () => ({ refreshTagDeckTagCount: vi.fn() }));
vi.mock("../../../tags/search.js", () => ({ reapplyTagFilter: vi.fn() }));
vi.mock("../../cards/filtering.js", () => ({
  updateVisibleURLsForTagCount: vi.fn(),
  writeTagChipDenominator: vi.fn(),
}));

vi.mock("../../tags/combobox.js", () => ({
  BULK_RESET_KEY: "urlTagComboboxResetBulk",
  ComboboxMode: Object.freeze({ URL: "url", CREATE: "create", BULK: "bulk" }),
  createTagComboboxBlock: vi.fn(() =>
    window.jQuery(
      '<div class="urlTagComboboxWrap hidden">' +
        '<input class="urlTagComboboxInput" />' +
        '<div class="urlTagComboboxActions"><button class="urlTagComboboxSubmitBtn" type="button"></button></div>' +
        "</div>",
    ),
  ),
}));

const REASON = "Only the owner and co-owners can tag URLs in this UTub.";

function settings(canTag: boolean) {
  return resolveUtubSettings({
    tags: { members_can_tag: canTag, members_can_delete_tags: true },
  } as never);
}

function addTags(): HTMLElement {
  return document.querySelector(
    '[data-bulk-action-id="bulk-add-tags"]',
  ) as HTMLElement;
}

describe("bulk Add tags policy", () => {
  beforeAll(() => {
    initBulkTag();
  });

  beforeEach(() => {
    document.body.innerHTML = `
      <div id="URLDeck">
        <div id="listURLs"></div>
        <div id="bulkActionBar">
          <button id="bulkSelectExit" type="button">Exit</button>
          <span id="bulkSelectCount"></span>
          <div id="bulkActionButtons"></div>
          <div id="bulkTagPickerMount" class="hidden"></div>
          <div id="bulkTagResultBanner" class="hidden"></div>
        </div>
      </div>`;
    window.matchMedia = vi.fn(() => ({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })) as unknown as typeof window.matchMedia;
    vi.mocked(isCoarsePointer).mockReturnValue(false);
    resetStore();
    setState({
      activeUTubID: 1,
      isCurrentUserOwner: false,
      isCoCreator: false,
      settings: settings(true),
      selectedURLCardIDs: [1, 2],
    });
    initBulkBar();
    setState({ selectedURLCardIDs: [1] });
    refreshBulkActionButtons();
  });

  it("renders Add tags enabled for a permitted plain member and opens the picker", () => {
    expect(addTags().hasAttribute("aria-disabled")).toBe(false);
    addTags().click();
    expect(isBulkTagPickerOpen()).toBe(true);
  });

  it("renders Add tags blocked with the reason, opening no picker", () => {
    setState({ settings: settings(false) });
    expect(addTags().getAttribute("aria-disabled")).toBe("true");
    const tooltip = document.getElementById(
      addTags().getAttribute("aria-describedby") ?? "none",
    );
    expect(tooltip?.textContent).toBe(REASON);
    addTags().click();
    expect(isBulkTagPickerOpen()).toBe(false);
  });

  it("a blocked button stays blocked after a selection repaint", () => {
    setState({ settings: settings(false) });
    refreshBulkActionButtons();
    refreshBulkActionButtons();
    expect(addTags().getAttribute("aria-disabled")).toBe("true");
  });

  it("closes an open picker when tagging turns off and returns focus to the blocked button if it was inside", () => {
    addTags().click();
    expect(isBulkTagPickerOpen()).toBe(true);
    (document.querySelector(".urlTagComboboxInput") as HTMLElement).focus();
    setState({ settings: settings(false) });
    expect(isBulkTagPickerOpen()).toBe(false);
    expect(addTags().getAttribute("aria-disabled")).toBe("true");
    expect(document.activeElement).toBe(addTags());
  });

  it("leaves focus unchanged on a flip when focus was outside the picker", () => {
    addTags().click();
    (document.getElementById("bulkSelectExit") as HTMLElement).focus();
    setState({ settings: settings(false) });
    expect(isBulkTagPickerOpen()).toBe(false);
    expect(document.activeElement).toBe(
      document.getElementById("bulkSelectExit"),
    );
  });

  it("unblocks Add tags when tagging turns back on", () => {
    setState({ settings: settings(false) });
    setState({ settings: settings(true) });
    expect(addTags().hasAttribute("aria-disabled")).toBe(false);
    expect(document.querySelector('[role="tooltip"]')).toBeNull();
  });
});
