import {
  createMockJqXHRChainable,
  createMockXhr,
} from "../../__tests__/helpers/mock-jquery.js";
import { ajaxCall, is429Handled } from "../../lib/ajax.js";
import {
  initChangePassword,
  _resetChangePasswordForTests,
} from "../change-password.js";

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

const CHANGE_URL = "/users/1/password";
const CURRENT_PASSWORD = "FakePassword1234";
const NEW_PASSWORD = "NewFakePassword5678";
const SUCCESS_MESSAGE =
  "Your password has been updated. You've been signed out of all other devices.";
const CURRENT_INCORRECT_MESSAGE = "Current password is incorrect.";
const MISMATCH_MESSAGE = "Passwords are not identical.";

function formHtml(): string {
  return `
    <section id="SettingsPanelAccount">
      <div class="SettingsChangePassword">
        <div id="SettingsPasswordStatus" class="alert d-none" role="alert"></div>
        <div class="form-group">
          <input id="SettingsCurrentPassword" class="form-control" type="password" />
        </div>
        <div class="form-group">
          <input id="SettingsNewPassword" class="form-control" type="password" />
        </div>
        <div class="form-group">
          <input id="SettingsConfirmNewPassword" class="form-control" type="password" />
        </div>
        <button type="button" id="SettingsChangePasswordBtn" data-action-url="${CHANGE_URL}"></button>
      </div>
    </section>
  `;
}

function fillFields(current: string, next: string, confirm: string): void {
  $("#SettingsCurrentPassword").val(current);
  $("#SettingsNewPassword").val(next);
  $("#SettingsConfirmNewPassword").val(confirm);
}

