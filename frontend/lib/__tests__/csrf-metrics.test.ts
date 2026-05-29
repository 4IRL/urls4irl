import { UI_EVENTS } from "../metrics-events.js";
import { setupCSRF } from "../csrf.js";

const { mockMetricsClient } = await vi.hoisted(
  async () => await import("../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../metrics-client.js", () => mockMetricsClient());

vi.mock("../page-utils.js", () => ({
  showNewPageOnAJAXHTMLResponse: vi.fn(),
}));

const $ = window.jQuery;

describe("csrf prefilter 429 handling — metrics", () => {
  let ajaxPrefilterSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    ajaxPrefilterSpy = vi.spyOn($, "ajaxPrefilter");
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  function installPrefilter(options: JQuery.AjaxSettings): void {
    setupCSRF();
    const prefilterCallback = ajaxPrefilterSpy.mock.calls[0][0];
    prefilterCallback(options, {}, {} as JQuery.jqXHR);
  }

  it("emits ui_rate_limit_hit and calls showNewPageOnAJAXHTMLResponse on HTML 429; sets _429Handled and does NOT chain prevError", async () => {
    const { emit } = await import("../metrics-client.js");
    const { showNewPageOnAJAXHTMLResponse } = await import("../page-utils.js");
    const prevError = vi.fn();
    const options: JQuery.AjaxSettings = {
      error: prevError as unknown as JQuery.TypeOrArray<
        JQuery.Ajax.ErrorCallback<unknown>
      >,
    };
    installPrefilter(options);

    const fakeXhr = {
      status: 429,
      responseText: "<html>Rate limited</html>",
      getResponseHeader: vi.fn().mockReturnValue("text/html; charset=utf-8"),
    } as unknown as JQuery.jqXHR;

    (options.error as (...args: unknown[]) => void).call(
      null,
      fakeXhr,
      "error",
      "Too Many Requests",
    );

    expect(emit).toHaveBeenCalledWith(UI_EVENTS.UI_RATE_LIMIT_HIT);
    expect(emit).toHaveBeenCalledTimes(1);
    expect(showNewPageOnAJAXHTMLResponse).toHaveBeenCalledWith(
      "<html>Rate limited</html>",
    );
    expect(
      (fakeXhr as JQuery.jqXHR & { _429Handled: boolean })._429Handled,
    ).toBe(true);
    expect(prevError).not.toHaveBeenCalled();
  });

  it("emits ui_rate_limit_hit and chains prevError on JSON 429; does NOT call showNewPageOnAJAXHTMLResponse and does NOT set _429Handled", async () => {
    const { emit } = await import("../metrics-client.js");
    const { showNewPageOnAJAXHTMLResponse } = await import("../page-utils.js");
    const prevError = vi.fn();
    const options: JQuery.AjaxSettings = {
      error: prevError as unknown as JQuery.TypeOrArray<
        JQuery.Ajax.ErrorCallback<unknown>
      >,
    };
    installPrefilter(options);

    const fakeXhr = {
      status: 429,
      responseText: '{"error":"rate_limited"}',
      getResponseHeader: vi.fn().mockReturnValue("application/json"),
    } as unknown as JQuery.jqXHR;

    (options.error as (...args: unknown[]) => void).call(
      null,
      fakeXhr,
      "error",
      "Too Many Requests",
    );

    expect(emit).toHaveBeenCalledWith(UI_EVENTS.UI_RATE_LIMIT_HIT);
    expect(emit).toHaveBeenCalledTimes(1);
    expect(showNewPageOnAJAXHTMLResponse).not.toHaveBeenCalled();
    expect(
      (fakeXhr as JQuery.jqXHR & { _429Handled?: boolean })._429Handled,
    ).toBeUndefined();
    expect(prevError).toHaveBeenCalledTimes(1);
    expect(prevError).toHaveBeenCalledWith(
      fakeXhr,
      "error",
      "Too Many Requests",
    );
  });

  it("does NOT emit on non-429 errors and chains prevError", async () => {
    const { emit } = await import("../metrics-client.js");
    const { showNewPageOnAJAXHTMLResponse } = await import("../page-utils.js");
    const prevError = vi.fn();
    const options: JQuery.AjaxSettings = {
      error: prevError as unknown as JQuery.TypeOrArray<
        JQuery.Ajax.ErrorCallback<unknown>
      >,
    };
    installPrefilter(options);

    const fakeXhr = {
      status: 500,
      responseText: "Internal Server Error",
      getResponseHeader: vi.fn().mockReturnValue("text/html; charset=utf-8"),
    } as unknown as JQuery.jqXHR;

    (options.error as (...args: unknown[]) => void).call(
      null,
      fakeXhr,
      "error",
      "Internal Server Error",
    );

    expect(emit).not.toHaveBeenCalled();
    expect(showNewPageOnAJAXHTMLResponse).not.toHaveBeenCalled();
    expect(prevError).toHaveBeenCalledTimes(1);
    expect(prevError).toHaveBeenCalledWith(
      fakeXhr,
      "error",
      "Internal Server Error",
    );
  });
});
