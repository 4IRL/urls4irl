import { UI_EVENTS } from "../../types/metrics-events.js";
import { createMockJqXHR } from "../../__tests__/helpers/mock-jquery.js";
import { showNewPageOnAJAXHTMLResponse } from "../../lib/page-utils.js";
import { initLoginForm } from "../login-form.js";
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
  resetModalFormState: vi.fn(),
  handleImproperFormErrors: vi.fn(),
  handleUserHasAccountNotEmailValidated: vi.fn(),
  switchModal: vi.fn(),
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

// Minimal HTML — only the DOM nodes the function under test actually queries.
// This decouples tests from template markup and avoids maintaining HTML in two places.
const LOGIN_MODAL_HTML = `
  <div class="modal fade" id="LoginModal">
    <div id="ToRegisterFromLogin"></div>
    <div class="to-forgot-password"></div>
    <div class="form-group" id="ForgotPasswordLink"></div>
    <input id="username" class="form-control" value="testuser" />
    <input id="password" class="form-control" value="testpass" />
    <button id="submit" type="submit"></button>
  </div>
`;

describe("login-form 429 HTML response", () => {
  beforeEach(() => {
    document.body.innerHTML = LOGIN_MODAL_HTML;
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("calls showNewPageOnAJAXHTMLResponse when server returns 429 with HTML content", () => {
    const mockDeferred = createMockJqXHR();
    vi.spyOn($, "ajax").mockReturnValue(mockDeferred);

    const $modal = $("#LoginModal");
    initLoginForm($modal);
    $modal.find("#submit").trigger("click");

    // Simulate 429 HTML response
    const fakeXhr = {
      status: 429,
      responseText: "<html>Rate limited</html>",
      getResponseHeader: vi.fn().mockReturnValue("text/html; charset=utf-8"),
    };
    mockDeferred.reject(fakeXhr, "error", "Too Many Requests");

    expect(showNewPageOnAJAXHTMLResponse).toHaveBeenCalledWith(
      "<html>Rate limited</html>",
    );
  });

  it("calls showNewPageOnAJAXHTMLResponse when server returns 403 with HTML content", () => {
    const mockDeferred = createMockJqXHR();
    vi.spyOn($, "ajax").mockReturnValue(mockDeferred);

    const $modal = $("#LoginModal");
    initLoginForm($modal);
    $modal.find("#submit").trigger("click");

    const fakeXhr = {
      status: 403,
      responseText: "<html>Forbidden</html>",
      getResponseHeader: vi.fn().mockReturnValue("text/html; charset=utf-8"),
    };
    mockDeferred.reject(fakeXhr, "error", "Forbidden");

    expect(showNewPageOnAJAXHTMLResponse).toHaveBeenCalledWith(
      "<html>Forbidden</html>",
    );
  });
});

describe("login-form metrics — UI_LOGIN_SUBMIT", () => {
  beforeEach(() => {
    document.body.innerHTML = LOGIN_MODAL_HTML;
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("emits ui_login_submit once per submit-button click", async () => {
    const { emit } = await import("../../lib/metrics-client.js");
    const mockDeferred = createMockJqXHR();
    vi.spyOn($, "ajax").mockReturnValue(mockDeferred);

    const $modal = $("#LoginModal");
    initLoginForm($modal);
    $modal.find("#submit").trigger("click");

    expect(emit).toHaveBeenCalledWith({ event: UI_EVENTS.UI_LOGIN_SUBMIT });
    expect(emit).toHaveBeenCalledTimes(1);
  });

  it("emits ui_validation_error with form=login on 400 errorCode response", async () => {
    const { emit } = await import("../../lib/metrics-client.js");
    const mockDeferred = createMockJqXHR();
    vi.spyOn($, "ajax").mockReturnValue(mockDeferred);

    const $modal = $("#LoginModal");
    initLoginForm($modal);
    $modal.find("#submit").trigger("click");

    const fakeXhr = {
      status: 400,
      responseJSON: { errorCode: 2, message: "Invalid" },
      getResponseHeader: vi.fn(),
    };
    mockDeferred.reject(fakeXhr, "error", "Bad Request");

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_VALIDATION_ERROR,
      form: VALIDATION_FORM.LOGIN,
    });
  });
});

describe("login-form double-submit guard", () => {
  beforeEach(() => {
    document.body.innerHTML = LOGIN_MODAL_HTML;
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("disables #submit while the login request is in flight", () => {
    const mockDeferred = createMockJqXHR();
    vi.spyOn($, "ajax").mockReturnValue(mockDeferred);

    const $modal = $("#LoginModal");
    initLoginForm($modal);
    expect($modal.find("#submit").attr("disabled")).toBeUndefined();
    expect($modal.find("#submit").attr("aria-busy")).toBeUndefined();

    $modal.find("#submit").trigger("click");

    expect($modal.find("#submit").attr("disabled")).toBe("disabled");
    expect($modal.find("#submit").attr("aria-busy")).toBe("true");
  });

  it("leaves #submit disabled (and aria-busy) on errorCode=1 (email-not-validated)", () => {
    const mockDeferred = createMockJqXHR();
    vi.spyOn($, "ajax").mockReturnValue(mockDeferred);

    const $modal = $("#LoginModal");
    initLoginForm($modal);
    $modal.find("#submit").trigger("click");

    // disabled-leftover is intentional: handleUserHasAccountNotEmailValidated
    // removes .modal-footer so re-enable in case 1 would be a silent no-op
    // (jQuery set is empty); aria-busy is similarly left set.
    mockDeferred.reject(
      {
        status: 401,
        responseJSON: { errorCode: 1, message: "Email not validated" },
        getResponseHeader: vi.fn(),
      },
      "error",
      "Unauthorized",
    );

    expect($modal.find("#submit").attr("disabled")).toBe("disabled");
    expect($modal.find("#submit").attr("aria-busy")).toBe("true");
  });

  it("re-enables #submit on a 400 errorCode=2 failure", () => {
    const mockDeferred = createMockJqXHR();
    vi.spyOn($, "ajax").mockReturnValue(mockDeferred);

    const $modal = $("#LoginModal");
    initLoginForm($modal);
    $modal.find("#submit").trigger("click");
    expect($modal.find("#submit").attr("disabled")).toBe("disabled");

    mockDeferred.reject(
      {
        status: 400,
        responseJSON: {
          errorCode: 2,
          message: "Invalid",
          errors: { password: ["Invalid"] },
        },
        getResponseHeader: vi.fn(),
      },
      "error",
      "Bad Request",
    );

    // handleImproperFormErrors is mocked (no-op DOM) in this test file;
    // only the removeAttr calls are under test here.
    expect($modal.find("#submit").attr("disabled")).toBeUndefined();
    expect($modal.find("#submit").attr("aria-busy")).toBeUndefined();
  });

  it("re-enables #submit when failure JSON has no errorCode", () => {
    const mockDeferred = createMockJqXHR();
    vi.spyOn($, "ajax").mockReturnValue(mockDeferred);

    const $modal = $("#LoginModal");
    initLoginForm($modal);
    $modal.find("#submit").trigger("click");
    expect($modal.find("#submit").attr("disabled")).toBe("disabled");

    mockDeferred.reject(
      {
        status: 500,
        responseJSON: { message: "Server error" },
        getResponseHeader: vi.fn(),
      },
      "error",
      "Server Error",
    );

    expect($modal.find("#submit").attr("disabled")).toBeUndefined();
    expect($modal.find("#submit").attr("aria-busy")).toBeUndefined();
  });
});
