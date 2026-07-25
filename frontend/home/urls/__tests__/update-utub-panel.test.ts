import {
  setupUTubEditPanelToggle,
  openUTubEditPanel,
  resetUTubEditPanelState,
  closeUTubEditPanel,
} from "../update-utub-panel.js";
import {
  updateUTubNameHideInput,
  updateUTubNameShowInput,
  setupUpdateUTubNameEventListeners,
} from "../update-name.js";
import {
  updateUTubDescriptionHideInput,
  updateUTubDescriptionShowInput,
  setupUpdateUTubDescriptionEventListeners,
} from "../update-description.js";
import { getState } from "../../../store/app-store.js";
import { ajaxCall } from "../../../lib/ajax.js";
import { AppEvents, emit } from "../../../lib/event-bus.js";
import { getOpenForm } from "../../../lib/modal-tracking.js";
import { HOME_FORM } from "../../../types/metrics-dim-values.js";
import { deselectAllURLs } from "../cards/selection.js";
import { isCoarsePointer } from "../../mobile.js";
import { createMockJqXHR } from "../../../__tests__/helpers/mock-jquery.js";

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
    routes: {
      updateUTubName: vi.fn(() => "/utubs/1/name"),
      updateUTubDescription: vi.fn(() => "/utubs/1/description"),
    },
    constants: {},
    strings: {
      FIELD_SAVED: "Saved",
      FIELD_SAVED_LABEL_UTUB_NAME: "UTub name",
      FIELD_SAVED_LABEL_UTUB_DESCRIPTION: "UTub description",
    },
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
          <div class="field-saved-tick-slot">
            <span class="field-saved-tick opa-0" id="utubNameSavedTick" aria-hidden="true">Saved <i class="bi bi-check"></i></span>
          </div>
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
        <div class="field-saved-tick-slot">
          <span class="field-saved-tick opa-0" id="utubDescriptionSavedTick" aria-hidden="true">Saved <i class="bi bi-check"></i></span>
        </div>
      </div>
    </div>
  </div>

  <span class="visually-hidden" id="fieldSavedAnnouncement" aria-live="polite"></span>

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

  describe("panel-level Escape coordination", () => {
    it("closes BOTH the name and description forms on a document Escape keydown", () => {
      setupUTubEditPanelToggle(UTUB_ID);
      openUTubEditPanel(UTUB_ID);
      expect($("#URLDeckHeader").hasClass("hidden")).toBe(true);
      expect($("#URLDeckSubheader").hasClass("hidden")).toBe(true);

      $(document).trigger($.Event("keydown", { key: "Escape" }));

      // Both fields close together and the toggle/close visibility is restored.
      expect($("#URLDeckHeader").hasClass("hidden")).toBe(false);
      expect($("#URLDeckSubheader").hasClass("hidden")).toBe(false);
      expect($("#utubEditPanelClose").hasClass("hidden")).toBe(true);
      expect($("#utubEditPanelToggle").hasClass("hidden")).toBe(false);
    });

    it("closes the panel exactly once — a second Escape is a no-op (guards the hidden-close early-return)", () => {
      setupUTubEditPanelToggle(UTUB_ID);
      openUTubEditPanel(UTUB_ID);
      const focusSpy = vi.spyOn($("#utubEditPanelToggle")[0], "focus");

      // Two Escapes in a row: the first closes the panel (hiding
      // #utubEditPanelClose), the second must early-return on the hidden-close
      // guard rather than double-closing — so focus is returned exactly once.
      $(document).trigger($.Event("keydown", { key: "Escape" }));
      $(document).trigger($.Event("keydown", { key: "Escape" }));

      expect(focusSpy).toHaveBeenCalledTimes(1);
      focusSpy.mockRestore();
    });

    it("ignores non-Escape keydowns while the panel is open", () => {
      setupUTubEditPanelToggle(UTUB_ID);
      openUTubEditPanel(UTUB_ID);

      $(document).trigger($.Event("keydown", { key: "a" }));

      expect($("#URLDeckHeader").hasClass("hidden")).toBe(true);
      expect($("#URLDeckSubheader").hasClass("hidden")).toBe(true);
    });
  });

  describe("URL_CARD_SELECTED panel-close wiring", () => {
    // The panel-close handler is registered exactly once at module load against
    // the REAL event bus (not per UTub switch), so these tests emit the real
    // AppEvents.URL_CARD_SELECTED event rather than calling a bound handler
    // directly. The handler reads the active UTub id from app state to thread it
    // into the close path, so each test pins `activeUTubID` first.
    it("closes an open UTub panel when a URL card is selected", () => {
      vi.mocked(getState).mockReturnValue({
        isCurrentUserOwner: true,
        activeUTubID: UTUB_ID,
      } as ReturnType<typeof getState>);

      openUTubEditPanel(UTUB_ID);
      // Precondition: the panel is open (close button visible, forms shown).
      expect($("#utubEditPanelClose").hasClass("hidden")).toBe(false);
      expect($("#URLDeckHeader").hasClass("hidden")).toBe(true);

      emit(AppEvents.URL_CARD_SELECTED, { urlID: 999 });

      // Both forms are restored and the toggle is the visible control again.
      expect($("#URLDeckHeader").hasClass("hidden")).toBe(false);
      expect($("#URLDeckSubheader").hasClass("hidden")).toBe(false);
      expect($("#utubEditPanelClose").hasClass("hidden")).toBe(true);
      expect($("#utubEditPanelToggle").hasClass("hidden")).toBe(false);
    });

    it("is a no-op when the panel is already closed (guards the hidden-close early-return)", () => {
      vi.mocked(getState).mockReturnValue({
        isCurrentUserOwner: true,
        activeUTubID: UTUB_ID,
      } as ReturnType<typeof getState>);

      // Panel never opened: #utubEditPanelClose starts hidden. Selecting a URL
      // card must not trigger a spurious close/teardown/focus-return.
      const focusSpy = vi.spyOn($("#utubEditPanelToggle")[0], "focus");

      emit(AppEvents.URL_CARD_SELECTED, { urlID: 999 });

      expect(focusSpy).not.toHaveBeenCalled();
      expect($("#utubEditPanelClose").hasClass("hidden")).toBe(true);
      focusSpy.mockRestore();
    });
  });

  describe("mobile form model — per-field Hide is keep-open while the panel is open", () => {
    it("name Hide keeps the field open, chrome hidden, close visible, and re-registers the open form", () => {
      openUTubEditPanel(UTUB_ID);
      // Precondition: panel open (close visible), name field open (header hidden).
      expect($("#utubEditPanelClose").hasClass("hidden")).toBe(false);
      expect($("#URLDeckHeader").hasClass("hidden")).toBe(true);

      // Simulate the per-field submit's Hide call while the panel is open.
      updateUTubNameHideInput();

      // Field stays open (header still hidden), chrome stays hidden, close stays
      // visible, and the open form is re-registered for pagehide bookkeeping.
      expect($("#URLDeckHeader").hasClass("hidden")).toBe(true);
      expect($("#urlBtnCreate").hasClass("hidden")).toBe(true);
      expect($("#URLSearchFilterIcon").hasClass("hidden")).toBe(true);
      expect($("#utubEditPanelClose").hasClass("hidden")).toBe(false);
      expect(getOpenForm()).toBe(HOME_FORM.UTUB_NAME_EDIT);
    });

    it("description Hide keeps the field open, chrome hidden, and re-registers the open form", () => {
      openUTubEditPanel(UTUB_ID);
      expect($("#URLDeckSubheader").hasClass("hidden")).toBe(true);

      updateUTubDescriptionHideInput(UTUB_ID);

      expect($("#URLDeckSubheader").hasClass("hidden")).toBe(true);
      expect($("#urlBtnCreate").hasClass("hidden")).toBe(true);
      expect($("#URLSearchFilterIcon").hasClass("hidden")).toBe(true);
      expect($("#utubEditPanelClose").hasClass("hidden")).toBe(false);
      expect(getOpenForm()).toBe(HOME_FORM.UTUB_DESC_EDIT);
    });

    it("fine pointer (desktop): name Hide collapses the field as before", () => {
      openUTubEditPanel(UTUB_ID);
      vi.mocked(isCoarsePointer).mockReturnValue(false);

      updateUTubNameHideInput();

      // Desktop path: field collapses (header restored).
      expect($("#URLDeckHeader").hasClass("hidden")).toBe(false);
    });

    it("panel Close collapses everything and clears the tracked open form", () => {
      openUTubEditPanel(UTUB_ID);
      updateUTubNameHideInput(); // keep-open submit → form re-registered
      expect(getOpenForm()).toBe(HOME_FORM.UTUB_NAME_EDIT);

      closeUTubEditPanel(UTUB_ID);

      expect($("#URLDeckHeader").hasClass("hidden")).toBe(false);
      expect($("#URLDeckSubheader").hasClass("hidden")).toBe(false);
      expect($("#urlBtnCreate").hasClass("hidden")).toBe(false);
      expect($("#utubEditPanelClose").hasClass("hidden")).toBe(true);
      expect(getOpenForm()).toBe(null);
    });

    it("resetUTubEditPanelState force-clears any pending Saved✓ tick", () => {
      openUTubEditPanel(UTUB_ID);
      // Simulate a tick left visible by a recent save.
      $("#utubNameSavedTick").removeClass("opa-0").addClass("opa-1");
      $("#utubDescriptionSavedTick").removeClass("opa-0").addClass("opa-1");

      resetUTubEditPanelState(UTUB_ID);

      expect($("#utubNameSavedTick").hasClass("opa-1")).toBe(false);
      expect($("#utubNameSavedTick").hasClass("opa-0")).toBe(true);
      expect($("#utubDescriptionSavedTick").hasClass("opa-1")).toBe(false);
      expect($("#utubDescriptionSavedTick").hasClass("opa-0")).toBe(true);
    });
  });

  describe("mid-switch regression — teardown clears the guard + id-guards a stale success (DD-1)", () => {
    beforeEach(() => {
      // The name success path calls $("#confirmModal").modal("hide"); Bootstrap's
      // jQuery modal plugin isn't registered in this test env, so stub it.
      $.fn.modal = vi.fn().mockReturnThis();
    });

    it("name: switching UTubs mid-submit clears the in-flight guard and a stale success cannot overwrite the new UTub's header", () => {
      // Panel open on UTub A (id 1), which is the active UTub.
      vi.mocked(getState).mockReturnValue({
        isCurrentUserOwner: true,
        activeUTubID: 1,
        utubs: [],
      } as unknown as ReturnType<typeof getState>);

      setupUpdateUTubNameEventListeners(1);
      openUTubEditPanel(1);
      updateUTubNameShowInput(1);
      $("#utubNameUpdate").val("A Renamed"); // changed → real submit path

      // Fire-and-forget submit against a pending (unresolved) deferred.
      const deferred = createMockJqXHR();
      vi.mocked(ajaxCall).mockReturnValue(deferred);
      const submitBtn = $("#utubNameSubmitBtnUpdate");
      submitBtn.trigger("click.updateUTubname");
      expect(vi.mocked(ajaxCall)).toHaveBeenCalledTimes(1);
      expect(submitBtn.attr("aria-disabled")).toBe("true"); // in flight

      // Simulate a switch to UTub B (id 2): the header now shows B, B is active,
      // and the routine teardown runs. Teardown must clear the stuck guard.
      $("#URLDeckHeader").text("UTub B");
      vi.mocked(getState).mockReturnValue({
        isCurrentUserOwner: true,
        activeUTubID: 2,
        utubs: [],
      } as unknown as ReturnType<typeof getState>);
      resetUTubEditPanelState(2);
      expect(submitBtn.attr("aria-disabled")).toBeUndefined(); // guard cleared

      // A's stale success now lands (utubID 1 ≠ active 2): it must NOT overwrite
      // B's displayed header.
      deferred.resolve({ utubName: "A Renamed", utubID: 1 }, "success", {
        status: 200,
      });
      expect($("#URLDeckHeader").text()).toBe("UTub B");
    });

    it("description: switching UTubs mid-submit clears the in-flight guard and a stale success cannot overwrite the new UTub's subheader", () => {
      vi.mocked(getState).mockReturnValue({
        isCurrentUserOwner: true,
        activeUTubID: 1,
        utubs: [],
      } as unknown as ReturnType<typeof getState>);

      setupUpdateUTubDescriptionEventListeners(1);
      openUTubEditPanel(1);
      updateUTubDescriptionShowInput(1);
      $("#utubDescriptionUpdate").val("A Desc Changed"); // changed → real submit

      const deferred = createMockJqXHR();
      vi.mocked(ajaxCall).mockReturnValue(deferred);
      const submitBtn = $("#utubDescriptionSubmitBtnUpdate");
      submitBtn.trigger("click");
      expect(vi.mocked(ajaxCall)).toHaveBeenCalledTimes(1);
      expect(submitBtn.attr("aria-disabled")).toBe("true");

      // Switch to UTub B (id 2).
      $("#URLDeckSubheader").text("Desc B");
      vi.mocked(getState).mockReturnValue({
        isCurrentUserOwner: true,
        activeUTubID: 2,
        utubs: [],
      } as unknown as ReturnType<typeof getState>);
      resetUTubEditPanelState(2);
      expect(submitBtn.attr("aria-disabled")).toBeUndefined();

      // A's stale success lands (utubID 1 ≠ active 2): B's subheader is untouched.
      deferred.resolve(
        { utubDescription: "A Desc Changed", utubID: 1 },
        "success",
        {
          status: 200,
        },
      );
      expect($("#URLDeckSubheader").text()).toBe("Desc B");
    });
  });
});
