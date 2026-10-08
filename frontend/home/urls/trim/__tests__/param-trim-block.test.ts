import {
  createParamTrimBlock,
  TRIM_FLUSH_KEY,
  TRIM_GET_KEY,
  TRIM_RESET_KEY,
  TRIM_SUBMISSION_KEY,
  TRIM_SYNC_KEY,
  TrimMode,
  type TrimSubmission,
} from "../param-trim-block.js";
import { APP_CONFIG } from "../../../../lib/config.js";

const URL_WITH_AUTO = "https://a.com/p?ref=1&utm_source=x&size=L";
const UNPARSEABLE = "http://exa mple.com/?a=1";

type Wrap = JQuery<HTMLElement>;

function getTrimmed(wrap: Wrap): string {
  return (wrap.data(TRIM_GET_KEY) as () => string)();
}

function getSubmission(wrap: Wrap): TrimSubmission {
  return (wrap.data(TRIM_SUBMISSION_KEY) as () => TrimSubmission)();
}

function sync(wrap: Wrap, rawValue: string): void {
  (wrap.data(TRIM_SYNC_KEY) as (rawValue: string) => void)(rawValue);
}

function flush(wrap: Wrap, rawValue: string): void {
  (wrap.data(TRIM_FLUSH_KEY) as (rawValue: string) => void)(rawValue);
}

function reset(wrap: Wrap): void {
  (wrap.data(TRIM_RESET_KEY) as () => void)();
}

function mount(
  options: {
    mode?: TrimMode;
    urlCard?: JQuery | null;
    onDroppedChange?: () => void;
  } = {},
): Wrap {
  const wrap = createParamTrimBlock({
    mode: options.mode ?? TrimMode.CREATE,
    urlCard: options.urlCard ?? null,
    onDroppedChange: options.onDroppedChange,
  });
  window.jQuery(document.body).append(wrap);
  return wrap;
}

function chipButtons(wrap: Wrap): JQuery<HTMLElement> {
  return wrap.find("button.urlParamTrimChip");
}

function announcerText(wrap: Wrap): string {
  return wrap.find(".urlParamTrimAnnouncer").text();
}

function keydown(target: JQuery<HTMLElement>, key: string): JQuery.Event {
  const event = window.jQuery.Event("keydown", { key });
  target.trigger(event);
  return event;
}

