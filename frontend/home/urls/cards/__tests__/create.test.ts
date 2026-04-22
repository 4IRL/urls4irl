import { ajaxCall } from "../../../../lib/ajax.js";
import { createURL, resetCreateURLFailErrors } from "../create.js";

vi.mock("../../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
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

vi.mock("../filtering.js", () => ({
  isURLCurrentlyVisibleInURLDeck: vi.fn(() => false),
}));

vi.mock("../../../tags/utils.js", () => ({
  isATagSelected: vi.fn(() => false),
}));

vi.mock("../../../utubs/stale-data.js", () => ({
  updateUTubOnFindingStaleData: vi.fn(),
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
    <p id="NoURLsSubheader"></p>
    <div id="urlBtnDeckCreateWrap"></div>
  </div>
  <div id="urlCreateDualLoadingRing"></div>
  <a id="accessAllURLsBtn"></a>
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
});
