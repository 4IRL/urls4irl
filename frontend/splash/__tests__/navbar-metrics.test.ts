import { UI_EVENTS } from "../../lib/metrics-events.js";
import { initNavbar, NAVBAR_TOGGLER } from "../navbar.js";

const { mockMetricsClient } = await vi.hoisted(
  async () => await import("../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../../lib/globals.js", () => ({
  $: window.jQuery,
  jQuery: window.jQuery,
  bootstrap: window.bootstrap,
}));

vi.mock("../../lib/navbar-shared.js", () => ({
  initNavbarRouting: vi.fn(),
}));

const $ = window.jQuery;

const NAVBAR_HTML = `
  <nav id="mainNavbar">
    <a class="navbar-brand" href="#">Brand</a>
    <button class="navbar-toggler"></button>
    <div id="NavbarNavDropdown" class="collapse navbar-collapse"></div>
  </nav>
`;

describe("splash/navbar metrics emitters", () => {
  beforeEach(() => {
    document.body.innerHTML = NAVBAR_HTML;
    NAVBAR_TOGGLER.toggler = null;
    vi.clearAllMocks();
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("emits ui_navbar_mobile_menu_open on show.bs.collapse", async () => {
    const { emit } = await import("../../lib/metrics-client.js");

    initNavbar();
    $("#NavbarNavDropdown").trigger("show.bs.collapse");

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_NAVBAR_MOBILE_MENU_OPEN,
    });
  });

  it("emits ui_navbar_mobile_menu_close on hide.bs.collapse", async () => {
    const { emit } = await import("../../lib/metrics-client.js");

    initNavbar();
    $("#NavbarNavDropdown").trigger("hide.bs.collapse");

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_NAVBAR_MOBILE_MENU_CLOSE,
    });
  });
});
