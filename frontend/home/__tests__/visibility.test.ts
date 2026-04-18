import { isHidden, initVisibilityHandlers } from "../visibility.js";

vi.mock("../../lib/jquery-plugins.js", () => ({
  enableTabbableChildElements: vi.fn(),
}));

const $ = window.jQuery;

const VISIBILITY_HTML = `
  <div id="visibleEl" style="display:block;">Visible</div>
  <div id="hiddenEl" style="display:none;">Hidden</div>
  <div class="urlRow">
    <span class="goToUrlIcon">Go</span>
    <button class="focus">Btn</button>
  </div>
`;

describe("visibility", () => {
  beforeEach(() => {
    document.body.innerHTML = VISIBILITY_HTML;
  });

  describe("isHidden", () => {
    it("returns false for an element with a non-null offsetParent", () => {
      const el = $("#visibleEl");
      const domEl = el.get(0)!;
      Object.defineProperty(domEl, "offsetParent", {
        value: document.body,
        configurable: true,
      });

      expect(isHidden(el)).toBe(false);
    });

    it("returns true for an element with offsetParent === null", () => {
      const el = $("#hiddenEl");
      const domEl = el.get(0)!;
      Object.defineProperty(domEl, "offsetParent", {
        value: null,
        configurable: true,
      });

      expect(isHidden(el)).toBe(true);
    });

    it("returns true for an empty jQuery set (no matching element)", () => {
      const emptyEl = $("#nonExistentElement");
      expect(emptyEl.length).toBe(0);
      expect(isHidden(emptyEl)).toBe(true);
    });
  });

  describe("initVisibilityHandlers", () => {
    it("registers focus and blur handlers on the window", () => {
      const onSpy = vi.spyOn($.fn, "on");

      initVisibilityHandlers();

      const focusCall = onSpy.mock.calls.find(
        (call) => (call[0] as string) === "focus",
      );
      const blurCall = onSpy.mock.calls.find(
        (call) => (call[0] as string) === "blur",
      );
      expect(focusCall).toBeDefined();
      expect(blurCall).toBeDefined();

      onSpy.mockRestore();
    });

    it("focus handler is a no-op when no element has the focus class", () => {
      $(".focus").removeClass("focus");
      initVisibilityHandlers();

      // Trigger the window focus event
      $(window).trigger("focus");

      // No errors should occur - the early return should fire
      expect($(".focus").length).toBe(0);
    });
  });
});
