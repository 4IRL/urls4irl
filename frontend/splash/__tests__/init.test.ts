import type { Mock } from "vitest";

import { UI_EVENTS } from "../../types/metrics-events.js";
import {
  createImmediateAlwaysJqXHR,
  createMockModal,
} from "../../__tests__/helpers/mock-jquery.js";
import {
  clearOpenFormOnAuthModalHide,
  createLogoutOnExit,
  switchModal,
  loginModalOpener,
  registerModalOpener,
  displayFormErrors,
  showSplashModalAlertBanner,
  hideSplashModalAlertBanner,
  resetModalFormState,
  handleImproperFormErrors,
  handleUserHasAccountNotEmailValidated,
  emailValidationModalOpener,
} from "../init.js";
import {
  clearOpenForm,
  getOpenForm,
  setOpenForm,
} from "../../lib/modal-tracking.js";
import { initEmailValidationForm } from "../email-validation-form.js";
import {
  AUTH_FORM_SWITCH_TARGET,
  AUTH_MODAL_OPEN_FORM,
} from "../../types/metrics-dim-values.js";

const { mockMetricsClient } = await vi.hoisted(
  async () => await import("../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../lib/metrics-client.js", () => mockMetricsClient());

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

interface MockBootstrapModal extends bootstrap.Modal {
  show: Mock<(relatedTarget?: HTMLElement) => void>;
  hide: Mock<() => void>;
}

describe("createLogoutOnExit", () => {
  let ajaxGetSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    ajaxGetSpy = vi
      .spyOn($, "get")
      .mockReturnValue(createImmediateAlwaysJqXHR());
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
    mockFromModal = createMockModal() as MockBootstrapModal;
    mockToModal = createMockModal() as MockBootstrapModal;
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

  it("emits ui_auth_form_switch with target=login when toSelector is #LoginModal", async () => {
    const { emit } = await import("../../lib/metrics-client.js");
    vi.spyOn(window.bootstrap.Modal, "getInstance").mockReturnValue(null);
    vi.spyOn(window.bootstrap.Modal, "getOrCreateInstance").mockReturnValue(
      mockToModal,
    );

    switchModal($("#RegisterModal"), "#LoginModal");

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_AUTH_FORM_SWITCH,
      target: AUTH_FORM_SWITCH_TARGET.LOGIN,
    });
    expect(emit).toHaveBeenCalledTimes(1);
  });

  it("emits ui_auth_form_switch with target=register when toSelector is #RegisterModal", async () => {
    const { emit } = await import("../../lib/metrics-client.js");
    vi.spyOn(window.bootstrap.Modal, "getInstance").mockReturnValue(null);
    vi.spyOn(window.bootstrap.Modal, "getOrCreateInstance").mockReturnValue(
      mockToModal,
    );

    switchModal($("#LoginModal"), "#RegisterModal");

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_AUTH_FORM_SWITCH,
      target: AUTH_FORM_SWITCH_TARGET.REGISTER,
    });
    expect(emit).toHaveBeenCalledTimes(1);
  });

  it("emits ui_auth_form_switch with target=forgot_password when toSelector is #ForgotPasswordModal", async () => {
    const { emit } = await import("../../lib/metrics-client.js");
    vi.spyOn(window.bootstrap.Modal, "getInstance").mockReturnValue(null);
    vi.spyOn(window.bootstrap.Modal, "getOrCreateInstance").mockReturnValue(
      mockToModal,
    );

    switchModal($("#LoginModal"), "#ForgotPasswordModal");

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_AUTH_FORM_SWITCH,
      target: AUTH_FORM_SWITCH_TARGET.FORGOT_PASSWORD,
    });
    expect(emit).toHaveBeenCalledTimes(1);
  });

  it("does NOT emit ui_auth_form_switch when toSelector is #EmailValidationModal", async () => {
    const { emit } = await import("../../lib/metrics-client.js");
    vi.spyOn(window.bootstrap.Modal, "getInstance").mockReturnValue(null);
    vi.spyOn(window.bootstrap.Modal, "getOrCreateInstance").mockReturnValue(
      mockToModal,
    );

    switchModal($("#RegisterModal"), "#EmailValidationModal");

    expect(emit).not.toHaveBeenCalled();
  });
});

