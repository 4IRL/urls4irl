import { showNewPageOnAJAXHTMLResponse } from "../lib/page-utils.js";
import {
  handleContactSubmit,
  clearFieldErrors,
  showFieldErrors,
  showBanner,
  startSubmitCountdown,
} from "../contact.js";

vi.mock("../lib/page-utils.js", () => ({
  showNewPageOnAJAXHTMLResponse: vi.fn(),
}));

vi.mock("../lib/csrf.js", () => ({
  setupCSRF: vi.fn(),
}));

vi.mock("../lib/security-check.js", () => ({}));

vi.mock("../lib/navbar-shared.js", () => ({
  initNavbarRouting: vi.fn(),
}));

vi.mock("../lib/globals.js", () => ({
  $: window.jQuery,
  jQuery: window.jQuery,
  bootstrap: window.bootstrap,
}));

vi.mock("../lib/config.js", () => {
  const configScript = document.getElementById("app-config");
  const config = JSON.parse(configScript?.textContent ?? "{}");
  return { APP_CONFIG: config };
});

const $ = window.jQuery;

const CONTACT_FORM_HTML = `
  <form id="ContactForm" method="POST" novalidate>
    <div id="Banner" class="alert hidden" role="alert"></div>
    <input id="subject" name="subject" type="text" class="form-control" value="Test Subject" />
    <div id="subject-error" class="invalid-feedback"></div>
    <textarea id="content" name="content" class="form-control">Test content here</textarea>
    <div id="content-error" class="invalid-feedback"></div>
    <input id="submit" type="submit" value="Submit" />
  </form>
`;

describe("contact form AJAX submission", () => {
  let ajaxSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    document.body.innerHTML = CONTACT_FORM_HTML;
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("sends JSON POST and shows success banner on 200 response", () => {
    const mockDeferred = $.Deferred();
    ajaxSpy = vi
      .spyOn($, "ajax")
      .mockReturnValue(mockDeferred as unknown as JQuery.jqXHR);

    const $form = $("#ContactForm");
    const fakeEvent = {
      preventDefault: vi.fn(),
    } as unknown as JQuery.TriggeredEvent;
    handleContactSubmit(fakeEvent, $form);

    expect(fakeEvent.preventDefault).toHaveBeenCalled();
    expect(ajaxSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        url: "/contact",
        type: "POST",
        contentType: "application/json",
      }),
    );

    // Verify JSON body contains subject and content
    const ajaxCall = ajaxSpy.mock.calls[0][0];
    const parsedBody = JSON.parse(ajaxCall.data);
    expect(parsedBody).toEqual({
      subject: "Test Subject",
      content: "Test content here",
    });

    // Simulate success response
    mockDeferred.resolve({ message: "Sent! Thanks for reaching out." });

    const $banner = $form.find("#Banner");
    expect($banner.hasClass("hidden")).toBe(false);
    expect($banner.hasClass("alert-success")).toBe(true);
    expect($banner.text()).toBe("Sent! Thanks for reaching out.");
  });

  it("disables submit button with countdown on success", () => {
    vi.useFakeTimers();
    const mockDeferred = $.Deferred();
    ajaxSpy = vi
      .spyOn($, "ajax")
      .mockReturnValue(mockDeferred as unknown as JQuery.jqXHR);

    const $form = $("#ContactForm");
    const fakeEvent = {
      preventDefault: vi.fn(),
    } as unknown as JQuery.TriggeredEvent;
    handleContactSubmit(fakeEvent, $form);

    mockDeferred.resolve({ message: "Sent! Thanks for reaching out." });

    const $submitBtn = $form.find("#submit");
    expect($submitBtn.prop("disabled")).toBe(true);
    expect($submitBtn.val()).toBe("Submitted! Please wait 5s...");

    vi.advanceTimersByTime(1000);
    expect($submitBtn.val()).toBe("Submitted! Please wait 4s...");

    vi.advanceTimersByTime(4000);
    expect($submitBtn.prop("disabled")).toBe(false);
    expect($submitBtn.val()).toBe("Submit");

    vi.useRealTimers();
  });

  it("shows field-level errors on 400 validation failure", () => {
    const mockDeferred = $.Deferred();
    ajaxSpy = vi
      .spyOn($, "ajax")
      .mockReturnValue(mockDeferred as unknown as JQuery.jqXHR);

    const $form = $("#ContactForm");
    const fakeEvent = {
      preventDefault: vi.fn(),
    } as unknown as JQuery.TriggeredEvent;
    handleContactSubmit(fakeEvent, $form);

    const fakeXhr = {
      status: 400,
      responseJSON: {
        status: "Failure",
        message: "Unable to submit contact form.",
        errors: {
          subject: ["Subject must be at least 5 characters."],
          content: ["This field is required."],
        },
      },
      getResponseHeader: vi.fn(),
    };
    mockDeferred.reject(fakeXhr, "error", "Bad Request");

    expect($form.find("#subject").hasClass("is-invalid")).toBe(true);
    expect($form.find("#subject-error").text()).toBe(
      "Subject must be at least 5 characters.",
    );
    expect($form.find("#content").hasClass("is-invalid")).toBe(true);
    expect($form.find("#content-error").text()).toBe("This field is required.");
  });

  it("shows page-level error banner on 400 without field errors", () => {
    const mockDeferred = $.Deferred();
    ajaxSpy = vi
      .spyOn($, "ajax")
      .mockReturnValue(mockDeferred as unknown as JQuery.jqXHR);

    const $form = $("#ContactForm");
    const fakeEvent = {
      preventDefault: vi.fn(),
    } as unknown as JQuery.TriggeredEvent;
    handleContactSubmit(fakeEvent, $form);

    const fakeXhr = {
      status: 400,
      responseJSON: {
        status: "Failure",
        message: "Unable to submit contact form.",
      },
      getResponseHeader: vi.fn(),
    };
    mockDeferred.reject(fakeXhr, "error", "Bad Request");

    const $banner = $form.find("#Banner");
    expect($banner.hasClass("hidden")).toBe(false);
    expect($banner.hasClass("alert-danger")).toBe(true);
    expect($banner.text()).toBe("Unable to submit contact form.");
  });

  it("calls showNewPageOnAJAXHTMLResponse on 403 CSRF failure", () => {
    const mockDeferred = $.Deferred();
    ajaxSpy = vi
      .spyOn($, "ajax")
      .mockReturnValue(mockDeferred as unknown as JQuery.jqXHR);

    const $form = $("#ContactForm");
    const fakeEvent = {
      preventDefault: vi.fn(),
    } as unknown as JQuery.TriggeredEvent;
    handleContactSubmit(fakeEvent, $form);

    const fakeXhr = {
      status: 403,
      responseText: "<html>Forbidden</html>",
      getResponseHeader: vi.fn().mockReturnValue("text/html; charset=utf-8"),
    };
    mockDeferred.reject(fakeXhr, "error", "Forbidden");

    expect(showNewPageOnAJAXHTMLResponse).toHaveBeenCalledWith(
      "<html>Forbidden</html>",
    );
  });

  it("shows generic error banner when responseJSON is absent and Content-Type is not text/html", () => {
    const mockDeferred = $.Deferred();
    ajaxSpy = vi
      .spyOn($, "ajax")
      .mockReturnValue(mockDeferred as unknown as JQuery.jqXHR);

    const $form = $("#ContactForm");
    const fakeEvent = {
      preventDefault: vi.fn(),
    } as unknown as JQuery.TriggeredEvent;
    handleContactSubmit(fakeEvent, $form);

    const fakeXhr = {
      status: 500,
      responseText: "Internal Server Error",
      getResponseHeader: vi.fn().mockReturnValue("text/plain"),
    };
    mockDeferred.reject(fakeXhr, "error", "Internal Server Error");

    const $banner = $form.find("#Banner");
    expect($banner.hasClass("hidden")).toBe(false);
    expect($banner.hasClass("alert-danger")).toBe(true);
    expect($banner.text()).toBe("Unable to submit contact form.");
    expect(showNewPageOnAJAXHTMLResponse).not.toHaveBeenCalled();
  });

  it("calls showNewPageOnAJAXHTMLResponse on 429 rate limit", () => {
    const mockDeferred = $.Deferred();
    ajaxSpy = vi
      .spyOn($, "ajax")
      .mockReturnValue(mockDeferred as unknown as JQuery.jqXHR);

    const $form = $("#ContactForm");
    const fakeEvent = {
      preventDefault: vi.fn(),
    } as unknown as JQuery.TriggeredEvent;
    handleContactSubmit(fakeEvent, $form);

    const fakeXhr = {
      status: 429,
      responseText: "<html>Rate limited</html>",
      getResponseHeader: vi.fn().mockReturnValue("text/html; charset=utf-8"),
    };
    mockDeferred.reject(fakeXhr, "error", "Too Many Requests");

    expect(showNewPageOnAJAXHTMLResponse).toHaveBeenCalledWith(
      "<html>Rate limited</html>",
    );
  });
});

