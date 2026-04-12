import { showNewPageOnAJAXHTMLResponse } from "../../lib/page-utils.js";
import { initResetPasswordForm } from "../reset-password-form.js";

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

// Minimal HTML — only the DOM nodes the function under test actually queries.
// This decouples tests from template markup and avoids maintaining HTML in two places.
const RESET_PASSWORD_MODAL_HTML = `
  <div class="modal fade" id="ResetPasswordModal">
    <input id="newPassword" class="form-control" value="newpass123" />
    <input id="confirmNewPassword" class="form-control" value="newpass123" />
    <button id="submit" type="submit"></button>
  </div>
`;

describe("reset-password-form 429 HTML response", () => {
  beforeEach(() => {
    document.body.innerHTML = RESET_PASSWORD_MODAL_HTML;
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("calls showNewPageOnAJAXHTMLResponse when server returns 429 with HTML content", () => {
    const mockDeferred = $.Deferred();
    vi.spyOn($, "ajax").mockReturnValue(mockDeferred);

    const $modal = $("#ResetPasswordModal");
    initResetPasswordForm($modal);
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
    vi.spyOn($, "ajax").mockReturnValue(mockDeferred);

    const $modal = $("#ResetPasswordModal");
    initResetPasswordForm($modal);
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
