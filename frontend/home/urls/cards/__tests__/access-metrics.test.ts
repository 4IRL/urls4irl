import { accessLink } from "../access.js";

vi.mock("../../../../lib/metrics-client.js", () => ({
  emit: vi.fn(),
  flush: vi.fn().mockResolvedValue(undefined),
  initMetricsClient: vi.fn(),
  resetMetricsClient: vi.fn(),
}));

const $ = window.jQuery;

const ACCESS_WARNING_HTML = `
  <div id="confirmModal" class="modal">
    <span id="confirmModalTitle"></span>
    <div id="confirmModalBody"></div>
    <button id="modalDismiss"></button>
    <button id="modalSubmit"></button>
    <div id="modalRedirect"></div>
  </div>
`;

describe("access-warning metrics — UI_URL_ACCESS_WARNING / _DISMISS", () => {
  let openSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    document.body.innerHTML = ACCESS_WARNING_HTML;
    vi.clearAllMocks();
    ($.fn as unknown as Record<string, unknown>).modal = function (
      this: JQuery,
    ) {
      return this;
    };
    openSpy = vi
      .spyOn(window, "open")
      .mockReturnValue({ focus: vi.fn() } as unknown as Window);
  });

  afterEach(() => {
    document.body.innerHTML = "";
    openSpy.mockRestore();
  });

  it("emits ui_url_access_warning when modal is shown for a non-http URL", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");

    accessLink("ftp://example.com");

    expect(emit).toHaveBeenCalledWith("ui_url_access_warning");
  });

  it("does NOT show modal or emit warning for http:// URLs (direct open)", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");

    accessLink("https://example.com");

    expect(emit).not.toHaveBeenCalledWith("ui_url_access_warning");
    expect(openSpy).toHaveBeenCalledWith("https://example.com", "_blank");
  });

  it("emits ui_url_access_warning_dismiss on hidden.bs.modal when user did NOT submit", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");

    accessLink("ftp://example.com");
    vi.mocked(emit).mockClear();

    $("#confirmModal").trigger("hidden.bs.modal.accessWarning");

    expect(emit).toHaveBeenCalledWith("ui_url_access_warning_dismiss");
  });

  it("does NOT emit dismiss when user clicked 'Let's go!' submit then hidden fires", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");

    accessLink("ftp://example.com");
    $("#modalSubmit").trigger("click");
    vi.mocked(emit).mockClear();

    $("#confirmModal").trigger("hidden.bs.modal.accessWarning");

    expect(emit).not.toHaveBeenCalledWith("ui_url_access_warning_dismiss");
  });

  it("cleanup (removeClass + remove URL span) always runs on hidden, even after submit", () => {
    accessLink("ftp://example.com");
    expect($("#confirmModal").hasClass("accessExternalURLModal")).toBe(true);

    $("#modalSubmit").trigger("click");
    $("#confirmModal").trigger("hidden.bs.modal.accessWarning");

    expect($("#confirmModal").hasClass("accessExternalURLModal")).toBe(false);
    expect($("#confirmModalBody").hasClass("white-space-pre-line")).toBe(false);
    expect($("#AccessURLModalURLString").length).toBe(0);
  });

  it("opening the modal twice and dismissing the second open emits dismiss exactly once (no listener accumulation)", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");

    accessLink("ftp://example.com");
    $("#confirmModal").trigger("hidden.bs.modal.accessWarning");

    accessLink("ftp://example.com");
    vi.mocked(emit).mockClear();

    $("#confirmModal").trigger("hidden.bs.modal.accessWarning");

    const dismissCalls = vi
      .mocked(emit)
      .mock.calls.filter((call) => call[0] === "ui_url_access_warning_dismiss");
    expect(dismissCalls.length).toBe(1);
  });
});
