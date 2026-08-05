import {
  createMockJqXHRChainable,
  createMockXhr,
} from "../../__tests__/helpers/mock-jquery.js";
import { ajaxCall, is429Handled } from "../../lib/ajax.js";
import { emit } from "../../lib/metrics-client.js";
import { UI_EVENTS } from "../../types/metrics-events.js";
import {
  initAccountRemoval,
  _resetAccountRemovalForTests,
} from "../account-removal.js";

vi.mock("../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));

vi.mock("../../lib/globals.js", () => ({
  $: window.jQuery,
  jQuery: window.jQuery,
  bootstrap: window.bootstrap,
}));

vi.mock("../../lib/metrics-client.js", () => ({
  emit: vi.fn(),
}));

const $ = window.jQuery;

const DELETE_URL = "/users/1";
const REDIRECT_URL = "/splash";
const USERNAME = "river_stone";
const PASSWORD = "FakePassword1234";
const INCORRECT_MESSAGE = "Current password is incorrect.";

// Password-account fixture: the delete modal renders a password input + a confirm
// submit button (starting disabled, per the template), wrapped in the
// always-present #SettingsPanelAccount container the init guard keys off. The
// logout-everywhere card/modal moved to the Privacy & Data panel (Phase 5), so it
// is no longer part of this controller's Account-tab fixture.
function passwordHtml(): string {
  return `
    <section id="SettingsPanelAccount">
    <div class="SettingsStatCard" data-account-info="username">
      <dd class="SettingsStatValue">${USERNAME}</dd>
    </div>
    <div class="SettingsDangerZone">
      <button id="SettingsDeleteBtn"></button>
    </div>
    <div class="modal fade" id="SettingsDeleteModal" data-action-url="${DELETE_URL}">
      <div id="SettingsDeleteError" class="alert d-none"></div>
      <input id="SettingsDeleteConfirmUsername" type="text" />
      <input id="SettingsDeleteCurrentPassword" type="password" />
      <button id="SettingsDeleteSubmitBtn" disabled></button>
    </div>
    </section>
  `;
}

// OAuth-only fixture: the delete modal has no password input / no submit button;
// a re-authenticate button instead (starting disabled, typed-username gate DD-8).
function oauthHtml(): string {
  return `
    <section id="SettingsPanelAccount">
    <div class="SettingsStatCard" data-account-info="username">
      <dd class="SettingsStatValue">${USERNAME}</dd>
    </div>
    <div class="SettingsDangerZone">
      <button id="SettingsDeleteBtn"></button>
    </div>
    <div class="modal fade" id="SettingsDeleteModal" data-action-url="${DELETE_URL}">
      <div id="SettingsDeleteError" class="alert d-none"></div>
      <input id="SettingsDeleteConfirmUsername" type="text" />
      <button id="SettingsDeleteReauthBtn" disabled></button>
    </div>
    </section>
  `;
}

function mockDone(xhr: JQuery.jqXHR): JQuery.jqXHR {
  return createMockJqXHRChainable({
    done: (callback: unknown) => {
      (callback as (r: unknown, _t: unknown, xhr: JQuery.jqXHR) => void)(
        xhr.responseJSON,
        "success",
        xhr,
      );
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

function keyup(id: string, key = "x"): void {
  $(`#${id}`).trigger($.Event("keyup", { key }));
}

describe("account-removal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(is429Handled).mockReturnValue(false);
    // Stub the bootstrap jQuery modal plugin (show/hide are no-ops in jsdom).
    // eslint-disable-next-line @typescript-eslint/no-explicit-any -- jQuery plugin stub
    ($.fn as any).modal = vi.fn().mockReturnThis();
    _resetAccountRemovalForTests();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("is a no-op when the account panel is absent", () => {
    document.body.innerHTML = "<div id='Unrelated'></div>";
    initAccountRemoval();
    $("body").trigger("click");
    expect(vi.mocked(ajaxCall)).not.toHaveBeenCalled();
  });

  it("delete: submits typed-username + password and navigates on success", () => {
    document.body.innerHTML = passwordHtml();
    const assignSpy = vi
      .spyOn(window.location, "assign")
      .mockImplementation(() => {});
    const successXhr = createMockXhr({
      status: 200,
      responseJSON: {
        status: "Success",
        message: "Deleted.",
        redirectUrl: REDIRECT_URL,
      },
    });
    vi.mocked(ajaxCall).mockReturnValue(mockDone(successXhr));
    initAccountRemoval();

    $("#SettingsDeleteBtn").trigger("click");
    $("#SettingsDeleteConfirmUsername").val(USERNAME);
    $("#SettingsDeleteCurrentPassword").val(PASSWORD);
    keyup("SettingsDeleteConfirmUsername");
    keyup("SettingsDeleteCurrentPassword");

    // Gate satisfied — submit is now enabled.
    expect($("#SettingsDeleteSubmitBtn").is("[disabled]")).toBe(false);
    $("#SettingsDeleteSubmitBtn").trigger("click");

    expect(vi.mocked(ajaxCall)).toHaveBeenCalledWith("delete", DELETE_URL, {
      currentPassword: PASSWORD,
      confirmUsername: USERNAME,
    });
    expect(assignSpy).toHaveBeenCalledWith(REDIRECT_URL);
    assignSpy.mockRestore();
  });

  it("delete: typed-username mismatch keeps the submit disabled (no request)", () => {
    document.body.innerHTML = passwordHtml();
    initAccountRemoval();

    $("#SettingsDeleteBtn").trigger("click");
    $("#SettingsDeleteConfirmUsername").val("wrong_name");
    $("#SettingsDeleteCurrentPassword").val(PASSWORD);
    keyup("SettingsDeleteConfirmUsername");

    expect($("#SettingsDeleteSubmitBtn").is("[disabled]")).toBe(true);
    $("#SettingsDeleteSubmitBtn").trigger("click");
    expect(vi.mocked(ajaxCall)).not.toHaveBeenCalled();
  });

  it("delete: renders the currentPassword field error on a wrong-password 400", () => {
    document.body.innerHTML = passwordHtml();
    const failedXhr = createMockXhr({
      status: 400,
      responseJSON: {
        status: "Failure",
        message: INCORRECT_MESSAGE,
        errorCode: 2,
        errors: { currentPassword: [INCORRECT_MESSAGE] },
      },
    });
    vi.mocked(ajaxCall).mockReturnValue(mockFail(failedXhr));
    initAccountRemoval();

    $("#SettingsDeleteBtn").trigger("click");
    $("#SettingsDeleteConfirmUsername").val(USERNAME);
    $("#SettingsDeleteCurrentPassword").val("wrong");
    keyup("SettingsDeleteConfirmUsername");
    keyup("SettingsDeleteCurrentPassword");
    $("#SettingsDeleteSubmitBtn").trigger("click");

    const input = $("#SettingsDeleteCurrentPassword");
    expect(input.hasClass("is-invalid")).toBe(true);
    expect(input.siblings(".invalid-feedback").text()).toBe(INCORRECT_MESSAGE);
  });

  it("OAuth-only delete: the re-auth button is gated by the typed-username match (DD-8)", () => {
    document.body.innerHTML = oauthHtml();
    initAccountRemoval();

    $("#SettingsDeleteBtn").trigger("click");
    // Starts gated (disabled).
    expect($("#SettingsDeleteReauthBtn").is("[disabled]")).toBe(true);

    $("#SettingsDeleteConfirmUsername").val(USERNAME);
    keyup("SettingsDeleteConfirmUsername");
    expect($("#SettingsDeleteReauthBtn").is("[disabled]")).toBe(false);
  });

  it("OAuth-only delete: re-auth submits a null password + typed username and navigates on success", () => {
    document.body.innerHTML = oauthHtml();
    const assignSpy = vi
      .spyOn(window.location, "assign")
      .mockImplementation(() => {});
    const successXhr = createMockXhr({
      status: 200,
      responseJSON: {
        status: "Success",
        message: "Re-authenticating.",
        redirectUrl: REDIRECT_URL,
      },
    });
    vi.mocked(ajaxCall).mockReturnValue(mockDone(successXhr));
    initAccountRemoval();

    $("#SettingsDeleteBtn").trigger("click");
    // Satisfy the shared typed-username gate (DD-8) so the re-auth button enables.
    $("#SettingsDeleteConfirmUsername").val(USERNAME);
    keyup("SettingsDeleteConfirmUsername");

    // Gate satisfied — the OAuth-only re-auth button is now enabled.
    expect($("#SettingsDeleteReauthBtn").is("[disabled]")).toBe(false);
    $("#SettingsDeleteReauthBtn").trigger("click");

    // OAuth-proof path sends a null password so the service takes the OAuth branch,
    // still carrying the typed-username confirmation (DD-C).
    expect(vi.mocked(ajaxCall)).toHaveBeenCalledWith("delete", DELETE_URL, {
      currentPassword: null,
      confirmUsername: USERNAME,
    });
    expect(assignSpy).toHaveBeenCalledWith(REDIRECT_URL);
    assignSpy.mockRestore();
  });

  it("clears the delete modal fields on dismiss (DD-7)", () => {
    document.body.innerHTML = passwordHtml();
    initAccountRemoval();

    $("#SettingsDeleteBtn").trigger("click");
    $("#SettingsDeleteConfirmUsername").val(USERNAME);
    $("#SettingsDeleteCurrentPassword").val(PASSWORD);
    $("#SettingsDeleteModal").trigger("hidden.bs.modal");
    expect($("#SettingsDeleteConfirmUsername").val()).toBe("");
    expect($("#SettingsDeleteCurrentPassword").val()).toBe("");
  });

  it("delete: submits on Enter keyup in the confirm-username input", () => {
    document.body.innerHTML = passwordHtml();
    const assignSpy = vi
      .spyOn(window.location, "assign")
      .mockImplementation(() => {});
    const successXhr = createMockXhr({
      status: 200,
      responseJSON: {
        status: "Success",
        message: "Deleted.",
        redirectUrl: REDIRECT_URL,
      },
    });
    vi.mocked(ajaxCall).mockReturnValue(mockDone(successXhr));
    initAccountRemoval();

    $("#SettingsDeleteBtn").trigger("click");
    $("#SettingsDeleteConfirmUsername").val(USERNAME);
    $("#SettingsDeleteCurrentPassword").val(PASSWORD);
    // Open the gate first (a plain keystroke recomputes the typed-username gate).
    keyup("SettingsDeleteConfirmUsername");
    $("#SettingsDeleteConfirmUsername").trigger(
      $.Event("keyup", { key: "Enter" }),
    );

    expect(vi.mocked(ajaxCall)).toHaveBeenCalledWith("delete", DELETE_URL, {
      currentPassword: PASSWORD,
      confirmUsername: USERNAME,
    });
    assignSpy.mockRestore();
  });

  it("does not double-submit when Enter fires while a click-triggered request is in flight", () => {
    document.body.innerHTML = passwordHtml();
    // Pending promise: neither done nor fail fires, so the button stays disabled.
    vi.mocked(ajaxCall).mockReturnValue(createMockJqXHRChainable());
    initAccountRemoval();

    // Delete keeps real text inputs, so its Enter-keyup route genuinely
    // re-enters submitDelete() and exercises the shared reentrancy guard —
    // unlike logout-everywhere, whose field-less modal never binds keyup.
    $("#SettingsDeleteBtn").trigger("click");
    $("#SettingsDeleteConfirmUsername").val(USERNAME);
    $("#SettingsDeleteCurrentPassword").val(PASSWORD);
    keyup("SettingsDeleteConfirmUsername");
    keyup("SettingsDeleteCurrentPassword");
    $("#SettingsDeleteSubmitBtn").trigger("click");
    $("#SettingsDeleteCurrentPassword").trigger(
      $.Event("keyup", { key: "Enter" }),
    );

    expect(vi.mocked(ajaxCall)).toHaveBeenCalledTimes(1);
  });

  it("emits the OPEN metric when the delete modal opens", () => {
    document.body.innerHTML = passwordHtml();
    initAccountRemoval();

    $("#SettingsDeleteBtn").trigger("click");

    expect(vi.mocked(emit)).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_ACCOUNT_DELETE_OPEN,
    });
  });

  it("emits CANCEL on a plain dismiss (no confirm)", () => {
    document.body.innerHTML = passwordHtml();
    initAccountRemoval();

    $("#SettingsDeleteBtn").trigger("click");
    $("#SettingsDeleteModal").trigger("hidden.bs.modal");

    expect(vi.mocked(emit)).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_ACCOUNT_DELETE_CANCEL,
    });
  });

  it("does NOT emit CANCEL after a confirmed removal is dismissed", () => {
    document.body.innerHTML = passwordHtml();
    const assignSpy = vi
      .spyOn(window.location, "assign")
      .mockImplementation(() => {});
    const successXhr = createMockXhr({
      status: 200,
      responseJSON: {
        status: "Success",
        message: "Deleted.",
        redirectUrl: REDIRECT_URL,
      },
    });
    vi.mocked(ajaxCall).mockReturnValue(mockDone(successXhr));
    initAccountRemoval();

    $("#SettingsDeleteBtn").trigger("click");
    $("#SettingsDeleteConfirmUsername").val(USERNAME);
    $("#SettingsDeleteCurrentPassword").val(PASSWORD);
    keyup("SettingsDeleteConfirmUsername");
    keyup("SettingsDeleteCurrentPassword");
    $("#SettingsDeleteSubmitBtn").trigger("click");

    // The modal then closes after the confirmed removal completed.
    $("#SettingsDeleteModal").trigger("hidden.bs.modal");

    expect(vi.mocked(emit)).not.toHaveBeenCalledWith({
      event: UI_EVENTS.UI_ACCOUNT_DELETE_CANCEL,
    });
    assignSpy.mockRestore();
  });
});
