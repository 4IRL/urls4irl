import {
  setupUTubEditPanelToggle,
  openUTubEditPanel,
  resetUTubEditPanelState,
  closeUTubEditPanel,
} from "../update-utub-panel.js";
import { getState } from "../../../store/app-store.js";
import { deselectAllURLs } from "../cards/selection.js";
import { isCoarsePointer } from "../../mobile.js";

// This suite exercises the real UTub-panel orchestrator together with the real
// update-name/update-description show/hide functions and the real search module
// (search.js is intentionally NOT mocked) so the assertions can pin resulting
// DOM state — including the idempotent double-hide of the search icon that fires
// when both Show functions call temporarilyHideSearchForEdit() back-to-back.

vi.mock("../../../lib/globals.js", async () => {
  const jquery = (await import("jquery")).default;
  return {
    $: jquery,
    jQuery: jquery,
    getInputValue: (input: string | JQuery) => {
      const element = typeof input === "string" ? jquery(input) : input;
      return element.val() as string;
    },
  };
});

vi.mock("../../../lib/config.js", () => ({
  APP_CONFIG: {
    debugEnabled: true,
    routes: {},
    constants: {},
    strings: {},
  },
}));

vi.mock("../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));

const { mockMetricsClient } = await vi.hoisted(
  async () => await import("../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../../utubs/utils.js", () => ({
  getCurrentUTubName: vi.fn(() => "Test UTub"),
  getAllAccessibleUTubNames: vi.fn(() => []),
  sameNameWarningHideModal: vi.fn(),
}));

vi.mock("../../../store/app-store.js", () => ({
  getState: vi.fn(() => ({ isCurrentUserOwner: true })),
  setState: vi.fn(),
}));

vi.mock("../../btns-forms.js", () => ({
  showInput: vi.fn(),
  hideInput: vi.fn(),
  highlightInput: vi.fn(),
  hideInputs: vi.fn(),
}));

vi.mock("../cards/selection.js", () => ({
  deselectAllURLs: vi.fn(),
}));

vi.mock("../../visibility.js", () => ({
  isHidden: vi.fn(() => false),
}));

vi.mock("../../utubs/create.js", () => ({
  createUTubHideInput: vi.fn(),
}));

vi.mock("../../members/create.js", () => ({
  createMemberHideInput: vi.fn(),
}));

vi.mock("../../mobile.js", () => ({
  isCoarsePointer: vi.fn(() => true),
}));

const $ = window.jQuery;

const UTUB_ID = 1;

// The search icon/wrap start visible (no `hidden` class) so the open-path
// assertions can prove they end up hidden.
const PANEL_HTML = `
  <div class="titleElement">
    <div class="flex-row align-center" id="UTubNameOuterUpdateWrap">
      <div class="flex-row align-center" id="UTubNameUpdateWrap">
        <h2 id="URLDeckHeader">Test UTub</h2>
        <span class="edit-pencil-icon hidden" role="button" tabindex="0"
              aria-label="Edit UTub name"></span>
      </div>
      <div class="createDiv flex-row full-width hidden">
        <div class="text-input-container">
          <div class="text-input-inner-container flex-row align-center">
            <input class="text-input" type="text" id="utubNameUpdate" />
            <button id="utubNameSubmitBtnUpdate"></button>
            <button id="utubNameCancelBtnUpdate"></button>
          </div>
          <span class="text-input-error-message" id="utubNameUpdate-error"></span>
        </div>
      </div>
    </div>
  </div>

  <div id="UTubDescriptionSubheaderOuterWrap" class="titleElement flex-start align-center">
    <div class="flex-row align-center flex-start" id="UTubDescriptionSubheaderWrap">
      <h5 id="URLDeckSubheader">Test Description</h5>
      <span class="edit-pencil-icon hidden" role="button" tabindex="0"
            aria-label="Edit UTub description"></span>
    </div>

    <span id="URLDeckNoDescription" class="hidden">No description</span>

    <div id="SearchURLWrap" class="input-text-holder flex-column">
      <div class="text-input-container">
        <div class="text-input-inner-container">
          <input placeholder="Filter URLs" class="text-input search-input" type="text"
                 id="URLContentSearch" name="urlSearch" />
        </div>
      </div>
    </div>

    <button id="URLDeckSubheaderCreateDescription" class="opa-0 height-0"></button>
    <div class="createDiv flex-row full-width hidden" id="UTubDescriptionUpdateWrap">
      <div class="text-input-container" id="UTubDescriptionInnerUpdateWrap">
        <div class="text-input-inner-container flex-row align-center">
          <input class="text-input" type="text" id="utubDescriptionUpdate" />
          <button id="utubDescriptionSubmitBtnUpdate"></button>
          <button id="utubDescriptionCancelBtnUpdate"></button>
        </div>
        <span class="text-input-error-message" id="utubDescriptionUpdate-error"></span>
      </div>
    </div>
  </div>

  <button id="URLSearchFilterIcon"></button>
  <button id="URLSearchFilterIconClose" class="hidden"></button>
  <button id="utubEditPanelToggle" class="hidden" type="button"
          aria-label="Edit UTub name and description"></button>
  <button id="utubEditPanelClose" class="hidden" type="button"
          aria-label="Close edit panel"></button>
  <button id="urlBtnCreate" class="hidden"></button>
`;

describe("UTub edit panel orchestrator", () => {
  beforeEach(() => {
    document.body.innerHTML = PANEL_HTML;
    vi.clearAllMocks();
    vi.mocked(getState).mockReturnValue({
      isCurrentUserOwner: true,
    } as ReturnType<typeof getState>);
    vi.mocked(isCoarsePointer).mockReturnValue(true);
  });

  afterEach(() => {
    $(window).off();
    $(document).off();
    document.body.innerHTML = "";
  });

  describe("setupUTubEditPanelToggle", () => {
    it("binds the toggle so clicking it opens the panel on a coarse pointer", () => {
      setupUTubEditPanelToggle(UTUB_ID);

      $("#utubEditPanelToggle").trigger("click");

      expect($("#URLDeckHeader").hasClass("hidden")).toBe(true);
      expect($("#URLDeckSubheader").hasClass("hidden")).toBe(true);
    });

    it("does NOT bind on a fine pointer (desktop)", () => {
      vi.mocked(isCoarsePointer).mockReturnValue(false);

      setupUTubEditPanelToggle(UTUB_ID);
      $("#utubEditPanelToggle").trigger("click");

      expect($("#URLDeckHeader").hasClass("hidden")).toBe(false);
      expect($("#URLDeckSubheader").hasClass("hidden")).toBe(false);
    });

    it("binds the close button so clicking it closes an open panel", () => {
      setupUTubEditPanelToggle(UTUB_ID);
      openUTubEditPanel(UTUB_ID);

      $("#utubEditPanelClose").trigger("click");

      expect($("#URLDeckHeader").hasClass("hidden")).toBe(false);
      expect($("#URLDeckSubheader").hasClass("hidden")).toBe(false);
    });
  });

  describe("openUTubEditPanel", () => {
    it("opens BOTH the name and description forms together", () => {
      openUTubEditPanel(UTUB_ID);

      expect($("#URLDeckHeader").hasClass("hidden")).toBe(true);
      expect($("#URLDeckSubheader").hasClass("hidden")).toBe(true);
    });

    it("calls deselectAllURLs exactly once", () => {
      openUTubEditPanel(UTUB_ID);

      expect(deselectAllURLs).toHaveBeenCalledTimes(1);
    });

    it("leaves the search icon and wrap hidden (idempotent double-hide, DOM state only)", () => {
      // Both Show functions call temporarilyHideSearchForEdit() back-to-back;
      // the underlying hideURLSearchIcon() is idempotent by design, so we assert
      // the resulting DOM state rather than a specific call count.
      openUTubEditPanel(UTUB_ID);

      expect($("#SearchURLWrap").hasClass("hidden")).toBe(true);
      expect($("#URLSearchFilterIcon").hasClass("hidden")).toBe(true);
    });

    it("swaps the toggle button for the close button", () => {
      openUTubEditPanel(UTUB_ID);

      expect($("#utubEditPanelToggle").hasClass("hidden")).toBe(true);
      expect($("#utubEditPanelClose").hasClass("hidden")).toBe(false);
    });
  });

  describe("resetUTubEditPanelState (low-level teardown)", () => {
    it("hides both forms and restores the toggle/close visibility", () => {
      openUTubEditPanel(UTUB_ID);

      resetUTubEditPanelState();

      expect($("#URLDeckHeader").hasClass("hidden")).toBe(false);
      expect($("#URLDeckSubheader").hasClass("hidden")).toBe(false);
      expect($("#utubEditPanelClose").hasClass("hidden")).toBe(true);
      expect($("#utubEditPanelToggle").hasClass("hidden")).toBe(false);
    });

    it("is idempotent — a second call is a safe no-op", () => {
      openUTubEditPanel(UTUB_ID);

      resetUTubEditPanelState();
      expect(() => resetUTubEditPanelState()).not.toThrow();

      expect($("#URLDeckHeader").hasClass("hidden")).toBe(false);
      expect($("#URLDeckSubheader").hasClass("hidden")).toBe(false);
      expect($("#utubEditPanelClose").hasClass("hidden")).toBe(true);
      expect($("#utubEditPanelToggle").hasClass("hidden")).toBe(false);
    });

    it("does NOT return focus to the toggle button", () => {
      const focusSpy = vi.spyOn($("#utubEditPanelToggle")[0], "focus");
      openUTubEditPanel(UTUB_ID);

      resetUTubEditPanelState();

      expect(focusSpy).not.toHaveBeenCalled();
      focusSpy.mockRestore();
    });
  });

  describe("closeUTubEditPanel (wrapper)", () => {
    it("closes BOTH forms (symmetric with the open path)", () => {
      openUTubEditPanel(UTUB_ID);
      expect($("#URLDeckHeader").hasClass("hidden")).toBe(true);
      expect($("#URLDeckSubheader").hasClass("hidden")).toBe(true);

      closeUTubEditPanel();

      expect($("#URLDeckHeader").hasClass("hidden")).toBe(false);
      expect($("#URLDeckSubheader").hasClass("hidden")).toBe(false);
    });

    it("swaps the close button back to the toggle button", () => {
      openUTubEditPanel(UTUB_ID);

      closeUTubEditPanel();

      expect($("#utubEditPanelClose").hasClass("hidden")).toBe(true);
      expect($("#utubEditPanelToggle").hasClass("hidden")).toBe(false);
    });

    it("returns focus to #utubEditPanelToggle", () => {
      const focusSpy = vi.spyOn($("#utubEditPanelToggle")[0], "focus");
      openUTubEditPanel(UTUB_ID);

      closeUTubEditPanel();

      expect(focusSpy).toHaveBeenCalled();
      focusSpy.mockRestore();
    });
  });
});