describe("loginModalOpener", () => {
  beforeEach(() => {
    document.body.innerHTML = modalShell("LoginModal");
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("emits ui_auth_modal_open with form=login and shows the login modal", async () => {
    const { emit } = await import("../../lib/metrics-client.js");
    const mockToModal = createMockModal() as MockBootstrapModal;
    vi.spyOn(window.bootstrap.Modal, "getOrCreateInstance").mockReturnValue(
      mockToModal,
    );

    loginModalOpener();

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_AUTH_MODAL_OPEN,
      form: AUTH_MODAL_OPEN_FORM.LOGIN,
    });
    expect(emit).toHaveBeenCalledTimes(1);
    expect(mockToModal.show).toHaveBeenCalled();
  });
});

describe("registerModalOpener", () => {
  beforeEach(() => {
    document.body.innerHTML = modalShell("RegisterModal");
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("emits ui_auth_modal_open with form=register and shows the register modal", async () => {
    const { emit } = await import("../../lib/metrics-client.js");
    const mockToModal = createMockModal() as MockBootstrapModal;
    vi.spyOn(window.bootstrap.Modal, "getOrCreateInstance").mockReturnValue(
      mockToModal,
    );

    registerModalOpener();

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_AUTH_MODAL_OPEN,
      form: AUTH_MODAL_OPEN_FORM.REGISTER,
    });
    expect(emit).toHaveBeenCalledTimes(1);
    expect(mockToModal.show).toHaveBeenCalled();
  });
});

describe("clearOpenFormOnAuthModalHide", () => {
  beforeEach(() => {
    document.body.innerHTML =
      modalShell("LoginModal") + modalShell("RegisterModal");
    clearOpenForm();
    vi.clearAllMocks();
  });

  afterEach(() => {
    clearOpenForm();
    vi.restoreAllMocks();
  });

  it("clears the open-form registry when the login modal fires hidden.bs.modal", () => {
    clearOpenFormOnAuthModalHide($("#LoginModal"));
    setOpenForm("login");
    expect(getOpenForm()).toBe("login");

    $("#LoginModal").trigger("hidden.bs.modal");

    expect(getOpenForm()).toBeNull();
  });

  it("clears the open-form registry when the register modal fires hidden.bs.modal", () => {
    clearOpenFormOnAuthModalHide($("#RegisterModal"));
    setOpenForm("register");
    expect(getOpenForm()).toBe("register");

    $("#RegisterModal").trigger("hidden.bs.modal");

    expect(getOpenForm()).toBeNull();
  });

  it("re-binding is idempotent — a single hidden.bs.modal clear, no stacked handlers", () => {
    clearOpenFormOnAuthModalHide($("#LoginModal"));
    clearOpenFormOnAuthModalHide($("#LoginModal"));
    setOpenForm("login");

    $("#LoginModal").trigger("hidden.bs.modal");
    expect(getOpenForm()).toBeNull();

    // A later open + dismiss still clears (persistent listener, not one-shot).
    setOpenForm("login");
    $("#LoginModal").trigger("hidden.bs.modal");
    expect(getOpenForm()).toBeNull();
  });
});

