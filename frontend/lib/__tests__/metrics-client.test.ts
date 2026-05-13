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
});
