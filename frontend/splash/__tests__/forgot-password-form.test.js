import { showNewPageOnAJAXHTMLResponse } from "../../lib/page-utils.js";
import { initForgotPasswordForm } from "../forgot-password-form.js";

vi.mock("../../lib/page-utils.js", () => ({
  showNewPageOnAJAXHTMLResponse: vi.fn(),
}));

vi.mock("../init.js", () => ({
  showSplashModalAlertBanner: vi.fn(),
  hideSplashModalAlertBanner: vi.fn(),
  handleImproperFormErrors: vi.fn(),
  switchModal: vi.fn(),
}));

vi.mock("../../lib/globals.js", () => ({
  $: window.jQuery,
  jQuery: window.jQuery,
  bootstrap: window.bootstrap,
}));

vi.mock("../../lib/config.js", () => {
  const configScript = document.getElementById("app-config");
  const config = JSON.parse(configScript.textContent);
  return { APP_CONFIG: config };
});

const $ = window.jQuery;

const FORGOT_PASSWORD_MODAL_HTML = `
  <div class="modal fade" id="ForgotPasswordModal">
    <div class="modal-content">
      <div id="SplashModalAlertBanner" class="alert-banner-splash-modal-hide"></div>
      <form id="ModalForm">
        <input id="email" class="form-control" value="test@test.com" />
        <button id="submit" type="submit"></button>
      </form>
      <div id="ToLoginFromForgotPassword">Back</div>
    </div>
  </div>
`;

describe("forgot-password-form 429 HTML response", () => {
  let ajaxSpy;

  beforeEach(() => {
    document.body.innerHTML = FORGOT_PASSWORD_MODAL_HTML;
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("calls showNewPageOnAJAXHTMLResponse when server returns 429 with HTML content", () => {
    const mockDeferred = $.Deferred();
    ajaxSpy = vi.spyOn($, "ajax").mockReturnValue(mockDeferred);

    const $modal = $("#ForgotPasswordModal");
    initForgotPasswordForm($modal);
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
    const mockDeferred = $.Deferred();
    ajaxSpy = vi.spyOn($, "ajax").mockReturnValue(mockDeferred);

    const $modal = $("#ForgotPasswordModal");
    initForgotPasswordForm($modal);
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
