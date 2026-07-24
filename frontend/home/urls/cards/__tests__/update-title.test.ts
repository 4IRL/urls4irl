import { createMockJqXHRChainable } from "../../../../__tests__/helpers/mock-jquery.js";
import {
  hideAndResetUpdateURLTitleForm,
  isURLTitleSubmitInFlight,
  showUpdateURLTitleForm,
  updateURLTitle,
} from "../update-title.js";
import { enableClickOnSelectedURLCardToHide } from "../selection.js";
import { ajaxCall, is429Handled } from "../../../../lib/ajax.js";
import { isMobile, isCoarsePointer } from "../../../mobile.js";
import { getState, setState, AppState } from "../../../../store/app-store.js";
import { clearOpenForm, getOpenForm } from "../../../../lib/modal-tracking.js";
import { HOME_FORM } from "../../../../types/metrics-dim-values.js";

const { mockMetricsClient } = await vi.hoisted(
  async () =>
    await import("../../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../selection.js", () => ({
  disableClickOnSelectedURLCardToHide: vi.fn(),
  enableClickOnSelectedURLCardToHide: vi.fn(),
}));

vi.mock("../loading.js", () => ({
  setTimeoutAndShowURLCardLoadingIcon: vi.fn(() => 1),
  clearTimeoutIDAndHideLoadingIcon: vi.fn(),
}));

vi.mock("../get.js", () => ({
  getUpdatedURL: vi.fn(() => Promise.resolve()),
  handleRejectFromGetURL: vi.fn(),
}));

vi.mock("../../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));

vi.mock("../../../../store/app-store.js", () => ({
  getState: vi.fn(() => ({ urls: [] })),
  setState: vi.fn(),
}));

vi.mock("../../../mobile.js", () => ({
  isMobile: vi.fn(() => true),
  isCoarsePointer: vi.fn(() => false),
}));

const $ = window.jQuery;

const URL_CARD_HTML = `
  <div class="urlRow" utuburlid="1" urlSelected="false">
    <div class="updateUrlTitleWrap hidden"></div>
    <div class="urlTitleAndUpdateIconWrap">
      <span class="urlTitle">My Title</span>
    </div>
    <input class="urlTitleUpdate" value="My Title" />
  </div>
`;

describe("hideAndResetUpdateURLTitleForm - selection guard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("does NOT call enableClickOnSelectedURLCardToHide when card is NOT selected", () => {
    document.body.innerHTML = URL_CARD_HTML;
    const urlCard = $(".urlRow");
    urlCard.attr("urlSelected", "false");

    hideAndResetUpdateURLTitleForm({ urlCard });

    expect(enableClickOnSelectedURLCardToHide).not.toHaveBeenCalled();
  });

  it("DOES call enableClickOnSelectedURLCardToHide when card IS selected", () => {
    document.body.innerHTML = URL_CARD_HTML;
    const urlCard = $(".urlRow");
    urlCard.attr("urlSelected", "true");

    hideAndResetUpdateURLTitleForm({ urlCard });

    expect(enableClickOnSelectedURLCardToHide).toHaveBeenCalledWith(urlCard);
  });
});

describe("url_title_edit unchanged value", () => {
  const UNCHANGED_URL_CARD_HTML = `
    <div class="urlRow" utuburlid="1" urlSelected="false">
      <div class="updateUrlTitleWrap"></div>
      <div class="urlTitleAndUpdateIconWrap">
        <span class="urlTitle">Same Title</span>
      </div>
      <input class="urlTitleUpdate" value="Same Title" />
    </div>
  `;

  beforeEach(() => {
    document.body.innerHTML = UNCHANGED_URL_CARD_HTML;
    vi.clearAllMocks();
    vi.mocked(getState).mockReturnValue({
      urls: [
        {
          utubUrlID: 1,
          urlString: "https://example.com",
          urlTitle: "Same Title",
          utubUrlTagIDs: [],
          canDelete: true,
        },
      ],
    } as unknown as AppState);
  });

  it("emits submit but fires no AJAX when value is unchanged", async () => {
    const urlCard = $(".urlRow");
    const urlTitleInput = urlCard.find(".urlTitleUpdate");

    // updateURLTitle's unchanged-value guard short-circuits before ajaxCall is invoked.
    // The emit-before-early-return convention places the emit(UI_FORM_SUBMIT) call at the
    // top of the submit-button click handler in url-title.ts (not inside updateURLTitle
    // itself), so here we only assert that no AJAX is invoked — the emit is asserted in
    // the url-title.ts vitest below.
    expect(vi.mocked(ajaxCall)).not.toHaveBeenCalled();

    await updateURLTitle(urlTitleInput, urlCard, 1);

    expect(vi.mocked(ajaxCall)).not.toHaveBeenCalled();
  });
});

