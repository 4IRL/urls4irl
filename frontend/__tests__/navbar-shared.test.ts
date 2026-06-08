import { initMobileNavbarBackdrop } from "../lib/navbar-shared.js";

vi.mock("../lib/globals.js", () => ({
  $: window.jQuery,
  jQuery: window.jQuery,
  bootstrap: window.bootstrap,
}));

vi.mock("../lib/config.js", () => {
  const configScript = document.getElementById("app-config");
  const config = JSON.parse(configScript?.textContent ?? "{}");
  return { APP_CONFIG: config };
});

const $ = window.jQuery;

const NAVBAR_HTML = `
  <nav id="mainNavbar">
    <a class="navbar-brand" href="#">Brand</a>
    <button class="navbar-toggler" type="button"></button>
    <div id="NavbarNavDropdown" class="collapse navbar-collapse"></div>
  </nav>
`;

const BACKDROP_FADE_REMOVE_MS = 300;
const Z_INDEX_CLASS = "z9999";
const BACKDROP_CLASS = "navbar-backdrop";

describe("initMobileNavbarBackdrop", () => {
  beforeEach(() => {
    document.body.innerHTML = NAVBAR_HTML;
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("injects backdrop and lifts brand/toggler/dropdown on show.bs.collapse", () => {
    initMobileNavbarBackdrop();

    $("#NavbarNavDropdown").trigger("show.bs.collapse");

    const backdrop = $(`.${BACKDROP_CLASS}`);
    expect(backdrop.length).toBe(1);
    expect(backdrop.parent("#mainNavbar").length).toBe(1);

    expect($(".navbar-brand").hasClass(Z_INDEX_CLASS)).toBe(true);
    expect($(".navbar-toggler").hasClass(Z_INDEX_CLASS)).toBe(true);
    expect($("#NavbarNavDropdown").hasClass(Z_INDEX_CLASS)).toBe(true);
  });

  it("fades and removes backdrop and strips z-index classes on hide.bs.collapse", () => {
    initMobileNavbarBackdrop();

    $("#NavbarNavDropdown").trigger("show.bs.collapse");
    expect($(`.${BACKDROP_CLASS}`).length).toBe(1);

    $("#NavbarNavDropdown").trigger("hide.bs.collapse");

    const fadingBackdrop = $(`.${BACKDROP_CLASS}`);
    expect(fadingBackdrop.hasClass("navbar-backdrop-fade")).toBe(true);

    expect($(".navbar-brand").hasClass(Z_INDEX_CLASS)).toBe(false);
    expect($(".navbar-toggler").hasClass(Z_INDEX_CLASS)).toBe(false);
    expect($("#NavbarNavDropdown").hasClass(Z_INDEX_CLASS)).toBe(false);

    vi.advanceTimersByTime(BACKDROP_FADE_REMOVE_MS);
    expect($(`.${BACKDROP_CLASS}`).length).toBe(0);
  });
});
