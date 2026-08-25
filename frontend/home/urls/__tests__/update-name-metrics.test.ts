import { UI_EVENTS } from "../../../types/metrics-events.js";
import {
  setupUpdateUTubNameEventListeners,
  updateUTubNameHideInput,
  updateUTubNameShowInput,
} from "../update-name.js";
import { getState } from "../../../store/app-store.js";
import { ajaxCall, is429Handled } from "../../../lib/ajax.js";
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
      <span class="field-saved-tick opa-0" id="utubNameSavedTick" aria-hidden="true">Saved <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-check" viewBox="0 0 16 16" aria-hidden="true"><path d="M10.97 4.97a.75.75 0 0 1 1.07 1.05l-3.99 4.99a.75.75 0 0 1-1.08.02L4.324 8.384a.75.75 0 1 1 1.06-1.06l2.094 2.093 3.473-4.425a.267.267 0 0 1 .02-.022z"/></svg></span>
    </div>
  </div>
  <span id="URLDeckSubheader"></span>
  <span class="visually-hidden" id="fieldSavedAnnouncement" aria-live="polite"></span>
  <button id="URLDeckSubheaderCreateDescription"></button>
  <button id="URLSearchFilterIcon"></button>
  <button id="urlBtnCreate"></button>
  <button id="urlBtnMultiSelect" class="visible"></button>
  <button id="utubEditPanelToggle" class="hidden"></button>
  <button id="utubEditPanelClose" class="hidden"></button>
  <ul id="listUTubs"><li class="active"><span class="UTubName">Test UTub</span></li></ul>
  <div id="confirmModal">
    <span id="confirmModalTitle"></span>
    <span id="confirmModalBody"></span>
    <button id="modalDismiss"></button>
    <button id="modalRedirect"></button>
    <button id="modalSubmit"></button>
  </div>
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
        activeUTubID: UTUB_ID,
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
        activeUTubID: UTUB_ID,
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

    it("clears the guard on a genuine AJAX reject (.fail), so a fresh submit is not blocked", () => {
      vi.mocked(isCoarsePointer).mockReturnValue(true);
      vi.mocked(getState).mockReturnValue({
        isCurrentUserOwner: true,
        activeUTubID: UTUB_ID,
        utubs: [],
      } as unknown as ReturnType<typeof getState>);
      $("#utubEditPanelClose").removeClass("hidden"); // panel open

      setupUpdateUTubNameEventListeners(UTUB_ID);
      updateUTubNameShowInput(UTUB_ID);
      $("#utubNameUpdate").val("New Name"); // changed → real submit path

      const submitBtn = $("#utubNameSubmitBtnUpdate");

      // First submit → in flight, control aria-disabled.
      const deferred = createMockJqXHR();
      vi.mocked(ajaxCall).mockReturnValue(deferred);
      submitBtn.trigger("click.updateUTubname");
      expect(submitBtn.attr("aria-disabled")).toBe("true");

      // Genuine reject via the true `.fail()` branch (not a .done non-200). The
      // clear runs at the top of the fail handler; short-circuit the downstream
      // fail-display so it doesn't attempt an error-page navigation.
      vi.mocked(is429Handled).mockReturnValueOnce(true);
      deferred.reject({ status: 0 }, "error");
      expect(submitBtn.attr("aria-disabled")).toBeUndefined(); // guard cleared

      // A fresh submit is no longer blocked — it fires a new PATCH.
      const nextDeferred = createMockJqXHR();
      vi.mocked(ajaxCall).mockReturnValue(nextDeferred);
      submitBtn.trigger("click.updateUTubname");
      expect(vi.mocked(ajaxCall)).toHaveBeenCalledTimes(2);
      // Settle the second request (non-200 → clears the guard) so the
      // module-level flag doesn't leak into the next test.
      nextDeferred.resolve(
        { utubName: "New Name", utubID: UTUB_ID },
        "success",
        {
          status: 500,
        },
      );
    });
  });

  describe("mobile form model — sameName confirm-modal path", () => {
    // Confirming a duplicate-name submit through the sameName modal must keep the
    // name field open with the panel intact, rebind the Enter/Escape listeners
    // cleanly across the modal round-trip (no stacked handlers), and emit
    // UI_FORM_SUBMIT exactly once for the whole flow — one for the initial
    // duplicate-name attempt, none re-emitted on the modal confirm.
    async function setupDuplicateNameSubmit(): Promise<void> {
      const { getAllAccessibleUTubNames } = await import(
        "../../utubs/utils.js"
      );
      vi.mocked(getAllAccessibleUTubNames).mockReturnValue(["Existing UTub"]);
      vi.mocked(isCoarsePointer).mockReturnValue(true);
      vi.mocked(getState).mockReturnValue({
        isCurrentUserOwner: true,
        activeUTubID: UTUB_ID,
        utubs: [],
      } as unknown as ReturnType<typeof getState>);
      $("#utubEditPanelClose").removeClass("hidden"); // panel open

      setupUpdateUTubNameEventListeners(UTUB_ID);
      updateUTubNameShowInput(UTUB_ID); // open the field (header hidden)

      // A changed value that collides with another accessible UTub name → the
      // unchanged-value guard passes but checkSameNameUTubOnUpdate shows the modal.
      $("#utubNameUpdate").val("Existing UTub");
    }

    it("shows the confirm modal on a duplicate name without firing the PATCH", async () => {
      await setupDuplicateNameSubmit();

      $("#utubNameSubmitBtnUpdate").trigger("click.updateUTubname");

      // Modal shown, no PATCH yet (awaiting confirmation).
      expect($.fn.modal).toHaveBeenCalledWith("show");
      expect($("#modalSubmit").text()).toBe("Edit Name");
      expect(vi.mocked(ajaxCall)).not.toHaveBeenCalled();
      // The field stays open (header still hidden) behind the still-open modal.
      expect($("#URLDeckHeader").hasClass("hidden")).toBe(true);
    });

    it("confirming keeps the field open, emits UI_FORM_SUBMIT once, and rebinds Enter cleanly", async () => {
      const { emit } = await import("../../../lib/metrics-client.js");
      await setupDuplicateNameSubmit();

      // Confirmed PATCH resolves 200 → updateUTubNameSuccess keeps the field open.
      vi.mocked(ajaxCall).mockReturnValue(
        createMockJqXHRChainable({
          done: (callback) =>
            (
              callback as (
                response: { utubName: string; utubID: number },
                textStatus: string,
                xhr: { status: number },
              ) => void
            )({ utubName: "Existing UTub", utubID: UTUB_ID }, "success", {
              status: 200,
            }),
        }),
      );

      // Initial duplicate-name submit → emits UI_FORM_SUBMIT (once), opens modal.
      $("#utubNameSubmitBtnUpdate").trigger("click.updateUTubname");
      expect(vi.mocked(ajaxCall)).not.toHaveBeenCalled();

      // Confirm through the modal ("Edit Name") → updateUTubName re-invoked; the
      // confirm click itself must NOT re-emit UI_FORM_SUBMIT.
      $("#modalSubmit").trigger("click");

      // Exactly one PATCH fired, field kept open (panel intact), tick shown.
      expect(vi.mocked(ajaxCall)).toHaveBeenCalledTimes(1);
      expect($("#URLDeckHeader").hasClass("hidden")).toBe(true);
      expect($("#utubEditPanelClose").hasClass("hidden")).toBe(false);
      expect($("#utubNameSavedTick").hasClass("opa-1")).toBe(true);

      // UI_FORM_SUBMIT emitted exactly once for the whole flow (not twice).
      expect(
        vi.mocked(emit).mock.calls.filter((call) => {
          const args = call[0] as { event?: string };
          return args.event === UI_EVENTS.UI_FORM_SUBMIT;
        }),
      ).toHaveLength(1);

      // Simulate Bootstrap's modal-hidden event (mocked plugin doesn't fire it),
      // which rebinds the Enter/Escape listeners via
      // setEventListenersToEscapeUpdateUTubName.
      $("#confirmModal").trigger("hidden.bs.modal");
      vi.mocked(emit).mockClear();

      // The rebound keydown handler is bound inside the focus callback; focus the
      // input, then press Enter with the value now equal to the saved header text
      // → unchanged-skip path emits UI_FORM_SUBMIT exactly once (a stacked/duplicate
      // handler would emit it twice), proving a clean single rebind.
      $("#utubNameUpdate").trigger("focus");
      $("#utubNameUpdate").trigger(
        $.Event("keydown.updateUTubname", { key: "Enter" }),
      );

      expect(
        vi.mocked(emit).mock.calls.filter((call) => {
          const args = call[0] as { event?: string };
          return args.event === UI_EVENTS.UI_FORM_SUBMIT;
        }),
      ).toHaveLength(1);
      // No second PATCH — the post-rebind Enter took the unchanged-skip path.
      expect(vi.mocked(ajaxCall)).toHaveBeenCalledTimes(1);
    });
  });
});