function mockDone(xhr: JQuery.jqXHR): JQuery.jqXHR {
  return createMockJqXHRChainable({
    done: (callback: unknown) => {
      (
        callback as (
          response: unknown,
          _textStatus: unknown,
          xhr: JQuery.jqXHR,
        ) => void
      )(xhr.responseJSON, "success", xhr);
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

describe("change-password", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(is429Handled).mockReturnValue(false);
    _resetChangePasswordForTests();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("is a no-op when #SettingsCurrentPassword is absent", () => {
    document.body.innerHTML = "<div id='Unrelated'></div>";
    initChangePassword();
    $("body").trigger("click");
    expect(vi.mocked(ajaxCall)).not.toHaveBeenCalled();
  });

  it("PUTs the alias-keyed payload, clears all fields, and shows the success banner", () => {
    document.body.innerHTML = formHtml();
    const successXhr = createMockXhr({
      status: 200,
      responseJSON: { status: "Success", message: SUCCESS_MESSAGE },
    });
    vi.mocked(ajaxCall).mockReturnValue(mockDone(successXhr));
    initChangePassword();

    fillFields(CURRENT_PASSWORD, NEW_PASSWORD, NEW_PASSWORD);
    $("#SettingsChangePasswordBtn").trigger("click");

    expect(vi.mocked(ajaxCall)).toHaveBeenCalledWith("put", CHANGE_URL, {
      currentPassword: CURRENT_PASSWORD,
      newPassword: NEW_PASSWORD,
      confirmNewPassword: NEW_PASSWORD,
    });
    // Secrets never linger in the DOM.
    expect($("#SettingsCurrentPassword").val()).toBe("");
    expect($("#SettingsNewPassword").val()).toBe("");
    expect($("#SettingsConfirmNewPassword").val()).toBe("");
    // Server-sourced banner rendered.
    const status = $("#SettingsPasswordStatus");
    expect(status.hasClass("d-none")).toBe(false);
    expect(status.hasClass("alert-success")).toBe(true);
    expect(status.text()).toBe(SUCCESS_MESSAGE);
    // Button re-enabled for a subsequent change (DD-16).
    expect($("#SettingsChangePasswordBtn").attr("disabled")).toBeUndefined();
  });

  it("submits on Enter keyup in a password input", () => {
    document.body.innerHTML = formHtml();
    const successXhr = createMockXhr({
      status: 200,
      responseJSON: { status: "Success", message: SUCCESS_MESSAGE },
    });
    vi.mocked(ajaxCall).mockReturnValue(mockDone(successXhr));
    initChangePassword();

    fillFields(CURRENT_PASSWORD, NEW_PASSWORD, NEW_PASSWORD);
    $("#SettingsNewPassword").trigger($.Event("keyup", { key: "Enter" }));

    expect(vi.mocked(ajaxCall)).toHaveBeenCalledWith("put", CHANGE_URL, {
      currentPassword: CURRENT_PASSWORD,
      newPassword: NEW_PASSWORD,
      confirmNewPassword: NEW_PASSWORD,
    });
  });

  it("renders the currentPassword field error on a wrong-password 400", () => {
    document.body.innerHTML = formHtml();
    const failedXhr = createMockXhr({
      status: 400,
      responseJSON: {
        status: "Failure",
        message: CURRENT_INCORRECT_MESSAGE,
        errorCode: 2,
        errors: { currentPassword: [CURRENT_INCORRECT_MESSAGE] },
      },
    });
    vi.mocked(ajaxCall).mockReturnValue(mockFail(failedXhr));
    initChangePassword();

    fillFields("wrong", NEW_PASSWORD, NEW_PASSWORD);
    $("#SettingsChangePasswordBtn").trigger("click");

    const input = $("#SettingsCurrentPassword");
    expect(input.hasClass("is-invalid")).toBe(true);
    expect(input.siblings(".invalid-feedback").text()).toBe(
      CURRENT_INCORRECT_MESSAGE,
    );
  });

  it("renders the confirmNewPassword field error on a mismatch 400", () => {
    document.body.innerHTML = formHtml();
    const failedXhr = createMockXhr({
      status: 400,
      responseJSON: {
        status: "Failure",
        message: "Invalid input, please try again.",
        errorCode: 1,
        errors: { confirmNewPassword: [MISMATCH_MESSAGE] },
      },
    });
    vi.mocked(ajaxCall).mockReturnValue(mockFail(failedXhr));
    initChangePassword();

    fillFields(CURRENT_PASSWORD, NEW_PASSWORD, "different");
    $("#SettingsChangePasswordBtn").trigger("click");

    const input = $("#SettingsConfirmNewPassword");
    expect(input.hasClass("is-invalid")).toBe(true);
    expect(input.siblings(".invalid-feedback").text()).toBe(MISMATCH_MESSAGE);
  });

  it("does nothing further when the failure was already handled as a coarse 429", () => {
    document.body.innerHTML = formHtml();
    vi.mocked(is429Handled).mockReturnValue(true);
    const failedXhr = createMockXhr({ status: 429 });
    vi.mocked(ajaxCall).mockReturnValue(mockFail(failedXhr));
    initChangePassword();

    $("#SettingsChangePasswordBtn").trigger("click");

    const status = $("#SettingsPasswordStatus");
    expect(status.hasClass("d-none")).toBe(true);
    expect($("#SettingsCurrentPassword").hasClass("is-invalid")).toBe(false);
  });

  it("does not double-submit when Enter fires while a click-triggered request is in flight (DD-18)", () => {
    document.body.innerHTML = formHtml();
    // Pending promise: neither done nor fail fires, so the button stays disabled.
    vi.mocked(ajaxCall).mockReturnValue(createMockJqXHRChainable());
    initChangePassword();

    fillFields(CURRENT_PASSWORD, NEW_PASSWORD, NEW_PASSWORD);
    $("#SettingsChangePasswordBtn").trigger("click");
    $("#SettingsNewPassword").trigger($.Event("keyup", { key: "Enter" }));

    expect(vi.mocked(ajaxCall)).toHaveBeenCalledTimes(1);
  });
});
