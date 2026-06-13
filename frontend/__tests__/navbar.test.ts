vi.mock("../lib/security-check.js", () => ({}));

vi.mock("../lib/globals.js", () => ({
  $: window.jQuery,
  jQuery: window.jQuery,
  bootstrap: window.bootstrap,
}));

const { initNavbarRouting, initMobileNavbarBackdrop } = await vi.hoisted(
  async () => ({
    initNavbarRouting: vi.fn(),
    initMobileNavbarBackdrop: vi.fn(),
  }),
);

vi.mock("../lib/navbar-shared.js", () => ({
  initNavbarRouting,
  initMobileNavbarBackdrop,
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
    expect(initMobileNavbarBackdrop).toHaveBeenCalledTimes(1);
  });
});

export {};
