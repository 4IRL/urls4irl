import { isHidden, initVisibilityHandlers } from "../visibility.js";
import { enableTabbableChildElements } from "../../lib/jquery-plugins.js";

vi.mock("../../lib/jquery-plugins.js", () => ({
  enableTabbableChildElements: vi.fn(),
}));

const storeState = { multiSelectMode: false };
vi.mock("../../store/app-store.js", () => ({
  getState: vi.fn(() => storeState),
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
    // Each initVisibilityHandlers() binds fresh window focus/blur handlers;
    // clear them (and the mocks / store flag) so triggers fire exactly once.
    $(window).off("focus blur");
    storeState.multiSelectMode = false;
    vi.clearAllMocks();
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
        (call) => (call[0] as unknown as string) === "focus",
      );
      const blurCall = onSpy.mock.calls.find(
        (call) => (call[0] as unknown as string) === "blur",
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

    it("blur handler auto-expands the focused URL card in NORMAL mode (urlselected + tabbable children)", () => {
      storeState.multiSelectMode = false;
      initVisibilityHandlers();

      // Focus an element inside a .urlRow, then background the tab (window blur).
      ($(".urlRow button")[0] as HTMLElement).focus();
      $(window).trigger("blur");

      expect($(".urlRow").attr("urlselected")).toBe("true");
      expect(vi.mocked(enableTabbableChildElements)).toHaveBeenCalledTimes(1);
    });

    it("blur handler does NOT auto-expand the focused URL card in MULTI-SELECT mode (bug: backgrounding the app reopened a selected card)", () => {
      storeState.multiSelectMode = true;
      initVisibilityHandlers();

      ($(".urlRow button")[0] as HTMLElement).focus();
      $(window).trigger("blur");

      // The selected card must stay collapsed: no urlselected flip, no tabbable
      // re-enable — otherwise it renders expanded (tags + actions) on return.
      expect($(".urlRow").attr("urlselected")).toBeUndefined();
      expect(vi.mocked(enableTabbableChildElements)).not.toHaveBeenCalled();
    });
  });
});
