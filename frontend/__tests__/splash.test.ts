import type { Mock } from "vitest";

import { createMockModal } from "./helpers/mock-jquery.js";
import { initOAuthRejectIfPresent } from "../splash.js";

const { mockMetricsClient } = await vi.hoisted(
  async () => await import("./helpers/mock-metrics-client.js"),
);

vi.mock("../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../lib/csrf.js", () => ({
  setupCSRF: vi.fn(),
}));

vi.mock("../lib/security-check.js", () => ({}));

vi.mock("../lib/cookie-banner.js", () => ({
  initCookieBanner: vi.fn(),
}));

vi.mock("../lib/jquery-plugins.js", () => ({
  registerJQueryPlugins: vi.fn(),
}));

vi.mock("../splash/navbar.js", () => ({
  initNavbar: vi.fn(),
}));

vi.mock("../splash/init.js", () => ({
  initSplash: vi.fn(),
  createLogoutOnExit: vi.fn(),
}));

vi.mock("../splash/reset-password-form.js", () => ({
  initResetPasswordForm: vi.fn(),
}));

vi.mock("../splash/email-validation-form.js", () => ({
  initEmailValidationForm: vi.fn(),
  SKIP_INITIAL_EMAIL: false,
}));

vi.mock("../lib/globals.js", () => ({
  $: window.jQuery,
  jQuery: window.jQuery,
  bootstrap: window.bootstrap,
}));

interface MockBootstrapModal extends bootstrap.Modal {
  show: Mock<(relatedTarget?: HTMLElement) => void>;
}

describe("initOAuthRejectIfPresent", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    document.body.innerHTML = "";
  });

  it("shows the splash modal when the oauth-reject ModalForm is present", () => {
    document.body.innerHTML =
      '<div class="modal fade" id="SplashModal"></div>' +
      '<form id="ModalForm" data-modal-context="oauth-reject"></form>';
    const mockModal = createMockModal() as MockBootstrapModal;
    const getOrCreateInstanceSpy = vi
      .spyOn(window.bootstrap.Modal, "getOrCreateInstance")
      .mockReturnValue(mockModal);

    initOAuthRejectIfPresent();

    expect(getOrCreateInstanceSpy).toHaveBeenCalledWith("#SplashModal");
    expect(mockModal.show).toHaveBeenCalled();
  });

  it("does not show any modal when the oauth-reject ModalForm is absent", () => {
    document.body.innerHTML = '<div class="modal fade" id="SplashModal"></div>';
    const getOrCreateInstanceSpy = vi.spyOn(
      window.bootstrap.Modal,
      "getOrCreateInstance",
    );

    initOAuthRejectIfPresent();

    expect(getOrCreateInstanceSpy).not.toHaveBeenCalled();
  });
});
