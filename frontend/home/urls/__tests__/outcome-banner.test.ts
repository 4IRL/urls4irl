import { createMockJqXHRChainable } from "../../../__tests__/helpers/mock-jquery.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { ajaxCall, is429Handled } from "../../../lib/ajax.js";
import { isUtubLockedHandled } from "../../utub-locked.js";
import { showURLDeckBannerError } from "../deck.js";
import { deleteURLOnStale } from "../cards/get.js";
import { applyUpdatedURLString } from "../cards/apply-url-string.js";
import { URL_PARAMS_TRIMMED_FORM } from "../../../types/metrics-dim-values.js";
import { flushParamTrim } from "../trim/param-trim-block.js";
import { isCoarsePointer } from "../../mobile.js";
import {
  bindEditPanelDirtyState,
  unbindEditPanelDirtyState,
} from "../cards/edit-panel-dirty.js";
import {
  buildReviveMessage,
  clearURLOutcomeBanner,
  performUndo,
  showReviveBanner,
  showTrimSavedBanner,
  showURLOutcomeBanner,
  showURLUpdatedBanner,
} from "../outcome-banner.js";

vi.mock("../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));
vi.mock("../../utub-locked.js", () => ({
  isUtubLockedHandled: vi.fn(() => false),
}));
vi.mock("../deck.js", () => ({
  showURLDeckBannerError: vi.fn(),
}));
vi.mock("../cards/get.js", () => ({
  deleteURLOnStale: vi.fn(),
}));
vi.mock("../../mobile.js", () => ({
  isMobile: vi.fn(() => false),
  isCoarsePointer: vi.fn(() => false),
}));
vi.mock("../cards/apply-url-string.js", () => ({
  applyUpdatedURLString: vi.fn(),
}));
vi.mock("../trim/param-trim-block.js", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../trim/param-trim-block.js")>()),
  flushParamTrim: vi.fn(),
}));

const $ = window.jQuery;

const PAGE_HTML = `
  <div id="URLDeck" tabindex="-1">
    <div id="URLDeckOutcomeBanner" class="urlOutcomeBanner hidden" role="status"></div>
    <div id="listURLs">
      <div class="urlRow" utuburlid="42">
        <button class="urlStringBtnUpdate">edit</button>
      </div>
    </div>
  </div>
  <button id="elsewhere">elsewhere</button>
`;

const ORIGINAL = "https://example.com/p?a=1&b=2";

// jsdom has no layout, so jQuery's ":visible" is always false; let each test
// declare whether the focus target counts as rendered.
let targetVisible = true;

function banner(): JQuery {
  return $("#URLDeckOutcomeBanner");
}

function editButton(): JQuery {
  return $(".urlRow[utuburlid=42]").find(".urlStringBtnUpdate");
}

function mockXhr(
  handlers: Parameters<typeof createMockJqXHRChainable>[0],
): void {
  vi.mocked(ajaxCall).mockReturnValue(createMockJqXHRChainable(handlers));
}

function mockDone(response: unknown): void {
  mockXhr({
    done: (callback: unknown) => (callback as (r: unknown) => void)(response),
  });
}

function mockFail(status: number, message?: string): JQuery.jqXHR {
  const xhr = {
    status,
    responseJSON: message === undefined ? undefined : { message },
  } as unknown as JQuery.jqXHR;
  mockXhr({
    fail: (callback: unknown) =>
      (callback as (xhrArg: JQuery.jqXHR) => void)(xhr),
  });
  return xhr;
}

function runUndo(): void {
  performUndo({
    utubID: 3,
    utubUrlID: 42,
    urlCard: $(".urlRow[utuburlid=42]"),
    originalUrlString: ORIGINAL,
    returnFocusTo: editButton(),
  });
}

