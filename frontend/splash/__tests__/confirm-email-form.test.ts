import { createMockJqXHR } from "../../__tests__/helpers/mock-jquery.js";
import {
  initConfirmEmailForm,
  openConfirmEmailModal,
} from "../confirm-email-form.js";
import { switchModal, showSplashModalAlertBanner } from "../init.js";

vi.mock("../init.js", () => ({
  switchModal: vi.fn(),
  showSplashModalAlertBanner: vi.fn(),
  hideSplashModalAlertBanner: vi.fn(),
  resetModalFormState: vi.fn(),
}));

vi.mock("../../lib/metrics-client.js", () => ({ emit: vi.fn() }));

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

const PAGE_HTML = `
  <div id="splashHero"><button class="to-login">Login</button></div>
  <div class="modal fade" id="LoginModal">
    <input id="username" value="alice" />
    <input id="password" value="secret" />
    <div class="to-forgot-password"></div>
  </div>
  <div class="modal fade" id="ConfirmEmailModal">
    <h4 id="ConfirmEmailModalLabel" tabindex="-1">Confirm your email</h4>
    <div id="SplashModalAlertBanner"></div>
    <div id="ConfirmEmailStatus" role="status"></div>
    <button id="ResendConfirmationEmail" type="button">Resend confirmation email</button>
    <button id="BackToLoginFromConfirmEmail" type="button">Back to login</button>
  </div>
`;

const RESEND_LABEL = "Resend confirmation email";
const COOLDOWN_LABEL = "Sent — resend in a minute";
const COOLDOWN_MS = 60_000;

let keyCounter = 0;

// The cooldown record is module-scope state that outlives a test, so every
// test uses its own username (cooldown key) instead of sharing one.
function openModal(token: string = "tok-1"): {
  $modal: JQuery;
  $login: JQuery;
  key: string;
} {
  keyCounter += 1;
  const key = `user-${keyCounter}`;
  const $login = $("#LoginModal");
  $login.find("#username").val(key);
  const $modal = $("#ConfirmEmailModal");
  openConfirmEmailModal({ resendToken: token, fromModal: $login });
  $modal.trigger("show.bs.modal");
  return { $modal, $login, key };
}

function reopen($modal: JQuery, $login: JQuery, token: string): void {
  openConfirmEmailModal({ resendToken: token, fromModal: $login });
  $modal.trigger("show.bs.modal");
}

