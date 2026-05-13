import type { Mock } from "vitest";

import {
  emit,
  flush,
  initMetricsClient,
  resetMetricsClient,
} from "../metrics-client.js";

describe("metrics-client", () => {
  it("exports emit, flush, initMetricsClient, resetMetricsClient", () => {
    expect(typeof emit).toBe("function");
    expect(typeof flush).toBe("function");
    expect(typeof initMetricsClient).toBe("function");
    expect(typeof resetMetricsClient).toBe("function");
  });

  it("rejects non-UI EventName values at compile time", () => {
    // @ts-expect-error utub_created is a domain-category EventName, not a UI event name
    emit("utub_created", undefined);
  });

  describe("flush() POST contract", () => {
    beforeEach(() => {
      resetMetricsClient();
      document.head.innerHTML = '<meta name="csrf-token" content="test-token">';
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

    it("flush() POSTs buffered events as application/json with CSRF header and batch_id", async () => {
      emit("ui_utub_create_open");
      emit("ui_url_copy", { result: "success" });
      await flush();
      expect(fetch).toHaveBeenCalledOnce();
      const [url, init] = (fetch as unknown as Mock).mock.calls[0];
      expect(url).toBe("/api/metrics");
      expect(init.method).toBe("POST");
      expect(init.headers["Content-Type"]).toBe("application/json");
      expect(init.headers["X-CSRFToken"]).toBe("test-token");
      const body = JSON.parse(init.body);
      expect(body.events).toHaveLength(2);
      expect(body.events[0].event_name).toBe("ui_utub_create_open");
      expect(body.events[0].dimensions).toBeNull();
      expect(body.events[1].event_name).toBe("ui_url_copy");
      expect(body.events[1].dimensions).toEqual({ result: "success" });
      expect(body.batch_id).toMatch(/^[0-9a-f-]{36}$/i);
    });

    it("flush() is a no-op when buffer is empty", async () => {
      await flush();
      expect(fetch).not.toHaveBeenCalled();
    });

    it("flush() drains the buffer on success", async () => {
      emit("ui_utub_create_open");
      await flush();
      await flush();
      expect(fetch).toHaveBeenCalledOnce();
    });
  });

  describe("emit() dedupe with cooldown window", () => {
    beforeEach(() => {
      resetMetricsClient();
      document.head.innerHTML = '<meta name="csrf-token" content="test-token">';
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
      emit("ui_utub_create_open");
      emit("ui_utub_create_open");
      await flush();
      const body = JSON.parse((fetch as unknown as Mock).mock.calls[0][1].body);
      expect(body.events).toHaveLength(1);
      vi.useRealTimers();
    });

    it("treats same event with different dimensions as distinct", async () => {
      emit("ui_url_copy", { result: "success" });
      emit("ui_url_copy", { result: "failure" });
      await flush();
      const body = JSON.parse((fetch as unknown as Mock).mock.calls[0][1].body);
      expect(body.events).toHaveLength(2);
    });

    it("allows re-emit after cooldown expires", async () => {
      vi.useFakeTimers();
      emit("ui_utub_create_open");
      vi.advanceTimersByTime(1001);
      emit("ui_utub_create_open");
      await flush();
      const body = JSON.parse((fetch as unknown as Mock).mock.calls[0][1].body);
      expect(body.events).toHaveLength(2);
      vi.useRealTimers();
    });

    it("bounds dedupe map memory via prune across cooldown windows", async () => {
      vi.useFakeTimers();
      for (let index = 0; index < 5; index++) {
        emit("ui_url_card_click", { active_tag_count: index });
        vi.advanceTimersByTime(1001);
      }
      await flush();
      expect(fetch).toHaveBeenCalledOnce();
      const body = JSON.parse((fetch as unknown as Mock).mock.calls[0][1].body);
      expect(body.events).toHaveLength(5);
      vi.useRealTimers();
    });
  });

  describe("initMetricsClient() / resetMetricsClient() interval lifecycle", () => {
    beforeEach(() => {
      resetMetricsClient();
      document.head.innerHTML = '<meta name="csrf-token" content="test-token">';
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
      emit("ui_utub_create_open");
      expect(fetch).not.toHaveBeenCalled();
      await vi.advanceTimersByTimeAsync(60000);
      expect(fetch).toHaveBeenCalledOnce();
      vi.useRealTimers();
    });

    it("resetMetricsClient clears the interval and state", async () => {
      vi.useFakeTimers();
      initMetricsClient();
      emit("ui_utub_create_open");
      resetMetricsClient();
      await vi.advanceTimersByTimeAsync(120000);
      expect(fetch).not.toHaveBeenCalled();
      vi.useRealTimers();
    });

    it("initMetricsClient is idempotent — double-init does not register two intervals", async () => {
      vi.useFakeTimers();
      initMetricsClient();
      initMetricsClient();
      emit("ui_utub_create_open");
      await vi.advanceTimersByTimeAsync(60000);
      expect(fetch).toHaveBeenCalledOnce();
      vi.useRealTimers();
    });
  });

  describe("threshold flush at BATCH_THRESHOLD", () => {
    beforeEach(() => {
      resetMetricsClient();
      document.head.innerHTML = '<meta name="csrf-token" content="test-token">';
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
        emit("ui_url_card_click", { active_tag_count: index });
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
      document.head.innerHTML = '<meta name="csrf-token" content="test-token">';
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

    it("sendBeacon on visibilitychange-hidden carries CSRF in body and is called exactly once", () => {
      initMetricsClient();
      emit("ui_utub_create_open");
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
        expect(body.csrf_token).toBe("test-token");
        expect(body.events[0].event_name).toBe("ui_utub_create_open");
        expect(body.batch_id).toMatch(/^[0-9a-f-]{36}$/i);
      });
    });

    it("sendBeacon is never retried — single call only", async () => {
      initMetricsClient();
      emit("ui_utub_create_open");
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
      emit("ui_utub_create_open");
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
      emit("ui_utub_create_open");
      window.dispatchEvent(new Event("pagehide"));
      expect(sendBeaconMock).toHaveBeenCalledOnce();
    });

    it("visibilitychange while still visible is a no-op", () => {
      initMetricsClient();
      emit("ui_utub_create_open");
      Object.defineProperty(document, "visibilityState", {
        value: "visible",
        configurable: true,
      });
      document.dispatchEvent(new Event("visibilitychange"));
      expect(sendBeaconMock).not.toHaveBeenCalled();
    });

    it("does not double-send when both visibilitychange and pagehide fire", () => {
      initMetricsClient();
      emit("ui_utub_create_open");
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
      emit("ui_utub_create_open");
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

    it("flushBeacon does not fire when _csrfDeadForLifetime is true", async () => {
      (fetch as unknown as Mock).mockResolvedValueOnce({
        ok: false,
        status: 403,
      } as Response);
      initMetricsClient();
      emit("ui_utub_create_open");
      await flush();
      emit("ui_url_copy", { result: "success" });
      Object.defineProperty(document, "visibilityState", {
        value: "hidden",
        configurable: true,
      });
      document.dispatchEvent(new Event("visibilitychange"));
      expect(sendBeaconMock).not.toHaveBeenCalled();
    });
  });
});
