import {
  resetTagDeck,
  resetTagDeckIfNoUTubSelected,
  setTagDeckSubheaderWhenNoUTubSelected,
  updateCountOfTagFiltersApplied,
  updateTagDeck,
} from "../deck.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { resetStore, setState } from "../../../store/app-store.js";
import { applyDeckDiff } from "../../../logic/apply-deck-diff.js";
import { bootstrap } from "../../../lib/globals.js";

// The ambient test-setup Bootstrap mock returns null from getInstance(), which
// would make the tooltip-hide guards silent no-ops. Override lib/globals.js with
// a shared tooltip instance so the guards can be asserted on.
const { tooltipInstance, globalsMock } = await vi.hoisted(async () => {
  const { mockGlobalsWithTooltipInstance } = await import(
    "../../../__tests__/helpers/mock-globals.js"
  );
  return await mockGlobalsWithTooltipInstance();
});

vi.mock("../../../lib/globals.js", () => globalsMock);

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

describe("Tag deck reset - hides the #unselectAllTagFilters hover tooltip", () => {
  const TAG_DECK_RESET_HTML = `
    <div id="TagDeck">
      <div id="listTags"></div>
      <div id="createUTubTagWrap" class="hidden"></div>
      <button id="utubTagBtnCreate"></button>
      <button id="unselectAllTagFilters" data-bs-toggle="tooltip"></button>
      <button id="utubTagBtnUpdateAllOpen"></button>
    </div>
  `;

  // Records whether #unselectAllTagFilters already carried the `hidden` class at
  // the moment hide() ran. Asserting it is false proves the tooltip is hidden
  // BEFORE the button — swapping the two production lines flips it to true.
  let buttonHiddenWhenTooltipHidden: boolean | null = null;

  beforeEach(() => {
    resetStore();
    document.body.innerHTML = TAG_DECK_RESET_HTML;
    buttonHiddenWhenTooltipHidden = null;
    tooltipInstance.hide.mockReset();
    tooltipInstance.hide.mockImplementation(() => {
      buttonHiddenWhenTooltipHidden = window
        .jQuery("#unselectAllTagFilters")
        .hasClass("hidden");
    });
  });

  afterEach(() => {
    // Drop the recording implementation so it cannot leak into other describes
    // that share this hoisted tooltipInstance.
    tooltipInstance.hide.mockReset();
  });

  it("hides the tooltip before resetTagDeck() hides the button", () => {
    resetTagDeck();

    expect(tooltipInstance.hide).toHaveBeenCalled();
    expect(buttonHiddenWhenTooltipHidden).toBe(false);
    expect(window.jQuery("#unselectAllTagFilters").hasClass("hidden")).toBe(
      true,
    );
  });

  it("hides the tooltip before resetTagDeckIfNoUTubSelected() hides the button", () => {
    resetTagDeckIfNoUTubSelected();

    expect(tooltipInstance.hide).toHaveBeenCalled();
    expect(buttonHiddenWhenTooltipHidden).toBe(false);
    expect(window.jQuery("#unselectAllTagFilters").hasClass("hidden")).toBe(
      true,
    );
  });

  it("still hides the button and does not throw when no tooltip instance exists", () => {
    // Touch devices never construct a Tooltip, so getInstance() returns null and
    // the `?.` guard must no-op without breaking the reset.
    vi.mocked(bootstrap.Tooltip.getInstance).mockReturnValueOnce(null);

    expect(() => resetTagDeck()).not.toThrow();

    expect(tooltipInstance.hide).not.toHaveBeenCalled();
    expect(window.jQuery("#unselectAllTagFilters").hasClass("hidden")).toBe(
      true,
    );
  });
});

describe("Tag deck inline count", () => {
  const TAG_DECK_HTML = `
    <div id="TagDeck">
      <div class="titleElement">
        <h2 id="TagDeckHeader">Tags<span id="TagDeckCount" class="deck-title-count"></span></h2>
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

  it("renders the applied/max count inline next to the title", () => {
    updateCountOfTagFiltersApplied(2);

    expect(window.jQuery("#TagDeckCount").text()).toBe(
      `(2/${APP_CONFIG.constants.TAGS_MAX_ON_URLS})`,
    );
  });

  it("clears the inline count when no UTub is selected", () => {
    window.jQuery("#TagDeckCount").text("(2/3)");

    setTagDeckSubheaderWhenNoUTubSelected();

    expect(window.jQuery("#TagDeckCount").text()).toBe("");
  });
});
