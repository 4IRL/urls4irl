vi.mock("../lib/security-check.js", () => ({}));

vi.mock("../lib/globals.js", () => ({
  $: window.jQuery,
  jQuery: window.jQuery,
  bootstrap: window.bootstrap,
}));

const { initNavbarRouting, initNavbarBackdrop } = await vi.hoisted(
  async () => ({
    initNavbarRouting: vi.fn(),
    initNavbarBackdrop: vi.fn(),
  }),
);

vi.mock("../lib/navbar-shared.js", () => ({
  initNavbarRouting,
  initNavbarBackdrop,
}));

describe("generic navbar entry point", () => {
  afterEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    document.body.innerHTML = "";
  });

  it("wires both routing and the dropdown backdrop on document ready", async () => {
    await import("../navbar.js");
    await new Promise<void>((resolve) => setTimeout(resolve, 0));

    expect(initNavbarRouting).toHaveBeenCalledTimes(1);
    expect(initNavbarBackdrop).toHaveBeenCalledTimes(1);
  });
});

export {};
