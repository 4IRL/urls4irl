import { initCookieBanner } from "../cookie-banner.js";

const $ = window.jQuery;
const COOKIE_BANNER_SEEN = "cookie_banner_seen=true";

describe("initCookieBanner", () => {
  let fakeCookie: string;

  beforeEach(() => {
    fakeCookie = "";
    Object.defineProperty(document, "cookie", {
      configurable: true,
      get: () => fakeCookie,
      set: (val) => {
        const nameVal = val.split(";")[0].trim();
        if (!fakeCookie.includes(nameVal)) {
          fakeCookie += (fakeCookie ? "; " : "") + nameVal;
        }
      },
    });
    document.body.innerHTML = '<div id="CookieBanner"></div>';
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    $(document).off(".clickOutsideBanner");
  });

  describe("visibility based on cookie state", () => {
    it("does NOT add is-visible when COOKIE_BANNER_SEEN cookie is already set", () => {
      fakeCookie = COOKIE_BANNER_SEEN;
      initCookieBanner();
      vi.runAllTimers();
      expect($("#CookieBanner").hasClass("is-visible")).toBe(false);
    });

    it("adds is-visible after timers run when no cookie is present", () => {
      initCookieBanner();
      vi.runAllTimers();
      expect($("#CookieBanner").hasClass("is-visible")).toBe(true);
    });
  });

  describe("interactive elements hide the banner", () => {
    beforeEach(() => {
      initCookieBanner();
      vi.runAllTimers();
      document.body.insertAdjacentHTML(
        "beforeend",
        `<button id="testBtn">OK</button>
         <a id="testLink" href="#">link</a>
         <div class="clickable" id="testClickable">click</div>`,
      );
    });

    it("clicking a button removes is-visible", () => {
      document.getElementById("testBtn")!.click();
      expect($("#CookieBanner").hasClass("is-visible")).toBe(false);
    });

    it("clicking an a element removes is-visible", () => {
      document.getElementById("testLink")!.click();
      expect($("#CookieBanner").hasClass("is-visible")).toBe(false);
    });

    it("clicking a .clickable element removes is-visible", () => {
      document.getElementById("testClickable")!.click();
      expect($("#CookieBanner").hasClass("is-visible")).toBe(false);
    });

    it("sets COOKIE_BANNER_SEEN cookie after hiding via click", () => {
      document.getElementById("testBtn")!.click();
      expect(fakeCookie).toContain(COOKIE_BANNER_SEEN);
    });
  });

  describe("keyboard interaction", () => {
    beforeEach(() => {
      initCookieBanner();
      vi.runAllTimers();
      document.body.insertAdjacentHTML(
        "beforeend",
        `<div class="clickable" id="testClickable" tabindex="0">click</div>`,
      );
    });

    it("Enter keyup on a .clickable element removes is-visible", () => {
      const el = document.getElementById("testClickable")!;
      el.dispatchEvent(
        new KeyboardEvent("keyup", { key: "Enter", bubbles: true }),
      );
      expect($("#CookieBanner").hasClass("is-visible")).toBe(false);
    });
  });
});
