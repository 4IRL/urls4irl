import {
  createMockJqXHRChainable,
  createMockXhr,
} from "../../__tests__/helpers/mock-jquery.js";
import { ajaxCall, is429Handled } from "../../lib/ajax.js";
import { initChangeEmail, _resetChangeEmailForTests } from "../change-email.js";

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

const CHANGE_URL = "/users/1/email";
const NEW_EMAIL = "new@example.com";
const CURRENT_PASSWORD = "FakePassword1234";
const SUCCESS_MESSAGE =
  "We've sent a confirmation link to your new email address. Click it to finish changing your email.";
const CURRENT_INCORRECT_MESSAGE = "Current password is incorrect.";
const EMAIL_TAKEN_MESSAGE = "That email address is already in use.";
const MISMATCH_MESSAGE = "Emails do not match.";
const LOCKOUT_MESSAGE =
  "Too many incorrect password attempts. Please try again later.";
// Mirrors the bridged SETTINGS_ACCOUNT_PENDING_EMAIL_NOTE mock in test-setup.ts.
const PENDING_NOTE =
  "Pending change to new@example.com — check that inbox for the confirmation link.";

function formHtml({
  withPendingNote = false,
}: { withPendingNote?: boolean } = {}): string {
  const pendingNote = withPendingNote
    ? `<p class="SettingsAccountPendingEmailNote" aria-live="polite">stale</p>`
    : "";
  return `
    <section id="SettingsPanelAccount">
      <div class="SettingsStatCard" data-account-info="email">
        <dd class="SettingsStatValue">old@example.com</dd>
        ${pendingNote}
      </div>
      <div class="SettingsChangeEmail">
        <div id="SettingsEmailStatus" class="alert d-none" role="alert"></div>
        <div class="form-group">
          <input id="SettingsNewEmail" class="form-control" type="email" />
        </div>
        <div class="form-group">
          <input id="SettingsConfirmNewEmail" class="form-control" type="email" />
        </div>
        <div class="form-group">
          <input id="SettingsChangeEmailCurrentPassword" class="form-control" type="password" />
        </div>
        <button type="button" id="SettingsChangeEmailBtn" data-action-url="${CHANGE_URL}"></button>
      </div>
    </section>
  `;
}

