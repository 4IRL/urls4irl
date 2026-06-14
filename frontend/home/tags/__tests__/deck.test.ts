import {
  setTagDeckOnUTubSelected,
  setTagDeckSubheaderWhenNoUTubSelected,
  updateTagDeck,
} from "../deck.js";
import { resetStore, setState } from "../../../store/app-store.js";
import { applyDeckDiff } from "../../../logic/apply-deck-diff.js";

vi.mock("../../../logic/apply-deck-diff.js", () => ({
  applyDeckDiff: vi.fn(),
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

describe("updateTagDeck - applyDeckDiff config", () => {
  beforeEach(() => {
    resetStore();
    document.body.innerHTML = `<div id="listTags"></div>`;
    vi.mocked(applyDeckDiff).mockReset();
  });

  it("calls applyDeckDiff once with oldItems matching getState().tags and newItems matching updatedTags", () => {
    const existingTag = { id: 1, tagString: "existing", tagApplied: 0 };
    const newTag = { id: 5, tagString: "new-tag", tagApplied: 0 };
    setState({ tags: [existingTag] });
    const updatedTags = [existingTag, newTag];

    updateTagDeck(updatedTags, 42);

    expect(vi.mocked(applyDeckDiff)).toHaveBeenCalledTimes(1);
    const config = vi.mocked(applyDeckDiff).mock.calls[0][0];
    expect(config.oldItems).toEqual([existingTag]);
    expect(config.newItems).toEqual(updatedTags);
    expect(config.getID(existingTag)).toBe(1);
    expect(config.getID(newTag)).toBe(5);
    expect(typeof config.removeElement).toBe("function");
    expect(typeof config.addElement).toBe("function");
  });

  it("removeElement callback removes the tag filter element from the DOM", () => {
    setState({ tags: [{ id: 7, tagString: "deleted", tagApplied: 0 }] });
    document.body.innerHTML = `
      <div id="listTags">
        <div class="tagFilter" data-utub-tag-id="7">deleted</div>
      </div>
    `;

    updateTagDeck([], 42);
    const config = vi.mocked(applyDeckDiff).mock.calls[0][0];

    config.removeElement(7);

    expect(document.querySelector('[data-utub-tag-id="7"]')).toBeNull();
  });
});

describe("Tag deck subheader visibility on UTub selection", () => {
  const TAG_DECK_HTML = `
    <div id="TagDeck">
      <div class="titleElement dynamic-subheader hidden">
        <h5 id="TagDeckSubheader"></h5>
      </div>
      <div id="listTags"></div>
      <button id="utubTagBtnCreate" class="hidden"></button>
      <button id="unselectAllTagFilters" class="hidden"></button>
      <button id="utubTagBtnUpdateAllOpen" class="hidden"></button>
    </div>
  `;

  beforeEach(() => {
    resetStore();
    document.body.innerHTML = TAG_DECK_HTML;
  });

  it("reveals the subheader when a UTub is selected", () => {
    const subheader = window.jQuery("#TagDeck > .dynamic-subheader");
    expect(subheader.hasClass("hidden")).toBe(true);

    setTagDeckOnUTubSelected([], 42);

    expect(subheader.hasClass("hidden")).toBe(false);
    expect(subheader.hasClass("height-2p5rem")).toBe(true);
  });

  it("collapses the subheader and clears its text when no UTub is selected", () => {
    const subheader = window.jQuery("#TagDeck > .dynamic-subheader");
    subheader.removeClass("hidden");
    window.jQuery("#TagDeckSubheader").text("2 of 5 tag filters applied");

    setTagDeckSubheaderWhenNoUTubSelected();

    expect(subheader.hasClass("hidden")).toBe(true);
    expect(window.jQuery("#TagDeckSubheader").text()).toBe("");
  });
});
