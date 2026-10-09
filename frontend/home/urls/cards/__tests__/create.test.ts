import { createMockJqXHRChainable } from "../../../../__tests__/helpers/mock-jquery.js";
import { ajaxCall } from "../../../../lib/ajax.js";
import { APP_CONFIG } from "../../../../lib/config.js";
import { showURLsEmptyState, hideURLsEmptyState } from "../../empty-state.js";
import { showURLSearchIcon } from "../../search.js";
import { STAGED_GET_KEY } from "../../tags/combobox.js";
import { renderAppliedTagsForUrl } from "../../tags/tag-render.js";
import { getNumOfURLs } from "../../utils.js";
import { getState } from "../../../../store/app-store.js";
import { createURLBlock } from "../cards.js";
import { selectURLCard } from "../selection.js";
import {
  clearURLOutcomeBanner,
  showTrimSavedBanner,
} from "../../outcome-banner.js";
import { checkForStaleDataOn409 } from "../conflict-handler.js";
import {
  createURL,
  createURLHideInput,
  createURLShowInput,
  resetCreateURLFailErrors,
} from "../create.js";
import { applyDefaultUrlSort } from "../filtering.js";
import { triggerURLSwipeNudgeIfEligible } from "../swipe.js";

vi.mock("../../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));

// Partial mock: keep the real AppEvents enum (and any other exports) but spy
// `emit` so the URL_DECK_CHANGED notification fired on a successful create can be
// asserted without a real bus subscriber.
vi.mock("../../../../lib/event-bus.js", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("../../../../lib/event-bus.js")>();
  return {
    ...actual,
    emit: vi.fn(),
  };
});

vi.mock("../cards.js", () => ({
  createURLBlock: vi.fn(() => window.jQuery('<div class="urlRow"></div>')),
  newURLInputAddEventListeners: vi.fn(),
  newURLInputRemoveEventListeners: vi.fn(),
}));

vi.mock("../swipe.js", () => ({
  triggerURLSwipeNudgeIfEligible: vi.fn(),
}));

vi.mock("../selection.js", () => ({
  selectURLCard: vi.fn(),
}));

vi.mock("../../utils.js", () => ({
  getNumOfURLs: vi.fn(() => 0),
  getNumOfVisibleURLs: vi.fn(() => 0),
}));

vi.mock("../conflict-handler.js", () => ({
  checkForStaleDataOn409: vi.fn(),
}));

vi.mock("../../outcome-banner.js", () => ({
  showTrimSavedBanner: vi.fn(),
  clearURLOutcomeBanner: vi.fn(),
}));

vi.mock("../../../tags/utils.js", () => ({
  isATagSelected: vi.fn(() => false),
}));

vi.mock("../../search.js", () => ({
  closeURLSearchAndEraseInput: vi.fn(),
  temporarilyHideSearchForEdit: vi.fn(),
  showURLSearchIcon: vi.fn(),
}));

vi.mock("../../empty-state.js", () => ({
  showURLsEmptyState: vi.fn(),
  hideURLsEmptyState: vi.fn(),
}));

vi.mock("../utils.js", () => ({
  isEmptyString: vi.fn((val: string) => val.trim() === ""),
  updateColorOfFollowingURLCardsAfterURLCreated: vi.fn(),
}));

vi.mock("../../../../store/app-store.js", () => ({
  getState: vi.fn(() => ({
    urls: [],
    preferences: {
      theme: "system",
      defaultView: "list",
      defaultSort: "newest",
      density: "comfortable",
      dateFormat: "iso",
    },
  })),
  setState: vi.fn(),
}));

vi.mock("../../tags/combobox.js", () => ({
  ComboboxMode: { URL: "url", CREATE: "create" },
  createTagComboboxBlock: vi.fn(() =>
    window.jQuery('<div class="urlTagComboboxWrap"></div>'),
  ),
  STAGED_GET_KEY: "urlTagComboboxGetStaged",
  STAGED_RESET_KEY: "urlTagComboboxResetStaged",
}));

vi.mock("../../tags/tag-render.js", () => ({
  renderAppliedTagsForUrl: vi.fn(),
}));

