import { bindSwitchURLKeyboardEventListeners } from "../utils.js";
import { getSelectedURLCard, selectURLCard } from "../cards/selection.js";
import { resetStore, setState } from "../../../store/app-store.js";
import { KEYS } from "../../../lib/constants.js";

vi.mock("../cards/update-title.js", () => ({
  hideAndResetUpdateURLTitleForm: vi.fn(),
  clearTitleSubmitInFlight: vi.fn(),
}));
vi.mock("../cards/update-string.js", () => ({
  hideAndResetUpdateURLStringForm: vi.fn(),
  clearStringSubmitInFlight: vi.fn(),
}));
vi.mock("../tags/combobox.js", () => ({
  hideAndResetTagCombobox: vi.fn(),
}));
vi.mock("../cards/cards.js", () => ({
  setFocusEventListenersOnURLCard: vi.fn(),
}));
vi.mock("../cards/utils.js", () => ({
  enableTabbingOnURLCardElements: vi.fn(),
  disableTabbingOnURLCardElements: vi.fn(),
  enableEditingURLTitle: vi.fn(),
  disableEditingURLTitle: vi.fn(),
  isEmptyString: vi.fn(),
  updateColorOfFollowingURLCardsAfterURLCreated: vi.fn(),
}));

const $ = window.jQuery;

const FOUR_CARDS_HTML = `
  <div class="urlRow" utuburlid="1" urlSelected="false" filterable="true">
    <span class="goToUrlIcon"></span>
    <a class="urlString" href="https://alpha.com"></a>
  </div>
  <div class="urlRow" utuburlid="2" urlSelected="false" filterable="true">
    <span class="goToUrlIcon"></span>
    <a class="urlString" href="https://beta.com"></a>
  </div>
  <div class="urlRow" utuburlid="3" urlSelected="false" filterable="true">
    <span class="goToUrlIcon"></span>
    <a class="urlString" href="https://gamma.com"></a>
  </div>
  <div class="urlRow" utuburlid="4" urlSelected="false" filterable="true">
    <span class="goToUrlIcon"></span>
    <a class="urlString" href="https://delta.com"></a>
  </div>
`;

function pressArrowKey(direction: string): void {
  $(document).trigger($.Event("keyup", { key: direction }));
}

function getSelectedCardId(): number | null {
  const card = getSelectedURLCard();
  if (card === null) return null;
  return parseInt(card.attr("utuburlid")!);
}

