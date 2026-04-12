import {
  createLogoutOnExit,
  switchModal,
  displayFormErrors,
  showSplashModalAlertBanner,
  hideSplashModalAlertBanner,
  resetModalFormState,
  handleImproperFormErrors,
  handleUserHasAccountNotEmailValidated,
  emailValidationModalOpener,
} from "../init.js";
import { initEmailValidationForm } from "../email-validation-form.js";

vi.mock("../navbar.js", () => ({
  NAVBAR_TOGGLER: { toggler: { hide: vi.fn() } },
}));

vi.mock("../login-form.js", () => ({
  initLoginForm: vi.fn(),
}));

vi.mock("../register-form.js", () => ({
  initRegisterForm: vi.fn(),
}));

vi.mock("../forgot-password-form.js", () => ({
  initForgotPasswordForm: vi.fn(),
}));

vi.mock("../email-validation-form.js", () => ({
  initEmailValidationForm: vi.fn(),
  SEND_INITIAL_EMAIL: true,
  SKIP_INITIAL_EMAIL: false,
}));

vi.mock("../../lib/page-utils.js", () => ({
  showNewPageOnAJAXHTMLResponse: vi.fn(),
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

// Minimal HTML fixtures — each test builds only the DOM nodes its function
// under test actually queries, rather than replicating full modal templates.
// This decouples tests from template markup and avoids maintaining HTML in two places.

function modalShell(id: string, innerHTML: string = ""): string {
  return `<div class="modal fade" id="${id}">${innerHTML}</div>`;
}

const ALERT_BANNER = `<div id="SplashModalAlertBanner" class="alert-banner-splash-modal-hide"></div>`;

interface MockBootstrapModal {
  show: ReturnType<typeof vi.fn>;
  hide: ReturnType<typeof vi.fn>;
}

describe("createLogoutOnExit", () => {
  let ajaxGetSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    ajaxGetSpy = vi.spyOn($, "get").mockReturnValue({
      always: vi.fn((callback) => {
        callback();
        return { always: vi.fn() };
      }),
    });
    vi.spyOn(window.location, "replace").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns a closure that calls $.get(logout) and redirects to /", () => {
    const logoutFn = createLogoutOnExit();
    logoutFn();

    expect(ajaxGetSpy).toHaveBeenCalledWith("/logout");
    expect(window.location.replace).toHaveBeenCalledWith("/");
  });

  it("returns independent closures on each call", () => {
    const firstClosure = createLogoutOnExit();
    const secondClosure = createLogoutOnExit();

    expect(firstClosure).not.toBe(secondClosure);
  });
});

describe("switchModal", () => {
  let mockFromModal: MockBootstrapModal;
  let mockToModal: MockBootstrapModal;

  beforeEach(() => {
    document.body.innerHTML =
      modalShell("LoginModal") + modalShell("RegisterModal");
    mockFromModal = {
      show: vi.fn(),
      hide: vi.fn(),
    };
    mockToModal = {
      show: vi.fn(),
      hide: vi.fn(),
    };
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("hides from-modal and shows to-modal after hidden.bs.modal event", () => {
    vi.spyOn(window.bootstrap.Modal, "getInstance").mockReturnValue(
      mockFromModal,
    );
    vi.spyOn(window.bootstrap.Modal, "getOrCreateInstance").mockReturnValue(
      mockToModal,
    );

    switchModal($("#LoginModal"), "#RegisterModal");

    expect(mockFromModal.hide).toHaveBeenCalled();
    expect(mockToModal.show).not.toHaveBeenCalled();

    // Simulate the hidden.bs.modal event firing
    $("#LoginModal").trigger("hidden.bs.modal");

    expect(mockToModal.show).toHaveBeenCalled();
  });

  it("shows to-modal directly when from-modal has no Bootstrap instance", () => {
    vi.spyOn(window.bootstrap.Modal, "getInstance").mockReturnValue(null);
    vi.spyOn(window.bootstrap.Modal, "getOrCreateInstance").mockReturnValue(
      mockToModal,
    );

    switchModal($("#LoginModal"), "#RegisterModal");

    expect(mockToModal.show).toHaveBeenCalled();
  });

  it("registers a one-time hidden.bs.modal listener on from-modal", () => {
    vi.spyOn(window.bootstrap.Modal, "getInstance").mockReturnValue(
      mockFromModal,
    );
    vi.spyOn(window.bootstrap.Modal, "getOrCreateInstance").mockReturnValue(
      mockToModal,
    );

    switchModal($("#LoginModal"), "#RegisterModal");

    // First trigger shows the to-modal
    $("#LoginModal").trigger("hidden.bs.modal");
    expect(mockToModal.show).toHaveBeenCalledTimes(1);

    // Second trigger should NOT show again (one-time listener)
    $("#LoginModal").trigger("hidden.bs.modal");
    expect(mockToModal.show).toHaveBeenCalledTimes(1);
  });
});

describe("displayFormErrors", () => {
  beforeEach(() => {
    document.body.innerHTML =
      modalShell("LoginModal", `<input id="username" class="form-control" />`) +
      modalShell(
        "RegisterModal",
        `<input id="username" class="form-control" />`,
      );
  });

  it("adds is-invalid class and inserts error message after the matching input", () => {
    const $modal = $("#LoginModal");

    displayFormErrors($modal, "username", "Username is required");

    const usernameInput = $modal.find("#username");
    expect(usernameInput.hasClass("is-invalid")).toBe(true);

    const feedback = $modal.find("#username + .invalid-feedback");
    expect(feedback.length).toBe(1);
    expect(feedback.text()).toBe("Username is required");
  });

  it("scopes to the correct modal and does not affect other modals", () => {
    const $loginModal = $("#LoginModal");
    const $registerModal = $("#RegisterModal");

    displayFormErrors($loginModal, "username", "Login error");

    expect($loginModal.find("#username").hasClass("is-invalid")).toBe(true);
    expect($registerModal.find("#username").hasClass("is-invalid")).toBe(false);
  });

  it("does not throw when key does not match any input", () => {
    const $modal = $("#LoginModal");

    expect(() => {
      displayFormErrors($modal, "nonexistent", "Error message");
    }).not.toThrow();

    expect($modal.find(".invalid-feedback").length).toBe(0);
  });
});

describe("handleImproperFormErrors", () => {
  beforeEach(() => {
    document.body.innerHTML = modalShell(
      "LoginModal",
      `<input id="username" class="form-control" />`,
    );
  });

  it("returns early without inserting invalid-feedback when errors is null", () => {
    const $modal = $("#LoginModal");
    // Pre-populate DOM state that handleImproperFormErrors should still clear
    $modal.find("#username").addClass("is-invalid");
    $modal.find("#username").after('<div class="invalid-feedback">Stale</div>');

    const errorResponse = {
      status: "Failure" as const,
      message: "Something went wrong",
      errorCode: null,
      errors: null,
      details: null,
    };

    const result = handleImproperFormErrors($modal, errorResponse);

    // The early-return still performs the cleanup at the top of the function
    expect($modal.find(".form-control.is-invalid").length).toBe(0);
    expect($modal.find(".invalid-feedback").length).toBe(0);
    // Returns undefined (void)
    expect(result).toBeUndefined();
  });
});

describe("showSplashModalAlertBanner", () => {
  beforeEach(() => {
    document.body.innerHTML =
      modalShell("LoginModal", ALERT_BANNER) +
      modalShell("RegisterModal", ALERT_BANNER);
  });

  it("shows alert banner with correct message and category class within modal scope", () => {
    const $modal = $("#LoginModal");

    showSplashModalAlertBanner($modal, "Login failed", "danger");

    const banner = $modal.find("#SplashModalAlertBanner");
    expect(banner.hasClass("alert-banner-splash-modal-display")).toBe(true);
    expect(banner.hasClass("alert-banner-splash-modal-hide")).toBe(false);
    expect(banner.hasClass("alert-danger")).toBe(true);
    expect(banner.text()).toBe("Login failed");
  });

  it("does not affect alert banners in other modals", () => {
    const $loginModal = $("#LoginModal");
    const $registerModal = $("#RegisterModal");

    showSplashModalAlertBanner($loginModal, "Error", "danger");

    const registerBanner = $registerModal.find("#SplashModalAlertBanner");
    expect(registerBanner.hasClass("alert-banner-splash-modal-hide")).toBe(
      true,
    );
    expect(registerBanner.hasClass("alert-banner-splash-modal-display")).toBe(
      false,
    );
  });
});

describe("hideSplashModalAlertBanner", () => {
  beforeEach(() => {
    document.body.innerHTML = modalShell("LoginModal", ALERT_BANNER);
  });

  it("hides the alert banner and removes alert category classes", () => {
    const $modal = $("#LoginModal");
    const banner = $modal.find("#SplashModalAlertBanner");

    // First show it
    banner
      .removeClass("alert-banner-splash-modal-hide")
      .addClass("alert-banner-splash-modal-display alert-danger");

    hideSplashModalAlertBanner($modal);

    expect(banner.hasClass("alert-banner-splash-modal-hide")).toBe(true);
    expect(banner.hasClass("alert-banner-splash-modal-display")).toBe(false);
    expect(banner.hasClass("alert-danger")).toBe(false);
  });
});

describe("resetModalFormState", () => {
  beforeEach(() => {
    document.body.innerHTML = modalShell(
      "LoginModal",
      ALERT_BANNER + `<input id="username" class="form-control" />`,
    );
  });

  it("removes invalid-feedback elements, strips is-invalid class, and hides alert banner", () => {
    const $modal = $("#LoginModal");

    // Add invalid state
    $modal.find(".form-control").addClass("is-invalid");
    $modal.find("#username").after('<div class="invalid-feedback">Error</div>');
    const banner = $modal.find("#SplashModalAlertBanner");
    banner
      .removeClass("alert-banner-splash-modal-hide")
      .addClass("alert-banner-splash-modal-display alert-danger");

    resetModalFormState($modal);

    expect($modal.find(".invalid-feedback").length).toBe(0);
    expect($modal.find(".form-control.is-invalid").length).toBe(0);
    expect(banner.hasClass("alert-banner-splash-modal-hide")).toBe(true);
    expect(banner.hasClass("alert-banner-splash-modal-display")).toBe(false);
  });
});

describe("initEmailValidationForm", () => {
  beforeEach(() => {
    document.body.innerHTML = modalShell("EmailValidationModal");
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("does NOT bind a hide.bs.modal logout handler", async () => {
    const { initEmailValidationForm: realInitEmailValidationForm } =
      await vi.importActual<typeof import("../email-validation-form.js")>(
        "../email-validation-form.js",
      );
    const $modal = $("#EmailValidationModal");
    const ajaxGetSpy = vi.spyOn($, "get");

    realInitEmailValidationForm($modal, false);

    // Trigger hide.bs.modal — should NOT call $.get(logout)
    $modal.trigger("hide.bs.modal");

    expect(ajaxGetSpy).not.toHaveBeenCalledWith("/logout");
  });
});

describe("handleUserHasAccountNotEmailValidated", () => {
  let ajaxGetSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    document.body.innerHTML =
      modalShell(
        "LoginModal",
        ALERT_BANNER +
          `<div class="to-forgot-password"></div>` +
          `<div class="register-to-login-footer"></div>` +
          `<div class="modal-footer"></div>`,
      ) + modalShell("EmailValidationModal");
    ajaxGetSpy = vi.spyOn($, "get").mockReturnValue({
      always: vi.fn((callback) => {
        callback();
        return { always: vi.fn() };
      }),
    });
    vi.spyOn(window.location, "replace").mockImplementation(() => {});
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("binds logoutOnExit to source modal via .one() — closing fires logout and redirect", () => {
    handleUserHasAccountNotEmailValidated(
      $("#LoginModal"),
      "Please validate your email",
    );

    // Trigger hide.bs.modal on the source modal
    $("#LoginModal").trigger("hide.bs.modal");

    expect(ajaxGetSpy).toHaveBeenCalledWith("/logout");
    expect(window.location.replace).toHaveBeenCalledWith("/");
  });

  it("logoutOnExit auto-unbinds after one firing (.one() behavior)", () => {
    handleUserHasAccountNotEmailValidated(
      $("#LoginModal"),
      "Please validate your email",
    );

    $("#LoginModal").trigger("hide.bs.modal");
    ajaxGetSpy.mockClear();

    // Second trigger should NOT fire logout again
    $("#LoginModal").trigger("hide.bs.modal");
    expect(ajaxGetSpy).not.toHaveBeenCalled();
  });

  it("removes form controls, forgot-password link, footer from source modal", () => {
    handleUserHasAccountNotEmailValidated(
      $("#LoginModal"),
      "Please validate your email",
    );

    const $modal = $("#LoginModal");
    expect($modal.find(".to-forgot-password").length).toBe(0);
    expect($modal.find(".register-to-login-footer").length).toBe(0);
    expect($modal.find(".modal-footer").length).toBe(0);
  });

  it("shows validate-my-email button in alert banner", () => {
    handleUserHasAccountNotEmailValidated(
      $("#LoginModal"),
      "Please validate your email",
    );

    const $modal = $("#LoginModal");
    const banner = $modal.find("#SplashModalAlertBanner");
    expect(banner.hasClass("alert-info")).toBe(true);
    expect(banner.hasClass("alert-banner-splash-modal-show")).toBe(true);
    expect(banner.find("button").text()).toBe("Validate My Email");
  });

  it("clicking validate-my-email unbinds logoutOnExit from source, switches to email validation modal", () => {
    const mockFromModal = { hide: vi.fn() };
    const mockToModal = { show: vi.fn() };

    vi.spyOn(window.bootstrap.Modal, "getInstance").mockReturnValue(
      mockFromModal,
    );
    vi.spyOn(window.bootstrap.Modal, "getOrCreateInstance").mockReturnValue(
      mockToModal,
    );

    handleUserHasAccountNotEmailValidated(
      $("#LoginModal"),
      "Please validate your email",
    );

    // Click the validate-my-email button
    const $modal = $("#LoginModal");
    $modal.find("#SplashModalAlertBanner button").trigger("click");

    // switchModal was called — from-modal should be hidden
    expect(mockFromModal.hide).toHaveBeenCalled();

    // initEmailValidationForm should be called with #EmailValidationModal
    expect(initEmailValidationForm).toHaveBeenCalledWith(
      expect.any(Object),
      true,
    );
  });

  it("after clicking validate-my-email, logoutOnExit is bound to EmailValidationModal", () => {
    vi.spyOn(window.bootstrap.Modal, "getInstance").mockReturnValue(null);
    vi.spyOn(window.bootstrap.Modal, "getOrCreateInstance").mockReturnValue({
      show: vi.fn(),
    });

    handleUserHasAccountNotEmailValidated(
      $("#LoginModal"),
      "Please validate your email",
    );

    // Click validate-my-email — this unbinds from source and binds to email validation modal
    $("#LoginModal").find("#SplashModalAlertBanner button").trigger("click");

    // Source modal hide should NOT trigger logout anymore
    $("#LoginModal").trigger("hide.bs.modal");
    expect(ajaxGetSpy).not.toHaveBeenCalledWith("/logout");

    // EmailValidationModal hide should trigger logout
    $("#EmailValidationModal").trigger("hide.bs.modal");
    expect(ajaxGetSpy).toHaveBeenCalledWith("/logout");
    expect(window.location.replace).toHaveBeenCalledWith("/");
  });
});

describe("emailValidationModalOpener", () => {
  beforeEach(() => {
    document.body.innerHTML =
      modalShell("RegisterModal") + modalShell("EmailValidationModal");
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("calls switchModal from source to EmailValidationModal", () => {
    const mockFromModal = { hide: vi.fn() };
    const mockToModal = { show: vi.fn() };
    vi.spyOn(window.bootstrap.Modal, "getInstance").mockReturnValue(
      mockFromModal,
    );
    vi.spyOn(window.bootstrap.Modal, "getOrCreateInstance").mockReturnValue(
      mockToModal,
    );

    emailValidationModalOpener($("#RegisterModal"));

    expect(mockFromModal.hide).toHaveBeenCalled();
  });

  it("calls initEmailValidationForm with EmailValidationModal and sendInitialEmail=true", () => {
    vi.spyOn(window.bootstrap.Modal, "getInstance").mockReturnValue(null);
    vi.spyOn(window.bootstrap.Modal, "getOrCreateInstance").mockReturnValue({
      show: vi.fn(),
    });

    emailValidationModalOpener($("#RegisterModal"));

    expect(initEmailValidationForm).toHaveBeenCalledWith(
      expect.any(Object),
      true,
    );
  });

  it("registers a one-time hide.bs.modal logout handler on EmailValidationModal", () => {
    vi.spyOn(window.bootstrap.Modal, "getInstance").mockReturnValue(null);
    vi.spyOn(window.bootstrap.Modal, "getOrCreateInstance").mockReturnValue({
      show: vi.fn(),
    });
    const ajaxGetSpy = vi.spyOn($, "get").mockReturnValue({
      always: vi.fn((callback) => {
        callback();
        return { always: vi.fn() };
      }),
    });
    vi.spyOn(window.location, "replace").mockImplementation(() => {});

    emailValidationModalOpener($("#RegisterModal"));

    // Trigger hide on EmailValidationModal
    $("#EmailValidationModal").trigger("hide.bs.modal");

    expect(ajaxGetSpy).toHaveBeenCalledWith("/logout");
    expect(window.location.replace).toHaveBeenCalledWith("/");
  });
});

describe("show.bs.modal reset handlers", () => {
  beforeEach(() => {
    document.body.innerHTML =
      modalShell(
        "LoginModal",
        ALERT_BANNER +
          `<input id="username" class="form-control" /><button id="submit"></button>`,
      ) +
      modalShell(
        "RegisterModal",
        ALERT_BANNER +
          `<input id="username" class="form-control" /><button id="submit"></button>`,
      ) +
      modalShell(
        "ForgotPasswordModal",
        ALERT_BANNER +
          `<input id="email" class="form-control" /><button id="submit"></button>`,
      ) +
      modalShell(
        "EmailValidationModal",
        ALERT_BANNER + `<button id="submit"></button>`,
      );
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("login form show.bs.modal removes invalid-feedback and is-invalid, hides alert banner", async () => {
    const { initLoginForm } =
      await vi.importActual<typeof import("../login-form.js")>(
        "../login-form.js",
      );
    const $modal = $("#LoginModal");

    // Add some invalid state
    $modal.find(".form-control").addClass("is-invalid");
    $modal.find("#username").after('<div class="invalid-feedback">Error</div>');
    const banner = $modal.find("#SplashModalAlertBanner");
    banner
      .removeClass("alert-banner-splash-modal-hide")
      .addClass("alert-banner-splash-modal-display alert-danger");

    initLoginForm($modal);
    $modal.trigger("show.bs.modal");

    expect($modal.find(".invalid-feedback").length).toBe(0);
    expect($modal.find(".form-control.is-invalid").length).toBe(0);
    expect(banner.hasClass("alert-banner-splash-modal-hide")).toBe(true);
    expect(banner.hasClass("alert-banner-splash-modal-display")).toBe(false);
  });

  it("register form show.bs.modal removes invalid-feedback and is-invalid, hides alert banner", async () => {
    const { initRegisterForm } = await vi.importActual<
      typeof import("../register-form.js")
    >("../register-form.js");
    const $modal = $("#RegisterModal");

    $modal.find(".form-control").addClass("is-invalid");
    $modal.find("#username").after('<div class="invalid-feedback">Error</div>');
    const banner = $modal.find("#SplashModalAlertBanner");
    banner
      .removeClass("alert-banner-splash-modal-hide")
      .addClass("alert-banner-splash-modal-display alert-danger");

    initRegisterForm($modal);
    $modal.trigger("show.bs.modal");

    expect($modal.find(".invalid-feedback").length).toBe(0);
    expect($modal.find(".form-control.is-invalid").length).toBe(0);
    expect(banner.hasClass("alert-banner-splash-modal-hide")).toBe(true);
    expect(banner.hasClass("alert-banner-splash-modal-display")).toBe(false);
  });

  it("forgot password form show.bs.modal removes invalid-feedback and is-invalid, hides alert banner", async () => {
    const { initForgotPasswordForm } = await vi.importActual<
      typeof import("../forgot-password-form.js")
    >("../forgot-password-form.js");
    const $modal = $("#ForgotPasswordModal");

    $modal.find(".form-control").addClass("is-invalid");
    $modal.find("#email").after('<div class="invalid-feedback">Error</div>');
    const banner = $modal.find("#SplashModalAlertBanner");
    banner
      .removeClass("alert-banner-splash-modal-hide")
      .addClass("alert-banner-splash-modal-display alert-danger");

    initForgotPasswordForm($modal);
    $modal.trigger("show.bs.modal");

    expect($modal.find(".invalid-feedback").length).toBe(0);
    expect($modal.find(".form-control.is-invalid").length).toBe(0);
    expect(banner.hasClass("alert-banner-splash-modal-hide")).toBe(true);
    expect(banner.hasClass("alert-banner-splash-modal-display")).toBe(false);
  });

  it("email validation form show.bs.modal removes invalid-feedback and is-invalid, hides alert banner", async () => {
    const { initEmailValidationForm: realInit } = await vi.importActual<
      typeof import("../email-validation-form.js")
    >("../email-validation-form.js");
    const $modal = $("#EmailValidationModal");

    const banner = $modal.find("#SplashModalAlertBanner");
    banner
      .removeClass("alert-banner-splash-modal-hide")
      .addClass("alert-banner-splash-modal-display alert-danger");

    realInit($modal, false);
    $modal.trigger("show.bs.modal");

    expect(banner.hasClass("alert-banner-splash-modal-hide")).toBe(true);
    expect(banner.hasClass("alert-banner-splash-modal-display")).toBe(false);
  });
});
