import {
  refreshTagDeckTagCount,
  removeTagFromTagDeckGivenTagID,
  resetTagDeck,
  resetTagDeckIfNoUTubSelected,
  setTagDeckOnUTubSelected,
  setTagDeckSubheaderWhenNoUTubSelected,
  updateTagDeck,
} from "../deck.js";
import { emit, AppEvents } from "../../../lib/event-bus.js";
import { resetStore, setState } from "../../../store/app-store.js";
import { applyDeckDiff } from "../../../logic/apply-deck-diff.js";
import { bootstrap } from "../../../lib/globals.js";

// The ambient test-setup Bootstrap mock returns null from getInstance(), which
// would make the tooltip-hide guards silent no-ops. Override lib/globals.js with
// a shared tooltip instance so the guards can be asserted on.
const { tooltipInstance, globalsMock } = await vi.hoisted(async () => {
  const { mockGlobalsWithTooltipInstance } =
    await import("../../../__tests__/helpers/mock-globals.js");
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
}));

vi.mock("../search.js", () => ({
  applyAlternatingTagBackground: vi.fn(),
  hideTagFilterBar: vi.fn(),
  reapplyTagFilter: vi.fn(),
  resetTagFilter: vi.fn(),
  setTagNameFilterToggleListeners: vi.fn(),
  setTagSelectorSearchEventListener: vi.fn(),
  showTagFilterBar: vi.fn(),
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

describe("Tag deck inline tag count", () => {
  // Mirrors the production header markup landed in Step 3: a real <button>
  // holding an unroled title <span>, with the semantic <h2> as a sibling.
  const TAG_DECK_HTML = `
    <div id="TagDeck">
      <div class="titleElement">
        <div id="TagDeckTitleGroup" class="flex-row gap-10p">
          <button type="button" id="TagDeckHeaderAndCaret" class="flex-row flex-center gap-2p clickable" aria-expanded="true" aria-controls="TagDeckContent">
            <span class="title-caret"></span>
            <span id="TagDeckHeader">Tags<span id="TagDeckCount" class="deck-title-count"></span></span>
          </button>
          <h2 id="TagDeckHeaderA11y" class="visually-hidden">Tags</h2>
        </div>
      </div>
      <div id="listTags"></div>
      <button id="utubTagBtnCreate" class="hidden"></button>
      <button id="unselectAllTagFilters" class="hidden"></button>
      <button id="utubTagBtnUpdateAllOpen" class="hidden"></button>
    </div>
  `;

  const count = (): string => window.jQuery("#TagDeckCount").text();

  beforeEach(() => {
    resetStore();
    document.body.innerHTML = TAG_DECK_HTML;
  });

  it("renders the rendered tag total inline next to the title after a deck build", () => {
    setTagDeckOnUTubSelected(
      [
        { id: 1, tagString: "alpha", tagApplied: 0 },
        { id: 2, tagString: "beta", tagApplied: 0 },
        { id: 3, tagString: "gamma", tagApplied: 0 },
      ],
      42,
    );

    expect(window.jQuery("#listTags > .tagFilter").length).toBe(3);
    expect(count()).toBe("(3)");
  });

  // NOTE: there is deliberately no "(0) for a tagless UTub" case here. It would
  // be vacuous: setTagDeckOnUTubSelected() opens with resetTagDeck(), which
  // already writes "(0)" against the emptied list, so with no tags to append the
  // post-loop refresh is a no-op and deleting it would not fail the assertion.
  // The empty-deck "(0)" guarantee is pinned by "resets the count to (0) when
  // the deck is reset" below; the post-loop refresh is pinned by the 3-tag build
  // case above.

  it("drops the count when a tag row is removed from the deck", () => {
    setTagDeckOnUTubSelected(
      [
        { id: 1, tagString: "alpha", tagApplied: 0 },
        { id: 2, tagString: "beta", tagApplied: 0 },
      ],
      42,
    );
    expect(count()).toBe("(2)");

    removeTagFromTagDeckGivenTagID(2);

    expect(count()).toBe("(1)");
  });

  it("tracks both halves of an updateTagDeck diff", () => {
    setState({ tags: [{ id: 1, tagString: "alpha", tagApplied: 0 }] });
    window
      .jQuery("#listTags")
      .append('<div class="tagFilter" data-utub-tag-id="1">alpha</div>');
    // applyDeckDiff is mocked in this file, so apply the diff's DOM effects
    // directly — what is under test is that the count is refreshed AFTER the
    // diff runs, not applyDeckDiff itself (covered in the describe above).
    vi.mocked(applyDeckDiff).mockImplementationOnce(() => {
      window.jQuery('[data-utub-tag-id="1"]').remove();
      window
        .jQuery("#listTags")
        .append(
          '<div class="tagFilter" data-utub-tag-id="2">beta</div><div class="tagFilter" data-utub-tag-id="3">gamma</div>',
        );
    });

    updateTagDeck(
      [
        { id: 2, tagString: "beta", tagApplied: 0 },
        { id: 3, tagString: "gamma", tagApplied: 0 },
      ],
      42,
    );

    expect(count()).toBe("(2)");
  });

  it("does not change when a tag filter is applied", () => {
    setTagDeckOnUTubSelected(
      [
        { id: 1, tagString: "alpha", tagApplied: 0 },
        { id: 2, tagString: "beta", tagApplied: 0 },
        { id: 3, tagString: "gamma", tagApplied: 0 },
      ],
      42,
    );
    expect(count()).toBe("(3)");

    // The deck used to subscribe to TAG_FILTER_CHANGED and rewrite this span as
    // "(applied/max)". It must not any more — the Step 10 pill owns filter state.
    emit(AppEvents.TAG_FILTER_CHANGED, { selectedTagIDs: [1, 2] });

    expect(count()).toBe("(3)");
  });

  it("resets the count to (0) when the deck is reset", () => {
    setTagDeckOnUTubSelected(
      [{ id: 1, tagString: "alpha", tagApplied: 0 }],
      42,
    );
    expect(count()).toBe("(1)");

    resetTagDeck();

    expect(count()).toBe("(0)");
  });

  it("clears the inline count when no UTub is selected", () => {
    window.jQuery("#TagDeckCount").text("(2)");

    setTagDeckSubheaderWhenNoUTubSelected();

    expect(count()).toBe("");
  });

  it("still counts rows the tag-NAME filter has hidden", () => {
    // `tags/search.ts` hides non-matching rows with `.hidden` (display: none)
    // rather than removing them. That is a view filter, not a change to the
    // UTub's tag total, so the count must stay at the full total — a distinct
    // mechanism from the applied-tag-filter case above.
    setTagDeckOnUTubSelected(
      [
        { id: 1, tagString: "alpha", tagApplied: 0 },
        { id: 2, tagString: "beta", tagApplied: 0 },
        { id: 3, tagString: "gamma", tagApplied: 0 },
      ],
      42,
    );
    window
      .jQuery('#listTags > .tagFilter[data-utub-tag-id="2"]')
      .addClass("hidden");
    window
      .jQuery('#listTags > .tagFilter[data-utub-tag-id="3"]')
      .addClass("hidden");

    refreshTagDeckTagCount();

    expect(count()).toBe("(3)");
  });

  it("counts only rows rendered inside #listTags", () => {
    // A .tagFilter outside the deck list (e.g. a detached/cloned row) must not
    // inflate the total — the selector is deliberately a direct-child one.
    document.body.insertAdjacentHTML(
      "beforeend",
      '<div class="tagFilter" data-utub-tag-id="99">stray</div>',
    );
    window
      .jQuery("#listTags")
      .append('<div class="tagFilter" data-utub-tag-id="1">alpha</div>');

    refreshTagDeckTagCount();

    expect(count()).toBe("(1)");
  });
});
