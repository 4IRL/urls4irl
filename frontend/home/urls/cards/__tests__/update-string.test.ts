import { createMockJqXHRChainable } from "../../../../__tests__/helpers/mock-jquery.js";
import { ajaxCall } from "../../../../lib/ajax.js";
import { checkForStaleDataOn409 } from "../conflict-handler.js";
import {
  updateURL,
  hideAndResetUpdateURLStringForm,
  showUpdateURLStringForm,
} from "../update-string.js";
import { enableClickOnSelectedURLCardToHide } from "../selection.js";
import { isCoarsePointer } from "../../../mobile.js";
import { openURLEditPanel } from "../update-url-panel.js";
import { getState, setState, AppState } from "../../../../store/app-store.js";

const { mockMetricsClient } = await vi.hoisted(
  async () =>
    await import("../../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../../../../lib/globals.js", async () => {
  const jquery = (await import("jquery")).default;
  const tooltipInstance = {
    setContent: vi.fn(),
    show: vi.fn(),
    hide: vi.fn(),
    enable: vi.fn(),
    disable: vi.fn(),
  };
  return {
    $: jquery,
    jQuery: jquery,
    bootstrap: {
      Tooltip: {
        getInstance: vi.fn(() => tooltipInstance),
        getOrCreateInstance: vi.fn(() => tooltipInstance),
      },
    },
    getInputValue: (input: string | JQuery) => {
      const element = typeof input === "string" ? jquery(input) : input;
      return element.val() as string;
    },
  };
});

vi.mock("../../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));

vi.mock("../loading.js", () => ({
  setTimeoutAndShowURLCardLoadingIcon: vi.fn(() => 1),
  clearTimeoutIDAndHideLoadingIcon: vi.fn(),
}));

vi.mock("../get.js", () => ({
  getUpdatedURL: vi.fn(() => Promise.resolve()),
  handleRejectFromGetURL: vi.fn(),
}));

vi.mock("../selection.js", () => ({
  disableClickOnSelectedURLCardToHide: vi.fn(),
  enableClickOnSelectedURLCardToHide: vi.fn(),
}));

vi.mock("../options/edit-string-btn.js", () => ({
  createEditURLIcon: vi.fn(() => window.jQuery("<i></i>")),
  bindURLStringEditClickHandler: vi.fn(),
}));

vi.mock("../update-url-panel.js", () => ({
  openURLEditPanel: vi.fn(),
  closeURLEditPanel: vi.fn(),
}));

vi.mock("../../tags/tags.js", () => ({
  disableTagRemovalInURLCard: vi.fn(),
  enableTagRemovalInURLCard: vi.fn(),
}));

vi.mock("../../../mobile.js", () => ({
  isMobile: vi.fn(() => false),
  isCoarsePointer: vi.fn(() => false),
}));

vi.mock("../../../btns-forms.js", () => ({
  highlightInput: vi.fn(),
}));

vi.mock("../conflict-handler.js", () => ({
  checkForStaleDataOn409: vi.fn(),
}));

vi.mock("../access.js", () => ({
  accessLink: vi.fn(),
}));

vi.mock("../copy.js", () => ({
  copyURLString: vi.fn(),
}));

vi.mock("../../../../store/app-store.js", () => ({
  getState: vi.fn(() => ({ urls: [] })),
  setState: vi.fn(),
}));

const $ = window.jQuery;

const URL_CARD_HTML = `
  <div class="urlRow" utuburlid="1" urlSelected="false">
    <a class="urlString" href="https://example.com">https://example.com</a>
    <div class="updateUrlStringWrap">
      <input class="urlStringUpdate" value="https://example.com" />
      <div class="urlStringUpdate-error"></div>
    </div>
    <div class="urlCardDualLoadingRing"></div>
  </div>
`;

const HIDE_RESET_URL_CARD_HTML = `
  <div class="urlRow" utuburlid="1" urlSelected="false">
    <div class="updateUrlStringWrap hidden"></div>
    <a class="urlString" href="https://ex.com">https://ex.com</a>
    <input class="urlStringUpdate" value="https://ex.com" />
  </div>
`;

const CONCURRENT_EDIT_CARD_HTML = `<div class="urlRow" utuburlid="42" urlSelected="true" filterable="true">
    <a class="urlString" href="https://example.com">https://example.com</a>
    <div class="updateUrlStringWrap hidden"><input class="urlStringUpdate" type="text" value="https://example.com" /></div>
    <button class="urlStringBtnUpdate"></button>
    <button class="urlStringCancelBigBtnUpdate"></button>
    <button class="urlTitleBtnUpdate"></button>
    <button class="urlBtnAccess"></button>
    <button class="urlTagBtnCreate"></button>
    <button class="urlBtnDelete"></button>
    <button class="urlBtnCopy"></button>
    <span class="goToUrlIcon"></span>
</div>`;

describe("hideAndResetUpdateURLStringForm - selection guard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("does NOT call enableClickOnSelectedURLCardToHide when card is NOT selected", () => {
    document.body.innerHTML = HIDE_RESET_URL_CARD_HTML;
    const urlCard = $(".urlRow");
    urlCard.attr("urlSelected", "false");

    hideAndResetUpdateURLStringForm({ urlCard });

    expect(enableClickOnSelectedURLCardToHide).not.toHaveBeenCalled();
  });

  it("DOES call enableClickOnSelectedURLCardToHide when card IS selected", () => {
    document.body.innerHTML = HIDE_RESET_URL_CARD_HTML;
    const urlCard = $(".urlRow");
    urlCard.attr("urlSelected", "true");

    hideAndResetUpdateURLStringForm({ urlCard });

    expect(enableClickOnSelectedURLCardToHide).toHaveBeenCalledWith(urlCard);
  });
});

