import { createMockJqXHR } from "../../__tests__/helpers/mock-jquery.js";
import { initRegisterConfirmationModal } from "../register-confirmation-form.js";
import { switchModal, showSplashModalAlertBanner } from "../init.js";

vi.mock("../init.js", () => ({
  switchModal: vi.fn(),
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

const CONFIRMATION_MODAL_HTML = `
  <div class="modal fade" id="RegisterConfirmationModal">
    <div id="SplashModalAlertBanner" class="alert" role="alert"></div>
    <a id="ResendRegistrationEmail" href="#" class="splash-page-links"></a>
    <button id="BackToLoginFromConfirmation"></button>
  </div>
`;

describe("register-confirmation-form", () => {
  beforeEach(() => {
    document.body.innerHTML = CONFIRMATION_MODAL_HTML;
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("Back to login switches to #LoginModal", () => {
    const $modal = $("#RegisterConfirmationModal");
    initRegisterConfirmationModal($modal);

    $modal.find("#BackToLoginFromConfirmation").trigger("click");

    expect(switchModal).toHaveBeenCalledWith($modal, "#LoginModal");
  });

  it("Resend POSTs to resendRegistrationEmail with the stashed email and a 10s timeout", () => {
    const mockDeferred = createMockJqXHR();
    const ajaxSpy = vi.spyOn($, "ajax").mockReturnValue(mockDeferred);

    const $modal = $("#RegisterConfirmationModal");
    $modal.data("registerEmail", "user@test.com");
    initRegisterConfirmationModal($modal);

    $modal.find("#ResendRegistrationEmail").trigger("click");

    expect(ajaxSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        url: "/resend-registration-email",
        type: "POST",
        contentType: "application/json",
        data: JSON.stringify({ email: "user@test.com" }),
        timeout: 10000,
      }),
    );
  });

  it("shows the loading state on click and clears it on settle", () => {
    const mockDeferred = createMockJqXHR();
    vi.spyOn($, "ajax").mockReturnValue(mockDeferred);

    const $modal = $("#RegisterConfirmationModal");
    $modal.data("registerEmail", "user@test.com");
    initRegisterConfirmationModal($modal);

    const $link = $modal.find("#ResendRegistrationEmail");
    $link.trigger("click");

    expect($link.hasClass("disabled")).toBe(true);
    expect($link.attr("aria-busy")).toBe("true");
    expect($link.attr("aria-disabled")).toBe("true");

    mockDeferred.resolve({ status: "Success", message: "Almost there" });

    expect($link.hasClass("disabled")).toBe(false);
    expect($link.attr("aria-busy")).toBeUndefined();
    expect($link.attr("aria-disabled")).toBeUndefined();
  });

  it("re-shows the success banner from the response on done", () => {
    const mockDeferred = createMockJqXHR();
    vi.spyOn($, "ajax").mockReturnValue(mockDeferred);

    const $modal = $("#RegisterConfirmationModal");
    $modal.data("registerEmail", "user@test.com");
    initRegisterConfirmationModal($modal);
    $modal.find("#ResendRegistrationEmail").trigger("click");

    mockDeferred.resolve({ status: "Success", message: "Almost there" });

    expect(showSplashModalAlertBanner).toHaveBeenCalledWith(
      $modal,
      "Almost there",
      "success",
    );
  });

  it("re-shows the stashed confirmation text on a network/timeout failure (status 0)", () => {
    const mockDeferred = createMockJqXHR();
    vi.spyOn($, "ajax").mockReturnValue(mockDeferred);

    const $modal = $("#RegisterConfirmationModal");
    $modal
      .data("registerEmail", "user@test.com")
      .data("confirmMessage", "Check your email");
    initRegisterConfirmationModal($modal);
    $modal.find("#ResendRegistrationEmail").trigger("click");

    mockDeferred.reject({ status: 0 }, "error", "Network");

    expect(showSplashModalAlertBanner).toHaveBeenCalledWith(
      $modal,
      "Check your email",
      "success",
    );
  });

  it("bails without touching the banner when the 429 handler already fired", () => {
    const mockDeferred = createMockJqXHR();
    vi.spyOn($, "ajax").mockReturnValue(mockDeferred);

    const $modal = $("#RegisterConfirmationModal");
    $modal
      .data("registerEmail", "user@test.com")
      .data("confirmMessage", "Check your email");
    initRegisterConfirmationModal($modal);
    const $link = $modal.find("#ResendRegistrationEmail");
    $link.trigger("click");

    // The global $.ajaxPrefilter owns the 429 case (page replacement); the
    // handler must early-return and not write to the now-stale DOM.
    mockDeferred.reject(
      { status: 429, _429Handled: true },
      "error",
      "Too Many Requests",
    );

    expect(showSplashModalAlertBanner).not.toHaveBeenCalled();
    // Link is left in its in-flight state — resetResendLink is not reached.
    expect($link.hasClass("disabled")).toBe(true);
  });

  it("surfaces an error banner (not success) on a generic HTTP failure", () => {
    const mockDeferred = createMockJqXHR();
    vi.spyOn($, "ajax").mockReturnValue(mockDeferred);

    const $modal = $("#RegisterConfirmationModal");
    $modal
      .data("registerEmail", "user@test.com")
      .data("confirmMessage", "Check your email");
    initRegisterConfirmationModal($modal);
    $modal.find("#ResendRegistrationEmail").trigger("click");

    // A real HTTP error (e.g. 500, or 400 stale CSRF) must NOT be rendered as
    // a success banner.
    mockDeferred.reject({ status: 500 }, "error", "Server Error");

    expect(showSplashModalAlertBanner).toHaveBeenCalledWith(
      $modal,
      "Unable to process request...",
      "danger",
    );
  });

  it("clears a lingering disabled/busy resend state on show.bs.modal reopen", () => {
    const $modal = $("#RegisterConfirmationModal");
    initRegisterConfirmationModal($modal);

    // Simulate a stuck busy state left over from a prior resend that never
    // settled (e.g. the modal was dismissed mid-request), independent of the
    // settle-based reset path.
    const $link = $modal.find("#ResendRegistrationEmail");
    $link
      .addClass("disabled")
      .attr("aria-disabled", "true")
      .attr("aria-busy", "true");

    $modal.trigger("show.bs.modal");

    expect($link.hasClass("disabled")).toBe(false);
    expect($link.attr("aria-disabled")).toBeUndefined();
    expect($link.attr("aria-busy")).toBeUndefined();
  });
});
