import {
  createMockJqXHRChainable,
  createMockXhr,
} from "../../__tests__/helpers/mock-jquery.js";
import { ajaxCall, is429Handled } from "../../lib/ajax.js";
import { initAdminActions } from "../admin-actions.js";

vi.mock("../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));

const $ = window.jQuery;

const ACTION_URL = "/admin/actions/test-action";
const CONFIRM_TITLE = "Trigger the test action?";
const CONFIRM_BODY = "This runs the test action immediately.";
const SUBMIT_TEXT = "Run it";
const SUCCESS_MESSAGE = "Test action completed.";
const FAILURE_MESSAGE = "Test action failed on the server.";
const REASON_TEXT = "routine maintenance";

const ADMIN_ACTION_HTML = `
  <div id="confirmModal">
    <div id="confirmModalTitle"></div>
    <div id="HomeModalAlertBanner" class="alert alert-danger hidden"></div>
    <div id="confirmModalBody"></div>
    <button id="modalDismiss"></button>
    <button id="modalRedirect"></button>
    <button id="modalSubmit"></button>
  </div>
  <button
    id="TestActionButton"
    data-admin-action="test-action"
    data-action-url="${ACTION_URL}"
    data-confirm-title="${CONFIRM_TITLE}"
    data-confirm-body="${CONFIRM_BODY}"
    data-submit-text="${SUBMIT_TEXT}"
  ></button>
  <div id="AdminActionResult" class="hidden"></div>
`;

let modalCalls: string[];

describe("admin-actions confirm-modal controller", () => {
  beforeEach(() => {
    document.body.innerHTML = ADMIN_ACTION_HTML;
    vi.clearAllMocks();
    vi.mocked(is429Handled).mockReturnValue(false);
    modalCalls = [];
    ($.fn as unknown as Record<string, unknown>).modal = function (
      this: JQuery,
      command: string,
    ) {
      modalCalls.push(command);
      return this;
    };
    initAdminActions();
  });

  function openModalViaButtonClick(): void {
    $("#TestActionButton").trigger("click");
  }

  it("opens the confirm modal with title, body, reason field, and submit text", () => {
    openModalViaButtonClick();

    expect($("#confirmModalTitle").text()).toBe(CONFIRM_TITLE);
    expect($("#confirmModalBody").text()).toContain(CONFIRM_BODY);
    expect($("#AdminActionReasonInput").length).toBe(1);
    expect($("#modalSubmit").text()).toBe(SUBMIT_TEXT);
    expect(modalCalls).toContain("show");
    expect(vi.mocked(ajaxCall)).not.toHaveBeenCalled();
  });

  it("POSTs to the action URL with the typed reason and renders the success message", () => {
    const successXhr = createMockXhr({ status: 200 });
    const chainable = createMockJqXHRChainable({
      done: (callback: unknown) => {
        (
          callback as (
            response: unknown,
            _textStatus: unknown,
            xhr: JQuery.jqXHR,
          ) => void
        )(
          { status: "Success", message: SUCCESS_MESSAGE },
          "success",
          successXhr,
        );
      },
    });
    vi.mocked(ajaxCall).mockReturnValue(chainable as unknown as JQuery.jqXHR);

    openModalViaButtonClick();
    $("#AdminActionReasonInput").val(REASON_TEXT);
    $("#modalSubmit").trigger("click");

    expect(vi.mocked(ajaxCall)).toHaveBeenCalledWith(
      "post",
      ACTION_URL,
      { reason: REASON_TEXT },
      30000,
    );
    expect(modalCalls).toContain("hide");
    expect($("#AdminActionResult").text()).toBe(SUCCESS_MESSAGE);
    expect($("#AdminActionResult").hasClass("alert-success")).toBe(true);
  });

  it("POSTs an empty-string reason and falls back to the default success message when the response has none", () => {
    const successXhr = createMockXhr({ status: 200 });
    const chainable = createMockJqXHRChainable({
      done: (callback: unknown) => {
        (
          callback as (
            response: unknown,
            _textStatus: unknown,
            xhr: JQuery.jqXHR,
          ) => void
        )({ status: "Success" }, "success", successXhr);
      },
    });
    vi.mocked(ajaxCall).mockReturnValue(chainable as unknown as JQuery.jqXHR);

    openModalViaButtonClick();
    $("#modalSubmit").trigger("click");

    expect(vi.mocked(ajaxCall)).toHaveBeenCalledWith(
      "post",
      ACTION_URL,
      { reason: "" },
      30000,
    );
    expect($("#AdminActionResult").text()).toBe("Action completed.");
  });

  it("blocks submission and shows the required-reason message when reason is required but empty", () => {
    $("#TestActionButton").attr("data-reason-required", "true");

    openModalViaButtonClick();
    $("#modalSubmit").trigger("click");

    expect(vi.mocked(ajaxCall)).not.toHaveBeenCalled();
    expect($("#HomeModalAlertBanner").hasClass("hidden")).toBe(false);
    expect($("#HomeModalAlertBanner").text()).toBe(
      "A reason is required for this action.",
    );
  });

  it("shows the server error message in the modal banner and re-enables submit on failure", () => {
    const failedXhr = createMockXhr({
      status: 400,
      responseJSON: { status: "Failure", message: FAILURE_MESSAGE },
    });
    const chainable = createMockJqXHRChainable({
      fail: (callback: unknown) => {
        (callback as (xhr: JQuery.jqXHR) => void)(failedXhr);
      },
    });
    vi.mocked(ajaxCall).mockReturnValue(chainable as unknown as JQuery.jqXHR);

    openModalViaButtonClick();
    $("#modalSubmit").trigger("click");

    expect($("#HomeModalAlertBanner").hasClass("hidden")).toBe(false);
    expect($("#HomeModalAlertBanner").text()).toBe(FAILURE_MESSAGE);
    expect($("#modalSubmit").prop("disabled")).toBe(false);
    expect(modalCalls).not.toContain("hide");
  });

  it("does nothing further when a failure was already handled as a 429", () => {
    vi.mocked(is429Handled).mockReturnValue(true);
    const failedXhr = createMockXhr({ status: 429 });
    const chainable = createMockJqXHRChainable({
      fail: (callback: unknown) => {
        (callback as (xhr: JQuery.jqXHR) => void)(failedXhr);
      },
    });
    vi.mocked(ajaxCall).mockReturnValue(chainable as unknown as JQuery.jqXHR);

    openModalViaButtonClick();
    $("#modalSubmit").trigger("click");

    expect($("#HomeModalAlertBanner").hasClass("hidden")).toBe(true);
  });

  it("clears the reason field and banner when the modal closes", () => {
    openModalViaButtonClick();
    expect($("#AdminActionReasonInput").length).toBe(1);

    $("#confirmModal").trigger("hidden.bs.modal");

    expect($("#AdminActionReasonInput").length).toBe(0);
    expect($("#HomeModalAlertBanner").hasClass("hidden")).toBe(true);
  });
});
