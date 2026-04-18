import { initNavbar, NAVBAR_TOGGLER } from "../navbar.js";

vi.mock("../../lib/globals.js", () => ({
  $: window.jQuery,
  jQuery: window.jQuery,
  bootstrap: window.bootstrap,
}));

vi.mock("../../lib/navbar-shared.js", () => ({
  initNavbarRouting: vi.fn(),
}));

const $ = window.jQuery;

describe("splash/navbar", () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <nav id="mainNavbar">
        <a class="navbar-brand" href="#">Brand</a>
        <button class="navbar-toggler" type="button"></button>
        <div id="NavbarNavDropdown" class="collapse navbar-collapse"></div>
      </nav>
    `;
    NAVBAR_TOGGLER.toggler = null;
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  describe("initNavbar", () => {
    it("creates a Collapse toggler and registers show/hide listeners", () => {
      initNavbar();

      expect(NAVBAR_TOGGLER.toggler).not.toBeNull();
    });

    it("adds backdrop and z9999 classes on show.bs.collapse", () => {
      initNavbar();

      $("#NavbarNavDropdown").trigger("show.bs.collapse");

      expect($(".navbar-backdrop").length).toBe(1);
      expect($(".navbar-brand").hasClass("z9999")).toBe(true);
      expect($(".navbar-toggler").hasClass("z9999")).toBe(true);
      expect($("#NavbarNavDropdown").hasClass("z9999")).toBe(true);
    });

    it("removes z9999 classes on hide.bs.collapse", () => {
      initNavbar();

      // Open first to add classes
      $("#NavbarNavDropdown").trigger("show.bs.collapse");
      expect($(".navbar-brand").hasClass("z9999")).toBe(true);

      // Close
      $("#NavbarNavDropdown").trigger("hide.bs.collapse");

      expect($(".navbar-brand").hasClass("z9999")).toBe(false);
      expect($(".navbar-toggler").hasClass("z9999")).toBe(false);
      expect($("#NavbarNavDropdown").hasClass("z9999")).toBe(false);
    });

    it("clicking backdrop calls toggler.hide()", () => {
      initNavbar();

      const hideSpy = vi.fn();
      NAVBAR_TOGGLER.toggler = {
        hide: hideSpy,
      } as unknown as bootstrap.Collapse;

      $("#NavbarNavDropdown").trigger("show.bs.collapse");
      $(".navbar-backdrop").trigger("click");

      expect(hideSpy).toHaveBeenCalled();
    });

    it("removes backdrop element after timeout on close", () => {
      vi.useFakeTimers();

      initNavbar();
      $("#NavbarNavDropdown").trigger("show.bs.collapse");
      expect($(".navbar-backdrop").length).toBe(1);

      $("#NavbarNavDropdown").trigger("hide.bs.collapse");

      // Backdrop still present before timeout
      expect($(".navbar-backdrop").length).toBe(1);

      vi.advanceTimersByTime(300);

      expect($(".navbar-backdrop").length).toBe(0);

      vi.useRealTimers();
    });
  });
});