vi.mock("../filtering.js", () => ({
  updateURLsAndTagSubheaderWhenTagSelected: vi.fn(),
  applyDefaultUrlSort: vi.fn((urls: unknown[]) => urls),
  reapplyAlternatingURLCardBackgroundAfterFilter: vi.fn(),
}));

const $ = window.jQuery;

const CREATE_URL_FORM_HTML = `
  <div id="createURLWrap"></div>
  <input id="urlStringCreate" />
  <input id="urlTitleCreate" />
  <div id="urlStringCreate-error"></div>
  <div id="urlTitleCreate-error"></div>
  <button id="urlBtnCreate"></button>
  <button id="urlBtnMultiSelect" class="visible"></button>
  <div id="noURLsEmptyState" class="hidden">
    <p id="noURLsSubheader"></p>
    <div id="urlBtnDeckCreateWrap"></div>
  </div>
  <div id="urlCreateDualLoadingRing"></div>
`;

describe("createURL - client-side validation", () => {
  let urlStringInput: JQuery, urlTitleInput: JQuery;

  beforeEach(() => {
    document.body.innerHTML = CREATE_URL_FORM_HTML;
    urlStringInput = $("#urlStringCreate");
    urlTitleInput = $("#urlTitleCreate");
    vi.clearAllMocks();
  });

  describe("invalid URL schemes are blocked before AJAX", () => {
    it.each([
      ["javascript:alert(1)"],
      ["data:text/html,<h1>x</h1>"],
      ["vbscript:msgbox('x')"],
    ])("blocks '%s' and shows error without calling ajaxCall", (invalidUrl) => {
      urlStringInput.val(invalidUrl);
      urlTitleInput.val("My Title");

      createURL({
        createURLTitleInput: urlTitleInput,
        createURLInput: urlStringInput,
        utubID: 1,
      });

      expect($("#urlStringCreate-error").hasClass("visible")).toBe(true);
      expect($("#urlStringCreate-error").text()).toBeTruthy();
      expect($("#urlStringCreate").hasClass("invalid-field")).toBe(true);
      expect(ajaxCall).not.toHaveBeenCalled();
    });
  });

  describe("resetCreateURLFailErrors", () => {
    it("removes invalid-field and visible from both URL fields", () => {
      $("#urlStringCreate").addClass("invalid-field");
      $("#urlStringCreate-error").addClass("visible").text("bad URL");
      $("#urlTitleCreate").addClass("invalid-field");
      $("#urlTitleCreate-error").addClass("visible").text("bad title");

      resetCreateURLFailErrors();

      expect($("#urlStringCreate").hasClass("invalid-field")).toBe(false);
      expect($("#urlStringCreate-error").hasClass("visible")).toBe(false);
      expect($("#urlTitleCreate").hasClass("invalid-field")).toBe(false);
      expect($("#urlTitleCreate-error").hasClass("visible")).toBe(false);
    });

    it("is a no-op when no errors are present", () => {
      resetCreateURLFailErrors();

      expect($("#urlStringCreate").hasClass("invalid-field")).toBe(false);
      expect($("#urlStringCreate-error").hasClass("visible")).toBe(false);
    });

    it("clears the inline combobox message text and warn class", () => {
      $("#createURLWrap").html(
        '<div class="urlTagComboboxWrap"><div class="urlTagComboboxMsg warn">stale tag error</div></div>',
      );
      const comboboxMsg = $(
        "#createURLWrap .urlTagComboboxWrap .urlTagComboboxMsg",
      );

      resetCreateURLFailErrors();

      expect(comboboxMsg.text()).toBe("");
      expect(comboboxMsg.hasClass("warn")).toBe(false);
    });
  });

  describe("createURLHideInput — empty-state branches", () => {
    it("calls showURLsEmptyState when no URLs exist", () => {
      vi.mocked(getNumOfURLs).mockReturnValue(0);

      createURLHideInput();

      expect(showURLsEmptyState).toHaveBeenCalled();
      expect(showURLSearchIcon).not.toHaveBeenCalled();
    });

    it("calls showURLSearchIcon and does not show empty state when URLs exist", () => {
      vi.mocked(getNumOfURLs).mockReturnValue(3);

      createURLHideInput();

      expect(showURLsEmptyState).not.toHaveBeenCalled();
      expect(showURLSearchIcon).toHaveBeenCalled();
    });
  });

  describe("createURLShowInput — empty-state branch", () => {
    it("calls hideURLsEmptyState when no URLs exist", () => {
      vi.mocked(getNumOfURLs).mockReturnValue(0);

      createURLShowInput(1);

      expect(hideURLsEmptyState).toHaveBeenCalled();
    });
  });

  describe("#urlBtnMultiSelect toggle gating around the create-URL form", () => {
    it("hides the multi-select toggle when the create form opens", () => {
      // A form can only be opened from single-select, where a non-empty UTub
      // shows the toggle.
      vi.mocked(getNumOfURLs).mockReturnValue(3);
      $("#urlBtnMultiSelect").showClassNormal();

      createURLShowInput(1);

      expect($("#urlBtnMultiSelect").hasClass("hidden")).toBe(true);
      expect($("#urlBtnMultiSelect").hasClass("visible")).toBe(false);
    });

    it("restores the toggle on close when the UTub still has URLs", () => {
      vi.mocked(getNumOfURLs).mockReturnValue(3);
      $("#urlBtnMultiSelect").hideClass();

      createURLHideInput();

      expect($("#urlBtnMultiSelect").hasClass("hidden")).toBe(false);
      expect($("#urlBtnMultiSelect").hasClass("visible")).toBe(true);
    });

    it("keeps the toggle hidden on close when the UTub has no URLs", () => {
      vi.mocked(getNumOfURLs).mockReturnValue(0);
      $("#urlBtnMultiSelect").hideClass();

      createURLHideInput();

      expect($("#urlBtnMultiSelect").hasClass("hidden")).toBe(true);
      expect($("#urlBtnMultiSelect").hasClass("visible")).toBe(false);
    });
  });

  describe("createURL - 409 conflict delegates to checkForStaleDataOn409", () => {
    it("calls checkForStaleDataOn409 with utubID when ajaxCall fails with status 409", () => {
      urlStringInput.val("https://duplicate.example.com");
      urlTitleInput.val("Some Title");

      const responseJSON = {
        status: "Failure",
        message: "URL already in UTub",
        errorCode: null,
        errors: null,
        details: null,
        urlString: "https://duplicate.example.com",
      };
      const xhr = {
        status: 409,
        responseJSON,
      } as unknown as JQuery.jqXHR;

      const chainable = createMockJqXHRChainable({
        fail: (callback: unknown) =>
          (callback as (xhrArg: JQuery.jqXHR) => void)(xhr),
      });
      vi.mocked(ajaxCall).mockReturnValue(chainable);

      createURL({
        createURLTitleInput: urlTitleInput,
        createURLInput: urlStringInput,
        utubID: 99,
      });

      expect(checkForStaleDataOn409).toHaveBeenCalledTimes(1);
      expect(checkForStaleDataOn409).toHaveBeenCalledWith(responseJSON, 99);
    });
  });

  describe("createURL - staged tags folded into request", () => {
    it("includes tagStrings from the combobox getter in the POST body", () => {
      $("#createURLWrap").append('<div class="urlTagComboboxWrap"></div>');
      const wrap = $("#createURLWrap").find(".urlTagComboboxWrap");
      wrap.data(STAGED_GET_KEY, () => ["python", "web"]);
      urlStringInput.val("https://example.com");
      urlTitleInput.val("Example");

      const chainable = createMockJqXHRChainable();
      vi.mocked(ajaxCall).mockReturnValue(chainable);

      createURL({
        createURLTitleInput: urlTitleInput,
        createURLInput: urlStringInput,
        utubID: 1,
      });

      expect(ajaxCall).toHaveBeenCalledTimes(1);
      const postData = vi.mocked(ajaxCall).mock.calls[0][2] as {
        urlString: string;
        urlTitle: string;
        tagStrings: string[];
      };
      expect(postData.tagStrings).toEqual(["python", "web"]);
    });

    it("defaults tagStrings to [] when no combobox is mounted", () => {
      urlStringInput.val("https://example.com");
      urlTitleInput.val("Example");

      const chainable = createMockJqXHRChainable();
      vi.mocked(ajaxCall).mockReturnValue(chainable);

      createURL({
        createURLTitleInput: urlTitleInput,
        createURLInput: urlStringInput,
        utubID: 1,
      });

      const postData = vi.mocked(ajaxCall).mock.calls[0][2] as {
        tagStrings: string[];
      };
      expect(postData.tagStrings).toEqual([]);
    });
  });

  describe("createURLSuccess - renders applied tags", () => {
    it("merges the new URL into the store and delegates tag rendering on 200", () => {
      urlStringInput.val("https://example.com");
      urlTitleInput.val("Example");

      const response = {
        utubID: 1,
        addedByUserID: 1,
        URL: {
          utubUrlID: 42,
          urlString: "https://example.com",
          urlTitle: "Example",
          utubUrlTagIDs: [5, 6],
        },
        appliedTags: [
          { id: 5, tagString: "python", tagApplied: 1 },
          { id: 6, tagString: "web", tagApplied: 1 },
        ],
      };
      const xhr = { status: 200 } as JQuery.jqXHR;

      const chainable = createMockJqXHRChainable({
        done: (callback: unknown) =>
          (callback as (r: unknown, t: unknown, x: unknown) => void)(
            response,
            "success",
            xhr,
          ),
      });
      vi.mocked(ajaxCall).mockReturnValue(chainable);

      createURL({
        createURLTitleInput: urlTitleInput,
        createURLInput: urlStringInput,
        utubID: 1,
      });

      expect(renderAppliedTagsForUrl).toHaveBeenCalledTimes(1);
      const renderArgs = vi.mocked(renderAppliedTagsForUrl).mock.calls[0][0];
      expect(renderArgs.appliedTags).toEqual(response.appliedTags);
      expect(renderArgs.utubUrlTagIDs).toEqual([5, 6]);
      expect(renderArgs.utubID).toBe(1);

      // The server's TOP-LEVEL addedByUserID must reach the constructed URL
      // object handed to createURLBlock (it drives the "Added by <user>"
      // attribution badge). Guards against a regression that reads the
      // nonexistent response.URL.addedByUserID instead of response.addedByUserID.
      expect(vi.mocked(createURLBlock).mock.calls[0][0]).toEqual(
        expect.objectContaining({ addedByUserID: response.addedByUserID }),
      );

      expect(vi.mocked(triggerURLSwipeNudgeIfEligible)).toHaveBeenCalledTimes(
        1,
      );
      const createdRow = vi.mocked(createURLBlock).mock.results[0]
        .value as JQuery;
      expect(vi.mocked(triggerURLSwipeNudgeIfEligible)).toHaveBeenCalledWith({
        urlRow: createdRow,
      });
    });
  });

  describe("createURLSuccess - notifies the onboarding nudge system", () => {
    it("emits AppEvents.URL_DECK_CHANGED after a successful create", async () => {
      const { emit, AppEvents } = await import("../../../../lib/event-bus.js");
      urlStringInput.val("https://example.com");
      urlTitleInput.val("Example");

      const response = {
        utubID: 1,
        addedByUserID: 1,
        URL: {
          utubUrlID: 42,
          urlString: "https://example.com",
          urlTitle: "Example",
          utubUrlTagIDs: [],
        },
        appliedTags: [],
      };
      const xhr = { status: 200 } as JQuery.jqXHR;
      const chainable = createMockJqXHRChainable({
        done: (callback: unknown) =>
          (callback as (r: unknown, t: unknown, x: unknown) => void)(
            response,
            "success",
            xhr,
          ),
      });
      vi.mocked(ajaxCall).mockReturnValue(chainable);

      createURL({
        createURLTitleInput: urlTitleInput,
        createURLInput: urlStringInput,
        utubID: 1,
      });

      expect(emit).toHaveBeenCalledWith(AppEvents.URL_DECK_CHANGED);
    });
  });

  describe("createURLSuccess - create-time re-sort, scroll, and highlight", () => {
    beforeEach(() => {
      vi.useFakeTimers();
      document.body.innerHTML = `
        <div id="listURLs">
          <div id="createURLWrap"></div>
          <div class="urlRow" utuburlid="10"></div>
          <div class="urlRow" utuburlid="11"></div>
        </div>
        <input id="urlStringCreate" />
        <input id="urlTitleCreate" />
        <button id="urlBtnCreate"></button>
        <div id="urlCreateDualLoadingRing"></div>
        <span id="fieldSavedAnnouncement"></span>
      `;
      vi.mocked(getState).mockReturnValue({
        urls: [{ utubUrlID: 10 }, { utubUrlID: 11 }, { utubUrlID: 42 }],
        preferences: {
          theme: "system",
          defaultView: "list",
          defaultSort: "oldest",
          density: "comfortable",
          dateFormat: "iso",
        },
      } as unknown as ReturnType<typeof getState>);
      // A non-append order that places the new card (42) last, forcing a move
      // away from its top-of-list insertion point.
      vi.mocked(applyDefaultUrlSort).mockReturnValue([
        { utubUrlID: 10 },
        { utubUrlID: 11 },
        { utubUrlID: 42 },
      ] as unknown as ReturnType<typeof applyDefaultUrlSort>);
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it("re-sorts the new card to its sorted DOM position, scrolls it into view, and flashes a transient highlight", () => {
      const newCard = $('<div class="urlRow" utuburlid="42"></div>');
      const scrollSpy = vi.fn();
      (newCard[0] as HTMLElement).scrollIntoView = scrollSpy;
      vi.mocked(createURLBlock).mockReturnValue(newCard);

      $("#urlStringCreate").val("https://example.com");
      $("#urlTitleCreate").val("Example");

      const response = {
        utubID: 1,
        addedByUserID: 1,
        URL: {
          utubUrlID: 42,
          urlString: "https://example.com",
          urlTitle: "Example",
          utubUrlTagIDs: [],
          addedAt: "2024-03-09T12:00:00+00:00",
        },
        appliedTags: [],
      };
      const xhr = { status: 200 } as JQuery.jqXHR;
      const chainable = createMockJqXHRChainable({
        done: (callback: unknown) =>
          (callback as (r: unknown, t: unknown, x: unknown) => void)(
            response,
            "success",
            xhr,
          ),
      });
      vi.mocked(ajaxCall).mockReturnValue(chainable);

      createURL({
        createURLTitleInput: $("#urlTitleCreate"),
        createURLInput: $("#urlStringCreate"),
        utubID: 1,
      });

      // (1) The new card lands at its sorted DOM position (last), via the
      // detach/re-append reorder into #listURLs.
      const orderedIDs = $("#listURLs .urlRow")
        .toArray()
        .map((el) => el.getAttribute("utuburlid"));
      expect(orderedIDs).toEqual(["10", "11", "42"]);

      // (2) The moved card is scrolled into view, centered.
      expect(scrollSpy).toHaveBeenCalledTimes(1);
      expect(scrollSpy).toHaveBeenCalledWith(
        expect.objectContaining({ block: "center" }),
      );

      // Aria-live announcement fires on a non-no-op reorder.
      expect($("#fieldSavedAnnouncement").text()).toBe("URL added");

      // (3) Highlight class added synchronously, removed only after ~0.7s.
      expect(newCard.hasClass("url-card-created-highlight")).toBe(true);
      vi.advanceTimersByTime(700);
      expect(newCard.hasClass("url-card-created-highlight")).toBe(false);

      // Swipe-nudge fires last, against the final position.
      expect(triggerURLSwipeNudgeIfEligible).toHaveBeenCalledWith({
        urlRow: newCard,
      });
    });
  });

  describe("createURLFail - tagStrings error routes to combobox message", () => {
    it("writes the tagStrings error into the inline combobox message element", () => {
      $("#createURLWrap").append(
        '<div class="urlTagComboboxWrap"><div class="urlTagComboboxMsg"></div></div>',
      );
      urlStringInput.val("https://example.com");
      urlTitleInput.val("Example");

      const responseJSON = {
        status: "Failure",
        message: "Validation failed",
        errors: { tagStrings: ["Tag is too long"] },
      };
      const xhr = {
        status: 400,
        responseJSON,
      } as unknown as JQuery.jqXHR;

      const chainable = createMockJqXHRChainable({
        fail: (callback: unknown) =>
          (callback as (xhrArg: JQuery.jqXHR) => void)(xhr),
      });
      vi.mocked(ajaxCall).mockReturnValue(chainable);

      createURL({
        createURLTitleInput: urlTitleInput,
        createURLInput: urlStringInput,
        utubID: 1,
      });

      const msg = $("#createURLWrap .urlTagComboboxMsg");
      expect(msg.text()).toBe("Tag is too long");
      expect(msg.hasClass("warn")).toBe(true);
    });
  });
});

describe("createURL - query-parameter trim block", () => {
  const QUERY_URL = "https://example.com/p?a=1&b=2&c=3";
  let urlStringInput: JQuery, urlTitleInput: JQuery;

  function typeURL(value: string): void {
    urlStringInput.val(value);
    urlStringInput.trigger("input");
  }

  function trimWrap(): JQuery {
    return $("#createURLWrap").find(".urlParamTrimWrap");
  }

  function mockCreateRequest(
    handlers: Parameters<typeof createMockJqXHRChainable>[0] = {},
  ): void {
    vi.mocked(ajaxCall).mockReturnValue(createMockJqXHRChainable(handlers));
  }

  function submittedURLString(): string {
    return (vi.mocked(ajaxCall).mock.calls[0][2] as { urlString: string })
      .urlString;
  }

  function submit(): void {
    createURL({
      createURLTitleInput: urlTitleInput,
      createURLInput: urlStringInput,
      utubID: 1,
    });
  }

  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    document.body.innerHTML = `
      <div id="createURLWrap">
        <div class="flex-row"><button id="urlSubmitBtnCreate"></button></div>
      </div>
      <input id="urlStringCreate" />
      <input id="urlTitleCreate" />
      <div id="urlStringCreate-error"></div>
      <div id="urlTitleCreate-error"></div>
      <button id="urlBtnCreate"></button>
      <button id="urlBtnMultiSelect" class="visible"></button>
      <div id="urlCreateDualLoadingRing"></div>
    `;
    urlStringInput = $("#urlStringCreate");
    urlTitleInput = $("#urlTitleCreate");
    createURLShowInput(1);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("mounts the block before the action row and tag combobox", () => {
    expect(trimWrap()).toHaveLength(1);
    const order = $("#createURLWrap")
      .children()
      .toArray()
      .map((el) => el.className);
    expect(order[0]).toContain("urlParamTrimWrap");
    expect(order[1]).toContain("urlTagComboboxWrap");
    expect(order[2]).toContain("flex-row");
  });

  it("stays hidden for a query-less URL", () => {
    typeURL("https://example.com/p");
    vi.advanceTimersByTime(200);

    expect(trimWrap().hasClass("hidden")).toBe(true);
  });

  it("appears collapsed after a debounced input with a query", () => {
    typeURL(QUERY_URL);
    expect(trimWrap().hasClass("hidden")).toBe(true);

    vi.advanceTimersByTime(200);

    expect(trimWrap().hasClass("hidden")).toBe(false);
    expect(trimWrap().hasClass("collapsed")).toBe(true);
    expect(trimWrap().find(".urlParamTrimHeader").attr("aria-expanded")).toBe(
      "false",
    );
  });

  it("preserves the user's expanded choice across a re-parse", () => {
    typeURL(QUERY_URL);
    vi.advanceTimersByTime(200);
    trimWrap().find(".urlParamTrimHeader").trigger("click");
    expect(trimWrap().hasClass("collapsed")).toBe(false);

    typeURL(`${QUERY_URL}&d=4`);
    vi.advanceTimersByTime(200);

    expect(trimWrap().hasClass("collapsed")).toBe(false);
    expect(trimWrap().find(".urlParamTrimHeader").attr("aria-expanded")).toBe(
      "true",
    );
  });

  it("does not steal focus or flag the URL input when it appears", () => {
    urlStringInput.trigger("focus");
    typeURL(QUERY_URL);
    vi.advanceTimersByTime(200);

    expect(document.activeElement).toBe(urlStringInput[0]);
    expect(urlStringInput.hasClass("invalid-field")).toBe(false);
    expect($("#urlStringCreate-error").hasClass("visible")).toBe(false);
  });

  it("keeps listening after the URL input blurs and refocuses", () => {
    urlStringInput.trigger("blur");
    urlStringInput.trigger("focus");
    typeURL(QUERY_URL);
    vi.advanceTimersByTime(200);

    expect(trimWrap().hasClass("hidden")).toBe(false);
  });

  it("submits the typed value byte-for-byte when nothing is dropped", () => {
    typeURL(QUERY_URL);
    vi.advanceTimersByTime(200);
    mockCreateRequest();

    submit();

    expect(submittedURLString()).toBe(QUERY_URL);
  });

  it("submits a urlString with the dropped segments removed", () => {
    typeURL(QUERY_URL);
    vi.advanceTimersByTime(200);
    trimWrap().find(".urlParamTrimChip").eq(1).trigger("click");
    mockCreateRequest();

    submit();

    expect(submittedURLString()).toBe("https://example.com/p?a=1&c=3");
  });

  it("flushes a pending debounce so a fast submit trims the current value", () => {
    typeURL(QUERY_URL);
    vi.advanceTimersByTime(200);
    trimWrap().find(".urlParamTrimChip").eq(0).trigger("click");
    // Edit then submit before the block's 200ms debounce fires. The edit resets
    // all drops, so the stale parse (with `a` dropped) must not be used.
    typeURL("https://example.com/p?x=9&y=8");
    mockCreateRequest();

    submit();

    expect(submittedURLString()).toBe("https://example.com/p?x=9&y=8");
  });

  describe("409 conflict", () => {
    function failWith409(): void {
      const xhr = {
        status: 409,
        responseJSON: {
          status: "Failure",
          message: "URL already in UTub",
          errorCode: null,
          errors: null,
          details: null,
          urlString: "https://example.com/p?a=1",
        },
      } as unknown as JQuery.jqXHR;
      mockCreateRequest({
        fail: (callback: unknown) =>
          (callback as (xhrArg: JQuery.jqXHR) => void)(xhr),
      });
    }

    it("substitutes the trim message and expands the section when params were dropped", () => {
      typeURL(QUERY_URL);
      vi.advanceTimersByTime(200);
      trimWrap().find(".urlParamTrimChip").eq(1).trigger("click");
      failWith409();

      submit();

      expect($("#urlStringCreate-error").text()).toBe(
        APP_CONFIG.strings.URL_TRIM_CONFLICT,
      );
      expect(trimWrap().hasClass("collapsed")).toBe(false);
      expect(trimWrap().find(".title-caret").hasClass("closed")).toBe(false);
      expect(trimWrap().find(".urlParamTrimHeader").attr("aria-expanded")).toBe(
        "true",
      );
      expect(checkForStaleDataOn409).toHaveBeenCalledTimes(1);
    });

    it("keeps the server message and stays collapsed when nothing was dropped", () => {
      typeURL(QUERY_URL);
      vi.advanceTimersByTime(200);
      failWith409();

      submit();

      expect($("#urlStringCreate-error").text()).toBe("URL already in UTub");
      expect(trimWrap().hasClass("collapsed")).toBe(true);
    });

    it("keeps the server message when a drop was toggled back to zero", () => {
      typeURL(QUERY_URL);
      vi.advanceTimersByTime(200);
      trimWrap().find(".urlParamTrimChip").eq(1).trigger("click");
      trimWrap().find(".urlParamTrimChip").eq(1).trigger("click");
      failWith409();

      submit();

      expect($("#urlStringCreate-error").text()).toBe("URL already in UTub");
      expect(trimWrap().hasClass("collapsed")).toBe(true);
    });

    // A removed block yields a null trimSubmission.
    it("keeps the server message when the block is absent", () => {
      trimWrap().remove();
      urlStringInput.val(QUERY_URL);
      failWith409();

      submit();

      expect($("#urlStringCreate-error").text()).toBe("URL already in UTub");
    });
  });

  it("creates the card with the trimmed URL and removes the block on success", () => {
    typeURL(QUERY_URL);
    vi.advanceTimersByTime(200);
    trimWrap().find(".urlParamTrimChip").eq(1).trigger("click");
    const trimmed = "https://example.com/p?a=1&c=3";
    const response = {
      utubID: 1,
      addedByUserID: 1,
      URL: {
        utubUrlID: 42,
        urlString: trimmed,
        urlTitle: "T",
        utubUrlTagIDs: [],
        addedAt: "2024-03-09T12:00:00+00:00",
      },
      appliedTags: [],
    };
    mockCreateRequest({
      done: (callback: unknown) =>
        (callback as (r: unknown, t: unknown, x: unknown) => void)(
          response,
          "success",
          { status: 200 },
        ),
    });

    submit();

    expect(submittedURLString()).toBe(trimmed);
    expect(createURLBlock).toHaveBeenCalledTimes(1);
    expect(trimWrap()).toHaveLength(0);
  });

  describe("outcome banner", () => {
    function succeedWith(urlString: string): void {
      const response = {
        utubID: 1,
        addedByUserID: 1,
        URL: {
          utubUrlID: 42,
          urlString,
          urlTitle: "T",
          utubUrlTagIDs: [],
          addedAt: "2024-03-09T12:00:00+00:00",
        },
        appliedTags: [],
      };
      mockCreateRequest({
        done: (callback: unknown) =>
          (callback as (r: unknown, t: unknown, x: unknown) => void)(
            response,
            "success",
            { status: 200 },
          ),
      });
    }

    it("shows the Undo banner with the untrimmed original after a trim-and-save", () => {
      typeURL(QUERY_URL);
      vi.advanceTimersByTime(200);
      trimWrap().find(".urlParamTrimChip").eq(1).trigger("click");
      succeedWith("https://example.com/p?a=1&c=3");

      submit();

      expect(showTrimSavedBanner).toHaveBeenCalledTimes(1);
      const args = vi.mocked(showTrimSavedBanner).mock.calls[0][0];
      expect(args.trimSubmission).toEqual({
        originalUrlString: QUERY_URL,
        droppedSegments: ["b=2"],
        droppedCount: 1,
      });
      expect(args.utubID).toBe(1);
      expect(args.utubUrlID).toBe(42);
      expect(args.form).toBe("url_create");
      expect(args.urlCard[0]).toBe(
        vi.mocked(createURLBlock).mock.results[0].value[0],
      );
    });

    it("shows no banner, and the form reset clears a stale one, when nothing was dropped", () => {
      typeURL(QUERY_URL);
      vi.advanceTimersByTime(200);
      succeedWith(QUERY_URL);
      vi.mocked(clearURLOutcomeBanner).mockClear();

      submit();

      expect(showTrimSavedBanner).not.toHaveBeenCalled();
      expect(clearURLOutcomeBanner).toHaveBeenCalledTimes(1);
    });

    it("shows the banner after the reset and selection that clear it", () => {
      typeURL(QUERY_URL);
      vi.advanceTimersByTime(200);
      trimWrap().find(".urlParamTrimChip").eq(1).trigger("click");
      succeedWith("https://example.com/p?a=1&c=3");
      vi.mocked(selectURLCard).mockImplementationOnce(() =>
        clearURLOutcomeBanner(),
      );

      submit();

      const clearOrders = vi
        .mocked(clearURLOutcomeBanner)
        .mock.invocationCallOrder.slice();
      const showOrder =
        vi.mocked(showTrimSavedBanner).mock.invocationCallOrder[0];
      expect(Math.max(...clearOrders)).toBeLessThan(showOrder);
    });

    it("shows no banner when the trim block is absent", () => {
      trimWrap().remove();
      urlStringInput.val(QUERY_URL);
      succeedWith(QUERY_URL);

      submit();

      expect(showTrimSavedBanner).not.toHaveBeenCalled();
    });

    it("clears the banner when the create form is reset", () => {
      vi.mocked(clearURLOutcomeBanner).mockClear();

      createURLHideInput();

      expect(clearURLOutcomeBanner).toHaveBeenCalled();
    });
  });

  it("removes the block and its input listener when the form resets", () => {
    typeURL(QUERY_URL);
    vi.advanceTimersByTime(200);

    createURLHideInput();

    expect(trimWrap()).toHaveLength(0);
    typeURL(QUERY_URL);
    vi.advanceTimersByTime(200);
    expect(trimWrap()).toHaveLength(0);
  });
});