describe("updateURL - client-side validation", () => {
  let urlCard: JQuery, urlStringInput: JQuery;

  beforeEach(() => {
    document.body.innerHTML = URL_CARD_HTML;
    urlCard = $(".urlRow");
    urlStringInput = urlCard.find(".urlStringUpdate");
    vi.clearAllMocks();
  });

  describe("invalid URL schemes are blocked before AJAX", () => {
    it.each([
      ["javascript:alert(1)"],
      ["data:text/html,<h1>x</h1>"],
      ["vbscript:msgbox('x')"],
    ])(
      "blocks '%s' and shows error without calling ajaxCall",
      async (invalidUrl) => {
        urlStringInput.val(invalidUrl);

        await updateURL(urlStringInput, urlCard, 1);

        expect(urlCard.find(".urlStringUpdate-error").hasClass("visible")).toBe(
          true,
        );
        expect(urlCard.find(".urlStringUpdate-error").text()).toBeTruthy();
        expect(urlCard.find(".urlStringUpdate").hasClass("invalid-field")).toBe(
          true,
        );
        expect(ajaxCall).not.toHaveBeenCalled();
      },
    );
  });
});

describe("updateURLSuccess - tag ID mapping regression guard", () => {
  let urlCard: JQuery, urlStringInput: JQuery;

  beforeEach(() => {
    document.body.innerHTML = URL_CARD_HTML;
    urlCard = $(".urlRow");
    urlStringInput = urlCard.find(".urlStringUpdate");
    vi.clearAllMocks();

    vi.mocked(getState).mockReturnValue({
      urls: [
        {
          utubUrlID: 1,
          urlString: "https://example.com",
          urlTitle: "Old Title",
          utubUrlTagIDs: [],
          canDelete: true,
        },
      ],
    } as unknown as AppState);
  });

  it("maps response.URL.urlTags via utubTagID (not legacy tagID) into setState", async () => {
    urlStringInput.val("https://new-example.com");

    const response = {
      URL: {
        utubUrlID: 1,
        urlString: "https://new-example.com",
        urlTitle: "New Title",
        urlTags: [
          { utubTagID: 10, tagString: "t10" },
          { utubTagID: 20, tagString: "t20" },
        ],
      },
    };

    const chainable = createMockJqXHRChainable({
      done: (cb: unknown) =>
        (cb as (...args: unknown[]) => void)(response, "success", {
          status: 200,
        }),
    });
    vi.mocked(ajaxCall).mockReturnValue(chainable);

    await updateURL(urlStringInput, urlCard, 1);

    expect(setState).toHaveBeenCalled();
    const setStateArg = vi.mocked(setState).mock.calls[0][0];
    const updatedUrl = setStateArg.urls!.find(
      (existingUrl) => existingUrl.utubUrlID === 1,
    );
    expect(updatedUrl!.utubUrlTagIDs).toEqual([10, 20]);
  });
});

describe("updateURL - 409 conflict delegates to checkForStaleDataOn409", () => {
  let urlCard: JQuery, urlStringInput: JQuery;

  beforeEach(() => {
    document.body.innerHTML = URL_CARD_HTML;
    urlCard = $(".urlRow");
    urlStringInput = urlCard.find(".urlStringUpdate");
    vi.clearAllMocks();
  });

  it("calls checkForStaleDataOn409 with utubID when ajaxCall fails with status 409", async () => {
    urlStringInput.val("https://duplicate.example.com");

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

    await updateURL(urlStringInput, urlCard, 99);

    expect(checkForStaleDataOn409).toHaveBeenCalledTimes(1);
    expect(checkForStaleDataOn409).toHaveBeenCalledWith(responseJSON, 99);
  });
});

describe("URL string edit hides title pencil for mutual exclusivity", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("hides .urlTitleBtnUpdate while string-edit form is open and restores it on close", () => {
    document.body.innerHTML = CONCURRENT_EDIT_CARD_HTML;
    const urlCard = $(".urlRow");
    const urlStringBtnUpdate = urlCard.find(".urlStringBtnUpdate");

    showUpdateURLStringForm({ urlCard, urlStringBtnUpdate });

    expect(urlCard.find(".urlTitleBtnUpdate").hasClass("hidden")).toBe(true);

    hideAndResetUpdateURLStringForm({ urlCard });

    expect(urlCard.find(".urlTitleBtnUpdate").hasClass("hidden")).toBe(false);
  });
});

