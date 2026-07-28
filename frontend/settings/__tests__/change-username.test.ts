import {
  createMockJqXHRChainable,
  createMockXhr,
} from "../../__tests__/helpers/mock-jquery.js";
import { ajaxCall, is429Handled } from "../../lib/ajax.js";
import {
  initChangeUsername,
  _resetChangeUsernameForTests,
} from "../change-username.js";

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

const CHANGE_URL = "/users/1/username";
const NEW_USERNAME = "renamed_user";
const SUCCESS_MESSAGE = "Your username has been updated.";
const TAKEN_MESSAGE = "That username is already taken. Please choose another.";
const RATE_LIMIT_MESSAGE =
  "You've changed your username too many times today. Try again later.";

function formHtml(currentUsername: string): string {
  return `
    <b id="loggedInAsHeader">Logged in as <span class="navLoggedInAsUsername">${currentUsername}</span></b>
    <b>Logged in as <span class="navLoggedInAsUsername">${currentUsername}</span></b>
    <section id="SettingsPanelAccount">
      <div class="SettingsStatCard" data-account-info="username">
        <dd class="SettingsStatValue">${currentUsername}</dd>
      </div>
      <div class="SettingsChangeUsername">
        <div id="SettingsUsernameStatus" class="alert d-none" role="alert"></div>
        <div class="form-group">
          <input id="SettingsNewUsername" class="form-control" type="text" value="${currentUsername}" />
        </div>
        <button type="button" id="SettingsChangeUsernameBtn" data-action-url="${CHANGE_URL}"></button>
      </div>
    </section>
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

describe("change-username", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(is429Handled).mockReturnValue(false);
    _resetChangeUsernameForTests();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("is a no-op when #SettingsNewUsername is absent", () => {
    document.body.innerHTML = "<div id='Unrelated'></div>";
    initChangeUsername();
    $("body").trigger("click");
    expect(vi.mocked(ajaxCall)).not.toHaveBeenCalled();
  });

  it("PUTs the new username and updates both displays + status banner on success (DD-15/DD-12)", () => {
    document.body.innerHTML = formHtml("old_name");
    const successXhr = createMockXhr({ status: 200 });
    vi.mocked(ajaxCall).mockReturnValue(
      mockDone(
        { username: NEW_USERNAME, status: "Success", message: SUCCESS_MESSAGE },
        successXhr,
      ),
    );
    initChangeUsername();

    $("#SettingsNewUsername").val(NEW_USERNAME);
    $("#SettingsChangeUsernameBtn").trigger("click");

    expect(vi.mocked(ajaxCall)).toHaveBeenCalledWith("put", CHANGE_URL, {
      username: NEW_USERNAME,
    });
    // Every on-page display refreshes from the echoed username — the input, the
    // account-info card, and both navbar "Logged in as" labels.
    expect($("#SettingsNewUsername").val()).toBe(NEW_USERNAME);
    expect($('[data-account-info="username"] .SettingsStatValue').text()).toBe(
      NEW_USERNAME,
    );
    const navLabels = $(".navLoggedInAsUsername");
    expect(navLabels.length).toBe(2);
    navLabels.each(function () {
      expect($(this).text()).toBe(NEW_USERNAME);
    });
    // Server-sourced banner text rendered.
    const status = $("#SettingsUsernameStatus");
    expect(status.hasClass("d-none")).toBe(false);
    expect(status.hasClass("alert-success")).toBe(true);
    expect(status.text()).toBe(SUCCESS_MESSAGE);
    // Button re-enabled for a subsequent edit (DD-16).
    expect($("#SettingsChangeUsernameBtn").attr("disabled")).toBeUndefined();
  });

  it("submits on Enter keyup in the username input", () => {
    document.body.innerHTML = formHtml("old_name");
    const successXhr = createMockXhr({ status: 200 });
    vi.mocked(ajaxCall).mockReturnValue(
      mockDone(
        { username: NEW_USERNAME, status: "Success", message: SUCCESS_MESSAGE },
        successXhr,
      ),
    );
    initChangeUsername();

    const input = $("#SettingsNewUsername");
    input.val(NEW_USERNAME);
    input.trigger($.Event("keyup", { key: "Enter" }));

    expect(vi.mocked(ajaxCall)).toHaveBeenCalledWith("put", CHANGE_URL, {
      username: NEW_USERNAME,
    });
  });

  it("ignores non-Enter keyup events", () => {
    document.body.innerHTML = formHtml("old_name");
    initChangeUsername();

    const input = $("#SettingsNewUsername");
    input.val(NEW_USERNAME);
    input.trigger($.Event("keyup", { key: "a" }));

    expect(vi.mocked(ajaxCall)).not.toHaveBeenCalled();
  });

  it("renders the username field error on a 400 failure", () => {
    document.body.innerHTML = formHtml("old_name");
    const failedXhr = createMockXhr({
      status: 400,
      responseJSON: {
        status: "Failure",
        message: "Unable to change username.",
        errorCode: 2,
        errors: { username: [TAKEN_MESSAGE] },
      },
    });
    vi.mocked(ajaxCall).mockReturnValue(mockFail(failedXhr));
    initChangeUsername();

    $("#SettingsNewUsername").val("taken_name");
    $("#SettingsChangeUsernameBtn").trigger("click");

    const input = $("#SettingsNewUsername");
    expect(input.hasClass("is-invalid")).toBe(true);
    expect(input.siblings(".invalid-feedback").text()).toBe(TAKEN_MESSAGE);
  });

  it("renders the JSON 429 daily-limit message in the status region (is429Handled false)", () => {
    document.body.innerHTML = formHtml("old_name");
    const failedXhr = createMockXhr({
      status: 429,
      responseJSON: {
        status: "Failure",
        message: RATE_LIMIT_MESSAGE,
        errorCode: 3,
        errors: null,
      },
    });
    vi.mocked(ajaxCall).mockReturnValue(mockFail(failedXhr));
    initChangeUsername();

    $("#SettingsChangeUsernameBtn").trigger("click");

    const status = $("#SettingsUsernameStatus");
    expect(status.hasClass("d-none")).toBe(false);
    expect(status.hasClass("alert-danger")).toBe(true);
    expect(status.text()).toBe(RATE_LIMIT_MESSAGE);
  });

  it("does nothing further when the failure was already handled as a coarse 429", () => {
    document.body.innerHTML = formHtml("old_name");
    vi.mocked(is429Handled).mockReturnValue(true);
    const failedXhr = createMockXhr({ status: 429 });
    vi.mocked(ajaxCall).mockReturnValue(mockFail(failedXhr));
    initChangeUsername();

    $("#SettingsChangeUsernameBtn").trigger("click");

    const status = $("#SettingsUsernameStatus");
    expect(status.hasClass("d-none")).toBe(true);
    expect($("#SettingsNewUsername").hasClass("is-invalid")).toBe(false);
  });

  it("does not double-submit when Enter fires while a click-triggered request is in flight (DD-18)", () => {
    document.body.innerHTML = formHtml("old_name");
    // Pending promise: neither done nor fail fires, so the button stays disabled.
    vi.mocked(ajaxCall).mockReturnValue(createMockJqXHRChainable());
    initChangeUsername();

    $("#SettingsNewUsername").val(NEW_USERNAME);
    $("#SettingsChangeUsernameBtn").trigger("click");
    $("#SettingsNewUsername").trigger($.Event("keyup", { key: "Enter" }));

    expect(vi.mocked(ajaxCall)).toHaveBeenCalledTimes(1);
  });
});