describe("createParamTrimBlock", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  describe("initial shape", () => {
    it("builds hidden and collapsed", () => {
      const wrap = mount();
      expect(wrap.hasClass("urlParamTrimWrap")).toBe(true);
      expect(wrap.hasClass("hidden")).toBe(true);
      expect(wrap.hasClass("collapsed")).toBe(true);
      expect(wrap.find(".title-caret").hasClass("closed")).toBe(true);
      expect(wrap.find(".urlParamTrimHeader").attr("aria-expanded")).toBe(
        "false",
      );
    });

    it("keeps the live region a sibling of the body, not a descendant", () => {
      const wrap = mount();
      const announcer = wrap.find(".urlParamTrimAnnouncer");
      expect(announcer.parent().is(wrap)).toBe(true);
      expect(wrap.find(".urlParamTrimBody .urlParamTrimAnnouncer").length).toBe(
        0,
      );
      expect(announcer.attr("aria-live")).toBe("polite");
    });

    it("gives the header no aria-label so its visible text is its name", () => {
      const wrap = mount();
      expect(wrap.find(".urlParamTrimHeader").attr("aria-label")).toBe(
        undefined,
      );
    });
  });

  describe("visibility", () => {
    it("stays hidden for a URL without a query", () => {
      const wrap = mount();
      flush(wrap, "https://a.com/p");
      expect(wrap.hasClass("hidden")).toBe(true);
    });

    it("shows once the URL carries a query", () => {
      const wrap = mount();
      flush(wrap, URL_WITH_AUTO);
      expect(wrap.hasClass("hidden")).toBe(false);
    });

    it("hides again when the query is removed", () => {
      const wrap = mount();
      flush(wrap, URL_WITH_AUTO);
      flush(wrap, "https://a.com/p");
      expect(wrap.hasClass("hidden")).toBe(true);
    });
  });

  describe("disclosure header", () => {
    it("flips caret, wrap and aria-expanded together in both directions", () => {
      const wrap = mount();
      flush(wrap, URL_WITH_AUTO);
      const header = wrap.find(".urlParamTrimHeader");
      const caret = wrap.find(".title-caret");

      header.trigger("click");
      expect(wrap.hasClass("collapsed")).toBe(false);
      expect(caret.hasClass("closed")).toBe(false);
      expect(header.attr("aria-expanded")).toBe("true");

      header.trigger("click");
      expect(wrap.hasClass("collapsed")).toBe(true);
      expect(caret.hasClass("closed")).toBe(true);
      expect(header.attr("aria-expanded")).toBe("false");
    });

    it("points aria-controls at the body id", () => {
      const wrap = mount();
      const bodyId = wrap.find(".urlParamTrimBody").attr("id");
      expect(bodyId).toBeTruthy();
      expect(wrap.find(".urlParamTrimHeader").attr("aria-controls")).toBe(
        bodyId,
      );
    });

    it("uses a unique body id per URL card in URL mode", () => {
      const firstCard = window.jQuery('<div utuburlid="11"></div>');
      const secondCard = window.jQuery('<div utuburlid="12"></div>');
      const first = mount({ mode: TrimMode.URL, urlCard: firstCard });
      const second = mount({ mode: TrimMode.URL, urlCard: secondCard });
      const firstId = first.find(".urlParamTrimBody").attr("id");
      const secondId = second.find(".urlParamTrimBody").attr("id");
      expect(firstId).toBe("urlParamTrimBody-11");
      expect(secondId).toBe("urlParamTrimBody-12");
      expect(first.find(".urlParamTrimHeader").attr("aria-controls")).toBe(
        firstId,
      );
    });

    it("renders the dropped count in the header while collapsed", () => {
      const wrap = mount();
      flush(wrap, URL_WITH_AUTO);
      chipButtons(wrap).first().trigger("click");
      expect(wrap.hasClass("collapsed")).toBe(true);
      const count = wrap.find(".urlParamTrimDroppedCount");
      expect(count.hasClass("hidden")).toBe(false);
      expect(count.text()).toBe("1 dropped");
    });

    it("hides the dropped count when nothing is dropped", () => {
      const wrap = mount();
      flush(wrap, URL_WITH_AUTO);
      expect(wrap.find(".urlParamTrimDroppedCount").hasClass("hidden")).toBe(
        true,
      );
    });

    it("re-parses without re-collapsing an expanded section", () => {
      const wrap = mount();
      flush(wrap, URL_WITH_AUTO);
      wrap.find(".urlParamTrimHeader").trigger("click");

      flush(wrap, "https://a.com/p?other=2&more=3");
      expect(wrap.hasClass("collapsed")).toBe(false);
      expect(wrap.find(".urlParamTrimHeader").attr("aria-expanded")).toBe(
        "true",
      );

      sync(wrap, "https://a.com/p?third=4&fourth=5");
      vi.advanceTimersByTime(200);
      expect(wrap.hasClass("collapsed")).toBe(false);
      expect(wrap.find(".urlParamTrimHeader").attr("aria-expanded")).toBe(
        "true",
      );
    });
  });

  describe("chips", () => {
    it("renders one chip per occurrence of a repeated key", () => {
      const wrap = mount();
      flush(wrap, "https://a.com/p?q=1&q=2");
      expect(chipButtons(wrap).length).toBe(2);
      expect(wrap.find(".urlParamTrimTitle").text()).toBe(
        "Query parameters (2)",
      );
    });

    it("renders auto chips as inert spans, excluded from both counts", () => {
      const wrap = mount();
      flush(wrap, URL_WITH_AUTO);
      const autoChip = wrap.find('.urlParamTrimChip[data-auto="true"]');
      expect(autoChip.length).toBe(1);
      expect(autoChip.is("span")).toBe(true);
      expect(autoChip.hasClass("tabbable")).toBe(false);
      expect(autoChip.attr("aria-pressed")).toBe(undefined);
      expect(autoChip.attr("aria-label")).toBe(
        "Parameter utm_source=x is removed automatically",
      );
      expect(chipButtons(wrap).length).toBe(2);
      expect(wrap.find(".urlParamTrimTitle").text()).toBe(
        "Query parameters (2)",
      );
      expect(wrap.find(".urlParamTrimCount").text()).toBe("2 of 2 kept");
    });

    it("renders param text through .text(), never as markup", () => {
      const wrap = mount();
      flush(wrap, "https://a.com/p?x=<b>hi</b>&y=2");
      expect(wrap.find(".urlParamTrimChips b").length).toBe(0);
      expect(chipButtons(wrap).first().text()).toContain("x=<b>hi</b>");
    });

    it("toggles aria-pressed and updates the preview", () => {
      const wrap = mount();
      flush(wrap, URL_WITH_AUTO);
      const preview = wrap.find(".urlParamTrimPreviewValue");
      expect(preview.text()).toBe("https://a.com/p?ref=1&size=L");

      chipButtons(wrap).first().trigger("click");
      expect(chipButtons(wrap).first().attr("aria-pressed")).toBe("false");
      expect(preview.text()).toBe("https://a.com/p?size=L");
      expect(wrap.find(".urlParamTrimCount").text()).toBe("1 of 2 kept");

      chipButtons(wrap).first().trigger("click");
      expect(chipButtons(wrap).first().attr("aria-pressed")).toBe("true");
      expect(preview.text()).toBe("https://a.com/p?ref=1&size=L");
    });

    it("keeps focus on the toggled chip after the re-render", () => {
      const wrap = mount();
      flush(wrap, URL_WITH_AUTO);
      chipButtons(wrap).first().trigger("focus");
      chipButtons(wrap).first().trigger("click");
      expect(document.activeElement).toBe(chipButtons(wrap).first()[0]);
    });

    it("notifies onDroppedChange on toggle", () => {
      const onDroppedChange = vi.fn();
      const wrap = mount({ onDroppedChange });
      flush(wrap, URL_WITH_AUTO);
      chipButtons(wrap).first().trigger("click");
      expect(onDroppedChange).toHaveBeenCalledTimes(1);
    });
  });

  describe("keyboard", () => {
    it.each([[" "], ["Enter"]])(
      "toggles on %j with preventDefault and stopPropagation",
      (key) => {
        const wrap = mount();
        flush(wrap, URL_WITH_AUTO);
        const event = keydown(chipButtons(wrap).first(), key);
        expect(event.isDefaultPrevented()).toBe(true);
        expect(event.isPropagationStopped()).toBe(true);
        expect(chipButtons(wrap).first().attr("aria-pressed")).toBe("false");
      },
    );

    it("swallows the Space keyup so no second toggle can fire", () => {
      const wrap = mount();
      flush(wrap, URL_WITH_AUTO);
      const event = window.jQuery.Event("keyup", { key: " " });
      chipButtons(wrap).first().trigger(event);
      expect(event.isDefaultPrevented()).toBe(true);
      expect(event.isPropagationStopped()).toBe(true);
      expect(chipButtons(wrap).first().attr("aria-pressed")).toBe("true");
    });

    it.each([["Escape"], ["ArrowDown"], ["ArrowUp"]])(
      "leaves %s unbound so it reaches the form",
      (key) => {
        const wrap = mount();
        flush(wrap, URL_WITH_AUTO);
        const event = keydown(chipButtons(wrap).first(), key);
        expect(event.isDefaultPrevented()).toBe(false);
        expect(event.isPropagationStopped()).toBe(false);
        expect(chipButtons(wrap).first().attr("aria-pressed")).toBe("true");
      },
    );
  });

  describe("bulk shortcuts", () => {
    it("drops and keeps every actionable segment", () => {
      const wrap = mount();
      flush(wrap, URL_WITH_AUTO);
      const [dropAll, keepAll] = wrap.find(".urlParamTrimBtn").toArray();

      window.jQuery(dropAll).trigger("click");
      // The auto-stripped param is never user-droppable, so it stays submitted.
      expect(getTrimmed(wrap)).toBe("https://a.com/p?utm_source=x");
      expect(wrap.find(".urlParamTrimPreviewValue").text()).toBe(
        "https://a.com/p",
      );
      expect(wrap.find(".urlParamTrimCount").text()).toBe("0 of 2 kept");

      window.jQuery(keepAll).trigger("click");
      expect(getTrimmed(wrap)).toBe(URL_WITH_AUTO);
      expect(wrap.find(".urlParamTrimCount").text()).toBe("2 of 2 kept");
    });

    it("are suppressed when only one segment is actionable", () => {
      const wrap = mount();
      flush(wrap, "https://a.com/p?ref=1&utm_source=x");
      expect(wrap.find(".urlParamTrimTitle").text()).toBe(
        APP_CONFIG.strings.URL_TRIM_PARAMS_LABEL_ONE,
      );
      expect(wrap.find(".urlParamTrimBtn").length).toBe(2);
      wrap.find(".urlParamTrimBtn").each((_, button) => {
        expect(window.jQuery(button).hasClass("hidden")).toBe(true);
      });
      expect(wrap.find(".urlParamTrimMsg").text()).toContain(
        APP_CONFIG.strings.URL_TRIM_WARNING_ONE,
      );
    });
  });

  describe("announcements", () => {
    it("announces a single toggle with URL_TRIM_ANNOUNCE", () => {
      const wrap = mount();
      flush(wrap, URL_WITH_AUTO);
      chipButtons(wrap).first().trigger("click");
      expect(announcerText(wrap)).toBe(
        "Dropped ref=1. 1 of 2 parameters kept.",
      );
      chipButtons(wrap).first().trigger("click");
      expect(announcerText(wrap)).toBe("Kept ref=1. 2 of 2 parameters kept.");
    });

    it("keeps placeholder-like text in a param literal", () => {
      const wrap = mount();
      flush(wrap, "https://a.com/p?a={kept}&b=2");
      chipButtons(wrap).first().trigger("click");
      expect(announcerText(wrap)).toBe(
        "Dropped a={kept}. 1 of 2 parameters kept.",
      );
    });

    it("announces Drop all and Keep all with URL_TRIM_BULK_ANNOUNCE", () => {
      const wrap = mount();
      flush(wrap, URL_WITH_AUTO);
      const [dropAll, keepAll] = wrap.find(".urlParamTrimBtn").toArray();

      window.jQuery(dropAll).trigger("click");
      expect(announcerText(wrap)).toBe("0 of 2 parameters kept.");
      window.jQuery(keepAll).trigger("click");
      expect(announcerText(wrap)).toBe("2 of 2 parameters kept.");
    });

    it("does not announce on a plain re-parse", () => {
      const wrap = mount();
      flush(wrap, URL_WITH_AUTO);
      flush(wrap, "https://a.com/p?other=2");
      expect(announcerText(wrap)).toBe("");
    });

    it("announces the reset on the debounced path too", () => {
      const wrap = mount();
      flush(wrap, URL_WITH_AUTO);
      chipButtons(wrap).first().trigger("click");
      sync(wrap, "https://a.com/p?ref=1&size=L&extra=3");
      vi.advanceTimersByTime(200);
      expect(announcerText(wrap)).toBe(APP_CONFIG.strings.URL_TRIM_DROPS_RESET);
    });

    it("announces the reset when dropped params meet an unparseable URL", () => {
      const wrap = mount();
      flush(wrap, URL_WITH_AUTO);
      chipButtons(wrap).first().trigger("click");
      flush(wrap, UNPARSEABLE);
      expect(announcerText(wrap)).toBe(APP_CONFIG.strings.URL_TRIM_DROPS_RESET);
      expect(getTrimmed(wrap)).toBe(UNPARSEABLE);
      expect(getSubmission(wrap).droppedCount).toBe(0);
      expect(wrap.hasClass("hidden")).toBe(true);
    });

    it("announces the reset exactly once on a dropped >0 to 0 re-parse", () => {
      const wrap = mount();
      flush(wrap, URL_WITH_AUTO);
      chipButtons(wrap).first().trigger("click");

      flush(wrap, "https://a.com/p?ref=1&size=L&extra=3");
      expect(announcerText(wrap)).toBe(APP_CONFIG.strings.URL_TRIM_DROPS_RESET);

      wrap.find(".urlParamTrimAnnouncer").text("");
      flush(wrap, "https://a.com/p?ref=1&size=L&extra=4");
      expect(announcerText(wrap)).toBe("");
    });
  });

  describe("TRIM_GET_KEY", () => {
    it("returns the original byte-for-byte when nothing is dropped", () => {
      const wrap = mount();
      const original =
        "https://a.com/p?q=hello%20world&next=https://b.com/x#frag";
      flush(wrap, original);
      expect(getTrimmed(wrap)).toBe(original);
    });

    it("returns the trimmed URL once segments are dropped", () => {
      const wrap = mount();
      flush(wrap, URL_WITH_AUTO);
      chipButtons(wrap).first().trigger("click");
      expect(getTrimmed(wrap)).toBe("https://a.com/p?utm_source=x&size=L");
    });

    it("returns an unparseable raw value completely unchanged", () => {
      const wrap = mount();
      flush(wrap, UNPARSEABLE);
      expect(getTrimmed(wrap)).toBe(UNPARSEABLE);
      expect(wrap.hasClass("hidden")).toBe(true);

      sync(wrap, "http://also bad.com/?a=1");
      vi.advanceTimersByTime(200);
      expect(getTrimmed(wrap)).toBe("http://also bad.com/?a=1");
    });
  });

  describe("TRIM_SUBMISSION_KEY", () => {
    it("reports nothing dropped by default", () => {
      const wrap = mount();
      flush(wrap, URL_WITH_AUTO);
      expect(getSubmission(wrap)).toEqual({
        originalUrlString: URL_WITH_AUTO,
        droppedSegments: [],
        droppedCount: 0,
      });
    });

    it("lists dropped segments in original order", () => {
      const wrap = mount();
      flush(wrap, "https://a.com/p?a=1&b=2&c=3");
      chipButtons(wrap).eq(2).trigger("click");
      chipButtons(wrap).eq(0).trigger("click");
      expect(getSubmission(wrap)).toEqual({
        originalUrlString: "https://a.com/p?a=1&b=2&c=3",
        droppedSegments: ["a=1", "c=3"],
        droppedCount: 2,
      });
    });

    it("keeps dropped segments when re-synced with an unchanged value", () => {
      const wrap = mount();
      flush(wrap, "https://a.com/p?a=1&b=2");
      chipButtons(wrap).eq(0).trigger("click");

      flush(wrap, "https://a.com/p?a=1&b=2");

      expect(getSubmission(wrap).droppedCount).toBe(1);
      expect(announcerText(wrap)).not.toBe(
        APP_CONFIG.strings.URL_TRIM_DROPS_RESET,
      );
    });

    it("resets droppedCount to 0 on a re-parse", () => {
      const wrap = mount();
      flush(wrap, "https://a.com/p?a=1&b=2");
      chipButtons(wrap).eq(0).trigger("click");
      expect(getSubmission(wrap).droppedCount).toBe(1);

      sync(wrap, "https://a.com/p?a=1&b=2&c=3");
      vi.advanceTimersByTime(200);
      expect(getSubmission(wrap).droppedCount).toBe(0);
    });
  });

  describe("debounce", () => {
    it("applies TRIM_SYNC_KEY only after 200ms", () => {
      const wrap = mount();
      sync(wrap, URL_WITH_AUTO);
      vi.advanceTimersByTime(199);
      expect(wrap.hasClass("hidden")).toBe(true);
      vi.advanceTimersByTime(1);
      expect(wrap.hasClass("hidden")).toBe(false);
    });

    it("coalesces rapid syncs to the latest value", () => {
      const wrap = mount();
      sync(wrap, "https://a.com/p?first=1");
      vi.advanceTimersByTime(100);
      sync(wrap, "https://a.com/p?second=2");
      vi.advanceTimersByTime(200);
      expect(getTrimmed(wrap)).toBe("https://a.com/p?second=2");
    });

    it("applies TRIM_FLUSH_KEY synchronously and cancels a pending sync", () => {
      const wrap = mount();
      sync(wrap, "https://a.com/p?stale=1");
      flush(wrap, "https://a.com/p?fresh=2");
      expect(getTrimmed(wrap)).toBe("https://a.com/p?fresh=2");

      vi.advanceTimersByTime(200);
      expect(getTrimmed(wrap)).toBe("https://a.com/p?fresh=2");
      expect(chipButtons(wrap).length).toBe(1);
    });
  });

  describe("TRIM_RESET_KEY", () => {
    it("clears state, hides the block and re-collapses all three parts", () => {
      const wrap = mount();
      flush(wrap, URL_WITH_AUTO);
      wrap.find(".urlParamTrimHeader").trigger("click");
      chipButtons(wrap).first().trigger("click");

      reset(wrap);
      expect(getTrimmed(wrap)).toBe("");
      expect(getSubmission(wrap).droppedCount).toBe(0);
      expect(wrap.hasClass("hidden")).toBe(true);
      expect(wrap.hasClass("collapsed")).toBe(true);
      expect(wrap.find(".title-caret").hasClass("closed")).toBe(true);
      expect(wrap.find(".urlParamTrimHeader").attr("aria-expanded")).toBe(
        "false",
      );
    });

    it("cancels a pending debounce so nothing fires after teardown", () => {
      const wrap = mount();
      sync(wrap, URL_WITH_AUTO);
      reset(wrap);
      vi.advanceTimersByTime(500);
      expect(getTrimmed(wrap)).toBe("");
      expect(wrap.hasClass("hidden")).toBe(true);
    });
  });
});