describe("outcome banner", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    document.body.innerHTML = PAGE_HTML;
    targetVisible = true;
    const originalIs = $.fn.is;
    vi.spyOn($.fn, "is").mockImplementation(function (
      this: JQuery,
      selector: unknown,
    ) {
      if (selector === ":visible") return targetVisible;
      return originalIs.call(this, selector as string);
    });
    vi.mocked(is429Handled).mockReturnValue(false);
    vi.mocked(isUtubLockedHandled).mockReturnValue(false);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  describe("showURLOutcomeBanner / clearURLOutcomeBanner", () => {
    it.each(["success", "partial"] as const)(
      "renders the %s variant with message and detail as text",
      (variant) => {
        showURLOutcomeBanner({
          variant,
          message: "Saved",
          detail: "<b>a=1</b>",
          returnFocusTo: editButton(),
        });

        expect(banner().hasClass("hidden")).toBe(false);
        expect(banner().hasClass(variant)).toBe(true);
        expect(banner().find(".urlOutcomeBannerMessage").text()).toBe("Saved");
        expect(banner().find(".urlOutcomeBannerDetail").text()).toBe(
          "<b>a=1</b>",
        );
        expect(banner().find("b")).toHaveLength(0);
      },
    );

    it("switching variants drops the previous variant class", () => {
      showURLOutcomeBanner({
        variant: "success",
        message: "one",
        returnFocusTo: editButton(),
      });
      showURLOutcomeBanner({
        variant: "partial",
        message: "two",
        returnFocusTo: editButton(),
      });

      expect(banner().hasClass("success")).toBe(false);
      expect(banner().hasClass("partial")).toBe(true);
      expect(banner().find(".urlOutcomeBannerMessage")).toHaveLength(1);
    });

    it("omits the action button when no action is given", () => {
      showURLOutcomeBanner({
        variant: "partial",
        message: "no action",
        returnFocusTo: editButton(),
      });

      expect(banner().find(".urlOutcomeBannerAction")).toHaveLength(0);
      expect(banner().find(".urlOutcomeBannerDismiss")).toHaveLength(1);
    });

    it("runs the action once even when clicked repeatedly", () => {
      const onAction = vi.fn();
      showURLOutcomeBanner({
        variant: "success",
        message: "m",
        actionLabel: "Undo",
        onAction,
        returnFocusTo: editButton(),
      });

      const action = banner().find(".urlOutcomeBannerAction");
      expect(action.text()).toBe("Undo");
      action.trigger("click");
      action.trigger("click");

      expect(onAction).toHaveBeenCalledTimes(1);
    });

    describe("auto-hide", () => {
      const AUTO_HIDE_MS = 10000;
      const AUTO_HIDE_PARTIAL_MS = 20000;

      function show(variant: "success" | "partial" = "success"): void {
        showURLOutcomeBanner({
          variant,
          message: "m",
          actionLabel: variant === "success" ? "Undo" : undefined,
          onAction: variant === "success" ? () => {} : undefined,
          returnFocusTo: editButton(),
        });
      }

      beforeEach(() => {
        vi.useFakeTimers();
      });

      it("hides itself after the timeout, not before", () => {
        show();

        vi.advanceTimersByTime(AUTO_HIDE_MS - 1);
        expect(banner().hasClass("hidden")).toBe(false);

        vi.advanceTimersByTime(1);
        expect(banner().hasClass("hidden")).toBe(true);
        expect(banner().children()).toHaveLength(0);
      });

      it("gives the partial variant a longer countdown", () => {
        show("partial");

        vi.advanceTimersByTime(AUTO_HIDE_MS);
        expect(banner().hasClass("hidden")).toBe(false);

        vi.advanceTimersByTime(AUTO_HIDE_PARTIAL_MS - AUTO_HIDE_MS - 1);
        expect(banner().hasClass("hidden")).toBe(false);

        vi.advanceTimersByTime(1);
        expect(banner().hasClass("hidden")).toBe(true);
      });

      it("restarts a partial banner with the partial duration after a pause", () => {
        show("partial");

        banner().trigger("focusin");
        banner().trigger("focusout");
        vi.advanceTimersByTime(AUTO_HIDE_PARTIAL_MS - 1);
        expect(banner().hasClass("hidden")).toBe(false);

        vi.advanceTimersByTime(1);
        expect(banner().hasClass("hidden")).toBe(true);
      });

      it("does not move focus when it hides", () => {
        show();
        $("#elsewhere").trigger("focus");

        vi.advanceTimersByTime(AUTO_HIDE_MS);

        expect(document.activeElement).toBe($("#elsewhere")[0]);
      });

      // jQuery maps pointerenter/pointerleave onto the native pointerover /
      // pointerout, so dispatch those with a pointerType to exercise real events.
      function firePointer({
        type,
        pointerType,
      }: {
        type: string;
        pointerType: string;
      }): void {
        const event = new MouseEvent(type, { bubbles: true });
        Object.defineProperty(event, "pointerType", { value: pointerType });
        banner()[0].dispatchEvent(event);
      }

      it.each([
        ["pointerenter", "pointerleave"],
        ["focusin", "focusout"],
        ["pointerdown", "pointerup"],
        ["pointerdown", "pointercancel"],
      ])(
        "pauses on %s and restarts the full countdown on %s",
        (pauseEvent, resumeEvent) => {
          show();
          vi.advanceTimersByTime(AUTO_HIDE_MS - 1000);

          banner().trigger(pauseEvent);
          vi.advanceTimersByTime(60 * 1000);
          expect(banner().hasClass("hidden")).toBe(false);

          banner().trigger(resumeEvent);
          vi.advanceTimersByTime(AUTO_HIDE_MS - 1);
          expect(banner().hasClass("hidden")).toBe(false);
          vi.advanceTimersByTime(1);
          expect(banner().hasClass("hidden")).toBe(true);
        },
      );

      it("a real mouse hover pauses and leaving restarts the countdown", () => {
        show();

        firePointer({ type: "pointerover", pointerType: "mouse" });
        vi.advanceTimersByTime(AUTO_HIDE_MS * 3);
        expect(banner().hasClass("hidden")).toBe(false);

        firePointer({ type: "pointerout", pointerType: "mouse" });
        vi.advanceTimersByTime(AUTO_HIDE_MS);
        expect(banner().hasClass("hidden")).toBe(true);
      });

      it("a touch followed by its compatibility mouse hover does not pin the countdown", () => {
        show();

        firePointer({ type: "pointerdown", pointerType: "touch" });
        firePointer({ type: "pointerup", pointerType: "touch" });
        // The browser's compat mouseenter-equivalent arrives right after touchend
        // with no matching leave until the next tap.
        firePointer({ type: "pointerover", pointerType: "mouse" });

        vi.advanceTimersByTime(AUTO_HIDE_MS);
        expect(banner().hasClass("hidden")).toBe(true);
      });

      it("a mouse hover long after a touch pauses again", () => {
        show();
        firePointer({ type: "pointerdown", pointerType: "touch" });
        firePointer({ type: "pointerup", pointerType: "touch" });

        vi.advanceTimersByTime(5000);
        firePointer({ type: "pointerover", pointerType: "mouse" });
        vi.advanceTimersByTime(AUTO_HIDE_MS * 3);

        expect(banner().hasClass("hidden")).toBe(false);
      });

      it("a banner replaced under a hovering pointer waits for it to leave", () => {
        const originalIs = $.fn.is;
        vi.spyOn($.fn, "is").mockImplementation(function (
          this: JQuery,
          selector: unknown,
        ) {
          if (selector === ":hover") return true;
          if (selector === ":visible") return targetVisible;
          return originalIs.call(this, selector as string);
        });

        show();
        vi.advanceTimersByTime(AUTO_HIDE_MS * 3);
        expect(banner().hasClass("hidden")).toBe(false);

        banner().trigger("pointerleave");
        vi.advanceTimersByTime(AUTO_HIDE_MS);
        expect(banner().hasClass("hidden")).toBe(true);
      });

      it("defers hiding while the Undo request is in flight and keeps the button", () => {
        show();
        banner().find(".urlOutcomeBannerAction").trigger("click");
        expect(
          banner().find(".urlOutcomeBannerAction").attr("aria-disabled"),
        ).toBe("true");

        vi.advanceTimersByTime(AUTO_HIDE_MS * 3);

        expect(banner().hasClass("hidden")).toBe(false);
        expect(banner().find(".urlOutcomeBannerAction")).toHaveLength(1);
      });

      it("pauses while the Undo button has focus and bubbles up to the banner", () => {
        show();

        banner().find(".urlOutcomeBannerAction").trigger("focusin");
        vi.advanceTimersByTime(AUTO_HIDE_MS * 3);

        expect(banner().hasClass("hidden")).toBe(false);
      });

      it("a newly shown banner gets a fresh full countdown", () => {
        show();
        vi.advanceTimersByTime(6000);

        show();
        vi.advanceTimersByTime(AUTO_HIDE_MS - 1);
        expect(banner().hasClass("hidden")).toBe(false);

        vi.advanceTimersByTime(1);
        expect(banner().hasClass("hidden")).toBe(true);
      });

      it("a replaced banner is not hidden by the earlier banner's timer", () => {
        show();
        vi.advanceTimersByTime(AUTO_HIDE_MS - 100);
        showURLOutcomeBanner({
          variant: "partial",
          message: "second",
          returnFocusTo: editButton(),
        });

        vi.advanceTimersByTime(200);

        expect(banner().hasClass("hidden")).toBe(false);
        expect(banner().find(".urlOutcomeBannerMessage").text()).toBe("second");
      });

      it("clearing and dismissing cancel the countdown and detach the pause handlers", () => {
        show();
        clearURLOutcomeBanner();
        banner().trigger("pointerleave");
        vi.advanceTimersByTime(AUTO_HIDE_MS * 2);
        expect(banner().hasClass("hidden")).toBe(true);

        show();
        banner().find(".urlOutcomeBannerDismiss").trigger("click");
        banner().trigger("pointerleave");
        expect(vi.getTimerCount()).toBe(0);
      });

      it("a pause event after clearing does not arm a stray timer", () => {
        show();
        clearURLOutcomeBanner();

        banner().trigger("focusout");

        expect(vi.getTimerCount()).toBe(0);
      });
    });

    it("does not move focus when shown", () => {
      $("#elsewhere").trigger("focus");

      showURLOutcomeBanner({
        variant: "success",
        message: "m",
        returnFocusTo: editButton(),
      });

      expect(document.activeElement).toBe($("#elsewhere")[0]);
    });

    it("dismiss clears the banner and returns focus to the target", () => {
      showURLOutcomeBanner({
        variant: "success",
        message: "m",
        returnFocusTo: editButton(),
      });

      banner().find(".urlOutcomeBannerDismiss").trigger("click");

      expect(banner().hasClass("hidden")).toBe(true);
      expect(banner().children()).toHaveLength(0);
      expect(document.activeElement).toBe(editButton()[0]);
    });

    it("dismiss falls back to the deck when the target is not rendered", () => {
      showURLOutcomeBanner({
        variant: "success",
        message: "m",
        returnFocusTo: editButton(),
      });
      targetVisible = false;

      banner().find(".urlOutcomeBannerDismiss").trigger("click");

      expect(document.activeElement).toBe($("#URLDeck")[0]);
    });

    it("dismiss falls back to the deck when the target no longer exists", () => {
      const missing = $(".urlRow[utuburlid=999]").find(".urlStringBtnUpdate");
      showURLOutcomeBanner({
        variant: "success",
        message: "m",
        returnFocusTo: missing,
      });

      banner().find(".urlOutcomeBannerDismiss").trigger("click");

      expect(document.activeElement).toBe($("#URLDeck")[0]);
    });

    it("clearURLOutcomeBanner is a safe no-op when nothing is showing", () => {
      expect(() => clearURLOutcomeBanner()).not.toThrow();
      expect(banner().hasClass("hidden")).toBe(true);
    });

    it("skips quietly when the container is missing", () => {
      document.body.innerHTML = "";
      expect(() =>
        showURLOutcomeBanner({
          variant: "success",
          message: "m",
          returnFocusTo: $(),
        }),
      ).not.toThrow();
    });
  });

  describe("buildReviveMessage", () => {
    it("returns the plain restored message when no tags were lost", () => {
      expect(buildReviveMessage({ lostTagCount: 0 })).toBe(
        APP_CONFIG.strings.URL_REVIVED_FROM_TRASH,
      );
    });

    it("returns the singular lost-tag message for one lost tag", () => {
      expect(buildReviveMessage({ lostTagCount: 1 })).toBe(
        APP_CONFIG.strings.URL_REVIVED_LOST_TAGS_ONE,
      );
    });

    it("fills the plural lost-tag message with the count", () => {
      expect(buildReviveMessage({ lostTagCount: 2 })).toBe(
        "Restored from trash. 2 tags no longer exist.",
      );
    });
  });

  describe("showReviveBanner", () => {
    it("shows a success banner with no action when no tags were lost", () => {
      showReviveBanner({ lostTagCount: 0, utubUrlID: 42 });

      expect(banner().hasClass("success")).toBe(true);
      expect(banner().find(".urlOutcomeBannerMessage").text()).toBe(
        APP_CONFIG.strings.URL_REVIVED_FROM_TRASH,
      );
      expect(banner().find(".urlOutcomeBannerAction")).toHaveLength(0);
    });

    it("shows a partial banner with no action when tags were lost", () => {
      showReviveBanner({ lostTagCount: 2, utubUrlID: 42 });

      expect(banner().hasClass("partial")).toBe(true);
      expect(banner().hasClass("success")).toBe(false);
      expect(banner().find(".urlOutcomeBannerMessage").text()).toBe(
        "Restored from trash. 2 tags no longer exist.",
      );
      expect(banner().find(".urlOutcomeBannerAction")).toHaveLength(0);
    });
  });

  describe("showTrimSavedBanner", () => {
    function show(
      droppedSegments: string[],
      revive?: { lostTagCount: number },
    ): void {
      showTrimSavedBanner({
        trimSubmission: {
          originalUrlString: ORIGINAL,
          droppedSegments,
          droppedCount: droppedSegments.length,
        },
        utubID: 3,
        utubUrlID: 42,
        urlCard: $(".urlRow[utuburlid=42]"),
        form: URL_PARAMS_TRIMMED_FORM.URL_CREATE,
        revive,
      });
    }

    it("prefixes the revive sentence, goes partial and keeps Undo when a revive lost tags", () => {
      show(["a=1"], { lostTagCount: 1 });

      expect(banner().find(".urlOutcomeBannerMessage").text()).toBe(
        `${APP_CONFIG.strings.URL_REVIVED_LOST_TAGS_ONE} ${APP_CONFIG.strings.URL_TRIM_SAVED_BANNER_ONE}`,
      );
      expect(banner().hasClass("partial")).toBe(true);
      expect(banner().find(".urlOutcomeBannerAction").text()).toBe(
        APP_CONFIG.strings.URL_TRIM_UNDO,
      );
    });

    it("stays a success banner when a revive lost no tags", () => {
      show(["a=1"], { lostTagCount: 0 });

      expect(banner().find(".urlOutcomeBannerMessage").text()).toBe(
        `${APP_CONFIG.strings.URL_REVIVED_FROM_TRASH} ${APP_CONFIG.strings.URL_TRIM_SAVED_BANNER_ONE}`,
      );
      expect(banner().hasClass("success")).toBe(true);
    });

    it("uses the singular message and lists the dropped segment", () => {
      show(["a=1"]);

      expect(banner().find(".urlOutcomeBannerMessage").text()).toBe(
        APP_CONFIG.strings.URL_TRIM_SAVED_BANNER_ONE,
      );
      expect(banner().find(".urlOutcomeBannerDetail").text()).toBe("a=1");
      expect(banner().hasClass("success")).toBe(true);
    });

    it("uses the plural message with the count", () => {
      show(["a=1", "b=2"]);

      expect(banner().find(".urlOutcomeBannerMessage").text()).toBe(
        "Saved without 2 parameters.",
      );
      expect(banner().find(".urlOutcomeBannerDetail").text()).toBe("a=1, b=2");
    });

    it("Undo PATCHes the untrimmed original string", () => {
      mockXhr({});
      show(["a=1"]);

      banner().find(".urlOutcomeBannerAction").trigger("click");

      expect(ajaxCall).toHaveBeenCalledWith(
        "patch",
        APP_CONFIG.routes.updateURL(3, 42),
        { urlString: ORIGINAL },
        35000,
      );
    });
  });

  describe("showURLUpdatedBanner", () => {
    const PREVIOUS = "https://example.com/before";

    function show(): void {
      showURLUpdatedBanner({
        utubID: 3,
        utubUrlID: 42,
        urlCard: $(".urlRow[utuburlid=42]"),
        previousUrlString: PREVIOUS,
      });
    }

    it("shows the plain updated message with an Undo and no dropped-parameter detail", () => {
      show();

      expect(banner().hasClass("success")).toBe(true);
      expect(banner().find(".urlOutcomeBannerMessage").text()).toBe(
        APP_CONFIG.strings.URL_UPDATED_BANNER,
      );
      expect(banner().find(".urlOutcomeBannerDetail")).toHaveLength(0);
      expect(banner().find(".urlOutcomeBannerAction").text()).toBe(
        APP_CONFIG.strings.URL_TRIM_UNDO,
      );
    });

    it("Undo PATCHes the string the card showed before the save", () => {
      mockXhr({});
      show();

      banner().find(".urlOutcomeBannerAction").trigger("click");

      expect(ajaxCall).toHaveBeenCalledWith(
        "patch",
        APP_CONFIG.routes.updateURL(3, 42),
        { urlString: PREVIOUS },
        35000,
      );
    });
  });

  describe("performUndo", () => {
    function showExistingBanner(): void {
      showURLOutcomeBanner({
        variant: "success",
        message: "Saved without 1 parameter.",
        returnFocusTo: editButton(),
      });
    }

    it("200 success rewrites the card, clears the banner and shows no new one", () => {
      const response = { status: "Success", URL: { utubUrlID: 42 } };
      showExistingBanner();
      mockDone(response);

      runUndo();

      expect(applyUpdatedURLString).toHaveBeenCalledTimes(1);
      const applied = vi.mocked(applyUpdatedURLString).mock.calls[0][0];
      expect(applied.response).toBe(response);
      expect(applied.urlCard[0]).toBe($(".urlRow[utuburlid=42]")[0]);
      expect(banner().hasClass("hidden")).toBe(true);
      expect(banner().children()).toHaveLength(0);
      expect(document.activeElement).toBe(editButton()[0]);
    });

    describe("edit form resync", () => {
      const TRIMMED = "https://example.com/p?a=1";

      // The card shows the just-saved (trimmed) string; the input still holds it.
      function addEditForm({
        closed = false,
      }: { closed?: boolean } = {}): void {
        $(".urlRow[utuburlid=42]").append(`
          <a class="urlString">${TRIMMED}</a>
          <div class="updateUrlStringWrap${closed ? " hidden" : ""}">
            <input class="urlStringUpdate" value="${TRIMMED}" />
            <div class="urlParamTrimWrap"></div>
          </div>
        `);
      }

      function mockUndoSuccess(): void {
        mockDone({
          status: "Success",
          URL: { utubUrlID: 42, urlString: ORIGINAL },
        });
      }

      it("leaves text the user typed since the save alone, but still updates the card", () => {
        addEditForm();
        $(".urlStringUpdate").val("https://example.com/typed");
        showExistingBanner();
        mockUndoSuccess();

        runUndo();

        expect($(".urlStringUpdate").val()).toBe("https://example.com/typed");
        expect(flushParamTrim).not.toHaveBeenCalled();
        expect(applyUpdatedURLString).toHaveBeenCalledTimes(1);
        expect(banner().hasClass("hidden")).toBe(true);
      });

      it("resyncs a closed form even if its input differs", () => {
        addEditForm({ closed: true });
        $(".urlStringUpdate").val("https://example.com/stale");
        showExistingBanner();
        mockUndoSuccess();

        runUndo();

        expect($(".urlStringUpdate").val()).toBe(ORIGINAL);
        expect(flushParamTrim).toHaveBeenCalledTimes(1);
      });

      it("restores the input to the stored original and re-renders the trim block from it", () => {
        addEditForm();
        showExistingBanner();
        mockDone({
          status: "Success",
          URL: { utubUrlID: 42, urlString: ORIGINAL },
        });

        runUndo();

        expect($(".urlStringUpdate").val()).toBe(ORIGINAL);
        expect(flushParamTrim).toHaveBeenCalledTimes(1);
        const flushed = vi.mocked(flushParamTrim).mock.calls[0][0];
        expect(flushed.rawValue).toBe(ORIGINAL);
        expect(flushed.trimWrap[0]).toBe($(".urlParamTrimWrap")[0]);
      });

      it('leaves the input alone on a "No change" response', () => {
        addEditForm();
        showExistingBanner();
        mockDone({
          status: "No change",
          URL: { utubUrlID: 42, urlString: TRIMMED },
        });

        runUndo();

        expect($(".urlStringUpdate").val()).toBe(TRIMMED);
        expect(flushParamTrim).not.toHaveBeenCalled();
      });

      it("leaves the input alone when the undo fails", () => {
        addEditForm();
        showExistingBanner();
        mockFail(409);

        runUndo();

        expect($(".urlStringUpdate").val()).toBe(TRIMMED);
        expect(flushParamTrim).not.toHaveBeenCalled();
      });
    });

    describe("open mobile panel dirty-state resync", () => {
      const TRIMMED = "https://example.com/p?a=1";

      // A Save URL that left the panel open because the title is dirty: the card
      // shows the saved string, the URL field holds it too (so URL ✓/Save URL are
      // disabled) and the title field has unsaved edits (title ✓ enabled).
      function openPanelAfterSaveUrl(): JQuery {
        const urlCard = $(".urlRow[utuburlid=42]");
        urlCard.append(`
          <span class="urlTitle">Stored title</span>
          <a class="urlString" href="${TRIMMED}">${TRIMMED}</a>
          <input class="urlTitleUpdate" value="Stored title" />
          <button class="urlTitleSubmitBtnUpdate"></button>
          <div class="updateUrlStringWrap">
            <input class="urlStringUpdate" value="${TRIMMED}" />
            <div class="urlParamTrimWrap"></div>
          </div>
          <button class="urlStringSubmitBtnUpdate"></button>
          <button class="urlStringSaveBigBtnUpdate"></button>
        `);
        // The real apply rewrites the card; the mocked one needs to do it here.
        vi.mocked(applyUpdatedURLString).mockImplementation(
          ({ response, urlCard: card }) => {
            card
              .find(".urlString")
              .attr("href", response.URL.urlString)
              .text(response.URL.urlString);
          },
        );
        vi.mocked(isCoarsePointer).mockReturnValue(true);
        bindEditPanelDirtyState(urlCard);
        urlCard.find(".urlTitleUpdate").val("Typed title").trigger("input");
        return urlCard;
      }

      afterEach(() => {
        unbindEditPanelDirtyState($(".urlRow[utuburlid=42]"));
      });

      it("disables the URL check and Save URL when a typed value now equals the restored string, leaving the title check alone", () => {
        const urlCard = openPanelAfterSaveUrl();
        urlCard.find(".urlStringUpdate").val(ORIGINAL).trigger("input");
        expect(
          urlCard.find(".urlStringSubmitBtnUpdate").attr("aria-disabled"),
        ).toBeUndefined();
        showExistingBanner();
        mockDone({
          status: "Success",
          URL: { utubUrlID: 42, urlString: ORIGINAL },
        });

        runUndo();

        ["urlStringSubmitBtnUpdate", "urlStringSaveBigBtnUpdate"].forEach(
          (name) => {
            const button = urlCard.find(`.${name}`);
            expect(button.attr("aria-disabled")).toBe("true");
            expect(button.hasClass("unchanged")).toBe(true);
          },
        );
        expect(
          urlCard.find(".urlTitleSubmitBtnUpdate").attr("aria-disabled"),
        ).toBeUndefined();
      });

      it("enables the URL check and Save URL when the restored string differs from the kept field text", () => {
        const urlCard = openPanelAfterSaveUrl();
        const typed = "https://example.com/typed";
        urlCard.find(".urlStringUpdate").val(TRIMMED).trigger("input");
        expect(
          urlCard.find(".urlStringSubmitBtnUpdate").attr("aria-disabled"),
        ).toBe("true");
        // Text typed after the save without a dirty sync yet (checks still disabled).
        urlCard.find(".urlStringUpdate").val(typed);
        showExistingBanner();
        mockDone({
          status: "Success",
          URL: { utubUrlID: 42, urlString: ORIGINAL },
        });

        runUndo();

        // The typed text is left alone, and now differs from the restored href.
        ["urlStringSubmitBtnUpdate", "urlStringSaveBigBtnUpdate"].forEach(
          (name) => {
            expect(urlCard.find(`.${name}`).attr("aria-disabled")).toBe(
              undefined,
            );
          },
        );
      });
    });

    it('200 "No change" shows the no-op message as a partial banner', () => {
      showExistingBanner();
      mockDone({ status: "No change", URL: { utubUrlID: 42 } });

      runUndo();

      expect(applyUpdatedURLString).not.toHaveBeenCalled();
      expect(banner().hasClass("partial")).toBe(true);
      expect(banner().find(".urlOutcomeBannerMessage").text()).toBe(
        APP_CONFIG.strings.URL_TRIM_UNDO_NOOP,
      );
      expect(banner().find(".urlOutcomeBannerAction")).toHaveLength(0);
      expect(document.activeElement).toBe(editButton()[0]);
    });

    it("409 shows the undo-conflict message as a partial banner", () => {
      showExistingBanner();
      mockFail(409, "URL already in UTub");

      runUndo();

      expect(banner().hasClass("partial")).toBe(true);
      expect(banner().find(".urlOutcomeBannerMessage").text()).toBe(
        APP_CONFIG.strings.URL_TRIM_UNDO_CONFLICT,
      );
      expect(showURLDeckBannerError).not.toHaveBeenCalled();
      expect(document.activeElement).toBe(editButton()[0]);
    });

    it("400 routes the server message to the deck error banner, not a new variant", () => {
      showExistingBanner();
      mockFail(400, "URL too long");

      runUndo();

      expect(showURLDeckBannerError).toHaveBeenCalledWith("URL too long");
      expect(banner().hasClass("hidden")).toBe(true);
      expect(document.activeElement).toBe(editButton()[0]);
    });

    it("403 delegates to isUtubLockedHandled with the xhr", () => {
      showExistingBanner();
      vi.mocked(isUtubLockedHandled).mockReturnValue(true);
      const xhr = mockFail(403, APP_CONFIG.strings.UTUB_IS_LOCKED);

      runUndo();

      expect(isUtubLockedHandled).toHaveBeenCalledWith(xhr);
      expect(showURLDeckBannerError).not.toHaveBeenCalled();
      expect(banner().hasClass("hidden")).toBe(true);
      expect(document.activeElement).toBe(editButton()[0]);
    });

    it("403 that is not the locked case still surfaces its message", () => {
      showExistingBanner();
      mockFail(403, "Forbidden");

      runUndo();

      expect(showURLDeckBannerError).toHaveBeenCalledWith("Forbidden");
    });

    it("403 falls back to the deck when the card's button is not rendered", () => {
      showExistingBanner();
      vi.mocked(isUtubLockedHandled).mockReturnValue(true);
      mockFail(403, APP_CONFIG.strings.UTUB_IS_LOCKED);
      targetVisible = false;

      runUndo();

      expect(document.activeElement).toBe($("#URLDeck")[0]);
    });

    it("404 shows the error, removes the stale card and focuses the deck", () => {
      showExistingBanner();
      mockFail(404, "URL not found");

      runUndo();

      expect(showURLDeckBannerError).toHaveBeenCalledWith("URL not found");
      expect(deleteURLOnStale).toHaveBeenCalledTimes(1);
      expect(vi.mocked(deleteURLOnStale).mock.calls[0][0][0]).toBe(
        $(".urlRow[utuburlid=42]")[0],
      );
      expect(banner().hasClass("hidden")).toBe(true);
      expect(document.activeElement).toBe($("#URLDeck")[0]);
    });

    it("a handled 429 shows nothing further, re-enables Undo and returns focus", () => {
      showTrimSavedBanner({
        trimSubmission: {
          originalUrlString: ORIGINAL,
          droppedSegments: ["a=1"],
          droppedCount: 1,
        },
        utubID: 3,
        utubUrlID: 42,
        urlCard: $(".urlRow[utuburlid=42]"),
        form: URL_PARAMS_TRIMMED_FORM.URL_CREATE,
      });
      mockFail(429);
      vi.mocked(is429Handled).mockReturnValue(true);
      const undo = banner().find(".urlOutcomeBannerAction");
      undo.trigger("click");
      expect(undo.attr("aria-disabled")).toBeUndefined();
      expect(banner().hasClass("hidden")).toBe(false);
      expect(showURLDeckBannerError).not.toHaveBeenCalled();
      expect(document.activeElement).toBe(editButton()[0]);
    });

    it("a 429 after the countdown fired mid-request keeps the Undo button and restarts the countdown", () => {
      vi.useFakeTimers();
      showTrimSavedBanner({
        trimSubmission: {
          originalUrlString: ORIGINAL,
          droppedSegments: ["a=1"],
          droppedCount: 1,
        },
        utubID: 3,
        utubUrlID: 42,
        urlCard: $(".urlRow[utuburlid=42]"),
        form: URL_PARAMS_TRIMMED_FORM.URL_CREATE,
      });
      // The request stays pending until the test settles it.
      let settle: () => void = () => {};
      mockXhr({
        fail: (callback: unknown) => {
          settle = () =>
            (callback as (xhrArg: JQuery.jqXHR) => void)({
              status: 429,
            } as unknown as JQuery.jqXHR);
        },
      });
      vi.mocked(is429Handled).mockReturnValue(true);
      banner().find(".urlOutcomeBannerAction").trigger("click");

      vi.advanceTimersByTime(10000);
      expect(banner().hasClass("hidden")).toBe(false);

      settle();
      const undo = banner().find(".urlOutcomeBannerAction");
      expect(undo).toHaveLength(1);
      expect(undo.attr("aria-disabled")).toBeUndefined();

      vi.advanceTimersByTime(9999);
      expect(banner().hasClass("hidden")).toBe(false);
      vi.advanceTimersByTime(1);
      expect(banner().hasClass("hidden")).toBe(true);
    });

    it("(legacy) a handled 429 with no banner action still returns focus", () => {
      showExistingBanner();
      vi.mocked(is429Handled).mockReturnValue(true);
      mockFail(429);

      runUndo();

      expect(showURLDeckBannerError).not.toHaveBeenCalled();
      expect(document.activeElement).toBe(editButton()[0]);
    });

    it("a failure with no JSON body shows an empty deck error", () => {
      showExistingBanner();
      mockFail(500);

      runUndo();

      expect(showURLDeckBannerError).toHaveBeenCalledWith("");
    });
  });
});