describe("contact form helper functions", () => {
  beforeEach(() => {
    document.body.innerHTML = CONTACT_FORM_HTML;
  });

  it("clearFieldErrors removes is-invalid class and error text", () => {
    const $form = $("#ContactForm");
    $form.find("#subject").addClass("is-invalid");
    $form.find("#subject-error").text("Some error");

    clearFieldErrors($form);

    expect($form.find("#subject").hasClass("is-invalid")).toBe(false);
    expect($form.find("#subject-error").text()).toBe("");
  });

  it("showFieldErrors adds is-invalid class and sets error text", () => {
    const $form = $("#ContactForm");
    showFieldErrors($form, {
      subject: ["Error 1", "Error 2"],
    });

    expect($form.find("#subject").hasClass("is-invalid")).toBe(true);
    expect($form.find("#subject-error").text()).toBe("Error 1, Error 2");
  });

  it("showBanner displays message with correct alert type", () => {
    const $banner = $("#Banner");
    showBanner($banner, "Test message", "success");

    expect($banner.hasClass("hidden")).toBe(false);
    expect($banner.hasClass("alert-success")).toBe(true);
    expect($banner.text()).toBe("Test message");
  });

  it("startSubmitCountdown disables button and re-enables after countdown", () => {
    vi.useFakeTimers();
    const $submitBtn = $("#submit");

    startSubmitCountdown($submitBtn, 3);

    expect($submitBtn.prop("disabled")).toBe(true);
    expect($submitBtn.val()).toBe("Submitted! Please wait 3s...");

    vi.advanceTimersByTime(3000);
    expect($submitBtn.prop("disabled")).toBe(false);
    expect($submitBtn.val()).toBe("Submit");

    vi.useRealTimers();
  });
});
