import { accessLink } from "../cards/access.js";

vi.mock("../../../lib/globals.js", () => ({
  $: window.jQuery,
  jQuery: window.jQuery,
  bootstrap: window.bootstrap,
}));

vi.mock("../../../lib/config.js", () => {
  const configScript = document.getElementById("app-config")!;
  const config = JSON.parse(configScript.textContent!);
  return {
    APP_CONFIG: {
      ...config,
      constants: { ...config.constants, MAX_NUM_OF_URLS_TO_ACCESS: 5 },
    },
  };
});

vi.mock("../utils.js", () => ({
  getNumOfURLs: vi.fn(() => 1),
  getNumOfVisibleURLs: vi.fn(() => 1),
}));

vi.mock("../cards/access.js", () => ({
  accessLink: vi.fn(),
}));

const $ = window.jQuery;

describe("accessAllURLsInUTub", () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <button id="accessAllURLsBtn"></button>
      <div id="confirmModal"></div>
      <div id="confirmModalTitle"></div>
      <div id="confirmModalBody"></div>
      <button id="modalDismiss"></button>
      <button id="modalSubmit"></button>
      <div id="modalRedirect"></div>
    `;
    vi.clearAllMocks();
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("calls accessLink for each visible URL with a valid href", async () => {
    document.body.innerHTML += `
      <div class="urlRow" filterable="true">
        <a class="urlString" href="https://example.com">Example</a>
      </div>
      <div class="urlRow" filterable="true">
        <a class="urlString" href="https://other.com">Other</a>
      </div>
      <div class="urlRow" filterable="true">
        <a class="urlString" href="https://third.com">Third</a>
      </div>
    `;

    const { initAccessAllURLsBtn } = await import("../access-all.js");
    initAccessAllURLsBtn();

    $("#accessAllURLsBtn").trigger("click");

    expect(accessLink).toHaveBeenCalledTimes(3);
    expect(accessLink).toHaveBeenCalledWith("https://example.com");
    expect(accessLink).toHaveBeenCalledWith("https://other.com");
    expect(accessLink).toHaveBeenCalledWith("https://third.com");
  });

  it("does not call accessLink for URL elements missing href attribute", async () => {
    document.body.innerHTML += `
      <div class="urlRow" filterable="true">
        <a class="urlString" href="https://example.com">Example</a>
      </div>
      <div class="urlRow" filterable="true">
        <span class="urlString">No href element</span>
      </div>
    `;

    const { initAccessAllURLsBtn } = await import("../access-all.js");
    initAccessAllURLsBtn();

    $("#accessAllURLsBtn").trigger("click");

    expect(accessLink).toHaveBeenCalledTimes(1);
    expect(accessLink).toHaveBeenCalledWith("https://example.com");
  });
});
