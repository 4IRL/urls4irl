import type { Mock } from "vitest";

import { createMockModal } from "./helpers/mock-jquery.js";
import {
  initExpiredConfirmEmailIfPresent,
  initOAuthRejectIfPresent,
} from "../splash.js";
import {
  announce,
  initConfirmEmailForm,
} from "../splash/confirm-email-form.js";

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
}));

vi.mock("../splash/reset-password-form.js", () => ({
  initResetPasswordForm: vi.fn(),
}));

vi.mock("../splash/confirm-email-form.js", () => ({
  initConfirmEmailForm: vi.fn(),
  announce: vi.fn(),
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

describe("initExpiredConfirmEmailIfPresent", () => {
  const SHELL_HTML =
    '<div class="modal fade show" id="ConfirmEmailModal" data-resend-token="tok.en.123">' +
    '<h4 id="ConfirmEmailModalLabel" tabindex="-1">Confirm your email</h4>' +
    '<div id="SplashModalAlertBanner">Link expired</div>' +
    '<div id="ConfirmEmailStatus"></div></div>';

  afterEach(() => {
    vi.restoreAllMocks();
    vi.clearAllMocks();
    document.body.innerHTML = "";
  });

  it("stashes the token, binds expired mode, then shows, focuses and announces in order", () => {
    document.body.innerHTML = SHELL_HTML;
    const mockModal = createMockModal() as MockBootstrapModal;
    vi.spyOn(window.bootstrap.Modal, "getOrCreateInstance").mockReturnValue(
      mockModal,
    );
    const title = document.getElementById("ConfirmEmailModalLabel")!;
    const focusSpy = vi.spyOn(title, "focus");

    initExpiredConfirmEmailIfPresent();

    const $shell = window.jQuery("#ConfirmEmailModal");
    expect($shell.data("resendToken")).toBe("tok.en.123");
    expect(initConfirmEmailForm).toHaveBeenCalledTimes(1);
    expect(initConfirmEmailForm).toHaveBeenCalledWith(expect.anything(), {
      mode: "expired",
    });
    expect(mockModal.show).toHaveBeenCalledTimes(1);
    expect(announce).toHaveBeenCalledWith(
      expect.objectContaining({ text: "Link expired", isError: false }),
    );

    const initOrder = (initConfirmEmailForm as Mock).mock
      .invocationCallOrder[0];
    const showOrder = mockModal.show.mock.invocationCallOrder[0];
    const focusOrder = focusSpy.mock.invocationCallOrder[0];
    const announceOrder = (announce as Mock).mock.invocationCallOrder[0];
    expect(initOrder).toBeLessThan(showOrder);
    expect(showOrder).toBeLessThan(focusOrder);
    expect(focusOrder).toBeLessThan(announceOrder);
  });

  it("does nothing when the expired shell is absent", () => {
    document.body.innerHTML = '<div class="modal fade" id="SplashModal"></div>';
    const getOrCreateInstanceSpy = vi.spyOn(
      window.bootstrap.Modal,
      "getOrCreateInstance",
    );

    initExpiredConfirmEmailIfPresent();

    expect(getOrCreateInstanceSpy).not.toHaveBeenCalled();
    expect(initConfirmEmailForm).not.toHaveBeenCalled();
  });
});
