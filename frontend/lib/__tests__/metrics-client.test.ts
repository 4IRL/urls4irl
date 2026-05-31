import type { Mock } from "vitest";

import { resetDeviceTypeCache } from "../../__tests__/helpers/device-type-test-utils.js";
import { APP_CONFIG } from "../config.js";
import {
  emit,
  flush,
  initMetricsClient,
  resetMetricsClient,
} from "../metrics-client.js";

import { UI_EVENTS } from "../metrics-events.js";
const DEVICE_TYPE_MOBILE = APP_CONFIG.constants.DEVICE_TYPE.MOBILE;
const DEVICE_TYPE_DESKTOP = APP_CONFIG.constants.DEVICE_TYPE.DESKTOP;

// Outer-scope matchMedia stub: defaults all tests to a desktop viewport so
// `getDeviceType()` consistently returns DEVICE_TYPE.DESKTOP in the
// auto-injected `device_type` dimension. Individual `describe` blocks may
// override via their own `beforeEach` to test mobile behavior; the outer
// `afterEach` restores the default via `vi.unstubAllGlobals()`.
beforeEach(() => {
  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockReturnValue({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  );
  resetDeviceTypeCache();
});

afterEach(() => {
  vi.unstubAllGlobals();
  resetDeviceTypeCache();
});

describe("metrics-client", () => {
  it("exports emit, flush, initMetricsClient, resetMetricsClient", () => {
    expect(typeof emit).toBe("function");
    expect(typeof flush).toBe("function");
    expect(typeof initMetricsClient).toBe("function");
    expect(typeof resetMetricsClient).toBe("function");
  });

  it("rejects non-UI EventName values at compile time", () => {
    // @ts-expect-error utub_created is a domain-category EventName, not a UI event name
    emit({ event: "utub_created" });
  });

  describe("flush() POST contract", () => {
    beforeEach(() => {
      resetMetricsClient();
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue({
          ok: true,
          status: 200,
          json: vi.fn().mockResolvedValue({ status: "Success", accepted: 2 }),
        } as unknown as Response),
      );
    });

    afterEach(() => {
      vi.unstubAllGlobals();
      resetMetricsClient();
    });

    it("flush() POSTs buffered events as application/json with batch_id", async () => {
      emit({ event: UI_EVENTS.UI_UTUB_CREATE_OPEN });
      emit({ event: UI_EVENTS.UI_URL_COPY, result: "success" });
      await flush();
      expect(fetch).toHaveBeenCalledOnce();
      const [url, init] = (fetch as unknown as Mock).mock.calls[0];
      expect(url).toBe("/api/metrics");
      expect(init.method).toBe("POST");
      expect(init.headers["Content-Type"]).toBe("application/json");
      const body = JSON.parse(init.body);
      expect(body.events).toHaveLength(2);
      expect(body.events[0].event_name).toBe(UI_EVENTS.UI_UTUB_CREATE_OPEN);
      expect(body.events[0].dimensions).toEqual({
        device_type: DEVICE_TYPE_DESKTOP,
      });
      expect(body.events[1].event_name).toBe(UI_EVENTS.UI_URL_COPY);
      expect(body.events[1].dimensions).toEqual({
        device_type: DEVICE_TYPE_DESKTOP,
        result: "success",
      });
      expect(body.batch_id).toMatch(/^[0-9a-f-]{36}$/i);
    });

    it("flush() is a no-op when buffer is empty", async () => {
      await flush();
      expect(fetch).not.toHaveBeenCalled();
    });

    it("flush() drains the buffer on success", async () => {
      emit({ event: UI_EVENTS.UI_UTUB_CREATE_OPEN });
      await flush();
      await flush();
      expect(fetch).toHaveBeenCalledOnce();
    });
  });

  describe("emit() dedupe with cooldown window", () => {
    beforeEach(() => {
      resetMetricsClient();
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue({
          ok: true,
          status: 200,
          json: vi.fn().mockResolvedValue({ status: "Success", accepted: 1 }),
        } as unknown as Response),
      );
    });

    afterEach(() => {
      vi.unstubAllGlobals();
      resetMetricsClient();
    });

    it("dedupes identical (event, dimensions) pairs within cooldown", async () => {
      vi.useFakeTimers();
      emit({ event: UI_EVENTS.UI_UTUB_CREATE_OPEN });
      emit({ event: UI_EVENTS.UI_UTUB_CREATE_OPEN });
      await flush();
      const body = JSON.parse((fetch as unknown as Mock).mock.calls[0][1].body);
      expect(body.events).toHaveLength(1);
      vi.useRealTimers();
    });

    it("treats same event with different dimensions as distinct", async () => {
      emit({ event: UI_EVENTS.UI_URL_COPY, result: "success" });
      emit({ event: UI_EVENTS.UI_URL_COPY, result: "failure" });
      await flush();
      const body = JSON.parse((fetch as unknown as Mock).mock.calls[0][1].body);
      expect(body.events).toHaveLength(2);
    });

    it("allows re-emit after cooldown expires", async () => {
      vi.useFakeTimers();
      emit({ event: UI_EVENTS.UI_UTUB_CREATE_OPEN });
      vi.advanceTimersByTime(1001);
      emit({ event: UI_EVENTS.UI_UTUB_CREATE_OPEN });
      await flush();
      const body = JSON.parse((fetch as unknown as Mock).mock.calls[0][1].body);
      expect(body.events).toHaveLength(2);
      vi.useRealTimers();
    });

    it("bounds dedupe map memory via prune across cooldown windows", async () => {
      vi.useFakeTimers();
      for (let index = 0; index < 5; index++) {
        emit({
          event: UI_EVENTS.UI_URL_CARD_CLICK,
          search_active: "false",
          active_tag_count: index,
        });
        vi.advanceTimersByTime(1001);
      }
      await flush();
      expect(fetch).toHaveBeenCalledOnce();
      const body = JSON.parse((fetch as unknown as Mock).mock.calls[0][1].body);
      expect(body.events).toHaveLength(5);
      vi.useRealTimers();
    });

    it("treats mobile↔desktop transition as distinct dedupe buckets", async () => {
      // Outer-scope beforeEach already stubbed matchMedia=matches=false (desktop).
      // First emit captures DEVICE_TYPE.DESKTOP into the dedupe key.
      emit({ event: UI_EVENTS.UI_UTUB_CREATE_OPEN });

      // Toggle viewport to mobile and reset the device-type cache so the next
      // getDeviceType() call re-queries matchMedia and returns MOBILE.
      vi.stubGlobal(
        "matchMedia",
        vi.fn().mockReturnValue({
          matches: true,
          addEventListener: vi.fn(),
          removeEventListener: vi.fn(),
        }),
      );
      resetDeviceTypeCache();
      emit({ event: UI_EVENTS.UI_UTUB_CREATE_OPEN });

      await flush();
      const body = JSON.parse((fetch as unknown as Mock).mock.calls[0][1].body);
      expect(body.events).toHaveLength(2);
      expect(body.events[0].dimensions).toEqual({
        device_type: DEVICE_TYPE_DESKTOP,
      });
      expect(body.events[1].dimensions).toEqual({
        device_type: DEVICE_TYPE_MOBILE,
      });
    });
  });

  describe("initMetricsClient() / resetMetricsClient() interval lifecycle", () => {
    beforeEach(() => {
      resetMetricsClient();
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue({
          ok: true,
          status: 200,
          json: vi.fn().mockResolvedValue({ status: "Success", accepted: 1 }),
        } as unknown as Response),
      );
    });

    afterEach(() => {
      vi.unstubAllGlobals();
      resetMetricsClient();
    });

    it("initMetricsClient registers a 60s flush interval", async () => {
      vi.useFakeTimers();
      initMetricsClient();
      emit({ event: UI_EVENTS.UI_UTUB_CREATE_OPEN });
      expect(fetch).not.toHaveBeenCalled();
      await vi.advanceTimersByTimeAsync(60000);
      expect(fetch).toHaveBeenCalledOnce();
      vi.useRealTimers();
    });

    it("resetMetricsClient clears the interval and state", async () => {
      vi.useFakeTimers();
      initMetricsClient();
      emit({ event: UI_EVENTS.UI_UTUB_CREATE_OPEN });
      resetMetricsClient();
      await vi.advanceTimersByTimeAsync(120000);
      expect(fetch).not.toHaveBeenCalled();
      vi.useRealTimers();
    });

    it("initMetricsClient is idempotent — double-init does not register two intervals", async () => {
      vi.useFakeTimers();
      initMetricsClient();
      initMetricsClient();
      emit({ event: UI_EVENTS.UI_UTUB_CREATE_OPEN });
      await vi.advanceTimersByTimeAsync(60000);
      expect(fetch).toHaveBeenCalledOnce();
      vi.useRealTimers();
    });

    it("initMetricsClient wires the device-type listener via matchMedia.addEventListener('change', ...)", () => {
      const addEventListenerSpy = vi.fn();
      const matchMediaMock = vi.fn().mockReturnValue({
        matches: false,
        addEventListener: addEventListenerSpy,
        removeEventListener: vi.fn(),
      });
      vi.stubGlobal("matchMedia", matchMediaMock);
      resetDeviceTypeCache();

      initMetricsClient();

      expect(matchMediaMock).toHaveBeenCalled();
      expect(addEventListenerSpy).toHaveBeenCalledWith(
        "change",
        expect.any(Function),
      );
    });
  });

  describe("threshold flush at BATCH_THRESHOLD", () => {
    beforeEach(() => {
      resetMetricsClient();
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue({
          ok: true,
          status: 200,
          json: vi.fn().mockResolvedValue({ status: "Success", accepted: 50 }),
        } as unknown as Response),
      );
    });

    afterEach(() => {
      vi.unstubAllGlobals();
      resetMetricsClient();
    });

    it("flushes immediately when buffer reaches BATCH_THRESHOLD", async () => {
      for (let index = 0; index < 50; index++) {
        emit({
          event: UI_EVENTS.UI_URL_CARD_CLICK,
          search_active: "false",
          active_tag_count: index,
        });
      }
      await Promise.resolve();
      expect(fetch).toHaveBeenCalledOnce();
      const body = JSON.parse((fetch as unknown as Mock).mock.calls[0][1].body);
      expect(body.events).toHaveLength(50);
    });
  });

  describe("visibilitychange + pagehide → navigator.sendBeacon", () => {
    let sendBeaconMock: Mock;

    beforeEach(() => {
      resetMetricsClient();
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue({
          ok: true,
          status: 200,
          json: vi.fn().mockResolvedValue({ status: "Success", accepted: 1 }),
        } as unknown as Response),
      );
      sendBeaconMock = vi.fn(() => true);
      Object.defineProperty(navigator, "sendBeacon", {
        value: sendBeaconMock,
        configurable: true,
        writable: true,
      });
      Object.defineProperty(document, "visibilityState", {
        value: "visible",
        configurable: true,
      });
    });

    afterEach(() => {
      vi.unstubAllGlobals();
      resetMetricsClient();
      delete (navigator as Partial<Navigator>).sendBeacon;
    });

    it("sendBeacon on visibilitychange-hidden posts batch and is called exactly once", () => {
      initMetricsClient();
      emit({ event: UI_EVENTS.UI_UTUB_CREATE_OPEN });
      Object.defineProperty(document, "visibilityState", {
        value: "hidden",
        configurable: true,
      });
      document.dispatchEvent(new Event("visibilitychange"));
      expect(sendBeaconMock).toHaveBeenCalledOnce();
      const [url, blob] = sendBeaconMock.mock.calls[0];
      expect(url).toBe("/api/metrics");
      expect(blob).toBeInstanceOf(Blob);
      expect((blob as Blob).type).toBe("application/json");
      return (blob as Blob).text().then((text) => {
        const body = JSON.parse(text);
        expect(body.events[0].event_name).toBe(UI_EVENTS.UI_UTUB_CREATE_OPEN);
        expect(body.batch_id).toMatch(/^[0-9a-f-]{36}$/i);
      });
    });

    it("sendBeacon is never retried — single call only", async () => {
      initMetricsClient();
      emit({ event: UI_EVENTS.UI_UTUB_CREATE_OPEN });
      Object.defineProperty(document, "visibilityState", {
        value: "hidden",
        configurable: true,
      });
      document.dispatchEvent(new Event("visibilitychange"));
      vi.useFakeTimers();
      await vi.advanceTimersByTimeAsync(10000);
      expect(sendBeaconMock).toHaveBeenCalledOnce();
      vi.useRealTimers();
    });

    it("falls back to fetch with keepalive when sendBeacon returns false", () => {
      sendBeaconMock.mockReturnValueOnce(false);
      initMetricsClient();
      emit({ event: UI_EVENTS.UI_UTUB_CREATE_OPEN });
      Object.defineProperty(document, "visibilityState", {
        value: "hidden",
        configurable: true,
      });
      document.dispatchEvent(new Event("visibilitychange"));
      expect(fetch).toHaveBeenCalledOnce();
      const init = (fetch as unknown as Mock).mock.calls[0][1];
      expect(init.keepalive).toBe(true);
    });

    it("pagehide triggers the unload flush path", () => {
      initMetricsClient();
      emit({ event: UI_EVENTS.UI_UTUB_CREATE_OPEN });
      window.dispatchEvent(new Event("pagehide"));
      expect(sendBeaconMock).toHaveBeenCalledOnce();
    });

    it("visibilitychange while still visible is a no-op", () => {
      initMetricsClient();
      emit({ event: UI_EVENTS.UI_UTUB_CREATE_OPEN });
      Object.defineProperty(document, "visibilityState", {
        value: "visible",
        configurable: true,
      });
      document.dispatchEvent(new Event("visibilitychange"));
      expect(sendBeaconMock).not.toHaveBeenCalled();
    });

    it("does not double-send when both visibilitychange and pagehide fire", () => {
      initMetricsClient();
      emit({ event: UI_EVENTS.UI_UTUB_CREATE_OPEN });
      Object.defineProperty(document, "visibilityState", {
        value: "hidden",
        configurable: true,
      });
      document.dispatchEvent(new Event("visibilitychange"));
      window.dispatchEvent(new Event("pagehide"));
      expect(sendBeaconMock).toHaveBeenCalledTimes(1);
    });

    it("flushBeacon skips sendBeacon when buffer is empty", () => {
      initMetricsClient();
      Object.defineProperty(document, "visibilityState", {
        value: "hidden",
        configurable: true,
      });
      document.dispatchEvent(new Event("visibilitychange"));
      expect(sendBeaconMock).not.toHaveBeenCalled();
    });

    it("flushBeacon does not fire when a regular flush is in flight", async () => {
      let resolveFetch: (response: Response) => void = () => {};
      (fetch as unknown as Mock).mockReturnValueOnce(
        new Promise<Response>((resolve) => {
          resolveFetch = resolve;
        }),
      );
      initMetricsClient();
      emit({ event: UI_EVENTS.UI_UTUB_CREATE_OPEN });
      void flush();
      Object.defineProperty(document, "visibilityState", {
        value: "hidden",
        configurable: true,
      });
      document.dispatchEvent(new Event("visibilitychange"));
      expect(sendBeaconMock).not.toHaveBeenCalled();
      resolveFetch({
        ok: true,
        status: 200,
        json: vi.fn(),
      } as unknown as Response);
      await Promise.resolve();
      await Promise.resolve();
    });

    it("flushBeacon swallows exceptions thrown by sendBeacon", () => {
      sendBeaconMock.mockImplementation(() => {
        throw new Error("beacon failure");
      });
      initMetricsClient();
      emit({ event: UI_EVENTS.UI_UTUB_CREATE_OPEN });
      Object.defineProperty(document, "visibilityState", {
        value: "hidden",
        configurable: true,
      });
      expect(() => {
        document.dispatchEvent(new Event("visibilitychange"));
      }).not.toThrow();
      expect(sendBeaconMock).toHaveBeenCalledOnce();
    });
  });

  describe("retry-with-backoff on transient failures", () => {
    beforeEach(() => {
      resetMetricsClient();
      vi.stubGlobal("fetch", vi.fn());
    });

    afterEach(() => {
      vi.unstubAllGlobals();
      resetMetricsClient();
    });

    it("retries on 503 after 1s backoff with same batch_id", async () => {
      vi.useFakeTimers();
      (fetch as unknown as Mock)
        .mockResolvedValueOnce({ ok: false, status: 503 } as Response)
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
          json: vi.fn(),
        } as unknown as Response);
      emit({ event: UI_EVENTS.UI_UTUB_CREATE_OPEN });
      void flush();
      await Promise.resolve();
      await Promise.resolve();
      await vi.advanceTimersByTimeAsync(1000);
      expect(fetch).toHaveBeenCalledTimes(2);
      const firstBatchId = JSON.parse(
        (fetch as unknown as Mock).mock.calls[0][1].body,
      ).batch_id;
      const secondBatchId = JSON.parse(
        (fetch as unknown as Mock).mock.calls[1][1].body,
      ).batch_id;
      expect(firstBatchId).toBe(secondBatchId);
      vi.useRealTimers();
    });

    it("retries on 429 with same batch_id", async () => {
      vi.useFakeTimers();
      (fetch as unknown as Mock)
        .mockResolvedValueOnce({ ok: false, status: 429 } as Response)
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
          json: vi.fn(),
        } as unknown as Response);
      emit({ event: UI_EVENTS.UI_UTUB_CREATE_OPEN });
      void flush();
      await Promise.resolve();
      await Promise.resolve();
      await vi.advanceTimersByTimeAsync(1000);
      expect(fetch).toHaveBeenCalledTimes(2);
      const firstBatchId = JSON.parse(
        (fetch as unknown as Mock).mock.calls[0][1].body,
      ).batch_id;
      const secondBatchId = JSON.parse(
        (fetch as unknown as Mock).mock.calls[1][1].body,
      ).batch_id;
      expect(firstBatchId).toBe(secondBatchId);
      vi.useRealTimers();
    });

    it("retries on network error (fetch rejects) with same batch_id", async () => {
      vi.useFakeTimers();
      (fetch as unknown as Mock)
        .mockRejectedValueOnce(new TypeError("network down"))
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
          json: vi.fn(),
        } as unknown as Response);
      emit({ event: UI_EVENTS.UI_UTUB_CREATE_OPEN });
      void flush();
      await Promise.resolve();
      await Promise.resolve();
      await vi.advanceTimersByTimeAsync(1000);
      expect(fetch).toHaveBeenCalledTimes(2);
      const firstBatchId = JSON.parse(
        (fetch as unknown as Mock).mock.calls[0][1].body,
      ).batch_id;
      const secondBatchId = JSON.parse(
        (fetch as unknown as Mock).mock.calls[1][1].body,
      ).batch_id;
      expect(firstBatchId).toBe(secondBatchId);
      vi.useRealTimers();
    });

    it("drops the batch after RETRY_MAX_ATTEMPTS exhausted", async () => {
      vi.useFakeTimers();
      (fetch as unknown as Mock).mockResolvedValue({
        ok: false,
        status: 503,
      } as Response);
      emit({ event: UI_EVENTS.UI_UTUB_CREATE_OPEN });
      void flush();
      await Promise.resolve();
      await Promise.resolve();
      await vi.advanceTimersByTimeAsync(1000);
      await vi.advanceTimersByTimeAsync(2000);
      expect(fetch).toHaveBeenCalledTimes(3);
      vi.useRealTimers();
    });

    it("drops the batch immediately on 400 with no retry", async () => {
      vi.useFakeTimers();
      (fetch as unknown as Mock).mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: vi.fn().mockResolvedValue({ errorCode: 1 }),
      } as unknown as Response);
      emit({ event: UI_EVENTS.UI_UTUB_CREATE_OPEN });
      void flush();
      await vi.advanceTimersByTimeAsync(10000);
      expect(fetch).toHaveBeenCalledOnce();
      vi.useRealTimers();
    });

    it("flush() on unexpected 403 clears in-flight without retry", async () => {
      vi.useFakeTimers();
      const sendBeaconMock = vi.fn(() => true);
      Object.defineProperty(navigator, "sendBeacon", {
        value: sendBeaconMock,
        configurable: true,
        writable: true,
      });
      (fetch as unknown as Mock)
        .mockResolvedValueOnce({
          ok: false,
          status: 403,
        } as Response)
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
          json: vi.fn(),
        } as unknown as Response);
      emit({ event: UI_EVENTS.UI_UTUB_CREATE_OPEN });
      await flush();
      await vi.advanceTimersByTimeAsync(10000);
      expect(fetch).toHaveBeenCalledOnce();
      expect(sendBeaconMock).not.toHaveBeenCalled();

      emit({ event: UI_EVENTS.UI_URL_COPY, result: "success" });
      await flush();
      expect(fetch).toHaveBeenCalledTimes(2);
      const secondBody = JSON.parse(
        (fetch as unknown as Mock).mock.calls[1][1].body,
      );
      expect(secondBody.events).toHaveLength(1);
      expect(secondBody.events[0].event_name).toBe(UI_EVENTS.UI_URL_COPY);
      const firstBatchId = JSON.parse(
        (fetch as unknown as Mock).mock.calls[0][1].body,
      ).batch_id;
      expect(secondBody.batch_id).not.toBe(firstBatchId);

      delete (navigator as Partial<Navigator>).sendBeacon;
      vi.useRealTimers();
    });
  });

  describe("concurrent-flush guard", () => {
    beforeEach(() => {
      resetMetricsClient();
      vi.stubGlobal("fetch", vi.fn());
    });

    afterEach(() => {
      vi.unstubAllGlobals();
      resetMetricsClient();
    });

    it("does not issue concurrent POSTs when flush is in flight", async () => {
      let resolveFetch: (response: Response) => void = () => {};
      (fetch as unknown as Mock)
        .mockReturnValueOnce(
          new Promise<Response>((resolve) => {
            resolveFetch = resolve;
          }),
        )
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
          json: vi.fn(),
        } as unknown as Response);
      emit({ event: UI_EVENTS.UI_UTUB_CREATE_OPEN });
      void flush();
      emit({ event: UI_EVENTS.UI_URL_COPY, result: "success" });
      void flush();
      expect(fetch).toHaveBeenCalledOnce();
      resolveFetch({
        ok: true,
        status: 200,
        json: vi.fn(),
      } as unknown as Response);
      await Promise.resolve();
      await Promise.resolve();
    });

    it("buffers events emitted during in-flight flush and ships them next time", async () => {
      let resolveFirst: (response: Response) => void = () => {};
      (fetch as unknown as Mock)
        .mockReturnValueOnce(
          new Promise<Response>((resolve) => {
            resolveFirst = resolve;
          }),
        )
        .mockResolvedValue({
          ok: true,
          status: 200,
          json: vi.fn(),
        } as unknown as Response);
      emit({ event: UI_EVENTS.UI_UTUB_CREATE_OPEN });
      void flush();
      emit({ event: UI_EVENTS.UI_URL_COPY, result: "success" });
      resolveFirst({
        ok: true,
        status: 200,
        json: vi.fn(),
      } as unknown as Response);
      await Promise.resolve();
      await Promise.resolve();
      await flush();
      expect(fetch).toHaveBeenCalledTimes(2);
      const secondBody = JSON.parse(
        (fetch as unknown as Mock).mock.calls[1][1].body,
      );
      expect(secondBody.events).toHaveLength(1);
      expect(secondBody.events[0].event_name).toBe(UI_EVENTS.UI_URL_COPY);
    });
  });

  describe("MAX_BATCH_SIZE slicing", () => {
    beforeEach(() => {
      resetMetricsClient();
      vi.stubGlobal("fetch", vi.fn());
    });

    afterEach(() => {
      vi.unstubAllGlobals();
      resetMetricsClient();
    });

    it("slices buffers larger than MAX_BATCH_SIZE into separate POSTs", async () => {
      // Hold the first fetch open so the BATCH_THRESHOLD auto-flush triggered by
      // the priming emit stays in flight while we load 110 additional events into
      // the buffer (the in-flight guard suppresses further auto-flushes).
      let resolveFirst: (response: Response) => void = () => {};
      (fetch as unknown as Mock)
        .mockReturnValueOnce(
          new Promise<Response>((resolve) => {
            resolveFirst = resolve;
          }),
        )
        .mockResolvedValue({
          ok: true,
          status: 200,
          json: vi.fn(),
        } as unknown as Response);

      emit({ event: UI_EVENTS.UI_UTUB_CREATE_OPEN });
      void flush();

      for (let index = 0; index < 110; index++) {
        emit({
          event: UI_EVENTS.UI_URL_CARD_CLICK,
          search_active: "false",
          active_tag_count: index,
        });
      }

      resolveFirst({
        ok: true,
        status: 200,
        json: vi.fn(),
      } as unknown as Response);
      await Promise.resolve();
      await Promise.resolve();

      await flush();
      await flush();

      expect(fetch).toHaveBeenCalledTimes(3);
      const secondBody = JSON.parse(
        (fetch as unknown as Mock).mock.calls[1][1].body,
      );
      const thirdBody = JSON.parse(
        (fetch as unknown as Mock).mock.calls[2][1].body,
      );
      expect(secondBody.events).toHaveLength(100);
      expect(thirdBody.events).toHaveLength(10);
      expect(secondBody.batch_id).not.toBe(thirdBody.batch_id);
    });
  });

  describe("dimension allow-list filter", () => {
    beforeEach(() => {
      resetMetricsClient();
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue({
          ok: true,
          status: 200,
          json: vi.fn().mockResolvedValue({ status: "Success", accepted: 1 }),
        } as unknown as Response),
      );
    });

    afterEach(() => {
      vi.unstubAllGlobals();
      resetMetricsClient();
    });

    it("strips disallowed dimension keys before serialization", async () => {
      // Test exercises the runtime allow-list filter, so the cast bypasses
      // the strict per-event dimension type to simulate a caller smuggling
      // disallowed keys past `emit()`'s compile-time check.
      emit({
        event: UI_EVENTS.UI_URL_COPY,
        result: "success",
        userId: 42,
        email: "user@example.com",
      } as unknown as Parameters<typeof emit>[0]);
      await flush();
      const body = JSON.parse((fetch as unknown as Mock).mock.calls[0][1].body);
      expect(body.events[0].dimensions).toEqual({
        device_type: DEVICE_TYPE_DESKTOP,
        result: "success",
      });
    });

    it("passes through all allow-listed keys", async () => {
      emit({
        event: UI_EVENTS.UI_URL_ACCESS,
        trigger: "corner_button",
        search_active: "true",
        active_tag_count: 3,
      });
      await flush();
      const body = JSON.parse((fetch as unknown as Mock).mock.calls[0][1].body);
      expect(body.events[0].dimensions).toEqual({
        device_type: DEVICE_TYPE_DESKTOP,
        trigger: "corner_button",
        search_active: "true",
        active_tag_count: 3,
      });
    });

    it("keeps auto-injected device_type when all caller-supplied keys are disallowed", async () => {
      // Cast bypasses the args-object typed signature: UI_UTUB_CREATE_OPEN is a
      // device-only event (no caller dims), but the runtime allow-list must
      // still strip foreign keys if a caller smuggles them past TS.
      emit({
        event: UI_EVENTS.UI_UTUB_CREATE_OPEN,
        userId: 42,
      } as unknown as Parameters<typeof emit>[0]);
      await flush();
      const body = JSON.parse((fetch as unknown as Mock).mock.calls[0][1].body);
      expect(body.events[0].dimensions).toEqual({
        device_type: DEVICE_TYPE_DESKTOP,
      });
    });
  });

  describe("device_type auto-injection", () => {
    beforeEach(() => {
      resetMetricsClient();
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue({
          ok: true,
          status: 200,
          json: vi.fn().mockResolvedValue({ status: "Success", accepted: 1 }),
        } as unknown as Response),
      );
    });

    afterEach(() => {
      resetMetricsClient();
    });

    it("auto-injects device_type=MOBILE when matchMedia matches the mobile breakpoint", async () => {
      vi.stubGlobal(
        "matchMedia",
        vi.fn().mockReturnValue({
          matches: true,
          addEventListener: vi.fn(),
          removeEventListener: vi.fn(),
        }),
      );
      resetDeviceTypeCache();
      emit({ event: UI_EVENTS.UI_UTUB_CREATE_OPEN });
      await flush();
      const body = JSON.parse((fetch as unknown as Mock).mock.calls[0][1].body);
      expect(body.events[0].dimensions).toEqual({
        device_type: DEVICE_TYPE_MOBILE,
      });
    });

    it("caller-supplied device_type wins over the auto-injected value", async () => {
      // Same intent as above: device-only event + caller-injected dim that
      // would normally be auto-handled. The cast lets the test exercise the
      // override path at runtime.
      emit({
        event: UI_EVENTS.UI_UTUB_CREATE_OPEN,
        device_type: DEVICE_TYPE_MOBILE,
      } as unknown as Parameters<typeof emit>[0]);
      await flush();
      const body = JSON.parse((fetch as unknown as Mock).mock.calls[0][1].body);
      expect(body.events[0].dimensions).toEqual({
        device_type: DEVICE_TYPE_MOBILE,
      });
    });
  });
});
