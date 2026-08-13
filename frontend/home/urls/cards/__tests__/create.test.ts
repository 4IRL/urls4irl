import { createMockJqXHRChainable } from "../../../../__tests__/helpers/mock-jquery.js";
import { ajaxCall } from "../../../../lib/ajax.js";
import { showURLsEmptyState, hideURLsEmptyState } from "../../empty-state.js";
import { showURLSearchIcon } from "../../search.js";
import { STAGED_GET_KEY } from "../../tags/combobox.js";
import { renderAppliedTagsForUrl } from "../../tags/tag-render.js";
import { getNumOfURLs } from "../../utils.js";
import { getState } from "../../../../store/app-store.js";
import { createURLBlock } from "../cards.js";
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

      createURL(urlTitleInput, urlStringInput, 1);

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

      createURL(urlTitleInput, urlStringInput, 99);

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

      createURL(urlTitleInput, urlStringInput, 1);

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

      createURL(urlTitleInput, urlStringInput, 1);

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

      createURL(urlTitleInput, urlStringInput, 1);

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

      createURL($("#urlTitleCreate"), $("#urlStringCreate"), 1);

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

      createURL(urlTitleInput, urlStringInput, 1);

      const msg = $("#createURLWrap .urlTagComboboxMsg");
      expect(msg.text()).toBe("Tag is too long");
      expect(msg.hasClass("warn")).toBe(true);
    });
  });
});
