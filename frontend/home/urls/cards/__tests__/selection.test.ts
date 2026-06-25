import {
  getSelectedURLCard,
  selectURLCard,
  deselectAllURLs,
  disableClickOnSelectedURLCardToHide,
} from "../selection.js";
import { enableTabbingOnURLCardElements } from "../utils.js";
import { resetStore, setState } from "../../../../store/app-store.js";
import { AppEvents, emit } from "../../../../lib/event-bus.js";
import { isCoarsePointer } from "../../../mobile.js";

vi.mock("../update-title.js", () => ({
  hideAndResetUpdateURLTitleForm: vi.fn(),
}));
vi.mock("../update-string.js", () => ({
  hideAndResetUpdateURLStringForm: vi.fn(),
}));
vi.mock("../../tags/combobox.js", () => ({
  hideAndResetTagCombobox: vi.fn(),
}));
vi.mock("../cards.js", () => ({
  setFocusEventListenersOnURLCard: vi.fn(),
}));
vi.mock("../utils.js", () => ({
  enableTabbingOnURLCardElements: vi.fn(),
  disableTabbingOnURLCardElements: vi.fn(),
}));
vi.mock("../../../mobile.js", () => ({
  isCoarsePointer: vi.fn(() => false),
}));

const $ = window.jQuery;

const TAG_DELETE_REVEAL_CLASS = "tagBadgeDeleteRevealed";

const TAGGED_CARD_HTML = `
  <div class="urlRow" utuburlid="42" urlSelected="false" filterable="true">
    <span class="goToUrlIcon"></span>
    <div class="urlTagsContainer">
      <span class="tagBadge" data-tag="1">
        first<button class="urlTagBtnDelete">×</button>
      </span>
      <span class="tagBadge" data-tag="2">
        second<button class="urlTagBtnDelete">×</button>
      </span>
    </div>
    <a class="urlString" href="https://example.com"></a>
  </div>
`;

const URL_CARD_HTML = `
  <div class="urlRow" utuburlid="42" urlSelected="false" filterable="true">
    <span class="goToUrlIcon"></span>
    <a class="urlString" href="https://example.com"></a>
    <button class="urlBtnDelete">Delete</button>
  </div>
`;

// Staged chips, the listbox, and the combobox controls live inside the card but
// must never deselect it when clicked. The child elements MUST be present in the
// DOM here — if a selector were mistyped, trigger() would fire on nothing and the
// urlSelected assertion would pass vacuously.
const COMBOBOX_CARD_HTML = `
  <div class="urlRow" utuburlid="42" urlSelected="false" filterable="true">
    <span class="goToUrlIcon"></span>
    <div class="urlTagComboboxWrap">
      <div class="urlTagCombobox">
        <span class="urlTagStagedChip" data-staged-tag-string="react">
          react<button class="urlTagStagedChipRemove">×</button>
        </span>
        <input class="urlTagComboboxInput" type="text" />
      </div>
      <div class="urlTagListbox">
        <div class="urlTagOption">pytest</div>
      </div>
      <div class="urlTagComboboxFooter">
        <button class="urlTagComboboxCancelBtn">Cancel</button>
        <button class="urlTagComboboxSubmitBtn">Add tags</button>
      </div>
    </div>
    <a class="urlString" href="https://example.com"></a>
  </div>
`;

const MULTI_CARD_HTML = `
  <div class="urlRow" utuburlid="10" urlSelected="false" filterable="true">
    <span class="goToUrlIcon"></span>
    <a class="urlString" href="https://alpha.com"></a>
  </div>
  <div class="urlRow" utuburlid="20" urlSelected="false" filterable="true">
    <span class="goToUrlIcon"></span>
    <a class="urlString" href="https://beta.com"></a>
  </div>
  <div class="urlRow" utuburlid="30" urlSelected="false" filterable="true">
    <span class="goToUrlIcon"></span>
    <a class="urlString" href="https://gamma.com"></a>
  </div>
`;

