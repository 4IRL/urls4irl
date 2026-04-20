import {
  getSelectedURLCard,
  selectURLCard,
  deselectAllURLs,
  disableClickOnSelectedURLCardToHide,
} from "../selection.js";
import { enableTabbingOnURLCardElements } from "../utils.js";
import { resetStore, setState } from "../../../../store/app-store.js";
import { AppEvents, emit } from "../../../../lib/event-bus.js";

vi.mock("../update-title.js", () => ({
  hideAndResetUpdateURLTitleForm: vi.fn(),
}));
vi.mock("../update-string.js", () => ({
  hideAndResetUpdateURLStringForm: vi.fn(),
}));
vi.mock("../../tags/create.js", () => ({
  hideAndResetCreateURLTagForm: vi.fn(),
}));
vi.mock("../cards.js", () => ({
  setFocusEventListenersOnURLCard: vi.fn(),
}));
vi.mock("../utils.js", () => ({
  enableTabbingOnURLCardElements: vi.fn(),
  disableTabbingOnURLCardElements: vi.fn(),
}));

const $ = window.jQuery;

const URL_CARD_HTML = `
  <div class="urlRow" utuburlid="42" urlSelected="false" filterable="true">
    <span class="goToUrlIcon"></span>
    <a class="urlString" href="https://example.com"></a>
    <button class="urlBtnDelete">Delete</button>
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
});