// End-to-end DD-3 guard: an X-button/backdrop dismiss of the login modal
// (hidden.bs.modal) clears the open-form registry, so a subsequent page
// navigation no longer emits a spurious UI_AUTH_CANCEL{trigger:navigation}.
// Uses the REAL metrics-client pagehide handler (via vi.importActual) and the
// real modal-tracking registry the dismiss listener writes to.
describe("auth-modal dismiss suppresses spurious navigation cancel", () => {
  let sendBeaconMock: Mock;

  beforeEach(() => {
    document.body.innerHTML = modalShell("LoginModal");
    clearOpenForm();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValue({ status: "Success", accepted: 1 }),
      } as unknown as Response),
    );
    sendBeaconMock = vi.fn(() => true);
    Object.defineProperty(navigator, "sendBeacon", {
      value: sendBeaconMock,
      configurable: true,
      writable: true,
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    clearOpenForm();
    delete (navigator as Partial<Navigator>).sendBeacon;
    vi.restoreAllMocks();
  });

  it("dismissing the login modal then navigating emits NO UI_AUTH_CANCEL", async () => {
    const { initMetricsClient, resetMetricsClient } = await vi.importActual<
      typeof import("../../lib/metrics-client.js")
    >("../../lib/metrics-client.js");

    initMetricsClient();
    try {
      clearOpenFormOnAuthModalHide($("#LoginModal"));
      // Simulate the open-form registry being set when the login modal opens.
      setOpenForm("login");

      // User dismisses via the Bootstrap X / backdrop — clears the registry.
      $("#LoginModal").trigger("hidden.bs.modal");
      expect(getOpenForm()).toBeNull();

      // Then the user navigates away.
      window.dispatchEvent(new Event("pagehide"));

      // A beacon may still fire to flush the buffer, but it must NOT contain a
      // navigation cancel for the (now-cleared) login form.
      for (const call of sendBeaconMock.mock.calls) {
        const blob = call[1] as Blob;
        const text = await blob.text();
        const events = JSON.parse(text).events as Array<{
          event_name: string;
        }>;
        expect(
          events.some((entry) => entry.event_name === UI_EVENTS.UI_AUTH_CANCEL),
        ).toBe(false);
      }
    } finally {
      resetMetricsClient();
    }
  });

  it("WITHOUT the dismiss listener, navigating after open emits UI_AUTH_CANCEL", async () => {
    const { initMetricsClient, resetMetricsClient } = await vi.importActual<
      typeof import("../../lib/metrics-client.js")
    >("../../lib/metrics-client.js");

    initMetricsClient();
    try {
      // No dismiss-clear wiring: registry stays populated through navigation.
      setOpenForm("login");
      window.dispatchEvent(new Event("pagehide"));

      const cancelEmitted = await (async () => {
        for (const call of sendBeaconMock.mock.calls) {
          const blob = call[1] as Blob;
          const text = await blob.text();
          const events = JSON.parse(text).events as Array<{
            event_name: string;
          }>;
          if (
            events.some(
              (entry) => entry.event_name === UI_EVENTS.UI_AUTH_CANCEL,
            )
          ) {
            return true;
          }
        }
        return false;
      })();

      expect(cancelEmitted).toBe(true);
    } finally {
      resetMetricsClient();
    }
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
      urlString: null,
    };

    const result = handleImproperFormErrors($modal, errorResponse);

    // The early-return still performs the cleanup at the top of the function
    expect($modal.find(".form-control.is-invalid").length).toBe(0);
    expect($modal.find(".invalid-feedback").length).toBe(0);
    // Returns undefined (void)
    expect(result).toBeUndefined();
  });

  it("calls displayFormErrors with the first message for a known form field", () => {
    const $modal = $("#LoginModal");

    const errorResponse = {
      status: "Failure" as const,
      message: "Validation failed",
      errorCode: null,
      errors: {
        username: ["Username is required", "Secondary error"],
      },
      details: null,
      urlString: null,
    };

    handleImproperFormErrors($modal, errorResponse);

    const usernameInput = $modal.find("#username");
    expect(usernameInput.hasClass("is-invalid")).toBe(true);

    const feedback = $modal.find("#username + .invalid-feedback");
    expect(feedback.length).toBe(1);
    expect(feedback.text()).toBe("Username is required");
  });

  it("skips keys that are not in FORM_FIELD_NAMES without inserting invalid-feedback", () => {
    const $modal = $("#LoginModal");

    const errorResponse = {
      status: "Failure" as const,
      message: "Validation failed",
      errorCode: null,
      errors: {
        nonExistentField: ["Should be ignored"],
      },
      details: null,
      urlString: null,
    };

    handleImproperFormErrors($modal, errorResponse);

    expect($modal.find(".form-control.is-invalid").length).toBe(0);
    expect($modal.find(".invalid-feedback").length).toBe(0);
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

  it("removes stale disabled and aria-busy attrs from #submit", () => {
    // Self-contained local $modal fixture (the shared beforeEach DOM does not
    // include a #submit button) — do NOT modify the shared beforeEach.
    const $modal = $(
      '<div><button id="submit" disabled="disabled" aria-busy="true"></button></div>',
    );

    resetModalFormState($modal);

    expect($modal.find("#submit").attr("disabled")).toBeUndefined();
    expect($modal.find("#submit").attr("aria-busy")).toBeUndefined();
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
          `<div class="modal-footer"></div>` +
          `<div class="oauth-divider"></div>` +
          `<div class="oauth-google-button"></div>` +
          `<div class="oauth-github-button"></div>`,
      ) + modalShell("EmailValidationModal");
    ajaxGetSpy = vi
      .spyOn($, "get")
      .mockReturnValue(createImmediateAlwaysJqXHR());
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
    expect($modal.find(".oauth-divider").length).toBe(0);
    expect($modal.find(".oauth-google-button").length).toBe(0);
    expect($modal.find(".oauth-github-button").length).toBe(0);
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
    const localFromModal = createMockModal();
    const localToModal = createMockModal();

    vi.spyOn(window.bootstrap.Modal, "getInstance").mockReturnValue(
      localFromModal,
    );
    vi.spyOn(window.bootstrap.Modal, "getOrCreateInstance").mockReturnValue(
      localToModal,
    );

    handleUserHasAccountNotEmailValidated(
      $("#LoginModal"),
      "Please validate your email",
    );

    // Click the validate-my-email button
    const $modal = $("#LoginModal");
    $modal.find("#SplashModalAlertBanner button").trigger("click");

    // switchModal was called — from-modal should be hidden
    expect(localFromModal.hide).toHaveBeenCalled();

    // initEmailValidationForm should be called with #EmailValidationModal
    expect(initEmailValidationForm).toHaveBeenCalledWith(
      expect.any(Object),
      true,
    );
  });

  it("after clicking validate-my-email, logoutOnExit is bound to EmailValidationModal", () => {
    vi.spyOn(window.bootstrap.Modal, "getInstance").mockReturnValue(null);
    vi.spyOn(window.bootstrap.Modal, "getOrCreateInstance").mockReturnValue(
      createMockModal(),
    );

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
    const localFromModal = createMockModal();
    const localToModal = createMockModal();
    vi.spyOn(window.bootstrap.Modal, "getInstance").mockReturnValue(
      localFromModal,
    );
    vi.spyOn(window.bootstrap.Modal, "getOrCreateInstance").mockReturnValue(
      localToModal,
    );

    emailValidationModalOpener($("#RegisterModal"));

    expect(localFromModal.hide).toHaveBeenCalled();
  });

  it("calls initEmailValidationForm with EmailValidationModal and sendInitialEmail=true", () => {
    vi.spyOn(window.bootstrap.Modal, "getInstance").mockReturnValue(null);
    vi.spyOn(window.bootstrap.Modal, "getOrCreateInstance").mockReturnValue(
      createMockModal(),
    );

    emailValidationModalOpener($("#RegisterModal"));

    expect(initEmailValidationForm).toHaveBeenCalledWith(
      expect.any(Object),
      true,
    );
  });

  it("registers a one-time hide.bs.modal logout handler on EmailValidationModal", () => {
    vi.spyOn(window.bootstrap.Modal, "getInstance").mockReturnValue(null);
    vi.spyOn(window.bootstrap.Modal, "getOrCreateInstance").mockReturnValue(
      createMockModal(),
    );
    const ajaxGetSpy = vi
      .spyOn($, "get")
      .mockReturnValue(createImmediateAlwaysJqXHR());
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
