import { setupCSRF } from "../csrf.js";

const $ = window.jQuery;

describe("setupCSRF", () => {
  let ajaxSetupSpy: ReturnType<typeof vi.spyOn>;
  let ajaxPrefilterSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    ajaxSetupSpy = vi.spyOn($, "ajaxSetup");
    ajaxPrefilterSpy = vi.spyOn($, "ajaxPrefilter");
  });

  afterEach(() => {
    vi.restoreAllMocks();
    document.head
      .querySelectorAll("meta[name=csrf-token]")
      .forEach((el) => el.remove());
  });

  function injectCsrfMeta(token: string): void {
    const meta = document.createElement("meta");
    meta.name = "csrf-token";
    meta.content = token;
    document.head.appendChild(meta);
  }

  describe("beforeSend (ajaxSetup)", () => {
    it("does not call setRequestHeader when CSRF meta tag is absent", () => {
      setupCSRF();

      const beforeSend = ajaxSetupSpy.mock.calls[0][0].beforeSend!;
      const mockXhr = { setRequestHeader: vi.fn() } as unknown as JQuery.jqXHR;
      const settings: JQuery.AjaxSettings = {
        type: "POST",
        crossDomain: false,
      };

      beforeSend.call(settings, mockXhr, settings);

      expect(mockXhr.setRequestHeader).not.toHaveBeenCalled();
    });

    it("calls setRequestHeader with token when CSRF meta tag is present", () => {
      injectCsrfMeta("test-csrf-token");
      setupCSRF();

      const beforeSend = ajaxSetupSpy.mock.calls[0][0].beforeSend!;
      const mockXhr = { setRequestHeader: vi.fn() } as unknown as JQuery.jqXHR;
      const settings: JQuery.AjaxSettings = {
        type: "POST",
        crossDomain: false,
      };

      beforeSend.call(settings, mockXhr, settings);

      expect(mockXhr.setRequestHeader).toHaveBeenCalledWith(
        "X-CSRFToken",
        "test-csrf-token",
      );
    });

    it("does not cause a regex error when settings.type is undefined", () => {
      injectCsrfMeta("test-csrf-token");
      setupCSRF();

      const beforeSend = ajaxSetupSpy.mock.calls[0][0].beforeSend!;
      const mockXhr = { setRequestHeader: vi.fn() } as unknown as JQuery.jqXHR;
      const settings: JQuery.AjaxSettings = {
        type: undefined,
        crossDomain: false,
      };

      expect(() => beforeSend.call(settings, mockXhr, settings)).not.toThrow();
    });

    it("skips header for GET requests", () => {
      injectCsrfMeta("test-csrf-token");
      setupCSRF();

      const beforeSend = ajaxSetupSpy.mock.calls[0][0].beforeSend!;
      const mockXhr = { setRequestHeader: vi.fn() } as unknown as JQuery.jqXHR;
      const settings: JQuery.AjaxSettings = { type: "GET", crossDomain: false };

      beforeSend.call(settings, mockXhr, settings);

      expect(mockXhr.setRequestHeader).not.toHaveBeenCalled();
    });

    it("skips header for cross-domain requests", () => {
      injectCsrfMeta("test-csrf-token");
      setupCSRF();

      const beforeSend = ajaxSetupSpy.mock.calls[0][0].beforeSend!;
      const mockXhr = { setRequestHeader: vi.fn() } as unknown as JQuery.jqXHR;
      const settings: JQuery.AjaxSettings = { type: "POST" };

      beforeSend.call({ ...settings, crossDomain: true }, mockXhr, settings);

      expect(mockXhr.setRequestHeader).not.toHaveBeenCalled();
    });
  });

  describe("ajaxPrefilter (429 handling)", () => {
    it("replaces options.error to intercept 429 responses", () => {
      setupCSRF();

      const prefilterCallback = ajaxPrefilterSpy.mock.calls[0][0];
      const options: JQuery.AjaxSettings = {
        error: vi.fn() as unknown as JQuery.TypeOrArray<
          JQuery.Ajax.ErrorCallback<unknown>
        >,
      };
      const originalError = options.error;
      const mockJqXHR = {} as JQuery.jqXHR;

      prefilterCallback(options, {}, mockJqXHR);

      expect(options.error).not.toBe(originalError);
    });
  });
});
