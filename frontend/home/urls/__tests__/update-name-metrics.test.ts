import { UI_EVENTS } from "../../../types/metrics-events.js";
import {
  setupUpdateUTubNameEventListeners,
  updateUTubNameShowInput,
} from "../update-name.js";
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
  UTUB_NAME_EDIT_OPEN_TRIGGER,
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
    routes: { updateUTubName: vi.fn(() => "/utubs/1/name") },
    constants: {},
    strings: {
      FIELD_SAVED: "Saved",
      FIELD_SAVED_LABEL_UTUB_NAME: "UTub name",
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

vi.mock("../search.js", () => ({
  temporarilyHideSearchForEdit: vi.fn(),
  showURLSearchIcon: vi.fn(),
}));

vi.mock("../update-description.js", () => ({
  updateUTubDescriptionHideInput: vi.fn(),
  updateUTubDescriptionShowInput: vi.fn(),
}));

vi.mock("../cards/selection.js", () => ({
  deselectAllURLs: vi.fn(),
}));

const $ = window.jQuery;

const NAME_EDIT_HTML = `
  <div class="titleElement">
    <div id="UTubNameUpdateWrap">
      <h2 id="URLDeckHeader">Test UTub</h2>
      <span class="edit-pencil-icon hidden" role="button" tabindex="0"></span>
    </div>
    <input id="utubNameUpdate" />
    <button id="utubNameSubmitBtnUpdate"></button>
    <button id="utubNameCancelBtnUpdate"></button>
    <div class="field-saved-tick-slot">
      <span class="field-saved-tick opa-0" id="utubNameSavedTick" aria-hidden="true">Saved <i class="bi bi-check"></i></span>
    </div>
  </div>
  <span id="URLDeckSubheader"></span>
  <span class="visually-hidden" id="fieldSavedAnnouncement" aria-live="polite"></span>
  <button id="URLDeckSubheaderCreateDescription"></button>
  <button id="URLSearchFilterIcon"></button>
  <button id="urlBtnCreate"></button>
  <button id="utubEditPanelToggle" class="hidden"></button>
  <button id="utubEditPanelClose" class="hidden"></button>
  <ul id="listUTubs"><li class="active"><span class="UTubName">Test UTub</span></li></ul>
  <div id="confirmModal"></div>
`;

const UTUB_ID = 1;

describe("update-name metrics — UI_UTUB_NAME_EDIT_OPEN", () => {
  beforeEach(() => {
    document.body.innerHTML = NAME_EDIT_HTML;
    vi.clearAllMocks();
    vi.mocked(getState).mockReturnValue({
      isCurrentUserOwner: true,
    } as ReturnType<typeof getState>);
    vi.mocked(isCoarsePointer).mockReturnValue(false);
    // Bootstrap's jQuery modal plugin isn't registered in the test env; the name
    // success path calls $("#confirmModal").modal("hide").
    $.fn.modal = vi.fn().mockReturnThis();
  });

  afterEach(() => {
    $(window).off();
    document.body.innerHTML = "";
  });

  it("emits ui_utub_name_edit_open with trigger 'pencil_icon' on wrap click", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    setupUpdateUTubNameEventListeners(UTUB_ID);
    $("#UTubNameUpdateWrap").trigger("click.updateUTubname");

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_UTUB_NAME_EDIT_OPEN,
      trigger: UTUB_NAME_EDIT_OPEN_TRIGGER.PENCIL_ICON,
    });
  });

  it("emits ui_utub_name_edit_open with trigger 'keyboard' on Enter on pencil", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    setupUpdateUTubNameEventListeners(UTUB_ID);
    const enterEvent = $.Event("keydown.updateUTubname", { key: "Enter" });
    $("#UTubNameUpdateWrap .edit-pencil-icon").trigger(enterEvent);

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_UTUB_NAME_EDIT_OPEN,
      trigger: UTUB_NAME_EDIT_OPEN_TRIGGER.KEYBOARD,
    });
  });

  it("emits ui_utub_name_edit_open with trigger 'keyboard' on Space on pencil", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    setupUpdateUTubNameEventListeners(UTUB_ID);
    const spaceEvent = $.Event("keydown.updateUTubname", { key: " " });
    $("#UTubNameUpdateWrap .edit-pencil-icon").trigger(spaceEvent);

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_UTUB_NAME_EDIT_OPEN,
      trigger: UTUB_NAME_EDIT_OPEN_TRIGGER.KEYBOARD,
    });
  });

  it("does not emit when keydown is a non-activation key", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    setupUpdateUTubNameEventListeners(UTUB_ID);
    const tabEvent = $.Event("keydown.updateUTubname", { key: "Tab" });
    $("#UTubNameUpdateWrap .edit-pencil-icon").trigger(tabEvent);

    expect(emit).not.toHaveBeenCalled();
  });

  it("utub_name_edit unchanged value: emits submit but fires no AJAX", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    setupUpdateUTubNameEventListeners(UTUB_ID);
    // Pre-state: name input equals current header text — unchanged-value guard.
    $("#utubNameUpdate").val("Test UTub");
    expect(vi.mocked(ajaxCall)).not.toHaveBeenCalled();
    expect(emit).not.toHaveBeenCalled();

    $("#utubNameSubmitBtnUpdate").trigger("click.updateUTubname");

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_FORM_SUBMIT,
      form: HOME_FORM.UTUB_NAME_EDIT,
      trigger: FORM_SUBMIT_TRIGGER.BUTTON_CLICK,
    });
    expect(
      vi.mocked(emit).mock.calls.filter((call) => {
        const args = call[0] as { event?: string; form?: string };
        return (
          args.event === UI_EVENTS.UI_FORM_SUBMIT &&
          args.form === "utub_name_edit"
        );
      }),
    ).toHaveLength(1);
    expect(vi.mocked(ajaxCall)).not.toHaveBeenCalled();
  });

  it("emits ui_utub_desc_edit_open with trigger 'create_button' when the rebind path fires", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    // URLDeckSubheader is empty so rebindCreateDescriptionForNameUpdate runs
    // when name edit is shown.
    setupUpdateUTubNameEventListeners(UTUB_ID);
    $("#UTubNameUpdateWrap").trigger("click.updateUTubname");
    vi.mocked(emit).mockClear();

    $("#URLDeckSubheaderCreateDescription").trigger(
      "click.createUTubdescription",
    );

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_UTUB_DESC_EDIT_OPEN,
      trigger: UTUB_DESC_EDIT_OPEN_TRIGGER.CREATE_BUTTON,
    });
  });

  it("emits ui_form_cancel with trigger=outside_click when window-click handler triggers cancel", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    // Open the edit form first (rebinds window-click cancel handler).
    setupUpdateUTubNameEventListeners(UTUB_ID);
    $("#UTubNameUpdateWrap").trigger("click.updateUTubname");
    vi.mocked(emit).mockClear();

    // Simulate a click on an element outside the editor (e.g. body itself).
    $(window).trigger({
      type: "click.updateUTubname",
      target: document.body,
    } as unknown as JQuery.TriggeredEvent);

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_FORM_CANCEL,
      form: HOME_FORM.UTUB_NAME_EDIT,
      trigger: FORM_CANCEL_TRIGGER.OUTSIDE_CLICK,
    });
  });

  describe("mobile form model — keep name open + Saved✓ on success", () => {
    it("keeps the field open, flashes Saved✓, announces, and re-registers the open form", async () => {
      const { emit } = await import("../../../lib/metrics-client.js");
      vi.mocked(isCoarsePointer).mockReturnValue(true);
      vi.mocked(getState).mockReturnValue({
        isCurrentUserOwner: true,
        utubs: [],
      } as unknown as ReturnType<typeof getState>);
      $("#utubEditPanelClose").removeClass("hidden"); // panel open

      setupUpdateUTubNameEventListeners(UTUB_ID);
      updateUTubNameShowInput(UTUB_ID); // open the field (header hidden)
      expect($("#URLDeckHeader").hasClass("hidden")).toBe(true);

      $("#utubNameUpdate").val("New Name");
      vi.mocked(ajaxCall).mockReturnValue(
        createMockJqXHRChainable({
          done: (callback) =>
            (
              callback as (
                response: { utubName: string; utubID: number },
                textStatus: string,
                xhr: { status: number },
              ) => void
            )({ utubName: "New Name", utubID: UTUB_ID }, "success", {
              status: 200,
            }),
        }),
      );

      $("#utubNameSubmitBtnUpdate").trigger("click.updateUTubname");

      // Field stays open (header still hidden), tick visible, announced.
      expect($("#URLDeckHeader").hasClass("hidden")).toBe(true);
      expect($("#utubNameSavedTick").hasClass("opa-1")).toBe(true);
      expect($("#fieldSavedAnnouncement").text()).toBe("UTub name Saved");
      expect(getOpenForm()).toBe(HOME_FORM.UTUB_NAME_EDIT);
      expect(vi.mocked(ajaxCall)).toHaveBeenCalledTimes(1);

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

      setupUpdateUTubNameEventListeners(UTUB_ID);
      updateUTubNameShowInput(UTUB_ID); // input primed to current name "Test UTub"
      expect($("#URLDeckHeader").hasClass("hidden")).toBe(true);

      // Value unchanged: submit takes the skip path.
      $("#utubNameSubmitBtnUpdate").trigger("click.updateUTubname");

      expect($("#URLDeckHeader").hasClass("hidden")).toBe(true); // still open
      expect($("#utubNameSavedTick").hasClass("opa-1")).toBe(false); // no tick
      expect(getOpenForm()).toBe(HOME_FORM.UTUB_NAME_EDIT);
      expect(vi.mocked(ajaxCall)).not.toHaveBeenCalled();
    });

    it("fine pointer (desktop): a changed submit collapses the field with no tick", () => {
      vi.mocked(isCoarsePointer).mockReturnValue(false);
      vi.mocked(getState).mockReturnValue({
        isCurrentUserOwner: true,
        utubs: [],
      } as unknown as ReturnType<typeof getState>);

      setupUpdateUTubNameEventListeners(UTUB_ID);
      updateUTubNameShowInput(UTUB_ID);

      $("#utubNameUpdate").val("New Name");
      vi.mocked(ajaxCall).mockReturnValue(
        createMockJqXHRChainable({
          done: (callback) =>
            (
              callback as (
                response: { utubName: string; utubID: number },
                textStatus: string,
                xhr: { status: number },
              ) => void
            )({ utubName: "New Name", utubID: UTUB_ID }, "success", {
              status: 200,
            }),
        }),
      );

      $("#utubNameSubmitBtnUpdate").trigger("click.updateUTubname");

      // Desktop path: field collapses (header restored) and no tick shows.
      expect($("#URLDeckHeader").hasClass("hidden")).toBe(false);
      expect($("#utubNameSavedTick").hasClass("opa-1")).toBe(false);
    });
  });

  describe("mobile form model — in-flight submit guard (name)", () => {
    it("blocks a second overlapping submit, reflects state via aria-disabled (never native disabled), and re-enables on a non-200 settle", async () => {
      const { emit } = await import("../../../lib/metrics-client.js");
      vi.mocked(isCoarsePointer).mockReturnValue(true);
      vi.mocked(getState).mockReturnValue({
        isCurrentUserOwner: true,
        utubs: [],
      } as unknown as ReturnType<typeof getState>);
      $("#utubEditPanelClose").removeClass("hidden"); // panel open

      setupUpdateUTubNameEventListeners(UTUB_ID);
      updateUTubNameShowInput(UTUB_ID);
      $("#utubNameUpdate").val("New Name"); // changed → real submit path

      // Pending deferred: done/fail do not fire until we settle it explicitly,
      // so the field stays "in flight" between the two clicks.
      const deferred = createMockJqXHR();
      vi.mocked(ajaxCall).mockReturnValue(deferred);

      const submitBtn = $("#utubNameSubmitBtnUpdate");

      // First submit → request issued, control aria-disabled, focus preserved.
      submitBtn.trigger("click.updateUTubname");
      expect(vi.mocked(ajaxCall)).toHaveBeenCalledTimes(1);
      expect(submitBtn.attr("aria-disabled")).toBe("true");
      expect(submitBtn.prop("disabled")).toBe(false);

      // Second submit while in flight → blocked (no second PATCH).
      submitBtn.trigger("click.updateUTubname");
      expect(vi.mocked(ajaxCall)).toHaveBeenCalledTimes(1);

      // Non-200 settle re-enables (clear runs before the status check).
      deferred.resolve({ utubName: "New Name", utubID: UTUB_ID }, "success", {
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
