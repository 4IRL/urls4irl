import {
  newURLInputAddEventListeners,
  setFocusEventListenersOnURLCard,
} from "../cards.js";
import { emitFormCancel, emitFormSubmit } from "../../../btns-forms.js";
import { createURL, createURLHideInput } from "../create.js";

const { mockMetricsClient } = await vi.hoisted(
  async () =>
    await import("../../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../../url-context.js", () => ({
  isURLSearchActive: vi.fn(() => false),
  getActiveTagCount: vi.fn(() => 0),
}));

vi.mock("../selection.js", () => ({
  selectURLCard: vi.fn(),
  setURLCardSelectionEventListener: vi.fn(),
}));

vi.mock("../../../btns-forms.js", () => ({
  emitFormSubmit: vi.fn(),
  emitFormCancel: vi.fn(),
  emitValidationError: vi.fn(),
  showInput: vi.fn(),
  hideInput: vi.fn(),
}));

vi.mock("../create.js", () => ({
  createURL: vi.fn(),
  createURLHideInput: vi.fn(),
  bindCreateURLFocusEventListeners: vi.fn(),
  unbindCreateURLFocusEventListeners: vi.fn(),
  resetCreateURLFailErrors: vi.fn(),
}));

const $ = window.jQuery;

describe("cards metrics — UI_URL_CARD_CLICK (Enter key branch)", () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <div class="urlRow" utuburlid="7" urlSelected="false" tabindex="0"></div>
    `;
    vi.clearAllMocks();
  });

  afterEach(() => {
    $(document).off("keyup.focusURLCard7");
  });

  it("emits ui_url_card_click on Enter key when card is focused", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");
    const { isURLSearchActive, getActiveTagCount } = await import(
      "../../url-context.js"
    );
    vi.mocked(isURLSearchActive).mockReturnValue(false);
    vi.mocked(getActiveTagCount).mockReturnValue(0);

    const urlCard = $(".urlRow");
    setFocusEventListenersOnURLCard(urlCard);
    urlCard.trigger("focus.focusURLCard7");

    const enterEvent = $.Event("keyup.focusURLCard7", { key: "Enter" });
    $(document).trigger(enterEvent);

    expect(emit).toHaveBeenCalledWith("ui_url_card_click", {
      search_active: "false",
      active_tag_count: 0,
    });
  });

  it("does NOT emit on non-Enter keyup", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");

    const urlCard = $(".urlRow");
    setFocusEventListenersOnURLCard(urlCard);
    urlCard.trigger("focus.focusURLCard7");

    const tabEvent = $.Event("keyup.focusURLCard7", { key: "Tab" });
    $(document).trigger(tabEvent);

    expect(emit).not.toHaveBeenCalled();
  });

  it("emits with dimensions read at keypress time", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");
    const { isURLSearchActive, getActiveTagCount } = await import(
      "../../url-context.js"
    );

    const urlCard = $(".urlRow");
    setFocusEventListenersOnURLCard(urlCard);
    urlCard.trigger("focus.focusURLCard7");

    vi.mocked(isURLSearchActive).mockReturnValue(true);
    vi.mocked(getActiveTagCount).mockReturnValue(2);

    const enterEvent = $.Event("keyup.focusURLCard7", { key: "Enter" });
    $(document).trigger(enterEvent);

    expect(emit).toHaveBeenCalledWith("ui_url_card_click", {
      search_active: "true",
      active_tag_count: 2,
    });
  });
});

describe("cards metrics — url_create form via newURLInputAddEventListeners", () => {
  const UTUB_ID = 1;

  const NEW_URL_INPUT_HTML = `
    <form id="newURLInput">
      <input id="urlTitleCreate" type="text" />
      <input id="urlStringCreate" type="text" />
      <button id="urlSubmitBtnCreate" type="button"></button>
      <button id="urlCancelBtnCreate" type="button"></button>
    </form>
  `;

  beforeEach(() => {
    document.body.innerHTML = NEW_URL_INPUT_HTML;
    vi.clearAllMocks();
  });

  afterEach(() => {
    $("#urlSubmitBtnCreate").off();
    $("#urlCancelBtnCreate").off();
    $("#urlTitleCreate").off();
    $("#urlStringCreate").off();
  });

  it("submit button click emits ui_form_submit('url_create', 'button_click')", () => {
    const urlInputForm = $("#newURLInput");
    newURLInputAddEventListeners(urlInputForm, UTUB_ID);

    $("#urlSubmitBtnCreate").trigger("click.createURL");

    expect(vi.mocked(emitFormSubmit)).toHaveBeenCalledWith(
      "url_create",
      "button_click",
    );
    expect(vi.mocked(createURL)).toHaveBeenCalledTimes(1);
  });

  it("cancel button click emits ui_form_cancel('url_create', 'cancel_button')", () => {
    const urlInputForm = $("#newURLInput");
    newURLInputAddEventListeners(urlInputForm, UTUB_ID);

    $("#urlCancelBtnCreate").trigger("click.createURL");

    expect(vi.mocked(emitFormCancel)).toHaveBeenCalledWith(
      "url_create",
      "cancel_button",
    );
    expect(vi.mocked(createURLHideInput)).toHaveBeenCalledTimes(1);
  });
});
