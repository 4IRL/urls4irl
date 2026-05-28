import { setupUpdateUTubNameEventListeners } from "../update-name.js";
import { getState } from "../../../store/app-store.js";
import { ajaxCall } from "../../../lib/ajax.js";

vi.mock("../../../lib/metrics-client.js", () => ({
  emit: vi.fn(),
  flush: vi.fn().mockResolvedValue(undefined),
  initMetricsClient: vi.fn(),
  resetMetricsClient: vi.fn(),
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
    routes: {},
    constants: {},
    strings: {},
  },
}));

vi.mock("../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
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

vi.mock("../../btns-forms.js", async () => {
  const { emit } = await import("../../../lib/metrics-client.js");
  return {
    showInput: vi.fn(),
    hideInput: vi.fn(),
    highlightInput: vi.fn(),
    hideInputs: vi.fn(),
    emitFormSubmit: (
      form: string,
      trigger: "enter_key" | "button_click",
    ): void => {
      emit("ui_form_submit", { trigger, form } as Record<string, string>);
    },
    emitFormCancel: (
      form: string,
      trigger: "escape_key" | "cancel_button",
    ): void => {
      emit("ui_form_cancel", { trigger, form } as Record<string, string>);
    },
    emitValidationError: (form: string): void => {
      emit("ui_validation_error", { form } as Record<string, string>);
    },
  };
});

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
  </div>
  <span id="URLDeckSubheader"></span>
  <button id="URLDeckSubheaderCreateDescription"></button>
  <button id="urlBtnCreate"></button>
`;

const UTUB_ID = 1;

describe("update-name metrics — UI_UTUB_NAME_EDIT_OPEN", () => {
  beforeEach(() => {
    document.body.innerHTML = NAME_EDIT_HTML;
    vi.clearAllMocks();
    vi.mocked(getState).mockReturnValue({
      isCurrentUserOwner: true,
    } as ReturnType<typeof getState>);
  });

  afterEach(() => {
    $(window).off();
    document.body.innerHTML = "";
  });

  it("emits ui_utub_name_edit_open with trigger 'pencil_icon' on wrap click", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    setupUpdateUTubNameEventListeners(UTUB_ID);
    $("#UTubNameUpdateWrap").trigger("click.updateUTubname");

    expect(emit).toHaveBeenCalledWith("ui_utub_name_edit_open", {
      trigger: "pencil_icon",
    });
  });

  it("emits ui_utub_name_edit_open with trigger 'keyboard' on Enter on pencil", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    setupUpdateUTubNameEventListeners(UTUB_ID);
    const enterEvent = $.Event("keydown.updateUTubname", { key: "Enter" });
    $("#UTubNameUpdateWrap .edit-pencil-icon").trigger(enterEvent);

    expect(emit).toHaveBeenCalledWith("ui_utub_name_edit_open", {
      trigger: "keyboard",
    });
  });

  it("emits ui_utub_name_edit_open with trigger 'keyboard' on Space on pencil", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    setupUpdateUTubNameEventListeners(UTUB_ID);
    const spaceEvent = $.Event("keydown.updateUTubname", { key: " " });
    $("#UTubNameUpdateWrap .edit-pencil-icon").trigger(spaceEvent);

    expect(emit).toHaveBeenCalledWith("ui_utub_name_edit_open", {
      trigger: "keyboard",
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

    expect(emit).toHaveBeenCalledWith("ui_form_submit", {
      trigger: "button_click",
      form: "utub_name_edit",
    });
    expect(
      vi
        .mocked(emit)
        .mock.calls.filter(
          (call) =>
            call[0] === "ui_form_submit" &&
            (call[1] as { form?: string } | undefined)?.form ===
              "utub_name_edit",
        ),
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

    expect(emit).toHaveBeenCalledWith("ui_utub_desc_edit_open", {
      trigger: "create_button",
    });
  });
});
