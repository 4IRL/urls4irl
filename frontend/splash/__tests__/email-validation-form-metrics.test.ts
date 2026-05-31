import { UI_EVENTS } from "../../lib/metrics-events.js";
import { createMockJqXHR } from "../../__tests__/helpers/mock-jquery.js";
import {
  initEmailValidationForm,
  SEND_INITIAL_EMAIL,
  SKIP_INITIAL_EMAIL,
} from "../email-validation-form.js";
import {
  EMAIL_VALIDATION_SUBMIT_TRIGGER,
  VALIDATION_FORM,
} from "../../types/metrics-dim-values.js";

const { mockMetricsClient } = await vi.hoisted(
  async () => await import("../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../init.js", () => ({
  showSplashModalAlertBanner: vi.fn(),
  resetModalFormState: vi.fn(),
}));

vi.mock("../../lib/globals.js", () => ({
  $: window.jQuery,
  jQuery: window.jQuery,
  bootstrap: window.bootstrap,
}));

vi.mock("../../lib/config.js", () => {
  const configScript = document.getElementById("app-config")!;
  const config = JSON.parse(configScript.textContent!);
  return { APP_CONFIG: config };
});

const $ = window.jQuery;

const EMAIL_VALIDATION_MODAL_HTML = `
  <div class="modal fade" id="EmailValidationModal">
    <form id="ModalForm" method="POST" action="">
      <input id="email" class="form-control" value="test@test.com" />
      <button id="submit" type="submit"></button>
    </form>
  </div>
`;

describe("email-validation-form metrics — UI_EMAIL_VALIDATION_SUBMIT", () => {
  beforeEach(() => {
    document.body.innerHTML = EMAIL_VALIDATION_MODAL_HTML;
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("emits trigger=manual_click when the user clicks the submit button", async () => {
    const { emit } = await import("../../lib/metrics-client.js");
    const mockDeferred = createMockJqXHR();
    vi.spyOn($, "ajax").mockReturnValue(mockDeferred);

    const $modal = $("#EmailValidationModal");
    initEmailValidationForm($modal, SKIP_INITIAL_EMAIL);
    $modal.find("#submit").trigger("click");

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_EMAIL_VALIDATION_SUBMIT,
      trigger: EMAIL_VALIDATION_SUBMIT_TRIGGER.MANUAL_CLICK,
    });
  });

  it("emits trigger=auto_after_register on shown.bs.modal when sendInitialEmail is true", async () => {
    const { emit } = await import("../../lib/metrics-client.js");
    const mockDeferred = createMockJqXHR();
    vi.spyOn($, "ajax").mockReturnValue(mockDeferred);

    const $modal = $("#EmailValidationModal");
    initEmailValidationForm($modal, SEND_INITIAL_EMAIL);
    $modal.trigger("shown.bs.modal");

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_EMAIL_VALIDATION_SUBMIT,
      trigger: EMAIL_VALIDATION_SUBMIT_TRIGGER.AUTO_AFTER_REGISTER,
    });
  });
});

describe("email-validation-form metrics — UI_VALIDATION_ERROR", () => {
  beforeEach(() => {
    document.body.innerHTML = EMAIL_VALIDATION_MODAL_HTML;
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("emits ui_validation_error with form=email_validation when 400 response lacks errorCode", async () => {
    const { emit } = await import("../../lib/metrics-client.js");
    const mockDeferred = createMockJqXHR();
    vi.spyOn($, "ajax").mockReturnValue(mockDeferred);

    const $modal = $("#EmailValidationModal");
    initEmailValidationForm($modal, SKIP_INITIAL_EMAIL);
    $modal.find("#submit").trigger("click");

    const fakeXhr = {
      status: 400,
      responseJSON: { message: "Bad request" },
      getResponseHeader: vi.fn(),
    };
    mockDeferred.reject(fakeXhr, "error", "Bad Request");

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_VALIDATION_ERROR,
      form: VALIDATION_FORM.EMAIL_VALIDATION,
    });
  });
});