describe("suppressSiblingDisable parameter (consolidated panel)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    document.body.innerHTML = CONCURRENT_EDIT_CARD_HTML;
  });

  it("does NOT hide the sibling title pencil when suppressSiblingDisable is true", () => {
    const urlCard = $(".urlRow");
    const urlStringBtnUpdate = urlCard.find(".urlStringBtnUpdate");

    showUpdateURLStringForm({
      urlCard,
      urlStringBtnUpdate,
      suppressSiblingDisable: true,
    });

    expect(urlCard.find(".urlTitleBtnUpdate").hasClass("hidden")).toBe(false);
  });

  it("hides the sibling title pencil when suppressSiblingDisable is omitted (desktop mutual-exclusion preserved)", () => {
    const urlCard = $(".urlRow");
    const urlStringBtnUpdate = urlCard.find(".urlStringBtnUpdate");

    showUpdateURLStringForm({ urlCard, urlStringBtnUpdate });

    expect(urlCard.find(".urlTitleBtnUpdate").hasClass("hidden")).toBe(true);
  });

  it("does NOT re-enable the sibling title pencil on close when suppressSiblingDisable is true", () => {
    const urlCard = $(".urlRow");
    urlCard.find(".urlTitleBtnUpdate").addClass("hidden");

    hideAndResetUpdateURLStringForm({ urlCard, suppressSiblingDisable: true });

    expect(urlCard.find(".urlTitleBtnUpdate").hasClass("hidden")).toBe(true);
  });

  it("re-enables the sibling title pencil on close when suppressSiblingDisable is omitted", () => {
    const urlCard = $(".urlRow");
    urlCard.find(".urlTitleBtnUpdate").addClass("hidden");

    hideAndResetUpdateURLStringForm({ urlCard });

    expect(urlCard.find(".urlTitleBtnUpdate").hasClass("hidden")).toBe(false);
  });
});

describe("bindURLStringEditClickHandler - mobile vs desktop click target", () => {
  // The real helper lives in edit-string-btn.js (module-mocked above for
  // update-string.ts's own rebind call); pull the real implementation via
  // importActual so its isCoarsePointer() branch can be exercised end-to-end.
  const HELPER_CARD_HTML = `
    <div class="urlRow" utuburlid="1" urlSelected="true" filterable="true">
      <a class="urlString" href="https://example.com">https://example.com</a>
      <div class="updateUrlStringWrap hidden"><input class="urlStringUpdate" type="text" value="https://example.com" /></div>
      <button class="urlStringBtnUpdate"></button>
      <button class="urlTitleBtnUpdate"></button>
      <button class="urlBtnAccess"></button>
      <button class="urlTagBtnCreate"></button>
      <button class="urlBtnDelete"></button>
      <button class="urlBtnCopy"></button>
      <span class="goToUrlIcon"></span>
    </div>
  `;

  beforeEach(() => {
    vi.clearAllMocks();
    document.body.innerHTML = HELPER_CARD_HTML;
    // Restore the module default explicitly — each test sets its own pointer
    // type, but vi.clearAllMocks does not reset a prior mockReturnValue.
    vi.mocked(isCoarsePointer).mockReturnValue(false);
  });

  it("opens the consolidated panel (openURLEditPanel) on a coarse pointer", async () => {
    vi.mocked(isCoarsePointer).mockReturnValue(true);
    const { bindURLStringEditClickHandler } = await vi.importActual<
      typeof import("../options/edit-string-btn.js")
    >("../options/edit-string-btn.js");

    const urlCard = $(".urlRow");
    const urlStringBtnUpdate = urlCard.find(".urlStringBtnUpdate");
    bindURLStringEditClickHandler({ urlCard, urlStringBtnUpdate });

    urlStringBtnUpdate.trigger("click");

    expect(openURLEditPanel).toHaveBeenCalledWith(urlCard);
    // Desktop single-field open must NOT have run: the button never morphs.
    expect(urlCard.find(".urlStringCancelBigBtnUpdate").length).toBe(0);
  });

  it("opens only the string form (showUpdateURLStringForm) on a fine pointer", async () => {
    vi.mocked(isCoarsePointer).mockReturnValue(false);
    const { bindURLStringEditClickHandler } = await vi.importActual<
      typeof import("../options/edit-string-btn.js")
    >("../options/edit-string-btn.js");

    const urlCard = $(".urlRow");
    const urlStringBtnUpdate = urlCard.find(".urlStringBtnUpdate");
    bindURLStringEditClickHandler({ urlCard, urlStringBtnUpdate });

    urlStringBtnUpdate.trigger("click");

    expect(openURLEditPanel).not.toHaveBeenCalled();
    // Desktop path ran showUpdateURLStringForm, morphing the button to Cancel.
    expect(urlCard.find(".urlStringCancelBigBtnUpdate").text()).toBe("Cancel");
  });
});
