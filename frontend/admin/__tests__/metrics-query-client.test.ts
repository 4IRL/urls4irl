import { createMockJqXHRChainable } from "../../__tests__/helpers/mock-jquery.js";

// `vi.mock(...)` is hoisted above all imports, so the spy must be created via
// `vi.hoisted(...)` to be referenced from inside the mock factory. Mirrors the
// pattern in `frontend/lib/__tests__/metrics-client.test.ts`.
const { ajaxCallSpy } = vi.hoisted(() => ({ ajaxCallSpy: vi.fn() }));

vi.mock("../../lib/ajax.js", () => ({
  ajaxCall: ajaxCallSpy,
}));

import {
  fetchGroupedTimeseries,
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

    it("passes ?device_type=1 when deviceType is 1", () => {
      fetchTopEvents({
        window: "day",
        category: "ui",
        limit: 10,
        deviceType: 1,
      });
      const [, url] = ajaxCallSpy.mock.calls[0];
      expect(url).toBe(
        "/api/metrics/query/top?window=day&category=ui&limit=10&device_type=1",
      );
    });

    it("passes ?device_type=2 when deviceType is 2", () => {
      fetchTopEvents({
        window: "day",
        category: "api",
        limit: 10,
        deviceType: 2,
      });
      const [, url] = ajaxCallSpy.mock.calls[0];
      expect(url).toBe(
        "/api/metrics/query/top?window=day&category=api&limit=10&device_type=2",
      );
    });

    it("omits device_type when undefined", () => {
      fetchTopEvents({ window: "day", category: "ui", limit: 10 });
      const [, url] = ajaxCallSpy.mock.calls[0];
      expect(url).not.toContain("device_type");
    });

    it("omits device_type when null", () => {
      fetchTopEvents({
        window: "day",
        category: "ui",
        limit: 10,
        deviceType: null,
      });
      const [, url] = ajaxCallSpy.mock.calls[0];
      expect(url).not.toContain("device_type");
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

    it("passes ?device_type=1 when deviceType is 1", () => {
      fetchTimeseries({
        eventName: "utub_opened",
        window: "week",
        resolution: "day",
        deviceType: 1,
      });
      const [, url] = ajaxCallSpy.mock.calls[0];
      expect(url).toBe(
        "/api/metrics/query/timeseries?event_name=utub_opened&window=week&resolution=day&device_type=1",
      );
    });

    it("passes ?device_type=2 when deviceType is 2", () => {
      fetchTimeseries({
        eventName: "api_hit",
        window: "day",
        deviceType: 2,
      });
      const [, url] = ajaxCallSpy.mock.calls[0];
      expect(url).toBe(
        "/api/metrics/query/timeseries?event_name=api_hit&window=day&device_type=2",
      );
    });

    it("omits device_type when undefined", () => {
      fetchTimeseries({ eventName: "ui_url_copy", window: "day" });
      const [, url] = ajaxCallSpy.mock.calls[0];
      expect(url).not.toContain("device_type");
    });

    it("omits device_type when null", () => {
      fetchTimeseries({
        eventName: "ui_url_copy",
        window: "day",
        deviceType: null,
      });
      const [, url] = ajaxCallSpy.mock.calls[0];
      expect(url).not.toContain("device_type");
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

  describe("fetchGroupedTimeseries", () => {
    it("repeats the group_by query parameter for each entry", () => {
      fetchGroupedTimeseries({
        eventName: "api_metrics_ingest_batch",
        groupBy: ["batch_size_bucket", "transport", "device_type"],
        window: "day",
      });
      expect(ajaxCallSpy).toHaveBeenCalledOnce();
      const [method, url, data, timeout] = ajaxCallSpy.mock.calls[0];
      expect(method).toBe("GET");
      expect(url).toBe(
        "/api/metrics/query/grouped-timeseries?event_name=api_metrics_ingest_batch&window=day&group_by=batch_size_bucket&group_by=transport&group_by=device_type",
      );
      expect(data).toBeNull();
      expect(timeout).toBe(5000);
    });

    it("forwards the resolution query parameter when supplied", () => {
      fetchGroupedTimeseries({
        eventName: "api_metrics_ingest_batch",
        groupBy: ["transport"],
        window: "week",
        resolution: "day",
      });
      const [, url] = ajaxCallSpy.mock.calls[0];
      expect(url).toBe(
        "/api/metrics/query/grouped-timeseries?event_name=api_metrics_ingest_batch&window=week&group_by=transport&resolution=day",
      );
    });

    it("does NOT include device_type as a query param (middleware injects it)", () => {
      // device_type is a request-header dimension injected by the metrics
      // middleware; the grouped-timeseries query schema rejects unknown
      // parameters, so callers must NEVER include it as a flat query param.
      fetchGroupedTimeseries({
        eventName: "api_metrics_ingest_batch",
        groupBy: ["batch_size_bucket", "transport", "device_type"],
        window: "day",
      });
      const [, url] = ajaxCallSpy.mock.calls[0];
      expect(url).not.toMatch(/[?&]device_type=/);
    });

    it("works with a single-entry groupBy (e.g., transport-only chart)", () => {
      fetchGroupedTimeseries({
        eventName: "api_metrics_ingest_batch",
        groupBy: ["transport"],
        window: "day",
      });
      const [, url] = ajaxCallSpy.mock.calls[0];
      expect(url).toBe(
        "/api/metrics/query/grouped-timeseries?event_name=api_metrics_ingest_batch&window=day&group_by=transport",
      );
    });
  });
});
