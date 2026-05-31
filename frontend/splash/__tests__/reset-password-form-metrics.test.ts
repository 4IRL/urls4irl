import { UI_EVENTS } from "../../lib/metrics-events.js";
import { createMockJqXHR } from "../../__tests__/helpers/mock-jquery.js";
import { initResetPasswordForm } from "../reset-password-form.js";
import { VALIDATION_FORM } from "../../types/metrics-dim-values.js";

const { mockMetricsClient } = await vi.hoisted(
  async () => await import("../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../../lib/page-utils.js", () => ({
  showNewPageOnAJAXHTMLResponse: vi.fn(),
}));

vi.mock("../init.js", () => ({
  showSplashModalAlertBanner: vi.fn(),
  hideSplashModalAlertBanner: vi.fn(),
  handleImproperFormErrors: vi.fn(),
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

const RESET_PASSWORD_MODAL_HTML = `
  <div class="modal fade" id="ResetPasswordModal">
    <form id="ModalForm" method="POST" action="">
      <input id="newPassword" class="form-control" value="newpass123" />
      <input id="confirmNewPassword" class="form-control" value="newpass123" />
      <button id="submit" type="submit"></button>
    </form>
  </div>
`;

describe("reset-password-form metrics — UI_RESET_PASSWORD_SUBMIT", () => {
  beforeEach(() => {
    document.body.innerHTML = RESET_PASSWORD_MODAL_HTML;
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("emits ui_reset_password_submit once on form submit", async () => {
    const { emit } = await import("../../lib/metrics-client.js");
    const mockDeferred = createMockJqXHR();
    vi.spyOn($, "ajax").mockReturnValue(mockDeferred);

    const $modal = $("#ResetPasswordModal");
    initResetPasswordForm($modal);
    $modal.find("form").trigger("submit");

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_RESET_PASSWORD_SUBMIT,
    });
    expect(emit).toHaveBeenCalledTimes(1);
  });
});

describe("reset-password-form metrics — UI_VALIDATION_ERROR", () => {
  beforeEach(() => {
    document.body.innerHTML = RESET_PASSWORD_MODAL_HTML;
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("emits ui_validation_error with form=reset_password on 400 errorCode 1", async () => {
    const { emit } = await import("../../lib/metrics-client.js");
    const mockDeferred = createMockJqXHR();
    vi.spyOn($, "ajax").mockReturnValue(mockDeferred);

    const $modal = $("#ResetPasswordModal");
    initResetPasswordForm($modal);
    $modal.find("form").trigger("submit");

    const fakeXhr = {
      status: 400,
      responseJSON: { errorCode: 1, message: "Invalid" },
      getResponseHeader: vi.fn(),
    };
    mockDeferred.reject(fakeXhr, "error", "Bad Request");

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_VALIDATION_ERROR,
      form: VALIDATION_FORM.RESET_PASSWORD,
    });
  });
});