describe("confirm-email-form", () => {
  beforeEach(() => {
    document.body.innerHTML = PAGE_HTML;
    vi.useFakeTimers();
    vi.clearAllMocks();
    initConfirmEmailForm($("#ConfirmEmailModal"), { mode: "inline" });
  });

  afterEach(() => {
    $("#ConfirmEmailModal").trigger("hidden.bs.modal");
    vi.useRealTimers();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  function clickResend(): void {
    $("#ConfirmEmailModal").find("#ResendConfirmationEmail").trigger("click");
  }

  it("posts only the resend token, with the wrapper's JSON body and 10s timeout", () => {
    const ajaxSpy = vi.spyOn($, "ajax").mockReturnValue(createMockJqXHR());
    openModal("tok-abc");

    clickResend();

    expect(ajaxSpy).toHaveBeenCalledTimes(1);
    expect(ajaxSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        url: "/resend-registration-email",
        type: "POST",
        contentType: "application/json",
        data: JSON.stringify({ resendToken: "tok-abc" }),
        timeout: 10000,
      }),
    );
  });

  it("makes no request when the stashed token is empty", () => {
    const ajaxSpy = vi.spyOn($, "ajax").mockReturnValue(createMockJqXHR());
    openModal("");

    clickResend();

    expect(ajaxSpy).not.toHaveBeenCalled();
  });

  it("two rapid clicks send exactly one request", () => {
    const ajaxSpy = vi.spyOn($, "ajax").mockReturnValue(createMockJqXHR());
    openModal();

    clickResend();
    clickResend();

    expect(ajaxSpy).toHaveBeenCalledTimes(1);
  });

  it("repeat init binds the click handler once", () => {
    const ajaxSpy = vi.spyOn($, "ajax").mockReturnValue(createMockJqXHR());
    initConfirmEmailForm($("#ConfirmEmailModal"), { mode: "inline" });
    initConfirmEmailForm($("#ConfirmEmailModal"), { mode: "inline" });
    openModal();

    clickResend();

    expect(ajaxSpy).toHaveBeenCalledTimes(1);
  });

  it("shows in-flight state with aria-disabled and aria-busy, not the disabled attribute", () => {
    vi.spyOn($, "ajax").mockReturnValue(createMockJqXHR());
    const { $modal } = openModal();

    clickResend();

    const $button = $modal.find("#ResendConfirmationEmail");
    expect($button.attr("aria-disabled")).toBe("true");
    expect($button.attr("aria-busy")).toBe("true");
    expect($button.attr("disabled")).toBeUndefined();
    expect($button.text()).toBe("Sending…");
  });

  it("on success shows the banner, announces via the status node and starts the cooldown", () => {
    const deferred = createMockJqXHR();
    vi.spyOn($, "ajax").mockReturnValue(deferred);
    const { $modal } = openModal();

    clickResend();
    deferred.resolve({});
    vi.advanceTimersByTime(0);

    expect(showSplashModalAlertBanner).toHaveBeenCalledWith(
      expect.anything(),
      "Confirmation email resent — check your inbox.",
      "success",
    );
    const $status = $modal.find("#ConfirmEmailStatus");
    expect($status.text()).toBe(
      "Confirmation email resent — check your inbox.",
    );
    expect($status.attr("role")).toBe("status");
    const $button = $modal.find("#ResendConfirmationEmail");
    expect($button.attr("aria-disabled")).toBe("true");
    expect($button.attr("aria-busy")).toBeUndefined();
    expect($button.text()).toBe(COOLDOWN_LABEL);

    vi.advanceTimersByTime(COOLDOWN_MS);
    expect($button.attr("aria-disabled")).toBeUndefined();
    expect($button.text()).toBe(RESEND_LABEL);
  });

  it("keeps the cooldown across close and reopen for the same account", () => {
    const deferred = createMockJqXHR();
    vi.spyOn($, "ajax").mockReturnValue(deferred);
    const { $modal, $login } = openModal();
    clickResend();
    deferred.resolve({});

    $modal.trigger("hidden.bs.modal");
    expect($modal.find("#ResendConfirmationEmail").attr("aria-disabled")).toBe(
      undefined,
    );

    vi.advanceTimersByTime(20_000);
    // Same username key as the first open.
    reopen($modal, $login, "tok-2");

    const $button = $modal.find("#ResendConfirmationEmail");
    expect($button.attr("aria-disabled")).toBe("true");
    expect($button.text()).toBe(COOLDOWN_LABEL);

    // Re-enables when the remaining ~40s elapse, not a fresh 60s.
    vi.advanceTimersByTime(40_000);
    expect($button.attr("aria-disabled")).toBeUndefined();
  });

  it("ignores a cooldown recorded for a different username", () => {
    const deferred = createMockJqXHR();
    vi.spyOn($, "ajax").mockReturnValue(deferred);
    const { $modal, $login } = openModal();
    clickResend();
    deferred.resolve({});
    $modal.trigger("hidden.bs.modal");

    $login.find("#username").val("someone-else");
    reopen($modal, $login, "tok-2");

    expect($modal.find("#ResendConfirmationEmail").attr("aria-disabled")).toBe(
      undefined,
    );
  });

  it("a request settling after close is a no-op and records no cooldown", () => {
    const deferred = createMockJqXHR();
    vi.spyOn($, "ajax").mockReturnValue(deferred);
    const { $modal, $login } = openModal();
    clickResend();

    $modal.trigger("hidden.bs.modal");
    deferred.resolve({});
    vi.advanceTimersByTime(0);

    expect(showSplashModalAlertBanner).not.toHaveBeenCalled();
    expect($modal.find("#ConfirmEmailStatus").text()).toBe("");

    reopen($modal, $login, "tok-2");
    expect($modal.find("#ResendConfirmationEmail").attr("aria-disabled")).toBe(
      undefined,
    );
  });

  it("a request settling after a reopen with a new token is a no-op", () => {
    const deferred = createMockJqXHR();
    vi.spyOn($, "ajax").mockReturnValue(deferred);
    const { $modal, $login } = openModal("tok-old");
    clickResend();

    $modal.trigger("hidden.bs.modal");
    reopen($modal, $login, "tok-new");
    deferred.resolve({});

    expect(showSplashModalAlertBanner).not.toHaveBeenCalled();
    expect($modal.find("#ResendConfirmationEmail").attr("aria-disabled")).toBe(
      undefined,
    );
  });

  it("bails on a handled 429 without a banner but re-enables the button", () => {
    const deferred = createMockJqXHR();
    vi.spyOn($, "ajax").mockReturnValue(deferred);
    const { $modal } = openModal();
    clickResend();

    deferred.reject({ status: 429, _429Handled: true }, "error", "Too Many");

    expect(showSplashModalAlertBanner).not.toHaveBeenCalled();
    const $button = $modal.find("#ResendConfirmationEmail");
    expect($button.attr("aria-disabled")).toBeUndefined();
    expect($button.attr("aria-busy")).toBeUndefined();
    expect($button.text()).toBe(RESEND_LABEL);
  });

  it("a request settling after a reopen with an identical token is stale", () => {
    const deferred = createMockJqXHR();
    vi.spyOn($, "ajax").mockReturnValue(deferred);
    const { $modal, $login } = openModal("tok-same");
    clickResend();

    $modal.trigger("hidden.bs.modal");
    reopen($modal, $login, "tok-same");
    deferred.resolve({});

    expect(showSplashModalAlertBanner).not.toHaveBeenCalled();
    expect($modal.find("#ResendConfirmationEmail").attr("aria-disabled")).toBe(
      undefined,
    );
  });

  it("lowercases the username for the cooldown key", () => {
    const { $modal, $login } = openModal();
    $login.find("#username").val("  Alice  ");

    reopen($modal, $login, "tok-2");

    expect($modal.data("cooldownKey")).toBe("alice");
  });

  it("keeps the original button label when init repeats mid-cooldown", () => {
    const deferred = createMockJqXHR();
    vi.spyOn($, "ajax").mockReturnValue(deferred);
    const { $modal } = openModal();
    clickResend();
    deferred.resolve({});

    initConfirmEmailForm($modal, { mode: "inline" });
    $modal.trigger("hidden.bs.modal");

    expect($modal.find("#ResendConfirmationEmail").text()).toBe(RESEND_LABEL);
  });

  describe("expired mode", () => {
    it("Back to login replaces the location with the splash root", () => {
      const replaceSpy = vi.fn();
      vi.stubGlobal("location", { replace: replaceSpy });
      initConfirmEmailForm($("#ConfirmEmailModal"), { mode: "expired" });
      const { $modal } = openModal();

      $modal.find("#BackToLoginFromConfirmEmail").trigger("click");

      expect(replaceSpy).toHaveBeenCalledWith("/");
      expect(switchModal).not.toHaveBeenCalledWith($modal, "#LoginModal");
    });

    it("uses the shared 'expired' cooldown key", () => {
      initConfirmEmailForm($("#ConfirmEmailModal"), { mode: "expired" });
      const { $modal } = openModal();

      expect($modal.data("cooldownKey")).toBe("expired");
    });
  });

  it("treats status 0 as the opaque success copy", () => {
    const deferred = createMockJqXHR();
    vi.spyOn($, "ajax").mockReturnValue(deferred);
    openModal();
    clickResend();

    deferred.reject({ status: 0 }, "timeout", "");

    expect(showSplashModalAlertBanner).toHaveBeenCalledWith(
      expect.anything(),
      "Confirmation email resent — check your inbox.",
      "success",
    );
  });

  it("on a real HTTP error shows a danger banner, switches the status node to alert and re-enables", () => {
    const deferred = createMockJqXHR();
    vi.spyOn($, "ajax").mockReturnValue(deferred);
    const { $modal } = openModal();
    clickResend();

    deferred.reject({ status: 500 }, "error", "Server Error");
    vi.advanceTimersByTime(0);

    expect(showSplashModalAlertBanner).toHaveBeenCalledWith(
      expect.anything(),
      expect.stringContaining("Something went wrong"),
      "danger",
    );
    const $status = $modal.find("#ConfirmEmailStatus");
    expect($status.attr("role")).toBe("alert");
    expect($status.text()).toContain("Something went wrong");
    const $button = $modal.find("#ResendConfirmationEmail");
    expect($button.attr("aria-disabled")).toBeUndefined();
    expect($button.text()).toBe(RESEND_LABEL);
  });

  it("re-announces identical text: the status node is cleared, then set, each time", () => {
    const first = createMockJqXHR();
    const second = createMockJqXHR();
    vi.spyOn($, "ajax").mockReturnValueOnce(first).mockReturnValueOnce(second);
    const { $modal } = openModal();
    const $status = $modal.find("#ConfirmEmailStatus");

    clickResend();
    first.resolve({});
    expect($status.text()).toBe("");
    vi.advanceTimersByTime(0);
    const text = $status.text();
    expect(text).not.toBe("");

    vi.advanceTimersByTime(COOLDOWN_MS);
    clickResend();
    second.resolve({});
    expect($status.text()).toBe("");
    vi.advanceTimersByTime(0);
    expect($status.text()).toBe(text);
  });

  it("keeps the username and clears the password when opening", () => {
    const { $login } = openModal();

    expect($login.find("#password").val()).toBe("");
    expect(String($login.find("#username").val())).toMatch(/^user-/);
    expect(switchModal).toHaveBeenCalledWith($login, "#ConfirmEmailModal");
    // Login modal furniture is untouched.
    expect($login.find(".to-forgot-password").length).toBe(1);
  });

  it("moves focus to the title when shown", () => {
    openModal();
    $("#ConfirmEmailModal").trigger("shown.bs.modal");

    expect(document.activeElement?.id).toBe("ConfirmEmailModalLabel");
  });

  it("Back to login switches to #LoginModal and makes no logout request", () => {
    const getSpy = vi.spyOn($, "get");
    const { $modal } = openModal();

    $modal.find("#BackToLoginFromConfirmEmail").trigger("click");
    $modal.trigger("hidden.bs.modal");

    expect(switchModal).toHaveBeenCalledWith($modal, "#LoginModal");
    expect(getSpy).not.toHaveBeenCalled();
    expect(document.activeElement).not.toBe(
      document.querySelector("#splashHero .to-login"),
    );
  });

  it("returns focus to the hero login button on plain dismissal", () => {
    const getSpy = vi.spyOn($, "get");
    const { $modal } = openModal();

    $modal.trigger("hidden.bs.modal");

    expect(document.activeElement).toBe(
      document.querySelector("#splashHero .to-login"),
    );
    expect(getSpy).not.toHaveBeenCalled();
  });

  it("falls back to document.body when the hero login button is absent", () => {
    document.getElementById("splashHero")?.remove();
    const { $modal } = openModal();

    $modal.trigger("hidden.bs.modal");

    expect(document.activeElement).toBe(document.body);
  });

  it("clears the cooldown timer on hide so it cannot re-enable a closed modal", () => {
    const deferred = createMockJqXHR();
    vi.spyOn($, "ajax").mockReturnValue(deferred);
    const { $modal } = openModal();
    clickResend();
    deferred.resolve({});

    $modal.trigger("hidden.bs.modal");

    expect(vi.getTimerCount()).toBe(0);
  });
});
