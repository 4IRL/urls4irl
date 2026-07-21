import {
  openURLEditPanel,
  resetURLEditPanelState,
  closeURLEditPanel,
} from "../update-url-panel.js";
import { enableClickOnSelectedURLCardToHide } from "../selection.js";

// This suite runs the real URL-panel orchestrator together with the real
// update-title/update-string show/hide functions and the real cards/utils
// sibling helpers, mocking only leaf dependencies. It pins the behavior the
// panel inherits for free (go-to-URL icon, sibling-collapse, button morph) so a
// later refactor of the underlying calls cannot silently break it.

const { mockMetricsClient } = await vi.hoisted(
  async () =>
    await import("../../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../../../../lib/globals.js", async () => {
  const jquery = (await import("jquery")).default;
  const tooltipInstance = {
    setContent: vi.fn(),
    show: vi.fn(),
    hide: vi.fn(),
    enable: vi.fn(),
    disable: vi.fn(),
  };
  return {
    $: jquery,
    jQuery: jquery,
    bootstrap: {
      Tooltip: {
        getInstance: vi.fn(() => tooltipInstance),
        getOrCreateInstance: vi.fn(() => tooltipInstance),
      },
    },
    getInputValue: (input: string | JQuery) => {
      const element = typeof input === "string" ? jquery(input) : input;
      return element.val() as string;
    },
  };
});

vi.mock("../../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));

vi.mock("../loading.js", () => ({
  setTimeoutAndShowURLCardLoadingIcon: vi.fn(() => 1),
  clearTimeoutIDAndHideLoadingIcon: vi.fn(),
}));

vi.mock("../get.js", () => ({
  getUpdatedURL: vi.fn(() => Promise.resolve()),
  handleRejectFromGetURL: vi.fn(),
}));

vi.mock("../selection.js", () => ({
  disableClickOnSelectedURLCardToHide: vi.fn(),
  enableClickOnSelectedURLCardToHide: vi.fn(),
}));

vi.mock("../options/edit-string-btn.js", () => ({
  createEditURLIcon: vi.fn(() => window.jQuery("<i></i>")),
  bindURLStringEditClickHandler: vi.fn(),
}));

vi.mock("../../tags/tags.js", () => ({
  disableTagRemovalInURLCard: vi.fn(),
  enableTagRemovalInURLCard: vi.fn(),
}));

vi.mock("../../../mobile.js", () => ({
  isMobile: vi.fn(() => false),
  isCoarsePointer: vi.fn(() => true),
}));

vi.mock("../../../btns-forms.js", () => ({
  highlightInput: vi.fn(),
}));

vi.mock("../conflict-handler.js", () => ({
  checkForStaleDataOn409: vi.fn(),
}));

vi.mock("../access.js", () => ({
  accessLink: vi.fn(),
}));

vi.mock("../copy.js", () => ({
  copyURLString: vi.fn(),
}));

vi.mock("../../../../store/app-store.js", () => ({
  getState: vi.fn(() => ({ urls: [] })),
  setState: vi.fn(),
}));

const $ = window.jQuery;

const FULL_CARD_HTML = `
  <div class="urlRow" utuburlid="1" urlSelected="true" filterable="true">
    <div class="urlTitleAndUpdateIconWrap">
      <span class="urlTitle">My Title</span>
      <button class="urlTitleBtnUpdate"></button>
    </div>
    <div class="updateUrlTitleWrap hidden"><input class="urlTitleUpdate" value="My Title" /></div>
    <a class="urlString" href="https://example.com">https://example.com</a>
    <div class="updateUrlStringWrap hidden"><input class="urlStringUpdate" type="text" value="https://example.com" /></div>
    <button class="urlStringBtnUpdate fourty-p-width"></button>
    <button class="urlBtnAccess visible-flex"></button>
    <button class="urlTagBtnCreate visible-flex"></button>
    <button class="urlBtnDelete visible-flex"></button>
    <button class="urlBtnCopy visible-flex"></button>
    <span class="goToUrlIcon visible-flex"></span>
    <div class="tagBadge"></div>
  </div>
`;

function mountCard(selected: boolean = true): JQuery {
  document.body.innerHTML = FULL_CARD_HTML;
  const urlCard = $(".urlRow");
  urlCard.attr("urlSelected", selected ? "true" : "false");
  return urlCard;
}

describe("URL edit panel orchestrator", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    $(document).off();
    $(window).off();
    document.body.innerHTML = "";
  });

  describe("openURLEditPanel / closeURLEditPanel focus + open state", () => {
    it("returns focus to .urlStringBtnUpdate after closeURLEditPanel", () => {
      const urlCard = mountCard(true);
      const btnEl = urlCard.find(".urlStringBtnUpdate")[0];
      const focusSpy = vi.spyOn(btnEl, "focus");

      openURLEditPanel(urlCard);
      closeURLEditPanel(urlCard);

      expect(focusSpy).toHaveBeenCalled();
      focusSpy.mockRestore();
    });
  });

  describe("resetURLEditPanelState (low-level teardown)", () => {
    it("is idempotent — safe to call when the panel was never opened", () => {
      const urlCard = mountCard(true);

      expect(() => resetURLEditPanelState(urlCard)).not.toThrow();

      expect(urlCard.find(".updateUrlTitleWrap").hasClass("hidden")).toBe(true);
      expect(urlCard.find(".updateUrlStringWrap").hasClass("hidden")).toBe(
        true,
      );
    });

    it("does NOT return focus to .urlStringBtnUpdate (routine teardown)", () => {
      const urlCard = mountCard(true);
      const btnEl = urlCard.find(".urlStringBtnUpdate")[0];
      const focusSpy = vi.spyOn(btnEl, "focus");

      openURLEditPanel(urlCard);
      resetURLEditPanelState(urlCard);

      expect(focusSpy).not.toHaveBeenCalled();
      focusSpy.mockRestore();
    });
  });

  describe("panel-level Escape coordination", () => {
    it("closes BOTH the title and string forms on a document Escape keydown", () => {
      const urlCard = mountCard(true);
      openURLEditPanel(urlCard);
      expect(urlCard.find(".updateUrlTitleWrap").hasClass("hidden")).toBe(
        false,
      );
      expect(urlCard.find(".updateUrlStringWrap").hasClass("hidden")).toBe(
        false,
      );

      $(document).trigger($.Event("keydown", { key: "Escape" }));

      // Both fields close together (guards the panel-level document Escape bind).
      expect(urlCard.find(".updateUrlTitleWrap").hasClass("hidden")).toBe(true);
      expect(urlCard.find(".updateUrlStringWrap").hasClass("hidden")).toBe(
        true,
      );
    });

    it("closes the panel exactly once — a second Escape is a no-op (guards the handler unbind)", () => {
      const urlCard = mountCard(true);
      const btnEl = urlCard.find(".urlStringBtnUpdate")[0];
      const focusSpy = vi.spyOn(btnEl, "focus");
      openURLEditPanel(urlCard);

      // The first Escape closes the panel and unbinds keydown.urlEditPanelEscape;
      // the second must find no handler bound rather than double-closing — so
      // focus is returned to the edit button exactly once.
      $(document).trigger($.Event("keydown", { key: "Escape" }));
      $(document).trigger($.Event("keydown", { key: "Escape" }));

      expect(focusSpy).toHaveBeenCalledTimes(1);
      focusSpy.mockRestore();
    });

    it("ignores non-Escape keydowns while the panel is open", () => {
      const urlCard = mountCard(true);
      openURLEditPanel(urlCard);

      $(document).trigger($.Event("keydown", { key: "a" }));

      expect(urlCard.find(".updateUrlTitleWrap").hasClass("hidden")).toBe(
        false,
      );
      expect(urlCard.find(".updateUrlStringWrap").hasClass("hidden")).toBe(
        false,
      );
    });
  });

  describe("inherited .goToUrlIcon behavior", () => {
    it("hides the go-to-URL icon while the panel is open", () => {
      const urlCard = mountCard(true);

      openURLEditPanel(urlCard);

      expect(urlCard.find(".goToUrlIcon").hasClass("hidden")).toBe(true);
      expect(urlCard.find(".goToUrlIcon").hasClass("visible-flex")).toBe(false);
    });

    it("restores the go-to-URL icon on close when the card is still selected", () => {
      const urlCard = mountCard(true);

      openURLEditPanel(urlCard);
      closeURLEditPanel(urlCard);

      expect(urlCard.find(".goToUrlIcon").hasClass("visible-flex")).toBe(true);
      expect(urlCard.find(".goToUrlIcon").hasClass("hidden")).toBe(false);
    });
  });

  describe("inherited sibling-collapse behavior", () => {
    const SIBLING_SELECTORS = [
      ".urlBtnAccess",
      ".urlTagBtnCreate",
      ".urlBtnDelete",
      ".urlBtnCopy",
    ];

    it("hides Access/Tag/Copy/Delete and morphs the edit button to a full-width Cancel while open", () => {
      const urlCard = mountCard(true);

      openURLEditPanel(urlCard);

      SIBLING_SELECTORS.forEach((selector) => {
        expect(urlCard.find(selector).hasClass("hidden")).toBe(true);
        expect(urlCard.find(selector).hasClass("visible-flex")).toBe(false);
      });
      expect(urlCard.find(".urlStringCancelBigBtnUpdate").text()).toBe(
        "Cancel",
      );
      expect(urlCard.find(".urlStringBtnUpdate").length).toBe(0);
    });

    it("restores the four sibling buttons and reverts the edit button on resetURLEditPanelState", () => {
      const urlCard = mountCard(true);

      openURLEditPanel(urlCard);
      resetURLEditPanelState(urlCard);

      SIBLING_SELECTORS.forEach((selector) => {
        expect(urlCard.find(selector).hasClass("visible-flex")).toBe(true);
        expect(urlCard.find(selector).hasClass("hidden")).toBe(false);
      });
      expect(urlCard.find(".urlStringBtnUpdate").length).toBe(1);
      expect(urlCard.find(".urlStringCancelBigBtnUpdate").length).toBe(0);
    });

    it("restores the same state when closed via the closeURLEditPanel wrapper", () => {
      const urlCard = mountCard(true);

      openURLEditPanel(urlCard);
      closeURLEditPanel(urlCard);

      SIBLING_SELECTORS.forEach((selector) => {
        expect(urlCard.find(selector).hasClass("visible-flex")).toBe(true);
      });
      expect(urlCard.find(".urlStringBtnUpdate").length).toBe(1);
    });
  });

  describe("tap-to-deselect re-arm on user-initiated close (Cancel/Escape)", () => {
    it("re-arms enableClickOnSelectedURLCardToHide via closeURLEditPanel when the card stays selected", () => {
      // resetURLEditPanelState tears down both fields with
      // suppressSiblingDisable: true, which (post round-2) skips re-arming the
      // click.deselectURL handler. closeURLEditPanel must re-arm it explicitly
      // since the card remains selected after a Cancel/Escape close.
      const urlCard = mountCard(true);

      openURLEditPanel(urlCard);
      vi.mocked(enableClickOnSelectedURLCardToHide).mockClear();
      closeURLEditPanel(urlCard);

      expect(enableClickOnSelectedURLCardToHide).toHaveBeenCalledTimes(1);
      expect(enableClickOnSelectedURLCardToHide).toHaveBeenCalledWith(urlCard);
    });

    it("does NOT re-arm on resetURLEditPanelState for an unselected card (deselectURL routine teardown)", () => {
      // deselectURL() sets urlSelected="false" before calling
      // resetURLEditPanelState; that low-level teardown must never re-arm the
      // deselect handler on an already-deselected card.
      const urlCard = mountCard(false);

      openURLEditPanel(urlCard);
      vi.mocked(enableClickOnSelectedURLCardToHide).mockClear();
      resetURLEditPanelState(urlCard);

      expect(enableClickOnSelectedURLCardToHide).not.toHaveBeenCalled();
    });
  });

  describe("negative case — unselected card (CSS gate keys on urlSelected)", () => {
    it("does NOT restore the go-to-URL icon to visible on a card that is not selected", () => {
      // jsdom computes no CSS; the CSS reveal rule keys on urlSelected="true",
      // and the JS restore path mirrors that gate. Verify via class/attr state.
      const urlCard = mountCard(false);
      urlCard
        .find(".goToUrlIcon")
        .removeClass("visible-flex")
        .addClass("hidden");

      resetURLEditPanelState(urlCard);

      expect(urlCard.attr("urlSelected")).toBe("false");
      expect(urlCard.find(".goToUrlIcon").hasClass("visible-flex")).toBe(false);
    });
  });
});