describe("URL Card Selection", () => {
  let urlCard: JQuery;

  beforeEach(() => {
    resetStore();
    document.body.innerHTML = URL_CARD_HTML;
    urlCard = $(".urlRow");
    vi.clearAllMocks();
  });

  describe("getSelectedURLCard", () => {
    it("returns null when no URL card is selected", () => {
      expect(getSelectedURLCard()).toBeNull();
    });

    it("returns the selected card when selectedURLCardID is set in store", () => {
      setState({ selectedURLCardID: 42 });
      const result = getSelectedURLCard();
      expect(result).not.toBeNull();
      expect(result!.hasClass("urlRow")).toBe(true);
    });
  });

  describe("selectURLCard", () => {
    it("sets urlSelected to true on the card", () => {
      selectURLCard(urlCard);
      expect(urlCard.attr("urlSelected")).toBe("true");
    });

    it("adds visible-flex to .goToUrlIcon", () => {
      selectURLCard(urlCard);
      expect(urlCard.find(".goToUrlIcon").hasClass("visible-flex")).toBe(true);
    });

    it("calls enableTabbingOnURLCardElements", () => {
      selectURLCard(urlCard);
      expect(enableTabbingOnURLCardElements).toHaveBeenCalledWith(urlCard);
    });
  });

  describe("deselectAllURLs", () => {
    it("is a no-op when no URL card is selected", () => {
      deselectAllURLs();
      expect(urlCard.attr("urlSelected")).toBe("false");
    });

    it("sets urlSelected to false when a card is selected", () => {
      selectURLCard(urlCard);
      deselectAllURLs();
      expect(urlCard.attr("urlSelected")).toBe("false");
    });

    it("removes visible-flex from .goToUrlIcon when deselecting", () => {
      selectURLCard(urlCard);
      deselectAllURLs();
      expect(urlCard.find(".goToUrlIcon").hasClass("visible-flex")).toBe(false);
    });
  });

  describe("enableClickOnSelectedURLCardToHide", () => {
    it("clicking a non-ignored child element deselects the URL card", () => {
      selectURLCard(urlCard);
      urlCard.find(".urlString").trigger("click");
      expect(urlCard.attr("urlSelected")).toBe("false");
    });

    it("clicking an ignored element does NOT deselect the URL card", () => {
      selectURLCard(urlCard);
      urlCard.find(".urlBtnDelete").trigger("click");
      expect(urlCard.attr("urlSelected")).toBe("true");
    });

    it("clicking the urlTitleBtnUpdate pencil does NOT deselect the URL card", () => {
      document.body.innerHTML = `<div class="urlRow" utuburlid="42" urlSelected="false" filterable="true"><button class="urlTitleBtnUpdate"></button><span class="goToUrlIcon"></span></div>`;
      urlCard = $(".urlRow");
      selectURLCard(urlCard);
      urlCard.find(".urlTitleBtnUpdate").trigger("click");
      expect(urlCard.attr("urlSelected")).toBe("true");
    });

    it("clicking the urlTitleAndUpdateIconWrap (row-level edit affordance) does NOT deselect the URL card", () => {
      document.body.innerHTML = `<div class="urlRow" utuburlid="42" urlSelected="false" filterable="true"><div class="urlTitleAndUpdateIconWrap"><h6 class="urlTitle">My Title</h6></div><span class="goToUrlIcon"></span></div>`;
      urlCard = $(".urlRow");
      selectURLCard(urlCard);
      urlCard.find(".urlTitle").trigger("click");
      expect(urlCard.attr("urlSelected")).toBe("true");
    });
  });

  describe("tag combobox elements never deselect the URL card", () => {
    // Regression: the combobox lives inside the selected URL card, so interacting
    // with its input, staged chips, listbox, or submit/cancel buttons must not
    // bubble up to the card-level deselect handler. The coarse-pointer
    // tap-to-reveal-delete branch keys off `.tagBadge` only — staged chips and
    // options use distinct classes and bypass it entirely.
    beforeEach(() => {
      document.body.innerHTML = COMBOBOX_CARD_HTML;
      urlCard = $(".urlRow");
    });

    const COMBOBOX_CHILD_SELECTORS = [
      ".urlTagComboboxInput",
      ".urlTagStagedChip",
      ".urlTagListbox",
      ".urlTagComboboxSubmitBtn",
      ".urlTagComboboxCancelBtn",
    ];

    COMBOBOX_CHILD_SELECTORS.forEach((selector) => {
      it(`clicking ${selector} does NOT deselect the URL card`, () => {
        selectURLCard(urlCard);
        const target = urlCard.find(selector);
        expect(target.length).toBe(1);

        target.trigger("click");

        expect(urlCard.attr("urlSelected")).toBe("true");
      });
    });
  });

  describe("disableClickOnSelectedURLCardToHide", () => {
    it("clicking after disable does NOT deselect the URL card", () => {
      selectURLCard(urlCard);
      disableClickOnSelectedURLCardToHide(urlCard);
      urlCard.find(".urlString").trigger("click");
      expect(urlCard.attr("urlSelected")).toBe("true");
    });
  });

  describe("auto-deselect when selected card is hidden by search", () => {
    it("deselects when search sets searchable=false on the selected card", () => {
      selectURLCard(urlCard);
      expect(urlCard.attr("urlSelected")).toBe("true");

      urlCard.attr("searchable", "false");
      emit(AppEvents.URL_SEARCH_VISIBILITY_CHANGED);

      expect(urlCard.attr("urlSelected")).toBe("false");
      expect(getSelectedURLCard()).toBeNull();
    });

    it("does not deselect when search sets searchable=false on a non-selected card", () => {
      document.body.innerHTML = MULTI_CARD_HTML;
      const card10 = $(".urlRow[utuburlid=10]");
      const card20 = $(".urlRow[utuburlid=20]");

      selectURLCard(card10);
      card20.attr("searchable", "false");
      emit(AppEvents.URL_SEARCH_VISIBILITY_CHANGED);

      expect(card10.attr("urlSelected")).toBe("true");
      expect(getSelectedURLCard()).not.toBeNull();
    });

    it("does not deselect when selected card has searchable=true", () => {
      selectURLCard(urlCard);
      urlCard.attr("searchable", "true");
      emit(AppEvents.URL_SEARCH_VISIBILITY_CHANGED);

      expect(urlCard.attr("urlSelected")).toBe("true");
    });

    it("does not deselect when no card is selected", () => {
      urlCard.attr("searchable", "false");
      emit(AppEvents.URL_SEARCH_VISIBILITY_CHANGED);

      expect(getSelectedURLCard()).toBeNull();
    });

    it("does not deselect when searchable attribute is absent (search cleared)", () => {
      selectURLCard(urlCard);
      urlCard.removeAttr("searchable");
      emit(AppEvents.URL_SEARCH_VISIBILITY_CHANGED);

      expect(urlCard.attr("urlSelected")).toBe("true");
    });
  });

  describe("auto-deselect when selected card is hidden by tag filter", () => {
    it("deselects when tag filter sets filterable=false on the selected card", () => {
      selectURLCard(urlCard);
      expect(urlCard.attr("urlSelected")).toBe("true");

      urlCard.attr("filterable", "false");
      emit(AppEvents.URL_TAG_FILTER_APPLIED);

      expect(urlCard.attr("urlSelected")).toBe("false");
      expect(getSelectedURLCard()).toBeNull();
    });

    it("does not deselect when tag filter sets filterable=false on a non-selected card", () => {
      document.body.innerHTML = MULTI_CARD_HTML;
      const card10 = $(".urlRow[utuburlid=10]");
      const card20 = $(".urlRow[utuburlid=20]");

      selectURLCard(card10);
      card20.attr("filterable", "false");
      emit(AppEvents.URL_TAG_FILTER_APPLIED);

      expect(card10.attr("urlSelected")).toBe("true");
      expect(getSelectedURLCard()).not.toBeNull();
    });

    it("does not deselect when selected card has filterable=true", () => {
      selectURLCard(urlCard);
      urlCard.attr("filterable", "true");
      emit(AppEvents.URL_TAG_FILTER_APPLIED);

      expect(urlCard.attr("urlSelected")).toBe("true");
    });
  });

  describe("auto-deselect with combined search and tag filter", () => {
    it("deselects when both searchable=false and filterable=false", () => {
      selectURLCard(urlCard);
      urlCard.attr("searchable", "false");
      urlCard.attr("filterable", "false");
      emit(AppEvents.URL_SEARCH_VISIBILITY_CHANGED);

      expect(urlCard.attr("urlSelected")).toBe("false");
      expect(getSelectedURLCard()).toBeNull();
    });

    it("deselects when filterable=true but searchable=false", () => {
      selectURLCard(urlCard);
      urlCard.attr("filterable", "true");
      urlCard.attr("searchable", "false");
      emit(AppEvents.URL_SEARCH_VISIBILITY_CHANGED);

      expect(urlCard.attr("urlSelected")).toBe("false");
    });

    it("deselects when searchable=true but filterable=false", () => {
      selectURLCard(urlCard);
      urlCard.attr("searchable", "true");
      urlCard.attr("filterable", "false");
      emit(AppEvents.URL_TAG_FILTER_APPLIED);

      expect(urlCard.attr("urlSelected")).toBe("false");
    });
  });

  describe("mobile tap-to-reveal tag delete (coarse pointer)", () => {
    beforeEach(() => {
      vi.mocked(isCoarsePointer).mockReturnValue(true);
      document.body.innerHTML = TAGGED_CARD_HTML;
      urlCard = $(".urlRow");
    });

    it("tapping a tag reveals its delete × and does NOT deselect the card", () => {
      selectURLCard(urlCard);
      const firstTag = urlCard.find('.tagBadge[data-tag="1"]');

      firstTag.trigger("click");

      expect(firstTag.hasClass(TAG_DELETE_REVEAL_CLASS)).toBe(true);
      expect(urlCard.attr("urlSelected")).toBe("true");
    });

    it("tapping an already-revealed tag toggles the reveal off", () => {
      selectURLCard(urlCard);
      const firstTag = urlCard.find('.tagBadge[data-tag="1"]');

      firstTag.trigger("click");
      expect(firstTag.hasClass(TAG_DELETE_REVEAL_CLASS)).toBe(true);

      firstTag.trigger("click");

      expect(firstTag.hasClass(TAG_DELETE_REVEAL_CLASS)).toBe(false);
      expect(urlCard.attr("urlSelected")).toBe("true");
    });

    it("tapping a different tag moves the reveal to that one tag only", () => {
      selectURLCard(urlCard);
      const firstTag = urlCard.find('.tagBadge[data-tag="1"]');
      const secondTag = urlCard.find('.tagBadge[data-tag="2"]');

      firstTag.trigger("click");
      secondTag.trigger("click");

      expect(firstTag.hasClass(TAG_DELETE_REVEAL_CLASS)).toBe(false);
      expect(secondTag.hasClass(TAG_DELETE_REVEAL_CLASS)).toBe(true);
    });

    it("tapping a non-tag element still deselects the card", () => {
      selectURLCard(urlCard);

      urlCard.find(".urlString").trigger("click");

      expect(urlCard.attr("urlSelected")).toBe("false");
    });

    it("deselectAllURLs strips the reveal class from any revealed tag", () => {
      selectURLCard(urlCard);
      const firstTag = urlCard.find('.tagBadge[data-tag="1"]');
      firstTag.trigger("click");
      expect(firstTag.hasClass(TAG_DELETE_REVEAL_CLASS)).toBe(true);

      deselectAllURLs();

      expect(firstTag.hasClass(TAG_DELETE_REVEAL_CLASS)).toBe(false);
    });

    it("does NOT reveal on a fine pointer (desktop) — tag tap deselects", () => {
      vi.mocked(isCoarsePointer).mockReturnValue(false);
      selectURLCard(urlCard);
      const firstTag = urlCard.find('.tagBadge[data-tag="1"]');

      firstTag.trigger("click");

      expect(firstTag.hasClass(TAG_DELETE_REVEAL_CLASS)).toBe(false);
      expect(urlCard.attr("urlSelected")).toBe("false");
    });
  });
});
