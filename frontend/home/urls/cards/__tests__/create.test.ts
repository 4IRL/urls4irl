import { createMockJqXHRChainable } from "../../../../__tests__/helpers/mock-jquery.js";
import { ajaxCall } from "../../../../lib/ajax.js";
import { checkForStaleDataOn409 } from "../conflict-handler.js";
import { getNumOfURLs } from "../../utils.js";
import { showURLSearchIcon } from "../../search.js";
import { showURLsEmptyState, hideURLsEmptyState } from "../../empty-state.js";
import {
  createURL,
  createURLHideInput,
  createURLShowInput,
  resetCreateURLFailErrors,
} from "../create.js";

vi.mock("../../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));

vi.mock("../cards.js", () => ({
  createURLBlock: vi.fn(() => window.jQuery('<div class="urlRow"></div>')),
  newURLInputAddEventListeners: vi.fn(),
  newURLInputRemoveEventListeners: vi.fn(),
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
  getState: vi.fn(() => ({ urls: [] })),
  setState: vi.fn(),
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
});