describe("update-name — #urlBtnMultiSelect toggle gating", () => {
  // utils.js is unmocked here, so getNumOfURLs() counts real .urlRow nodes; the
  // fixture's URL count drives the guarded restore on close.
  beforeEach(() => {
    document.body.innerHTML = NAME_EDIT_HTML;
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

  it("hides the multi-select toggle when the name edit form opens", () => {
    $("#urlBtnMultiSelect").showClassNormal();

    updateUTubNameShowInput(UTUB_ID);

    expect($("#urlBtnMultiSelect").hasClass("hidden")).toBe(true);
    expect($("#urlBtnMultiSelect").hasClass("visible")).toBe(false);
  });

  it("restores the toggle on close when the UTub still has URLs", () => {
    $("#listUTubs").before('<div class="urlRow"></div>');
    $("#urlBtnMultiSelect").hideClass();

    updateUTubNameHideInput();

    expect($("#urlBtnMultiSelect").hasClass("hidden")).toBe(false);
    expect($("#urlBtnMultiSelect").hasClass("visible")).toBe(true);
  });

  it("keeps the toggle hidden on close when the UTub has no URLs", () => {
    $("#urlBtnMultiSelect").hideClass();

    updateUTubNameHideInput();

    expect($("#urlBtnMultiSelect").hasClass("hidden")).toBe(true);
    expect($("#urlBtnMultiSelect").hasClass("visible")).toBe(false);
  });
});
