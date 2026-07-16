import {
  createMockJqXHRChainable,
  createMockXhr,
} from "../../__tests__/helpers/mock-jquery.js";
import { ajaxCall, is429Handled } from "../../lib/ajax.js";
import {
  initConnectedAccounts,
  _resetConnectedAccountsForTests,
} from "../connected-accounts.js";

vi.mock("../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));

vi.mock("../../lib/globals.js", () => ({
  $: window.jQuery,
  jQuery: window.jQuery,
  bootstrap: window.bootstrap,
}));

const $ = window.jQuery;

const GOOGLE_LINK_URL = "/users/1/oauth/link/google";
const GITHUB_LINK_URL = "/users/1/oauth/link/github";
const GOOGLE_UNLINK_URL = "/users/1/oauth/link/google";
const REDIRECT_URL = "/oauth/google/link";
const FAILURE_MESSAGE = "Incorrect password.";

function passwordRequiredHtml(): string {
  return `
    <div id="SettingsConnectedAccounts" data-has-password="true">
      <div id="SettingsLinkStatusBanner" class="alert d-none"></div>
      <ul class="ConnectedAccountsList">
        <li class="ConnectedAccountRow" data-provider="google">
          <button type="button" class="ConnectedAccountLinkBtn" data-action-url="${GOOGLE_LINK_URL}"></button>
          <div class="ConnectedAccountPasswordConfirm d-none">
            <input class="ConnectedAccountPasswordInput" type="password" />
            <button type="button" class="ConnectedAccountPasswordContinueBtn"></button>
            <button type="button" class="ConnectedAccountPasswordCancelBtn"></button>
          </div>
        </li>
        <li class="ConnectedAccountRow" data-provider="github">
          <button type="button" class="ConnectedAccountLinkBtn" data-action-url="${GITHUB_LINK_URL}"></button>
          <div class="ConnectedAccountPasswordConfirm d-none">
            <input class="ConnectedAccountPasswordInput" type="password" />
            <button type="button" class="ConnectedAccountPasswordContinueBtn"></button>
            <button type="button" class="ConnectedAccountPasswordCancelBtn"></button>
          </div>
        </li>
      </ul>
    </div>
  `;
}

function oauthOnlyHtml(): string {
  return `
    <div id="SettingsConnectedAccounts" data-has-password="false">
      <div id="SettingsLinkStatusBanner" class="alert d-none"></div>
      <ul class="ConnectedAccountsList">
        <li class="ConnectedAccountRow" data-provider="google">
          <button type="button" class="ConnectedAccountLinkBtn" data-action-url="${GOOGLE_LINK_URL}"></button>
        </li>
      </ul>
    </div>
  `;
}

function unlinkHtml({ disabled }: { disabled: boolean }): string {
  return `
    <div id="SettingsConnectedAccounts" data-has-password="true">
      <div id="SettingsLinkStatusBanner" class="alert d-none"></div>
      <ul class="ConnectedAccountsList">
        <li class="ConnectedAccountRow" data-provider="google">
          <button
            type="button"
            class="ConnectedAccountUnlinkBtn"
            data-action-url="${GOOGLE_UNLINK_URL}"
            ${disabled ? "disabled" : ""}
          ></button>
        </li>
      </ul>
    </div>
  `;
}

function mockDone(response: unknown, xhr: JQuery.jqXHR): JQuery.jqXHR {
  return createMockJqXHRChainable({
    done: (callback: unknown) => {
      (
        callback as (
          response: unknown,
          _textStatus: unknown,
          xhr: JQuery.jqXHR,
        ) => void
      )(response, "success", xhr);
    },
  }) as unknown as JQuery.jqXHR;
}

function mockFail(xhr: JQuery.jqXHR): JQuery.jqXHR {
  return createMockJqXHRChainable({
    fail: (callback: unknown) => {
      (callback as (xhr: JQuery.jqXHR) => void)(xhr);
    },
  }) as unknown as JQuery.jqXHR;
}

describe("connected-accounts", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(is429Handled).mockReturnValue(false);
    _resetConnectedAccountsForTests();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("is a no-op when #SettingsConnectedAccounts is absent", () => {
    document.body.innerHTML = "<div id='Unrelated'></div>";
    initConnectedAccounts();
    $("body").trigger("click");
    expect(vi.mocked(ajaxCall)).not.toHaveBeenCalled();
  });

  it("reveals only the clicked row's password confirm block and focuses its input", () => {
    document.body.innerHTML = passwordRequiredHtml();
    initConnectedAccounts();

    $(
      `.ConnectedAccountRow[data-provider="github"] .ConnectedAccountLinkBtn`,
    ).trigger("click");

    const githubConfirm = $(
      '.ConnectedAccountRow[data-provider="github"] .ConnectedAccountPasswordConfirm',
    );
    const googleConfirm = $(
      '.ConnectedAccountRow[data-provider="google"] .ConnectedAccountPasswordConfirm',
    );
    expect(githubConfirm.hasClass("d-none")).toBe(false);
    expect(googleConfirm.hasClass("d-none")).toBe(true);
    expect(vi.mocked(ajaxCall)).not.toHaveBeenCalled();
  });

  it("hides a previously-open row's confirm block when a different row's link button is clicked", () => {
    document.body.innerHTML = passwordRequiredHtml();
    initConnectedAccounts();

    $(
      '.ConnectedAccountRow[data-provider="google"] .ConnectedAccountLinkBtn',
    ).trigger("click");
    $(
      '.ConnectedAccountRow[data-provider="github"] .ConnectedAccountLinkBtn',
    ).trigger("click");

    const googleConfirm = $(
      '.ConnectedAccountRow[data-provider="google"] .ConnectedAccountPasswordConfirm',
    );
    const githubConfirm = $(
      '.ConnectedAccountRow[data-provider="github"] .ConnectedAccountPasswordConfirm',
    );
    expect(googleConfirm.hasClass("d-none")).toBe(true);
    expect(githubConfirm.hasClass("d-none")).toBe(false);
  });

  it("POSTs the entered password to the row's link URL and navigates on success", () => {
    document.body.innerHTML = passwordRequiredHtml();
    const assignSpy = vi
      .spyOn(window.location, "assign")
      .mockImplementation(() => {});
    const successXhr = createMockXhr({ status: 200 });
    vi.mocked(ajaxCall).mockReturnValue(
      mockDone({ status: "Success", redirectUrl: REDIRECT_URL }, successXhr),
    );
    initConnectedAccounts();

    $(
      '.ConnectedAccountRow[data-provider="google"] .ConnectedAccountLinkBtn',
    ).trigger("click");
    $(
      '.ConnectedAccountRow[data-provider="google"] .ConnectedAccountPasswordInput',
    ).val("mypassword");
    $(
      '.ConnectedAccountRow[data-provider="google"] .ConnectedAccountPasswordContinueBtn',
    ).trigger("click");

    expect(vi.mocked(ajaxCall)).toHaveBeenCalledWith("post", GOOGLE_LINK_URL, {
      password: "mypassword",
    });
    expect(assignSpy).toHaveBeenCalledWith(REDIRECT_URL);

    assignSpy.mockRestore();
  });

  it("triggers the continue action when Enter is pressed in the password input", () => {
    document.body.innerHTML = passwordRequiredHtml();
    const assignSpy = vi
      .spyOn(window.location, "assign")
      .mockImplementation(() => {});
    const successXhr = createMockXhr({ status: 200 });
    vi.mocked(ajaxCall).mockReturnValue(
      mockDone({ status: "Success", redirectUrl: REDIRECT_URL }, successXhr),
    );
    initConnectedAccounts();

    $(
      '.ConnectedAccountRow[data-provider="google"] .ConnectedAccountLinkBtn',
    ).trigger("click");
    const passwordInput = $(
      '.ConnectedAccountRow[data-provider="google"] .ConnectedAccountPasswordInput',
    );
    passwordInput.val("mypassword");
    passwordInput.trigger($.Event("keyup", { key: "Enter" }));

    expect(vi.mocked(ajaxCall)).toHaveBeenCalledWith("post", GOOGLE_LINK_URL, {
      password: "mypassword",
    });
    expect(assignSpy).toHaveBeenCalledWith(REDIRECT_URL);

    assignSpy.mockRestore();
  });

  it("ignores non-Enter keyup events in the password input", () => {
    document.body.innerHTML = passwordRequiredHtml();
    initConnectedAccounts();

    $(
      '.ConnectedAccountRow[data-provider="google"] .ConnectedAccountLinkBtn',
    ).trigger("click");
    const passwordInput = $(
      '.ConnectedAccountRow[data-provider="google"] .ConnectedAccountPasswordInput',
    );
    passwordInput.val("mypassword");
    passwordInput.trigger($.Event("keyup", { key: "a" }));

    expect(vi.mocked(ajaxCall)).not.toHaveBeenCalled();
  });

  it("shows the field-level password error in the banner when the continue POST fails", () => {
    document.body.innerHTML = passwordRequiredHtml();
    const failedXhr = createMockXhr({
      status: 400,
      responseJSON: {
        status: "Failure",
        message: "Bad request",
        errorCode: 5,
        errors: { password: [FAILURE_MESSAGE] },
      },
    });
    vi.mocked(ajaxCall).mockReturnValue(mockFail(failedXhr));
    initConnectedAccounts();

    $(
      '.ConnectedAccountRow[data-provider="google"] .ConnectedAccountLinkBtn',
    ).trigger("click");
    const passwordInput = $(
      '.ConnectedAccountRow[data-provider="google"] .ConnectedAccountPasswordInput',
    );
    passwordInput.val("wrongpassword");
    $(
      '.ConnectedAccountRow[data-provider="google"] .ConnectedAccountPasswordContinueBtn',
    ).trigger("click");

    const banner = $("#SettingsLinkStatusBanner");
    expect(banner.hasClass("d-none")).toBe(false);
    expect(banner.hasClass("alert-danger")).toBe(true);
    expect(banner.text()).toBe(FAILURE_MESSAGE);
    // Entered password is preserved for the user to retype, not cleared.
    expect(passwordInput.val()).toBe("wrongpassword");
  });

  it("cancels: hides the confirm block and clears the password input", () => {
    document.body.innerHTML = passwordRequiredHtml();
    initConnectedAccounts();

    $(
      '.ConnectedAccountRow[data-provider="google"] .ConnectedAccountLinkBtn',
    ).trigger("click");
    const passwordInput = $(
      '.ConnectedAccountRow[data-provider="google"] .ConnectedAccountPasswordInput',
    );
    passwordInput.val("mypassword");
    $(
      '.ConnectedAccountRow[data-provider="google"] .ConnectedAccountPasswordCancelBtn',
    ).trigger("click");

    const confirmBlock = $(
      '.ConnectedAccountRow[data-provider="google"] .ConnectedAccountPasswordConfirm',
    );
    expect(confirmBlock.hasClass("d-none")).toBe(true);
    expect(passwordInput.val()).toBe("");
  });

  it("immediately POSTs an explicit null password for OAuth-only accounts and navigates on success", () => {
    document.body.innerHTML = oauthOnlyHtml();
    const assignSpy = vi
      .spyOn(window.location, "assign")
      .mockImplementation(() => {});
    const successXhr = createMockXhr({ status: 200 });
    vi.mocked(ajaxCall).mockReturnValue(
      mockDone({ status: "Success", redirectUrl: REDIRECT_URL }, successXhr),
    );
    initConnectedAccounts();

    $(".ConnectedAccountLinkBtn").trigger("click");

    expect(vi.mocked(ajaxCall)).toHaveBeenCalledWith("post", GOOGLE_LINK_URL, {
      password: null,
    });
    expect(assignSpy).toHaveBeenCalledWith(REDIRECT_URL);

    assignSpy.mockRestore();
  });

  it("DELETEs the unlink URL and reloads the page on success", () => {
    document.body.innerHTML = unlinkHtml({ disabled: false });
    const reloadSpy = vi
      .spyOn(window.location, "reload")
      .mockImplementation(() => {});
    const successXhr = createMockXhr({ status: 200 });
    vi.mocked(ajaxCall).mockReturnValue(
      mockDone({ status: "Success", message: "Unlinked" }, successXhr),
    );
    initConnectedAccounts();

    $(".ConnectedAccountUnlinkBtn").trigger("click");

    expect(vi.mocked(ajaxCall)).toHaveBeenCalledWith(
      "delete",
      GOOGLE_UNLINK_URL,
      null,
    );
    expect(reloadSpy).toHaveBeenCalled();

    reloadSpy.mockRestore();
  });

  it("ignores clicks on a disabled unlink button", () => {
    document.body.innerHTML = unlinkHtml({ disabled: true });
    initConnectedAccounts();

    $(".ConnectedAccountUnlinkBtn").trigger("click");

    expect(vi.mocked(ajaxCall)).not.toHaveBeenCalled();
  });

  it("shows the error message in the banner when the unlink DELETE fails", () => {
    document.body.innerHTML = unlinkHtml({ disabled: false });
    const failedXhr = createMockXhr({
      status: 403,
      responseJSON: {
        status: "Failure",
        message: "You must keep at least one sign-in method.",
        errorCode: 3,
        errors: null,
      },
    });
    vi.mocked(ajaxCall).mockReturnValue(mockFail(failedXhr));
    initConnectedAccounts();

    $(".ConnectedAccountUnlinkBtn").trigger("click");

    const banner = $("#SettingsLinkStatusBanner");
    expect(banner.hasClass("d-none")).toBe(false);
    expect(banner.hasClass("alert-danger")).toBe(true);
    expect(banner.text()).toBe("You must keep at least one sign-in method.");
  });

  it("does nothing further when a continue-POST failure was already handled as a 429", () => {
    document.body.innerHTML = passwordRequiredHtml();
    vi.mocked(is429Handled).mockReturnValue(true);
    const failedXhr = createMockXhr({ status: 429 });
    vi.mocked(ajaxCall).mockReturnValue(mockFail(failedXhr));
    initConnectedAccounts();

    $(
      '.ConnectedAccountRow[data-provider="google"] .ConnectedAccountLinkBtn',
    ).trigger("click");
    $(
      '.ConnectedAccountRow[data-provider="google"] .ConnectedAccountPasswordContinueBtn',
    ).trigger("click");

    const banner = $("#SettingsLinkStatusBanner");
    expect(banner.hasClass("d-none")).toBe(true);
  });

  it("does nothing further when an unlink-DELETE failure was already handled as a 429", () => {
    document.body.innerHTML = unlinkHtml({ disabled: false });
    vi.mocked(is429Handled).mockReturnValue(true);
    const failedXhr = createMockXhr({ status: 429 });
    vi.mocked(ajaxCall).mockReturnValue(mockFail(failedXhr));
    initConnectedAccounts();

    $(".ConnectedAccountUnlinkBtn").trigger("click");

    const banner = $("#SettingsLinkStatusBanner");
    expect(banner.hasClass("d-none")).toBe(true);
  });
});
