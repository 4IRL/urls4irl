import { createMockJqXHRChainable } from "../../../../__tests__/helpers/mock-jquery.js";
import { ajaxCall } from "../../../../lib/ajax.js";
import { checkForStaleDataOn409 } from "../conflict-handler.js";
import {
  updateURL,
  hideAndResetUpdateURLStringForm,
  isURLStringSubmitInFlight,
  showUpdateURLStringForm,
} from "../update-string.js";
import { showUpdateURLTitleForm } from "../update-title.js";
import { enableClickOnSelectedURLCardToHide } from "../selection.js";
import { isCoarsePointer } from "../../../mobile.js";
import { openURLEditPanel } from "../update-url-panel.js";
import { getState, setState, AppState } from "../../../../store/app-store.js";
import { clearOpenForm, getOpenForm } from "../../../../lib/modal-tracking.js";
import { HOME_FORM } from "../../../../types/metrics-dim-values.js";

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
    <div class="updateUrlTitleWrap hidden"></div>
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

describe("URL string edit keeps the title pencil visible (desktop full toggle)", () => {
  // Desktop full-toggle model: opening the string editor no longer HIDES the
  // title pencil — both triggers stay visible/hoverable at all times (the
  // sibling title wrap starts hidden/closed here, so no mutual close fires).
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("keeps .urlTitleBtnUpdate visible while the string-edit form is open (title pencil never vanishes)", () => {
    document.body.innerHTML = CONCURRENT_EDIT_CARD_HTML;
    const urlCard = $(".urlRow");
    const urlStringBtnUpdate = urlCard.find(".urlStringBtnUpdate");

    showUpdateURLStringForm({ urlCard, urlStringBtnUpdate });

    expect(urlCard.find(".urlTitleBtnUpdate").hasClass("hidden")).toBe(false);

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

  it("keeps the sibling title pencil visible when suppressSiblingDisable is omitted (desktop full toggle — pencil never vanishes)", () => {
    const urlCard = $(".urlRow");
    const urlStringBtnUpdate = urlCard.find(".urlStringBtnUpdate");

    showUpdateURLStringForm({ urlCard, urlStringBtnUpdate });

    expect(urlCard.find(".urlTitleBtnUpdate").hasClass("hidden")).toBe(false);
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

describe("desktop full toggle — Title and URL editors are mutually exclusive (fine pointer)", () => {
  // Both editors present. Exactly one wrap is open per test so we can assert that
  // opening the closed one CLOSES the open sibling. isCoarsePointer() is false
  // (fine pointer / desktop), so suppressSiblingDisable is never set and the
  // mutual-close path runs.
  const STRING_OPEN_CARD_HTML = `
    <div class="urlRow" utuburlid="1" urlSelected="true" filterable="true">
      <div class="urlTitleAndUpdateIconWrap">
        <span class="urlTitle">My Title</span>
        <button class="urlTitleBtnUpdate hidden"></button>
      </div>
      <div class="updateUrlTitleWrap hidden">
        <input class="urlTitleUpdate" value="My Title" />
      </div>
      <a class="urlString hidden" href="https://example.com">https://example.com</a>
      <div class="updateUrlStringWrap">
        <input class="urlStringUpdate" type="text" value="https://example.com" />
        <div class="urlStringUpdate-error"></div>
      </div>
      <button class="urlStringCancelBigBtnUpdate">Cancel</button>
      <button class="urlBtnAccess hidden"></button>
      <button class="urlTagBtnCreate hidden"></button>
      <button class="urlBtnDelete hidden"></button>
      <button class="urlBtnCopy hidden"></button>
      <span class="goToUrlIcon hidden"></span>
      <div class="tagBadge"></div>
    </div>
  `;

  const TITLE_OPEN_CARD_HTML = `
    <div class="urlRow" utuburlid="1" urlSelected="true" filterable="true">
      <div class="urlTitleAndUpdateIconWrap hidden">
        <span class="urlTitle">My Title</span>
        <button class="urlTitleBtnUpdate"></button>
      </div>
      <div class="updateUrlTitleWrap">
        <input class="urlTitleUpdate" value="My Title" />
      </div>
      <a class="urlString" href="https://example.com">https://example.com</a>
      <div class="updateUrlStringWrap hidden">
        <input class="urlStringUpdate" type="text" value="https://example.com" />
        <div class="urlStringUpdate-error"></div>
      </div>
      <button class="urlStringBtnUpdate"></button>
      <button class="urlBtnAccess"></button>
      <button class="urlTagBtnCreate"></button>
      <button class="urlBtnDelete"></button>
      <button class="urlBtnCopy"></button>
      <span class="goToUrlIcon"></span>
      <div class="tagBadge"></div>
    </div>
  `;

  beforeEach(() => {
    vi.clearAllMocks();
    // Desktop / fine pointer — mutual exclusion is active.
    vi.mocked(isCoarsePointer).mockReturnValue(false);
  });

  it("(a) opening the Title editor closes an open URL-string editor, restores its option buttons, and leaves the edit-URL trigger visible", () => {
    document.body.innerHTML = STRING_OPEN_CARD_HTML;
    const urlCard = $(".urlRow");
    const urlTitleAndIcon = urlCard.find(".urlTitleAndUpdateIconWrap");

    // Precondition: string editor open, title editor closed.
    expect(urlCard.find(".updateUrlStringWrap").hasClass("hidden")).toBe(false);
    expect(urlCard.find(".updateUrlTitleWrap").hasClass("hidden")).toBe(true);

    showUpdateURLTitleForm({
      urlTitleAndShowUpdateIconWrap: urlTitleAndIcon,
      urlCard,
    });

    // String editor closed by the mutual-close; title editor now open.
    expect(urlCard.find(".updateUrlStringWrap").hasClass("hidden")).toBe(true);
    expect(urlCard.find(".updateUrlTitleWrap").hasClass("hidden")).toBe(false);
    // Option buttons restored (the string reset re-showed them).
    expect(urlCard.find(".urlBtnAccess").hasClass("hidden")).toBe(false);
    expect(urlCard.find(".urlBtnCopy").hasClass("hidden")).toBe(false);
    // Edit-URL trigger is present and visible (morphed back from the Cancel bar).
    expect(urlCard.find(".urlStringBtnUpdate").length).toBe(1);
    expect(urlCard.find(".urlStringBtnUpdate").hasClass("hidden")).toBe(false);
    // Never both open.
    expect(
      urlCard.find(".updateUrlTitleWrap").hasClass("hidden") &&
        urlCard.find(".updateUrlStringWrap").hasClass("hidden"),
    ).toBe(false);
    const bothOpen =
      !urlCard.find(".updateUrlTitleWrap").hasClass("hidden") &&
      !urlCard.find(".updateUrlStringWrap").hasClass("hidden");
    expect(bothOpen).toBe(false);
  });

  it("(b) opening the URL-string editor closes an open Title editor and keeps the title pencil visible", () => {
    document.body.innerHTML = TITLE_OPEN_CARD_HTML;
    const urlCard = $(".urlRow");
    const urlStringBtnUpdate = urlCard.find(".urlStringBtnUpdate");

    // Precondition: title editor open, string editor closed.
    expect(urlCard.find(".updateUrlTitleWrap").hasClass("hidden")).toBe(false);
    expect(urlCard.find(".updateUrlStringWrap").hasClass("hidden")).toBe(true);

    showUpdateURLStringForm({ urlCard, urlStringBtnUpdate });

    // Title editor closed by the mutual-close; string editor now open.
    expect(urlCard.find(".updateUrlTitleWrap").hasClass("hidden")).toBe(true);
    expect(urlCard.find(".updateUrlStringWrap").hasClass("hidden")).toBe(false);
    // Title pencil restored/visible (enableEditingURLTitle ran on the title reset).
    expect(urlCard.find(".urlTitleBtnUpdate").hasClass("hidden")).toBe(false);
    // Never both open.
    const bothOpen =
      !urlCard.find(".updateUrlTitleWrap").hasClass("hidden") &&
      !urlCard.find(".updateUrlStringWrap").hasClass("hidden");
    expect(bothOpen).toBe(false);
  });

  it("(c) neither the string nor the title mutual-close fires on the mobile panel path (suppressSiblingDisable) — both stay open", () => {
    // Mobile keep-both-open guarantee: with suppressSiblingDisable the sibling is
    // NOT closed, so both editors remain open simultaneously.
    document.body.innerHTML = TITLE_OPEN_CARD_HTML;
    const urlCard = $(".urlRow");
    const urlStringBtnUpdate = urlCard.find(".urlStringBtnUpdate");

    showUpdateURLStringForm({
      urlCard,
      urlStringBtnUpdate,
      suppressSiblingDisable: true,
    });

    // Title editor is NOT closed by the sibling open (mobile keep-both-open).
    expect(urlCard.find(".updateUrlTitleWrap").hasClass("hidden")).toBe(false);
    expect(urlCard.find(".updateUrlStringWrap").hasClass("hidden")).toBe(false);
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

describe("panel-aware submit gate — deselect + sibling suppression (mobile consolidated panel)", () => {
  // Card with BOTH edit forms present. The sibling title wrap is left OPEN (no
  // `hidden` class) so, on a coarse pointer, the panel-aware gate suppresses the
  // sibling restore. The title pencil starts hidden so we can assert it STAYS
  // hidden (i.e. enableEditingURLTitle did not fire).
  const PANEL_CARD_HTML = `
    <span class="visually-hidden" id="fieldSavedAnnouncement" aria-live="polite"></span>
    <div class="urlRow" utuburlid="1" urlSelected="true" filterable="true">
      <a class="urlString" href="https://example.com">https://example.com</a>
      <div class="updateUrlStringWrap">
        <input class="urlStringUpdate" type="text" value="https://example.com" />
        <button class="urlStringSubmitBtnUpdate"></button>
        <div class="field-saved-tick-slot"><span class="field-saved-tick opa-0" aria-hidden="true"></span></div>
      </div>
      <div class="updateUrlTitleWrap">
        <input class="urlTitleUpdate" value="My Title" />
        <div class="field-saved-tick-slot"><span class="field-saved-tick opa-0" aria-hidden="true"></span></div>
      </div>
      <button class="urlStringBtnUpdate"></button>
      <button class="urlStringCancelBigBtnUpdate"></button>
      <button class="urlTitleBtnUpdate hidden"></button>
      <button class="urlBtnAccess hidden"></button>
      <button class="urlTagBtnCreate hidden"></button>
      <button class="urlBtnDelete hidden"></button>
      <button class="urlBtnCopy hidden"></button>
      <span class="goToUrlIcon hidden"></span>
      <div class="urlStringUpdate-error"></div>
      <div class="urlCardDualLoadingRing"></div>
    </div>
  `;

  beforeEach(() => {
    document.body.innerHTML = PANEL_CARD_HTML;
    vi.clearAllMocks();
    // Coarse pointer = the mobile consolidated panel is in play.
    vi.mocked(isCoarsePointer).mockReturnValue(true);
  });

  it("value-unchanged skip: keeps the title pencil hidden AND does not re-arm the card deselect handler while the sibling form is open on mobile", async () => {
    const urlCard = $(".urlRow");
    // Input value already equals the href → value-unchanged skip path.
    const urlStringInput = urlCard.find(".urlStringUpdate");

    await updateURL(urlStringInput, urlCard, 1);

    // (a) sibling title pencil stays hidden — enableEditingURLTitle suppressed.
    expect(urlCard.find(".urlTitleBtnUpdate").hasClass("hidden")).toBe(true);
    // (b) card deselect handler is NOT re-armed.
    expect(enableClickOnSelectedURLCardToHide).not.toHaveBeenCalled();
  });

  it("success path: keeps the title pencil hidden AND does not re-arm the card deselect handler while the sibling form is open on mobile", async () => {
    const urlCard = $(".urlRow");
    const urlStringInput = urlCard.find(".urlStringUpdate");
    urlStringInput.val("https://new-example.com");

    const response = {
      URL: {
        utubUrlID: 1,
        urlString: "https://new-example.com",
        urlTitle: "My Title",
        urlTags: [],
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

    expect(urlCard.find(".urlTitleBtnUpdate").hasClass("hidden")).toBe(true);
    expect(enableClickOnSelectedURLCardToHide).not.toHaveBeenCalled();
  });

  it("companion — panel closed: performs the normal restore (re-arms deselect, restores the title pencil)", async () => {
    const urlCard = $(".urlRow");
    // Panel is CLOSED — the morphed Cancel bar is hidden (the authoritative
    // panel-open signal), so keepOpen is false and the normal restore runs even
    // on a coarse pointer. Sibling title form also closed so suppressSibling is
    // false too.
    urlCard.find(".urlStringCancelBigBtnUpdate").addClass("hidden");
    urlCard.find(".updateUrlTitleWrap").addClass("hidden");
    const urlStringInput = urlCard.find(".urlStringUpdate");

    await updateURL(urlStringInput, urlCard, 1);

    expect(urlCard.find(".urlTitleBtnUpdate").hasClass("hidden")).toBe(false);
    expect(enableClickOnSelectedURLCardToHide).toHaveBeenCalledWith(urlCard);
  });

  it("panel open: a real string change keeps the wrap open, keeps action buttons hidden, shows the tick, announces, and re-registers the open form", async () => {
    clearOpenForm();
    const urlCard = $(".urlRow");
    const urlStringInput = urlCard.find(".urlStringUpdate");
    urlStringInput.val("https://new-example.com");

    const response = {
      URL: {
        utubUrlID: 1,
        urlString: "https://new-example.com",
        urlTitle: "My Title",
        urlTags: [],
      },
    };
    vi.mocked(ajaxCall).mockReturnValue(
      createMockJqXHRChainable({
        done: (cb: unknown) =>
          (cb as (...args: unknown[]) => void)(response, "success", {
            status: 200,
          }),
        always: (cb: unknown) => (cb as () => void)(),
      }),
    );

    await updateURL(urlStringInput, urlCard, 1);

    // Wrap stays open (keepOpen skipped the collapse).
    expect(urlCard.find(".updateUrlStringWrap").hasClass("hidden")).toBe(false);
    // Cancel bar preserved (panel-open signal intact — not morphed back).
    expect(
      urlCard.find(".urlStringCancelBigBtnUpdate").hasClass("hidden"),
    ).toBe(false);
    // Sibling action buttons stay hidden until the panel closes (keepOpen skips
    // the action-button restore) — the behavior the test name promises.
    expect(urlCard.find(".urlBtnAccess").hasClass("hidden")).toBe(true);
    expect(urlCard.find(".urlTagBtnCreate").hasClass("hidden")).toBe(true);
    expect(urlCard.find(".urlBtnDelete").hasClass("hidden")).toBe(true);
    expect(urlCard.find(".urlBtnCopy").hasClass("hidden")).toBe(true);
    expect(urlCard.find(".goToUrlIcon").hasClass("hidden")).toBe(true);
    // Saved✓ tick shown and shared announcer reflects the field label.
    expect(
      urlCard.find(".updateUrlStringWrap .field-saved-tick").hasClass("opa-1"),
    ).toBe(true);
    expect($("#fieldSavedAnnouncement").text()).toBe("URL Saved");
    expect(getOpenForm()).toBe(HOME_FORM.URL_STRING_EDIT);
  });

  it("panel open: marks the submit control aria-disabled while in flight and clears it (never native disabled) once settled", async () => {
    clearOpenForm();
    const urlCard = $(".urlRow");
    const submitBtn = urlCard.find(".urlStringSubmitBtnUpdate");
    const urlStringInput = urlCard.find(".urlStringUpdate");
    urlStringInput.val("https://new-example.com");

    const response = {
      URL: {
        utubUrlID: 1,
        urlString: "https://new-example.com",
        urlTitle: "My Title",
        urlTags: [],
      },
    };
    let inFlightAtRequest: boolean | undefined;
    let ariaAtRequest: string | undefined;
    vi.mocked(ajaxCall).mockImplementation(() => {
      inFlightAtRequest = isURLStringSubmitInFlight();
      ariaAtRequest = submitBtn.attr("aria-disabled");
      return createMockJqXHRChainable({
        done: (cb: unknown) =>
          (cb as (...args: unknown[]) => void)(response, "success", {
            status: 200,
          }),
        always: (cb: unknown) => (cb as () => void)(),
      });
    });

    await updateURL(urlStringInput, urlCard, 1);

    expect(inFlightAtRequest).toBe(true);
    expect(ariaAtRequest).toBe("true");
    expect(isURLStringSubmitInFlight()).toBe(false);
    expect(submitBtn.attr("aria-disabled")).toBeUndefined();
    expect(submitBtn.prop("disabled")).toBe(false);
  });

  it("fine pointer (desktop): a changed submit collapses the field with no tick", async () => {
    // Desktop: the consolidated panel is never in play, so isCardEditPanelOpen is
    // false and the field collapses on submit (no keep-open, no Saved✓ tick).
    vi.mocked(isCoarsePointer).mockReturnValue(false);
    const urlCard = $(".urlRow");
    const urlStringInput = urlCard.find(".urlStringUpdate");
    urlStringInput.val("https://new-example.com");

    const response = {
      URL: {
        utubUrlID: 1,
        urlString: "https://new-example.com",
        urlTitle: "My Title",
        urlTags: [],
      },
    };
    vi.mocked(ajaxCall).mockReturnValue(
      createMockJqXHRChainable({
        done: (cb: unknown) =>
          (cb as (...args: unknown[]) => void)(response, "success", {
            status: 200,
          }),
        always: (cb: unknown) => (cb as () => void)(),
      }),
    );

    await updateURL(urlStringInput, urlCard, 1);

    // Field collapses (wrap hidden, URL re-shown) and no tick flashes.
    expect(urlCard.find(".updateUrlStringWrap").hasClass("hidden")).toBe(true);
    expect(
      urlCard.find(".updateUrlStringWrap .field-saved-tick").hasClass("opa-1"),
    ).toBe(false);
  });

  it("clears the in-flight guard on a genuine AJAX reject (.fail), never leaving a permanent aria-disabled lockout", async () => {
    const urlCard = $(".urlRow");
    const submitBtn = urlCard.find(".urlStringSubmitBtnUpdate");
    const urlStringInput = urlCard.find(".urlStringUpdate");
    urlStringInput.val("https://new-example.com");

    // Fire the true `.fail()` reject branch (status 0 → benign timeout-error
    // display, no navigation) and settle `.always()`.
    vi.mocked(ajaxCall).mockReturnValue(
      createMockJqXHRChainable({
        fail: (cb: unknown) =>
          (cb as (xhr: JQuery.jqXHR) => void)({
            status: 0,
          } as unknown as JQuery.jqXHR),
        always: (cb: unknown) => (cb as () => void)(),
      }),
    );

    await updateURL(urlStringInput, urlCard, 1);

    expect(isURLStringSubmitInFlight()).toBe(false);
    expect(submitBtn.attr("aria-disabled")).toBeUndefined();
  });
});
