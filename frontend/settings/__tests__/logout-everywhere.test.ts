import {
  createMockJqXHRChainable,
  createMockXhr,
} from "../../__tests__/helpers/mock-jquery.js";
import { ajaxCall, is429Handled } from "../../lib/ajax.js";
import { emit } from "../../lib/metrics-client.js";
import { UI_EVENTS } from "../../types/metrics-events.js";
import {
  initLogoutEverywhere,
  _resetLogoutEverywhereForTests,
} from "../logout-everywhere.js";

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

const LOGOUT_EVERYWHERE_URL = "/users/1/logout-everywhere";
const REDIRECT_URL = "/splash";
const SERVICE_ERROR_MESSAGE = "Something went wrong. Please try again.";

// The logout-everywhere card + modal now live in the Privacy & Data panel, whose
// container `#SettingsPanelPrivacyData` is the init guard's no-op key.
function privacyDataHtml(): string {
  return `
    <section id="SettingsPanelPrivacyData">
    <div id="SettingsLogoutEverywhere">
      <button id="SettingsLogoutEverywhereBtn"></button>
    </div>
    <div class="modal fade" id="SettingsLogoutEverywhereModal" data-action-url="${LOGOUT_EVERYWHERE_URL}">
      <div id="SettingsLogoutEverywhereError" class="alert d-none"></div>
      <button id="SettingsLogoutEverywhereSubmitBtn"></button>
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

describe("logout-everywhere", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(is429Handled).mockReturnValue(false);
    // Stub the bootstrap jQuery modal plugin (show/hide are no-ops in jsdom).
    // eslint-disable-next-line @typescript-eslint/no-explicit-any -- jQuery plugin stub
    ($.fn as any).modal = vi.fn().mockReturnThis();
    _resetLogoutEverywhereForTests();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("is a no-op when the Privacy & Data panel is absent", () => {
    document.body.innerHTML = "<div id='Unrelated'></div>";
    initLogoutEverywhere();
    $("body").trigger("click");
    expect(vi.mocked(ajaxCall)).not.toHaveBeenCalled();
  });

  it("POSTs an empty body and navigates to the redirect", () => {
    document.body.innerHTML = privacyDataHtml();
    const assignSpy = vi
      .spyOn(window.location, "assign")
      .mockImplementation(() => {});
    const successXhr = createMockXhr({
      status: 200,
      responseJSON: {
        status: "Success",
        message: "Signed out everywhere.",
        redirectUrl: REDIRECT_URL,
      },
    });
    vi.mocked(ajaxCall).mockReturnValue(mockDone(successXhr));
    initLogoutEverywhere();

    $("#SettingsLogoutEverywhereBtn").trigger("click");
    $("#SettingsLogoutEverywhereSubmitBtn").trigger("click");

    expect(vi.mocked(ajaxCall)).toHaveBeenCalledWith(
      "post",
      LOGOUT_EVERYWHERE_URL,
      {},
    );
    expect(assignSpy).toHaveBeenCalledWith(REDIRECT_URL);
    assignSpy.mockRestore();
  });

  it("does nothing further when the failure is an already-handled 429", () => {
    document.body.innerHTML = privacyDataHtml();
    vi.mocked(is429Handled).mockReturnValue(true);
    const failedXhr = createMockXhr({ status: 429 });
    vi.mocked(ajaxCall).mockReturnValue(mockFail(failedXhr));
    initLogoutEverywhere();

    $("#SettingsLogoutEverywhereBtn").trigger("click");
    $("#SettingsLogoutEverywhereSubmitBtn").trigger("click");

    expect($("#SettingsLogoutEverywhereError").hasClass("d-none")).toBe(true);
  });

  it("surfaces a service-error message in the in-modal banner", () => {
    document.body.innerHTML = privacyDataHtml();
    vi.mocked(is429Handled).mockReturnValue(false);
    const failedXhr = createMockXhr({
      status: 500,
      responseJSON: {
        status: "Failure",
        message: SERVICE_ERROR_MESSAGE,
        errorCode: 1,
      },
    });
    vi.mocked(ajaxCall).mockReturnValue(mockFail(failedXhr));
    initLogoutEverywhere();

    $("#SettingsLogoutEverywhereBtn").trigger("click");
    $("#SettingsLogoutEverywhereSubmitBtn").trigger("click");

    const error = $("#SettingsLogoutEverywhereError");
    expect(error.hasClass("d-none")).toBe(false);
    expect(error.text()).toBe(SERVICE_ERROR_MESSAGE);
  });

  it("emits the OPEN metric when the modal opens", () => {
    document.body.innerHTML = privacyDataHtml();
    initLogoutEverywhere();

    $("#SettingsLogoutEverywhereBtn").trigger("click");

    expect(vi.mocked(emit)).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_ACCOUNT_LOGOUT_EVERYWHERE_OPEN,
    });
  });

  it("emits CANCEL on a plain dismiss (no confirm)", () => {
    document.body.innerHTML = privacyDataHtml();
    initLogoutEverywhere();

    $("#SettingsLogoutEverywhereBtn").trigger("click");
    $("#SettingsLogoutEverywhereModal").trigger("hidden.bs.modal");

    expect(vi.mocked(emit)).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_ACCOUNT_LOGOUT_EVERYWHERE_CANCEL,
    });
  });
});
