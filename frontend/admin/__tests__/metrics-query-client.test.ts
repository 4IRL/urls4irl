import { createMockJqXHRChainable } from "../../__tests__/helpers/mock-jquery.js";

// `vi.mock(...)` is hoisted above all imports, so the spy must be created via
// `vi.hoisted(...)` to be referenced from inside the mock factory. Mirrors the
// pattern in `frontend/lib/__tests__/metrics-client.test.ts`.
const { ajaxCallSpy } = vi.hoisted(() => ({ ajaxCallSpy: vi.fn() }));

vi.mock("../../lib/ajax.js", () => ({
  ajaxCall: ajaxCallSpy,
}));

import {
  fetchSummary,
  fetchTimeseries,
  fetchTopEvents,
} from "../metrics-query-client.js";

describe("metrics-query-client", () => {
  beforeEach(() => {
    ajaxCallSpy.mockReset();
    ajaxCallSpy.mockReturnValue(createMockJqXHRChainable({ done: vi.fn() }));
  });

  describe("fetchTopEvents", () => {
    it("builds the correct URL with window, category, and explicit limit", () => {
      fetchTopEvents({ window: "day", category: "ui", limit: 5 });
      expect(ajaxCallSpy).toHaveBeenCalledOnce();
      const [method, url, data, timeout] = ajaxCallSpy.mock.calls[0];
      expect(method).toBe("GET");
      expect(url).toBe("/api/metrics/query/top?window=day&category=ui&limit=5");
      expect(data).toBeNull();
      expect(timeout).toBe(5000);
    });

    it("defaults limit to 10 when not supplied", () => {
      fetchTopEvents({ window: "week", category: "api" });
      const [, url] = ajaxCallSpy.mock.calls[0];
      expect(url).toBe(
        "/api/metrics/query/top?window=week&category=api&limit=10",
      );
    });

    it("forwards the domain category when requested", () => {
      fetchTopEvents({ window: "month", category: "domain", limit: 25 });
      const [, url] = ajaxCallSpy.mock.calls[0];
      expect(url).toBe(
        "/api/metrics/query/top?window=month&category=domain&limit=25",
      );
    });
  });

  describe("fetchTimeseries", () => {
    it("forwards event_name, window, and resolution", () => {
      fetchTimeseries({
        eventName: "utub_opened",
        window: "week",
        resolution: "day",
      });
      const [method, url, data, timeout] = ajaxCallSpy.mock.calls[0];
      expect(method).toBe("GET");
      expect(url).toBe(
        "/api/metrics/query/timeseries?event_name=utub_opened&window=week&resolution=day",
      );
      expect(data).toBeNull();
      expect(timeout).toBe(5000);
    });

    it("omits resolution when not provided so server default applies", () => {
      fetchTimeseries({ eventName: "ui_url_copy", window: "day" });
      const [, url] = ajaxCallSpy.mock.calls[0];
      expect(url).toBe(
        "/api/metrics/query/timeseries?event_name=ui_url_copy&window=day",
      );
    });
  });

  describe("fetchSummary", () => {
    it("forwards the window query parameter only", () => {
      fetchSummary({ window: "year" });
      const [method, url, data, timeout] = ajaxCallSpy.mock.calls[0];
      expect(method).toBe("GET");
      expect(url).toBe("/api/metrics/query/summary?window=year");
      expect(data).toBeNull();
      expect(timeout).toBe(5000);
    });
  });
});
