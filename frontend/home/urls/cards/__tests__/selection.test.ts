import {
  getSelectedURLCard,
  selectURLCard,
  deselectAllURLs,
  disableClickOnSelectedURLCardToHide,
} from "../selection.js";
import { enableTabbingOnURLCardElements } from "../utils.js";
import { resetStore, setState } from "../../../../store/app-store.js";

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
  <div class="urlRow" utuburlid="42" urlSelected="false">
    <span class="goToUrlIcon"></span>
    <a class="urlString" href="https://example.com"></a>
    <button class="urlBtnDelete">Delete</button>
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
});