function fillFields(newEmail: string, confirm: string, password: string): void {
  $("#SettingsNewEmail").val(newEmail);
  $("#SettingsConfirmNewEmail").val(confirm);
  $("#SettingsChangeEmailCurrentPassword").val(password);
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

describe("change-email", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(is429Handled).mockReturnValue(false);
    _resetChangeEmailForTests();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("is a no-op when #SettingsNewEmail is absent", () => {
    document.body.innerHTML = "<div id='Unrelated'></div>";
    initChangeEmail();
    $("body").trigger("click");
    expect(vi.mocked(ajaxCall)).not.toHaveBeenCalled();
  });

  it("PUTs the alias-keyed payload, clears the password, and shows the success banner", () => {
    document.body.innerHTML = formHtml();
    const successXhr = createMockXhr({
      status: 200,
      responseJSON: {
        status: "Success",
        message: SUCCESS_MESSAGE,
        pendingEmail: NEW_EMAIL,
      },
    });
    vi.mocked(ajaxCall).mockReturnValue(mockDone(successXhr));
    initChangeEmail();

    fillFields(NEW_EMAIL, NEW_EMAIL, CURRENT_PASSWORD);
    $("#SettingsChangeEmailBtn").trigger("click");

    expect(vi.mocked(ajaxCall)).toHaveBeenCalledWith("put", CHANGE_URL, {
      newEmail: NEW_EMAIL,
      confirmEmail: NEW_EMAIL,
      currentPassword: CURRENT_PASSWORD,
    });
    // Secret never lingers in the DOM.
    expect($("#SettingsChangeEmailCurrentPassword").val()).toBe("");
    // Email inputs are NOT cleared (Approach B: stay on page, live email
    // unchanged until confirm).
    expect($("#SettingsNewEmail").val()).toBe(NEW_EMAIL);
    // Server-sourced banner rendered.
    const status = $("#SettingsEmailStatus");
    expect(status.hasClass("d-none")).toBe(false);
    expect(status.hasClass("alert-success")).toBe(true);
    expect(status.text()).toBe(SUCCESS_MESSAGE);
    // Button re-enabled for a subsequent change.
    expect($("#SettingsChangeEmailBtn").attr("disabled")).toBeUndefined();
  });

  it("constructs the pending-change note when none exists (DD-6, absent branch)", () => {
    document.body.innerHTML = formHtml();
    const successXhr = createMockXhr({
      status: 200,
      responseJSON: {
        status: "Success",
        message: SUCCESS_MESSAGE,
        pendingEmail: NEW_EMAIL,
      },
    });
    vi.mocked(ajaxCall).mockReturnValue(mockDone(successXhr));
    initChangeEmail();

    // No note in the initial render.
    expect(
      $('[data-account-info="email"] .SettingsAccountPendingEmailNote').length,
    ).toBe(0);

    fillFields(NEW_EMAIL, NEW_EMAIL, CURRENT_PASSWORD);
    $("#SettingsChangeEmailBtn").trigger("click");

    const note = $(
      '[data-account-info="email"] .SettingsAccountPendingEmailNote',
    );
    expect(note.length).toBe(1);
    expect(note.text()).toBe(PENDING_NOTE);
    expect(note.attr("aria-live")).toBe("polite");
  });

  it("patches the existing pending-change note in place (DD-6, present branch)", () => {
    document.body.innerHTML = formHtml({ withPendingNote: true });
    const successXhr = createMockXhr({
      status: 200,
      responseJSON: {
        status: "Success",
        message: SUCCESS_MESSAGE,
        pendingEmail: NEW_EMAIL,
      },
    });
    vi.mocked(ajaxCall).mockReturnValue(mockDone(successXhr));
    initChangeEmail();

    fillFields(NEW_EMAIL, NEW_EMAIL, CURRENT_PASSWORD);
    $("#SettingsChangeEmailBtn").trigger("click");

    // Exactly one note (updated in place, not duplicated).
    const note = $(
      '[data-account-info="email"] .SettingsAccountPendingEmailNote',
    );
    expect(note.length).toBe(1);
    expect(note.text()).toBe(PENDING_NOTE);
  });

  it("leaves the pending note untouched on a no-op 200 (null pendingEmail)", () => {
    document.body.innerHTML = formHtml();
    const noopXhr = createMockXhr({
      status: 200,
      responseJSON: {
        status: "No change",
        message: "That's already your email address.",
        pendingEmail: null,
      },
    });
    vi.mocked(ajaxCall).mockReturnValue(mockDone(noopXhr));
    initChangeEmail();

    fillFields("old@example.com", "old@example.com", CURRENT_PASSWORD);
    $("#SettingsChangeEmailBtn").trigger("click");

    // No pending note constructed for a no-op.
    expect(
      $('[data-account-info="email"] .SettingsAccountPendingEmailNote').length,
    ).toBe(0);
  });

  it("submits on Enter keyup in an input", () => {
    document.body.innerHTML = formHtml();
    const successXhr = createMockXhr({
      status: 200,
      responseJSON: {
        status: "Success",
        message: SUCCESS_MESSAGE,
        pendingEmail: NEW_EMAIL,
      },
    });
    vi.mocked(ajaxCall).mockReturnValue(mockDone(successXhr));
    initChangeEmail();

    fillFields(NEW_EMAIL, NEW_EMAIL, CURRENT_PASSWORD);
    $("#SettingsNewEmail").trigger($.Event("keyup", { key: "Enter" }));

    expect(vi.mocked(ajaxCall)).toHaveBeenCalledWith("put", CHANGE_URL, {
      newEmail: NEW_EMAIL,
      confirmEmail: NEW_EMAIL,
      currentPassword: CURRENT_PASSWORD,
    });
  });

  it("renders the currentPassword field error on a wrong-password 400", () => {
    document.body.innerHTML = formHtml();
    const failedXhr = createMockXhr({
      status: 400,
      responseJSON: {
        status: "Failure",
        message: CURRENT_INCORRECT_MESSAGE,
        errorCode: 3,
        errors: { currentPassword: [CURRENT_INCORRECT_MESSAGE] },
      },
    });
    vi.mocked(ajaxCall).mockReturnValue(mockFail(failedXhr));
    initChangeEmail();

    fillFields(NEW_EMAIL, NEW_EMAIL, "wrong");
    $("#SettingsChangeEmailBtn").trigger("click");

    const input = $("#SettingsChangeEmailCurrentPassword");
    expect(input.hasClass("is-invalid")).toBe(true);
    expect(input.siblings(".invalid-feedback").text()).toBe(
      CURRENT_INCORRECT_MESSAGE,
    );
  });

  it("renders the newEmail field error on a taken-email 400", () => {
    document.body.innerHTML = formHtml();
    const failedXhr = createMockXhr({
      status: 400,
      responseJSON: {
        status: "Failure",
        message: EMAIL_TAKEN_MESSAGE,
        errorCode: 2,
        errors: { newEmail: [EMAIL_TAKEN_MESSAGE] },
      },
    });
    vi.mocked(ajaxCall).mockReturnValue(mockFail(failedXhr));
    initChangeEmail();

    fillFields(NEW_EMAIL, NEW_EMAIL, CURRENT_PASSWORD);
    $("#SettingsChangeEmailBtn").trigger("click");

    const input = $("#SettingsNewEmail");
    expect(input.hasClass("is-invalid")).toBe(true);
    expect(input.siblings(".invalid-feedback").text()).toBe(
      EMAIL_TAKEN_MESSAGE,
    );
  });

  it("renders the confirmEmail field error on a mismatch 400 (DD-8)", () => {
    document.body.innerHTML = formHtml();
    const failedXhr = createMockXhr({
      status: 400,
      responseJSON: {
        status: "Failure",
        message: "Invalid input, please try again.",
        errorCode: 1,
        errors: { confirmEmail: [MISMATCH_MESSAGE] },
      },
    });
    vi.mocked(ajaxCall).mockReturnValue(mockFail(failedXhr));
    initChangeEmail();

    fillFields(NEW_EMAIL, "different@example.com", CURRENT_PASSWORD);
    $("#SettingsChangeEmailBtn").trigger("click");

    const input = $("#SettingsConfirmNewEmail");
    expect(input.hasClass("is-invalid")).toBe(true);
    expect(input.siblings(".invalid-feedback").text()).toBe(MISMATCH_MESSAGE);
  });

  it("does nothing further when the failure was already handled as a coarse 429", () => {
    document.body.innerHTML = formHtml();
    vi.mocked(is429Handled).mockReturnValue(true);
    const failedXhr = createMockXhr({ status: 429 });
    vi.mocked(ajaxCall).mockReturnValue(mockFail(failedXhr));
    initChangeEmail();

    $("#SettingsChangeEmailBtn").trigger("click");

    const status = $("#SettingsEmailStatus");
    expect(status.hasClass("d-none")).toBe(true);
    expect($("#SettingsNewEmail").hasClass("is-invalid")).toBe(false);
  });

  it("renders the service-issued JSON-429 lockout message in the status region", () => {
    document.body.innerHTML = formHtml();
    vi.mocked(is429Handled).mockReturnValue(false);
    const failedXhr = createMockXhr({
      status: 429,
      responseJSON: {
        status: "Failure",
        message: LOCKOUT_MESSAGE,
        errorCode: 5,
      },
    });
    vi.mocked(ajaxCall).mockReturnValue(mockFail(failedXhr));
    initChangeEmail();

    fillFields(NEW_EMAIL, NEW_EMAIL, CURRENT_PASSWORD);
    $("#SettingsChangeEmailBtn").trigger("click");

    const status = $("#SettingsEmailStatus");
    expect(status.hasClass("d-none")).toBe(false);
    expect(status.hasClass("alert-danger")).toBe(true);
    expect(status.text()).toBe(LOCKOUT_MESSAGE);
    expect($("#SettingsNewEmail").hasClass("is-invalid")).toBe(false);
  });

  it("does not double-submit when Enter fires while a click-triggered request is in flight", () => {
    document.body.innerHTML = formHtml();
    // Pending promise: neither done nor fail fires, so the button stays disabled.
    vi.mocked(ajaxCall).mockReturnValue(createMockJqXHRChainable());
    initChangeEmail();

    fillFields(NEW_EMAIL, NEW_EMAIL, CURRENT_PASSWORD);
    $("#SettingsChangeEmailBtn").trigger("click");
    $("#SettingsNewEmail").trigger($.Event("keyup", { key: "Enter" }));

    expect(vi.mocked(ajaxCall)).toHaveBeenCalledTimes(1);
  });
});
