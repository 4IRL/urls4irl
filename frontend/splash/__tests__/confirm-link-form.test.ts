import {
  createMockJqXHRChainable,
  createMockXhr,
} from "../../__tests__/helpers/mock-jquery.js";
import { ajaxCall, is429Handled } from "../../lib/ajax.js";
import { showSplashModalAlertBanner } from "../init.js";
import { initConfirmLinkForm } from "../confirm-link-form.js";

vi.mock("../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));

vi.mock("../../lib/page-utils.js", () => ({
  showNewPageOnAJAXHTMLResponse: vi.fn(),
}));

vi.mock("../init.js", () => ({
  showSplashModalAlertBanner: vi.fn(),
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

const ACTION_URL = "/oauth/link/confirm";
const REDIRECT_URL = "/home";
const FAILURE_MESSAGE = "Incorrect password.";

// Minimal HTML — only the DOM nodes the module under test actually queries.
const CONFIRM_LINK_MODAL_HTML = `
  <div class="modal fade show" id="SplashModal">
    <form id="ModalForm" method="POST" data-modal-type="confirm-link" action="${ACTION_URL}">
      <input id="password" type="password" value="correcthorse" />
      <input id="submit" type="submit" />
      <div id="SplashModalAlertBanner" class="alert alert-banner-splash-modal-hide"></div>
    </form>
  </div>
`;

const CONFIRM_LINK_NO_PASSWORD_MODAL_HTML = `
  <div class="modal fade show" id="SplashModal">
    <form id="ModalForm" method="POST" data-modal-type="confirm-link" action="${ACTION_URL}">
      <a id="ConfirmLinkContinueWithGoogle" class="confirm-link-provider-button" href="/oauth/google/login"></a>
      <div id="SplashModalAlertBanner" class="alert alert-banner-splash-modal-hide"></div>
    </form>
  </div>
`;

describe("confirm-link-form", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(is429Handled).mockReturnValue(false);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("POSTs the entered password to the form action and navigates to the redirect URL on success", () => {
    document.body.innerHTML = CONFIRM_LINK_MODAL_HTML;
    const assignSpy = vi
      .spyOn(window.location, "assign")
      .mockImplementation(() => {});
    const successXhr = createMockXhr({ status: 200 });
    const chainable = createMockJqXHRChainable({
      done: (callback: unknown) => {
        (
          callback as (
            response: unknown,
            _textStatus: unknown,
            xhr: JQuery.jqXHR,
          ) => void
        )(
          { status: "Success", redirectUrl: REDIRECT_URL },
          "success",
          successXhr,
        );
      },
    });
    vi.mocked(ajaxCall).mockReturnValue(chainable as unknown as JQuery.jqXHR);

    const $modal = $("#SplashModal");
    initConfirmLinkForm($modal);
    $modal.find("form").trigger("submit");

    expect(vi.mocked(ajaxCall)).toHaveBeenCalledWith("post", ACTION_URL, {
      password: "correcthorse",
    });
    expect(assignSpy).toHaveBeenCalledWith(REDIRECT_URL);

    assignSpy.mockRestore();
  });

  it("renders the error message into the splash modal alert banner on failure", () => {
    document.body.innerHTML = CONFIRM_LINK_MODAL_HTML;
    const failedXhr = createMockXhr({
      status: 400,
      responseJSON: {
        status: "Failure",
        message: FAILURE_MESSAGE,
        errorCode: 5,
        errors: { password: [FAILURE_MESSAGE] },
      },
    });
    const chainable = createMockJqXHRChainable({
      fail: (callback: unknown) => {
        (callback as (xhr: JQuery.jqXHR) => void)(failedXhr);
      },
    });
    vi.mocked(ajaxCall).mockReturnValue(chainable as unknown as JQuery.jqXHR);

    const $modal = $("#SplashModal");
    initConfirmLinkForm($modal);
    $modal.find("form").trigger("submit");

    expect(showSplashModalAlertBanner).toHaveBeenCalledWith(
      $modal,
      FAILURE_MESSAGE,
      "danger",
    );
  });

  it("does nothing further when a failure was already handled as a 429", () => {
    document.body.innerHTML = CONFIRM_LINK_MODAL_HTML;
    vi.mocked(is429Handled).mockReturnValue(true);
    const failedXhr = createMockXhr({ status: 429 });
    const chainable = createMockJqXHRChainable({
      fail: (callback: unknown) => {
        (callback as (xhr: JQuery.jqXHR) => void)(failedXhr);
      },
    });
    vi.mocked(ajaxCall).mockReturnValue(chainable as unknown as JQuery.jqXHR);

    const $modal = $("#SplashModal");
    initConfirmLinkForm($modal);
    $modal.find("form").trigger("submit");

    expect(showSplashModalAlertBanner).not.toHaveBeenCalled();
  });

  it("is a no-op for submit when the form has no #password input (OAuth-only variant)", () => {
    document.body.innerHTML = CONFIRM_LINK_NO_PASSWORD_MODAL_HTML;

    const $modal = $("#SplashModal");
    initConfirmLinkForm($modal);
    $modal.find("form").trigger("submit");

    expect(vi.mocked(ajaxCall)).not.toHaveBeenCalled();
  });
});