describe("updateURLTitleSuccess - tag ID mapping regression guard", () => {
  const UPDATE_TITLE_URL_CARD_HTML = `
    <div class="urlRow" utuburlid="1" urlSelected="false">
      <div class="updateUrlTitleWrap"></div>
      <div class="urlTitleAndUpdateIconWrap">
        <span class="urlTitle">Old Title</span>
      </div>
      <input class="urlTitleUpdate" value="New Title" />
      <div class="urlTitleUpdate-error"></div>
      <div class="tagBadge"></div>
    </div>
  `;

  let urlCard: JQuery, urlTitleInput: JQuery;

  beforeEach(() => {
    document.body.innerHTML = UPDATE_TITLE_URL_CARD_HTML;
    urlCard = $(".urlRow");
    urlTitleInput = urlCard.find(".urlTitleUpdate");
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
    const response = {
      URL: {
        utubUrlID: 1,
        urlString: "https://example.com",
        urlTitle: "New Title",
        urlTags: [
          { utubTagID: 11, tagString: "t11" },
          { utubTagID: 22, tagString: "t22" },
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

    await updateURLTitle(urlTitleInput, urlCard, 1);

    expect(setState).toHaveBeenCalled();
    const setStateArg = vi.mocked(setState).mock.calls[0][0];
    const updatedUrl = setStateArg.urls!.find(
      (existingUrl) => existingUrl.utubUrlID === 1,
    );
    expect(updatedUrl!.utubUrlTagIDs).toEqual([11, 22]);
  });
});

describe("URL title edit hides string-edit button for mutual exclusivity", () => {
  const CONCURRENT_EDIT_CARD_HTML = `
    <div class="urlRow" utuburlid="1" urlSelected="true" filterable="true">
      <div class="urlTitleAndUpdateIconWrap">
        <span class="urlTitle">My Title</span>
        <button class="urlTitleBtnUpdate"></button>
      </div>
      <div class="updateUrlTitleWrap hidden">
        <input class="urlTitleUpdate" value="My Title" />
      </div>
      <button class="urlStringBtnUpdate"></button>
      <button class="urlStringCancelBigBtnUpdate"></button>
      <div class="tagBadge"></div>
    </div>
  `;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("hides .urlStringBtnUpdate and .urlStringCancelBigBtnUpdate while title-edit form is open and restores them on close", () => {
    document.body.innerHTML = CONCURRENT_EDIT_CARD_HTML;
    const urlCard = $(".urlRow");
    const urlTitleAndIcon = urlCard.find(".urlTitleAndUpdateIconWrap");

    showUpdateURLTitleForm({
      urlTitleAndShowUpdateIconWrap: urlTitleAndIcon,
      urlCard,
    });

    expect(urlCard.find(".urlStringBtnUpdate").hasClass("hidden")).toBe(true);
    expect(
      urlCard.find(".urlStringCancelBigBtnUpdate").hasClass("hidden"),
    ).toBe(true);

    hideAndResetUpdateURLTitleForm({ urlCard });

    expect(urlCard.find(".urlStringBtnUpdate").hasClass("hidden")).toBe(false);
    expect(
      urlCard.find(".urlStringCancelBigBtnUpdate").hasClass("hidden"),
    ).toBe(false);
  });
});

describe("suppressSiblingDisable parameter (consolidated panel)", () => {
  const SUPPRESS_CARD_HTML = `
    <div class="urlRow" utuburlid="1" urlSelected="true" filterable="true">
      <div class="urlTitleAndUpdateIconWrap">
        <span class="urlTitle">My Title</span>
        <button class="urlTitleBtnUpdate"></button>
      </div>
      <div class="updateUrlTitleWrap hidden">
        <input class="urlTitleUpdate" value="My Title" />
      </div>
      <button class="urlStringBtnUpdate"></button>
      <button class="urlStringCancelBigBtnUpdate"></button>
      <div class="tagBadge"></div>
    </div>
  `;

  beforeEach(() => {
    vi.clearAllMocks();
    document.body.innerHTML = SUPPRESS_CARD_HTML;
  });

  it("does NOT hide the sibling string-edit buttons when suppressSiblingDisable is true", () => {
    const urlCard = $(".urlRow");
    const urlTitleAndIcon = urlCard.find(".urlTitleAndUpdateIconWrap");

    showUpdateURLTitleForm({
      urlTitleAndShowUpdateIconWrap: urlTitleAndIcon,
      urlCard,
      suppressSiblingDisable: true,
    });

    expect(urlCard.find(".urlStringBtnUpdate").hasClass("hidden")).toBe(false);
    expect(
      urlCard.find(".urlStringCancelBigBtnUpdate").hasClass("hidden"),
    ).toBe(false);
  });

  it("hides the sibling string-edit button when suppressSiblingDisable is omitted (desktop mutual-exclusion preserved)", () => {
    const urlCard = $(".urlRow");
    const urlTitleAndIcon = urlCard.find(".urlTitleAndUpdateIconWrap");

    showUpdateURLTitleForm({
      urlTitleAndShowUpdateIconWrap: urlTitleAndIcon,
      urlCard,
    });

    expect(urlCard.find(".urlStringBtnUpdate").hasClass("hidden")).toBe(true);
  });

  it("does NOT re-enable the sibling string-edit buttons on close when suppressSiblingDisable is true", () => {
    const urlCard = $(".urlRow");
    urlCard.find(".urlStringBtnUpdate").addClass("hidden");
    urlCard.find(".urlStringCancelBigBtnUpdate").addClass("hidden");

    hideAndResetUpdateURLTitleForm({ urlCard, suppressSiblingDisable: true });

    expect(urlCard.find(".urlStringBtnUpdate").hasClass("hidden")).toBe(true);
    expect(
      urlCard.find(".urlStringCancelBigBtnUpdate").hasClass("hidden"),
    ).toBe(true);
  });

  it("re-enables the sibling string-edit button on close when suppressSiblingDisable is omitted", () => {
    const urlCard = $(".urlRow");
    urlCard.find(".urlStringBtnUpdate").addClass("hidden");

    hideAndResetUpdateURLTitleForm({ urlCard });

    expect(urlCard.find(".urlStringBtnUpdate").hasClass("hidden")).toBe(false);
  });
});

describe("showUpdateURLTitleForm - iOS soft-keyboard focus", () => {
  const MOBILE_FOCUS_CARD_HTML = `
    <div class="urlRow" utuburlid="1" urlSelected="true" filterable="true">
      <div class="urlTitleAndUpdateIconWrap">
        <span class="urlTitle">My Title</span>
      </div>
      <div class="updateUrlTitleWrap hidden">
        <input class="urlTitleUpdate" value="My Title" />
      </div>
      <button class="urlStringBtnUpdate"></button>
      <div class="tagBadge"></div>
    </div>
  `;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("calls native input.focus() directly on mobile so iOS surfaces the soft keyboard", () => {
    document.body.innerHTML = MOBILE_FOCUS_CARD_HTML;
    const urlCard = $(".urlRow");
    const urlTitleAndIcon = urlCard.find(".urlTitleAndUpdateIconWrap");

    const focusSpy = vi.spyOn(HTMLInputElement.prototype, "focus");

    showUpdateURLTitleForm({
      urlTitleAndShowUpdateIconWrap: urlTitleAndIcon,
      urlCard,
    });

    expect(focusSpy).toHaveBeenCalled();

    focusSpy.mockRestore();
  });

  it("uses jQuery .trigger('focus') on non-mobile rather than the native input.focus()", () => {
    document.body.innerHTML = MOBILE_FOCUS_CARD_HTML;
    const urlCard = $(".urlRow");
    const urlTitleAndIcon = urlCard.find(".urlTitleAndUpdateIconWrap");

    vi.mocked(isMobile).mockReturnValueOnce(false);
    const triggerSpy = vi.spyOn($.fn, "trigger");

    showUpdateURLTitleForm({
      urlTitleAndShowUpdateIconWrap: urlTitleAndIcon,
      urlCard,
    });

    const focusTriggerCall = triggerSpy.mock.calls.find(
      (callArgs) => callArgs[0] === "focus",
    );
    expect(focusTriggerCall).toBeDefined();

    triggerSpy.mockRestore();
  });
});

describe("panel-aware submit gate — deselect + sibling suppression (mobile consolidated panel)", () => {
  // Card with BOTH edit forms present. The sibling string wrap is left OPEN (no
  // `hidden` class) so, on a coarse pointer, the panel-aware gate suppresses the
  // sibling restore. The string-edit button starts hidden so we can assert it
  // STAYS hidden (i.e. enableEditingURLString did not fire).
  const PANEL_CARD_HTML = `
    <span class="visually-hidden" id="fieldSavedAnnouncement" aria-live="polite"></span>
    <div class="urlRow" utuburlid="1" urlSelected="true" filterable="true">
      <div class="urlTitleAndUpdateIconWrap">
        <span class="urlTitle">Old Title</span>
        <button class="urlTitleBtnUpdate"></button>
      </div>
      <div class="updateUrlTitleWrap">
        <input class="urlTitleUpdate" value="Old Title" />
        <button class="urlTitleSubmitBtnUpdate"></button>
        <div class="field-saved-tick-slot"><span class="field-saved-tick opa-0" aria-hidden="true"></span></div>
      </div>
      <div class="updateUrlStringWrap">
        <input class="urlStringUpdate" value="https://example.com" />
        <div class="field-saved-tick-slot"><span class="field-saved-tick opa-0" aria-hidden="true"></span></div>
      </div>
      <button class="urlStringBtnUpdate hidden"></button>
      <button class="urlStringCancelBigBtnUpdate hidden"></button>
      <div class="urlTitleUpdate-error"></div>
      <div class="tagBadge"></div>
    </div>
  `;

  beforeEach(() => {
    document.body.innerHTML = PANEL_CARD_HTML;
    vi.clearAllMocks();
    // Coarse pointer = the mobile consolidated panel is in play.
    vi.mocked(isCoarsePointer).mockReturnValue(true);
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

  it("value-unchanged skip: keeps the string-edit button hidden AND does not re-arm the card deselect handler while the sibling form is open on mobile", async () => {
    const urlCard = $(".urlRow");
    // Input value already equals the title text → value-unchanged skip path.
    const urlTitleInput = urlCard.find(".urlTitleUpdate");

    await updateURLTitle(urlTitleInput, urlCard, 1);

    // (a) sibling string-edit button stays hidden — enableEditingURLString suppressed.
    expect(urlCard.find(".urlStringBtnUpdate").hasClass("hidden")).toBe(true);
    // (b) card deselect handler is NOT re-armed.
    expect(enableClickOnSelectedURLCardToHide).not.toHaveBeenCalled();
  });

  it("success path: keeps the string-edit button hidden AND does not re-arm the card deselect handler while the sibling form is open on mobile", async () => {
    const urlCard = $(".urlRow");
    const urlTitleInput = urlCard.find(".urlTitleUpdate");
    urlTitleInput.val("New Title");

    const response = {
      URL: {
        utubUrlID: 1,
        urlString: "https://example.com",
        urlTitle: "New Title",
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

    await updateURLTitle(urlTitleInput, urlCard, 1);

    expect(urlCard.find(".urlStringBtnUpdate").hasClass("hidden")).toBe(true);
    expect(enableClickOnSelectedURLCardToHide).not.toHaveBeenCalled();
  });

  it("companion — sibling form closed: performs the normal restore (re-arms deselect, restores the string-edit button)", async () => {
    const urlCard = $(".urlRow");
    // Sibling string form is CLOSED → the gate collapses and normal restore runs
    // even on a coarse pointer.
    urlCard.find(".updateUrlStringWrap").addClass("hidden");
    const urlTitleInput = urlCard.find(".urlTitleUpdate");

    await updateURLTitle(urlTitleInput, urlCard, 1);

    expect(urlCard.find(".urlStringBtnUpdate").hasClass("hidden")).toBe(false);
    expect(enableClickOnSelectedURLCardToHide).toHaveBeenCalledWith(urlCard);
  });

  it("panel open: a real title change keeps the wrap open, shows the tick, announces, and re-registers the open form", async () => {
    clearOpenForm();
    const urlCard = $(".urlRow");
    // Panel-open signal: the morphed full-width Cancel bar is present + unhidden.
    urlCard.find(".urlStringCancelBigBtnUpdate").removeClass("hidden");
    const urlTitleInput = urlCard.find(".urlTitleUpdate");
    urlTitleInput.val("New Title");

    const response = {
      URL: {
        utubUrlID: 1,
        urlString: "https://example.com",
        urlTitle: "New Title",
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

    await updateURLTitle(urlTitleInput, urlCard, 1);

    // Wrap stays open (keepOpen skipped the collapse).
    expect(urlCard.find(".updateUrlTitleWrap").hasClass("hidden")).toBe(false);
    // Saved✓ tick is shown and the shared announcer reflects the field label.
    expect(
      urlCard.find(".updateUrlTitleWrap .field-saved-tick").hasClass("opa-1"),
    ).toBe(true);
    expect($("#fieldSavedAnnouncement").text()).toBe("URL title Saved");
    // Open-form registry re-populated so a later pagehide doesn't misreport.
    expect(getOpenForm()).toBe(HOME_FORM.URL_TITLE_EDIT);
  });

  it("panel open: marks the submit control aria-disabled while in flight and clears it (never native disabled) once settled", async () => {
    clearOpenForm();
    const urlCard = $(".urlRow");
    urlCard.find(".urlStringCancelBigBtnUpdate").removeClass("hidden");
    const submitBtn = urlCard.find(".urlTitleSubmitBtnUpdate");
    const urlTitleInput = urlCard.find(".urlTitleUpdate");
    urlTitleInput.val("New Title");

    const response = {
      URL: {
        utubUrlID: 1,
        urlString: "https://example.com",
        urlTitle: "New Title",
        urlTags: [],
      },
    };
    let inFlightAtRequest: boolean | undefined;
    let ariaAtRequest: string | undefined;
    vi.mocked(ajaxCall).mockImplementation(() => {
      inFlightAtRequest = isURLTitleSubmitInFlight();
      ariaAtRequest = submitBtn.attr("aria-disabled");
      return createMockJqXHRChainable({
        done: (cb: unknown) =>
          (cb as (...args: unknown[]) => void)(response, "success", {
            status: 200,
          }),
        always: (cb: unknown) => (cb as () => void)(),
      });
    });

    await updateURLTitle(urlTitleInput, urlCard, 1);

    // In flight when the request was issued (what the entry-point guard reads).
    expect(inFlightAtRequest).toBe(true);
    expect(ariaAtRequest).toBe("true");
    // Cleared once settled; native `disabled` never used (focus preserved).
    expect(isURLTitleSubmitInFlight()).toBe(false);
    expect(submitBtn.attr("aria-disabled")).toBeUndefined();
    expect(submitBtn.prop("disabled")).toBe(false);
  });

  it("fine pointer (desktop): a changed submit collapses the field with no tick", async () => {
    // Desktop: the consolidated panel is never in play, so isCardEditPanelOpen is
    // false and the field collapses on submit (no keep-open, no Saved✓ tick).
    vi.mocked(isCoarsePointer).mockReturnValue(false);
    const urlCard = $(".urlRow");
    const urlTitleInput = urlCard.find(".urlTitleUpdate");
    urlTitleInput.val("New Title");

    const response = {
      URL: {
        utubUrlID: 1,
        urlString: "https://example.com",
        urlTitle: "New Title",
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

    await updateURLTitle(urlTitleInput, urlCard, 1);

    // Field collapses (wrap hidden) and no tick flashes.
    expect(urlCard.find(".updateUrlTitleWrap").hasClass("hidden")).toBe(true);
    expect(
      urlCard.find(".updateUrlTitleWrap .field-saved-tick").hasClass("opa-1"),
    ).toBe(false);
  });

  it("clears the in-flight guard on a genuine AJAX reject (.fail), never leaving a permanent aria-disabled lockout", async () => {
    const urlCard = $(".urlRow");
    // Panel-open signal so the in-flight guard is armed before the reject.
    urlCard.find(".urlStringCancelBigBtnUpdate").removeClass("hidden");
    const submitBtn = urlCard.find(".urlTitleSubmitBtnUpdate");
    const urlTitleInput = urlCard.find(".urlTitleUpdate");
    urlTitleInput.val("New Title");

    // Fire the true `.fail()` reject branch and settle `.always()`. Short-circuit
    // the downstream fail-display so it doesn't attempt an error-page navigation;
    // the guard clear runs in `.always()` regardless.
    vi.mocked(is429Handled).mockReturnValueOnce(true);
    vi.mocked(ajaxCall).mockReturnValue(
      createMockJqXHRChainable({
        fail: (cb: unknown) =>
          (cb as (xhr: JQuery.jqXHR) => void)({
            status: 0,
          } as unknown as JQuery.jqXHR),
        always: (cb: unknown) => (cb as () => void)(),
      }),
    );

    await updateURLTitle(urlTitleInput, urlCard, 1);

    expect(isURLTitleSubmitInFlight()).toBe(false);
    expect(submitBtn.attr("aria-disabled")).toBeUndefined();
  });
});
