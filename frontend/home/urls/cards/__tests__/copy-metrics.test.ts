import { UI_EVENTS } from "../../../../lib/metrics-events.js";
import { copyURLString } from "../copy.js";

const { mockMetricsClient } = await vi.hoisted(
  async () =>
    await import("../../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../../../../lib/globals.js", async () => {
  const jquery = (await import("jquery")).default;
  const tooltipInstance = {
    setContent: vi.fn(),
    show: vi.fn(),
    hide: vi.fn(),
  };
  return {
    $: jquery,
    jQuery: jquery,
    bootstrap: {
      Tooltip: {
        getInstance: vi.fn(() => tooltipInstance),
        getOrCreateInstance: vi.fn(() => tooltipInstance),
      },
    },
    getInputValue: (input: string | JQuery) => {
      const element = typeof input === "string" ? jquery(input) : input;
      return element.val() as string;
    },
  };
});

const $ = window.jQuery;

describe("copy metrics — UI_URL_COPY { result: success | failure }", () => {
  let urlBtnCopy: HTMLElement;

  beforeEach(() => {
    document.body.innerHTML = `<button class="urlBtnCopy"></button>`;
    urlBtnCopy = document.querySelector(".urlBtnCopy") as HTMLElement;
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("emits ui_url_copy with result 'success' when clipboard write resolves", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");

    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    });

    await copyURLString("https://example.com", urlBtnCopy);

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_URL_COPY,
      result: "success",
    });
  });

  it("emits ui_url_copy with result 'failure' when clipboard write rejects", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");

    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: {
        writeText: vi.fn().mockRejectedValue(new Error("denied")),
      },
    });

    await copyURLString("https://example.com", urlBtnCopy);

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_URL_COPY,
      result: "failure",
    });
  });

  it("does NOT emit success when clipboard write rejects", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");

    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: {
        writeText: vi.fn().mockRejectedValue(new Error("denied")),
      },
    });

    await copyURLString("https://example.com", urlBtnCopy);

    expect(emit).not.toHaveBeenCalledWith({
      event: UI_EVENTS.UI_URL_COPY,
      result: "success",
    });
  });
});

// Keep a $-reference so eslint does not flag the import as unused even when
// jQuery isn't directly invoked (used implicitly via the test fixture).
void $;
