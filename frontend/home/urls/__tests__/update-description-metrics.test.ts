import { UI_EVENTS } from "../../../types/metrics-events.js";
import {
  setupUpdateUTubDescriptionEventListeners,
  showCreateDescriptionButtonAlways,
  updateUTubDescriptionHideInput,
  updateUTubDescriptionShowInput,
} from "../update-description.js";
import { getState } from "../../../store/app-store.js";
import { ajaxCall } from "../../../lib/ajax.js";
import { getOpenForm } from "../../../lib/modal-tracking.js";
import { isCoarsePointer } from "../../mobile.js";
import {
  createMockJqXHR,
  createMockJqXHRChainable,
} from "../../../__tests__/helpers/mock-jquery.js";
import {
  FORM_CANCEL_TRIGGER,
  FORM_SUBMIT_TRIGGER,
  HOME_FORM,
  UTUB_DESC_EDIT_OPEN_TRIGGER,
} from "../../../types/metrics-dim-values.js";

const { mockMetricsClient } = await vi.hoisted(
  async () => await import("../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../../utubs/header-fit.js", () => ({
  fitUTubHeaderAndSubheader: vi.fn(),
}));

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
    routes: { updateUTubDescription: vi.fn(() => "/utubs/1/description") },
    constants: {},
    strings: {
      FIELD_SAVED: "Saved",
      FIELD_SAVED_LABEL_UTUB_DESCRIPTION: "UTub description",
    },
  },
}));

