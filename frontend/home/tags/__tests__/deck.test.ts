import { updateTagDeck } from "../deck.js";
import { resetStore, setState } from "../../../store/app-store.js";
import { diffIDLists } from "../../../logic/deck-diffing.js";

vi.mock("../../../logic/deck-diffing.js", () => ({
  diffIDLists: vi.fn(),
}));

vi.mock("../create.js", () => ({
  createUTubTagHideInput: vi.fn(),
  removeCreateUTubTagEventListeners: vi.fn(),
  resetCreateUTubTagFailErrors: vi.fn(),
  resetNewUTubTagForm: vi.fn(),
  setupOpenCreateUTubTagEventListeners: vi.fn(),
}));

vi.mock("../update-all.js", () => ({
  closeUTubTagBtnMenuOnUTubTags: vi.fn(),
  setTagDeckBtnsOnUpdateAllUTubTagsClosed: vi.fn(),
  setUnselectUpdateUTubTagEventListeners: vi.fn(),
}));

vi.mock("../unselect-all.js", () => ({
  disableUnselectAllButtonAfterTagFilterRemoved: vi.fn(),
  resetCountOfTagFiltersApplied: vi.fn(),
}));

vi.mock("../tags.js", () => ({
  buildTagFilterInDeck: vi.fn((_utubID, tagID, tagString) =>
    window.jQuery(
      `<div class="tagFilter" data-utub-tag-id="${tagID}">${tagString}</div>`,
    ),
  ),
}));

const $ = window.jQuery;

describe("updateTagDeck - missing tag ID guard", () => {
  beforeEach(() => {
    resetStore();
    document.body.innerHTML = `<div id="listTags"></div>`;
    vi.mocked(diffIDLists).mockReset();
  });

  it("skips a toAdd tag ID that is not present in updatedTags and throws no error", () => {
    // Store already contains tag 1. updatedTags also contains tag 1.
    // But we force diffIDLists to claim toAdd=[999], an ID absent from updatedTags,
    // exercising the `if (!tagData) return;` guard in updateTagDeck.
    setState({ tags: [{ id: 1, tagString: "existing", tagApplied: 0 }] });
    const updatedTags = [{ id: 1, tagString: "existing", tagApplied: 0 }];
    vi.mocked(diffIDLists).mockReturnValue({
      toRemove: [],
      toAdd: [999],
      toUpdate: [1],
    });

    expect(() => {
      updateTagDeck(updatedTags, 42);
    }).not.toThrow();

    // No filter element appended for the missing ID.
    expect($("#listTags").find('[data-utub-tag-id="999"]').length).toBe(0);
    expect($("#listTags").children().length).toBe(0);
  });

  it("appends a tag filter when the toAdd tag IS present in updatedTags", () => {
    setState({ tags: [] });
    const updatedTags = [{ id: 5, tagString: "new-tag", tagApplied: 0 }];
    vi.mocked(diffIDLists).mockReturnValue({
      toRemove: [],
      toAdd: [5],
      toUpdate: [],
    });

    updateTagDeck(updatedTags, 7);

    expect($("#listTags").find('[data-utub-tag-id="5"]').length).toBe(1);
  });
});