describe("Keyboard Navigation (arrow keys)", () => {
  beforeEach(() => {
    resetStore();
    document.body.innerHTML = FOUR_CARDS_HTML;
    bindSwitchURLKeyboardEventListeners();
  });

  describe("selection scroll (Cards only, once per keypress)", () => {
    const scrollIntoView = vi.fn();
    const originalMatchMedia = window.matchMedia;
    const originalScrollIntoView = window.HTMLElement.prototype.scrollIntoView;

    function setLayout({ view, wide }: { view: string; wide: boolean }): void {
      document.body.dataset.view = view;
      window.matchMedia = vi.fn().mockImplementation((query: string) => ({
        matches: query === "(min-width: 992px)" ? wide : false,
        media: query,
      })) as unknown as typeof window.matchMedia;
    }

    beforeEach(() => {
      scrollIntoView.mockClear();
      window.HTMLElement.prototype.scrollIntoView = scrollIntoView;
    });

    afterEach(() => {
      delete document.body.dataset.view;
      window.matchMedia = originalMatchMedia;
      window.HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
    });

    it.each([KEYS.ARROW_DOWN, KEYS.ARROW_UP])(
      "%s in Cards at >= 992px scrolls the newly selected card once",
      (direction) => {
        setLayout({ view: "cards", wide: true });
        selectURLCard($(".urlRow[utuburlid=2]"));
        scrollIntoView.mockClear();

        pressArrowKey(direction);

        expect(scrollIntoView).toHaveBeenCalledTimes(1);
        expect(scrollIntoView).toHaveBeenCalledWith(
          expect.objectContaining({ block: "nearest", behavior: "smooth" }),
        );
        expect(scrollIntoView.mock.contexts[0]).toBe(getSelectedURLCard()![0]);
      },
    );

    it("the first keypress with nothing selected also scrolls once", () => {
      setLayout({ view: "cards", wide: true });

      pressArrowKey(KEYS.ARROW_DOWN);

      expect(getSelectedCardId()).toBe(1);
      expect(scrollIntoView).toHaveBeenCalledTimes(1);
    });

    it.each([
      { view: "list", wide: true },
      { view: "title_line", wide: true },
      { view: "cards", wide: false },
    ])("no scroll in view=$view at wide=$wide", ({ view, wide }) => {
      setLayout({ view, wide });
      selectURLCard($(".urlRow[utuburlid=2]"));

      pressArrowKey(KEYS.ARROW_DOWN);

      expect(getSelectedCardId()).toBe(3);
      expect(scrollIntoView).not.toHaveBeenCalled();
    });
  });

  describe("skips cards hidden by search (searchable=false)", () => {
    it("skips hidden card when pressing DOWN", () => {
      selectURLCard($(".urlRow[utuburlid=1]"));
      $(".urlRow[utuburlid=2]").attr("searchable", "false");

      pressArrowKey(KEYS.ARROW_DOWN);

      expect(getSelectedCardId()).toBe(3);
    });

    it("skips multiple consecutive hidden cards", () => {
      selectURLCard($(".urlRow[utuburlid=1]"));
      $(".urlRow[utuburlid=2]").attr("searchable", "false");
      $(".urlRow[utuburlid=3]").attr("searchable", "false");

      pressArrowKey(KEYS.ARROW_DOWN);

      expect(getSelectedCardId()).toBe(4);
    });

    it("wraps around skipping hidden cards at the end", () => {
      selectURLCard($(".urlRow[utuburlid=3]"));
      $(".urlRow[utuburlid=4]").attr("searchable", "false");

      pressArrowKey(KEYS.ARROW_DOWN);

      expect(getSelectedCardId()).toBe(1);
    });
  });

  describe("skips cards hidden by tag filter (filterable=false)", () => {
    it("skips hidden card when pressing DOWN", () => {
      selectURLCard($(".urlRow[utuburlid=1]"));
      $(".urlRow[utuburlid=2]").attr("filterable", "false");

      pressArrowKey(KEYS.ARROW_DOWN);

      expect(getSelectedCardId()).toBe(3);
    });

    it("skips hidden card when pressing UP", () => {
      selectURLCard($(".urlRow[utuburlid=3]"));
      $(".urlRow[utuburlid=2]").attr("filterable", "false");

      pressArrowKey(KEYS.ARROW_UP);

      expect(getSelectedCardId()).toBe(1);
    });

    it("wraps around skipping hidden cards at the start when pressing UP", () => {
      selectURLCard($(".urlRow[utuburlid=2]"));
      $(".urlRow[utuburlid=1]").attr("filterable", "false");

      pressArrowKey(KEYS.ARROW_UP);

      expect(getSelectedCardId()).toBe(4);
    });
  });

  describe("edge cases", () => {
    it("does nothing when all cards are hidden", () => {
      $(".urlRow").attr("filterable", "false");

      pressArrowKey(KEYS.ARROW_DOWN);

      expect(getSelectedURLCard()).toBeNull();
    });

    it("selects first visible card when no card is selected and DOWN is pressed", () => {
      $(".urlRow[utuburlid=1]").attr("searchable", "false");

      pressArrowKey(KEYS.ARROW_DOWN);

      expect(getSelectedCardId()).toBe(2);
    });

    it("selects first visible card when no card is selected and UP is pressed", () => {
      $(".urlRow[utuburlid=1]").attr("searchable", "false");

      pressArrowKey(KEYS.ARROW_UP);

      expect(getSelectedCardId()).toBe(2);
    });

    it("stays on current card when it is the only visible card", () => {
      const card2 = $(".urlRow[utuburlid=2]");
      selectURLCard(card2);
      $(".urlRow[utuburlid=1]").attr("filterable", "false");
      $(".urlRow[utuburlid=3]").attr("filterable", "false");
      $(".urlRow[utuburlid=4]").attr("filterable", "false");

      pressArrowKey(KEYS.ARROW_DOWN);

      expect(getSelectedCardId()).toBe(2);
    });

    it("does nothing when no cards exist at all", () => {
      document.body.innerHTML = "";

      pressArrowKey(KEYS.ARROW_DOWN);

      expect(getSelectedURLCard()).toBeNull();
    });
  });

  describe("no-op in multi-select mode", () => {
    it("leaves the selected card unchanged on Arrow Down/Up while multiSelectMode is active", () => {
      selectURLCard($(".urlRow[utuburlid=2]"));
      expect(getSelectedCardId()).toBe(2);

      setState({ multiSelectMode: true });

      pressArrowKey(KEYS.ARROW_DOWN);
      expect(getSelectedCardId()).toBe(2);

      pressArrowKey(KEYS.ARROW_UP);
      expect(getSelectedCardId()).toBe(2);
    });
  });
});
