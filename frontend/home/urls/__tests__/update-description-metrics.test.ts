import { UI_EVENTS } from "../../../lib/metrics-events.js";
import {
  setupUpdateUTubDescriptionEventListeners,
  showCreateDescriptionButtonAlways,
} from "../update-description.js";
import { getState } from "../../../store/app-store.js";
import { ajaxCall } from "../../../lib/ajax.js";

const { mockMetricsClient } = await vi.hoisted(
  async () => await import("../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../lib/metrics-client.js", () => mockMetricsClient());

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
    <span id="URLDeckNoDescription" class="hidden"></span>
  </div>
  <button id="urlBtnCreate"></button>
`;

const UTUB_ID = 1;

describe("update-description metrics — UI_UTUB_DESC_EDIT_OPEN", () => {
  beforeEach(() => {
    document.body.innerHTML = DESCRIPTION_EDIT_HTML;
    vi.clearAllMocks();
    vi.mocked(getState).mockReturnValue({
      isCurrentUserOwner: true,
    } as ReturnType<typeof getState>);
  });

  afterEach(() => {
    $(window).off();
    document.body.innerHTML = "";
  });

  it("emits ui_utub_desc_edit_open with trigger 'pencil_icon' on wrap click", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    setupUpdateUTubDescriptionEventListeners(UTUB_ID);
    $("#UTubDescriptionSubheaderWrap").trigger("click.updateUTubDesc");

    expect(emit).toHaveBeenCalledWith(UI_EVENTS.UI_UTUB_DESC_EDIT_OPEN, {
      trigger: "pencil_icon",
    });
  });

  it("emits ui_utub_desc_edit_open with trigger 'keyboard' on Enter on pencil", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    setupUpdateUTubDescriptionEventListeners(UTUB_ID);
    const enterEvent = $.Event("keydown.updateUTubDesc", { key: "Enter" });
    $("#UTubDescriptionSubheaderWrap .edit-pencil-icon").trigger(enterEvent);

    expect(emit).toHaveBeenCalledWith(UI_EVENTS.UI_UTUB_DESC_EDIT_OPEN, {
      trigger: "keyboard",
    });
  });

  it("emits ui_utub_desc_edit_open with trigger 'keyboard' on Space on pencil", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    setupUpdateUTubDescriptionEventListeners(UTUB_ID);
    const spaceEvent = $.Event("keydown.updateUTubDesc", { key: " " });
    $("#UTubDescriptionSubheaderWrap .edit-pencil-icon").trigger(spaceEvent);

    expect(emit).toHaveBeenCalledWith(UI_EVENTS.UI_UTUB_DESC_EDIT_OPEN, {
      trigger: "keyboard",
    });
  });

  it("emits ui_utub_desc_edit_open with trigger 'create_button' from showCreateDescriptionButtonAlways", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    showCreateDescriptionButtonAlways(UTUB_ID);
    $("#URLDeckSubheaderCreateDescription").trigger(
      "click.createUTubdescription",
    );

    expect(emit).toHaveBeenCalledWith(UI_EVENTS.UI_UTUB_DESC_EDIT_OPEN, {
      trigger: "create_button",
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

    expect(emit).toHaveBeenCalledWith(UI_EVENTS.UI_FORM_SUBMIT, {
      form: "utub_desc_edit",
      trigger: "button_click",
    });
    expect(
      vi
        .mocked(emit)
        .mock.calls.filter(
          (call) =>
            call[0] === UI_EVENTS.UI_FORM_SUBMIT &&
            (
              (call as unknown as [string, { form?: string } | undefined])[1] ??
              {}
            ).form === "utub_desc_edit",
        ),
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

    expect(emit).toHaveBeenCalledWith(UI_EVENTS.UI_FORM_CANCEL, {
      form: "utub_desc_edit",
      trigger: "outside_click",
    });
  });
});