vi.mock("../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));

vi.mock("../../mobile.js", () => ({
  isCoarsePointer: vi.fn(() => false),
}));

vi.mock("../../../store/app-store.js", () => ({
  getState: vi.fn(() => ({ isCurrentUserOwner: true })),
  setState: vi.fn(),
}));

vi.mock("../../btns-forms.js", () => ({
  showInput: vi.fn(),
  hideInput: vi.fn(),
}));

vi.mock("../update-name.js", () => ({
  updateUTubNameHideInput: vi.fn(),
}));

vi.mock("../cards/selection.js", () => ({
  deselectAllURLs: vi.fn(),
}));

vi.mock("../search.js", () => ({
  temporarilyHideSearchForEdit: vi.fn(),
  showURLSearchIcon: vi.fn(),
}));

const $ = window.jQuery;

const DESCRIPTION_EDIT_HTML = `
  <div id="UTubDescriptionSubheaderOuterWrap">
    <div id="UTubDescriptionSubheaderWrap">
      <h5 id="URLDeckSubheader">Description</h5>
      <span class="edit-pencil-icon hidden" role="button" tabindex="0"></span>
    </div>
    <button id="URLDeckSubheaderCreateDescription"></button>
    <input id="utubDescriptionUpdate" />
    <button id="utubDescriptionSubmitBtnUpdate"></button>
    <button id="utubDescriptionCancelBtnUpdate"></button>
    <div class="field-saved-tick-slot">
      <span class="field-saved-tick opa-0" id="utubDescriptionSavedTick" aria-hidden="true">Saved <i class="bi bi-check"></i></span>
    </div>
    <span id="URLDeckNoDescription" class="hidden"></span>
  </div>
  <span class="visually-hidden" id="fieldSavedAnnouncement" aria-live="polite"></span>
  <button id="URLSearchFilterIcon"></button>
  <button id="urlBtnCreate"></button>
  <button id="utubEditPanelToggle" class="hidden"></button>
  <button id="utubEditPanelClose" class="hidden"></button>
`;

const UTUB_ID = 1;

describe("update-description metrics — UI_UTUB_DESC_EDIT_OPEN", () => {
  beforeEach(() => {
    document.body.innerHTML = DESCRIPTION_EDIT_HTML;
    vi.clearAllMocks();
    vi.mocked(getState).mockReturnValue({
      isCurrentUserOwner: true,
    } as ReturnType<typeof getState>);
    vi.mocked(isCoarsePointer).mockReturnValue(false);
  });

  afterEach(() => {
    $(window).off();
    document.body.innerHTML = "";
  });

  it("emits ui_utub_desc_edit_open with trigger 'pencil_icon' on wrap click", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    setupUpdateUTubDescriptionEventListeners(UTUB_ID);
    $("#UTubDescriptionSubheaderWrap").trigger("click.updateUTubDesc");

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_UTUB_DESC_EDIT_OPEN,
      trigger: UTUB_DESC_EDIT_OPEN_TRIGGER.PENCIL_ICON,
    });
  });

  it("emits ui_utub_desc_edit_open with trigger 'keyboard' on Enter on pencil", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    setupUpdateUTubDescriptionEventListeners(UTUB_ID);
    const enterEvent = $.Event("keydown.updateUTubDesc", { key: "Enter" });
    $("#UTubDescriptionSubheaderWrap .edit-pencil-icon").trigger(enterEvent);

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_UTUB_DESC_EDIT_OPEN,
      trigger: UTUB_DESC_EDIT_OPEN_TRIGGER.KEYBOARD,
    });
  });

  it("emits ui_utub_desc_edit_open with trigger 'keyboard' on Space on pencil", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    setupUpdateUTubDescriptionEventListeners(UTUB_ID);
    const spaceEvent = $.Event("keydown.updateUTubDesc", { key: " " });
    $("#UTubDescriptionSubheaderWrap .edit-pencil-icon").trigger(spaceEvent);

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_UTUB_DESC_EDIT_OPEN,
      trigger: UTUB_DESC_EDIT_OPEN_TRIGGER.KEYBOARD,
    });
  });

  it("emits ui_utub_desc_edit_open with trigger 'create_button' from showCreateDescriptionButtonAlways", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    showCreateDescriptionButtonAlways(UTUB_ID);
    $("#URLDeckSubheaderCreateDescription").trigger(
      "click.createUTubdescription",
    );

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_UTUB_DESC_EDIT_OPEN,
      trigger: UTUB_DESC_EDIT_OPEN_TRIGGER.CREATE_BUTTON,
    });
  });

  it("utub_desc_edit unchanged value: emits submit but fires no AJAX", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    setupUpdateUTubDescriptionEventListeners(UTUB_ID);
    // Pre-state: description input equals current subheader text — unchanged-value guard.
    $("#utubDescriptionUpdate").val("Description");
    expect(vi.mocked(ajaxCall)).not.toHaveBeenCalled();
    expect(emit).not.toHaveBeenCalled();

    $("#utubDescriptionSubmitBtnUpdate").trigger("click");

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_FORM_SUBMIT,
      form: HOME_FORM.UTUB_DESC_EDIT,
      trigger: FORM_SUBMIT_TRIGGER.BUTTON_CLICK,
    });
    expect(
      vi.mocked(emit).mock.calls.filter((call) => {
        const args = call[0] as { event?: string; form?: string };
        return (
          args.event === UI_EVENTS.UI_FORM_SUBMIT &&
          args.form === "utub_desc_edit"
        );
      }),
    ).toHaveLength(1);
    expect(vi.mocked(ajaxCall)).not.toHaveBeenCalled();
  });

  it("does not emit when keydown is a non-activation key", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    setupUpdateUTubDescriptionEventListeners(UTUB_ID);
    const tabEvent = $.Event("keydown.updateUTubDesc", { key: "Tab" });
    $("#UTubDescriptionSubheaderWrap .edit-pencil-icon").trigger(tabEvent);

    expect(emit).not.toHaveBeenCalled();
  });

  it("emits ui_form_cancel with trigger=outside_click when window-click handler triggers cancel", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    // Open the edit form first (rebinds window-click cancel handler).
    setupUpdateUTubDescriptionEventListeners(UTUB_ID);
    $("#UTubDescriptionSubheaderWrap").trigger("click.updateUTubDesc");
    vi.mocked(emit).mockClear();

    // Simulate a click outside the editor (e.g. body itself).
    $(window).trigger({
      type: "click.updateUTubDescription",
      target: document.body,
    } as unknown as JQuery.TriggeredEvent);

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_FORM_CANCEL,
      form: HOME_FORM.UTUB_DESC_EDIT,
      trigger: FORM_CANCEL_TRIGGER.OUTSIDE_CLICK,
    });
  });

  describe("mobile form model — keep description open + Saved✓ on success", () => {
    function mockSuccessfulPatch(newDescription: string): void {
      vi.mocked(ajaxCall).mockReturnValue(
        createMockJqXHRChainable({
          done: (callback) =>
            (
              callback as (
                response: { utubDescription: string },
                textStatus: string,
                xhr: { status: number },
              ) => void
            )({ utubDescription: newDescription }, "success", { status: 200 }),
        }),
      );
    }

    it("keeps the field open, flashes Saved✓, announces, and re-registers the open form", async () => {
      const { emit } = await import("../../../lib/metrics-client.js");
      vi.mocked(isCoarsePointer).mockReturnValue(true);
      $("#utubEditPanelClose").removeClass("hidden"); // panel open

      setupUpdateUTubDescriptionEventListeners(UTUB_ID);
      updateUTubDescriptionShowInput(UTUB_ID); // open the field (subheader hidden)
      expect($("#URLDeckSubheader").hasClass("hidden")).toBe(true);

      $("#utubDescriptionUpdate").val("New Description");
      mockSuccessfulPatch("New Description");

      $("#utubDescriptionSubmitBtnUpdate").trigger("click");

      // Field stays open (subheader still hidden), tick visible, announced.
      expect($("#URLDeckSubheader").hasClass("hidden")).toBe(true);
      expect($("#utubDescriptionSavedTick").hasClass("opa-1")).toBe(true);
      expect($("#utubDescriptionSavedTick").hasClass("opa-0")).toBe(false);
      expect($("#fieldSavedAnnouncement").text()).toBe(
        "UTub description Saved",
      );
      expect(getOpenForm()).toBe(HOME_FORM.UTUB_DESC_EDIT);
      expect(vi.mocked(ajaxCall)).toHaveBeenCalledTimes(1);

      // UI_FORM_SUBMIT emitted exactly once.
      expect(
        vi.mocked(emit).mock.calls.filter((call) => {
          const args = call[0] as { event?: string };
          return args.event === UI_EVENTS.UI_FORM_SUBMIT;
        }),
      ).toHaveLength(1);
    });

    it("no-op (unchanged) submit keeps the field open with no tick and re-registers the open form", () => {
      vi.mocked(isCoarsePointer).mockReturnValue(true);
      $("#utubEditPanelClose").removeClass("hidden"); // panel open

      setupUpdateUTubDescriptionEventListeners(UTUB_ID);
      updateUTubDescriptionShowInput(UTUB_ID); // input primed to current text
      expect($("#URLDeckSubheader").hasClass("hidden")).toBe(true);

      // Value unchanged: submit takes the skip path (no PATCH).
      $("#utubDescriptionSubmitBtnUpdate").trigger("click");

      expect($("#URLDeckSubheader").hasClass("hidden")).toBe(true); // still open
      expect($("#utubDescriptionSavedTick").hasClass("opa-1")).toBe(false); // no tick
      expect(getOpenForm()).toBe(HOME_FORM.UTUB_DESC_EDIT);
      expect(vi.mocked(ajaxCall)).not.toHaveBeenCalled();
    });

    it("empty→non-empty via panel: the subheader wrap is re-shown after the panel-closed Hide", () => {
      vi.mocked(isCoarsePointer).mockReturnValue(true);
      $("#utubEditPanelClose").removeClass("hidden"); // panel open
      // Simulate an empty-description UTub: selectors.ts hides the wrap.
      $("#URLDeckSubheader").text("");
      $("#UTubDescriptionSubheaderWrap").addClass("hidden");

      setupUpdateUTubDescriptionEventListeners(UTUB_ID);
      updateUTubDescriptionShowInput(UTUB_ID);
      $("#utubDescriptionUpdate").val("A brand new description");
      mockSuccessfulPatch("A brand new description");

      $("#utubDescriptionSubmitBtnUpdate").trigger("click");

      // While the panel stays open, the wrap re-show is deferred (still hidden).
      expect($("#UTubDescriptionSubheaderWrap").hasClass("hidden")).toBe(true);

      // Close the panel (flip the signal), then run the panel-closed Hide: it
      // reconciles the wrap to the now-non-empty description so it renders.
      $("#utubEditPanelClose").addClass("hidden");
      updateUTubDescriptionHideInput(UTUB_ID);

      expect($("#UTubDescriptionSubheaderWrap").hasClass("hidden")).toBe(false);
      expect($("#URLDeckSubheader").text()).toBe("A brand new description");
    });

    it("non-empty→empty via panel: the 'Add a description?' CTA is deferred until panel close", () => {
      vi.mocked(isCoarsePointer).mockReturnValue(true);
      $("#utubEditPanelClose").removeClass("hidden"); // panel open
      // Start from a UTub that HAS a description; the user clears it to empty.
      $("#URLDeckSubheader").text("Description");

      setupUpdateUTubDescriptionEventListeners(UTUB_ID);
      updateUTubDescriptionShowInput(UTUB_ID);
      $("#utubDescriptionUpdate").val(""); // cleared → real (changed) submit → empty
      mockSuccessfulPatch("");

      $("#utubDescriptionSubmitBtnUpdate").trigger("click");

      // While the panel stays open, the empty-description CTA re-arm is deferred:
      // showCreateDescriptionButtonAlways must NOT have run, so the create button
      // is not revealed (no opa-1 / height-2rem).
      const createCta = $("#URLDeckSubheaderCreateDescription");
      expect(createCta.hasClass("opa-1")).toBe(false);
      expect(createCta.hasClass("height-2rem")).toBe(false);
      // Field is still open (keep-open) and Saved✓ flashed on the real change.
      expect($("#URLDeckSubheader").hasClass("hidden")).toBe(true);
      expect($("#utubDescriptionSavedTick").hasClass("opa-1")).toBe(true);

      // Close the panel (flip the signal), then run the panel-closed Hide with the
      // active UTub id: NOW the deferred empty-description CTA re-arm fires.
      $("#utubEditPanelClose").addClass("hidden");
      updateUTubDescriptionHideInput(UTUB_ID);

      expect(createCta.hasClass("opa-1")).toBe(true);
      expect(createCta.hasClass("height-2rem")).toBe(true);
    });

    it("fine pointer (desktop): a changed submit collapses the field with no tick", async () => {
      vi.mocked(isCoarsePointer).mockReturnValue(false);

      setupUpdateUTubDescriptionEventListeners(UTUB_ID);
      updateUTubDescriptionShowInput(UTUB_ID);
      expect($("#URLDeckSubheader").hasClass("hidden")).toBe(true);

      $("#utubDescriptionUpdate").val("New Description");
      mockSuccessfulPatch("New Description");

      $("#utubDescriptionSubmitBtnUpdate").trigger("click");

      // Desktop path: field collapses (subheader restored) and no tick shows.
      expect($("#URLDeckSubheader").hasClass("hidden")).toBe(false);
      expect($("#utubDescriptionSavedTick").hasClass("opa-1")).toBe(false);
    });
  });

  describe("mobile form model — in-flight submit guard (description)", () => {
    it("blocks a second overlapping submit, reflects state via aria-disabled (never native disabled), and re-enables on a non-200 settle", async () => {
      const { emit } = await import("../../../lib/metrics-client.js");
      vi.mocked(isCoarsePointer).mockReturnValue(true);
      $("#utubEditPanelClose").removeClass("hidden"); // panel open

      setupUpdateUTubDescriptionEventListeners(UTUB_ID);
      updateUTubDescriptionShowInput(UTUB_ID);
      $("#utubDescriptionUpdate").val("New Description"); // changed → real submit

      const deferred = createMockJqXHR();
      vi.mocked(ajaxCall).mockReturnValue(deferred);

      const submitBtn = $("#utubDescriptionSubmitBtnUpdate");

      // First submit → request issued, control aria-disabled, focus preserved.
      submitBtn.trigger("click");
      expect(vi.mocked(ajaxCall)).toHaveBeenCalledTimes(1);
      expect(submitBtn.attr("aria-disabled")).toBe("true");
      expect(submitBtn.prop("disabled")).toBe(false);

      // Second submit while in flight → blocked (no second PATCH).
      submitBtn.trigger("click");
      expect(vi.mocked(ajaxCall)).toHaveBeenCalledTimes(1);

      // Non-200 settle re-enables (clear runs before the status check).
      deferred.resolve({ utubDescription: "New Description" }, "success", {
        status: 500,
      });
      expect(submitBtn.attr("aria-disabled")).toBeUndefined();
      expect(submitBtn.prop("disabled")).toBe(false);

      // Exactly one UI_FORM_SUBMIT (the guard returns before the second emit).
      expect(
        vi.mocked(emit).mock.calls.filter((call) => {
          const args = call[0] as { event?: string };
          return args.event === UI_EVENTS.UI_FORM_SUBMIT;
        }),
      ).toHaveLength(1);
    });
  });
});
