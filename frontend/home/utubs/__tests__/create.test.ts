import {
  createMockJqXHRChainable,
  createMockXhr,
} from "../../../__tests__/helpers/mock-jquery.js";
import { ajaxCall, is429Handled } from "../../../lib/ajax.js";
import {
  hideTooltip,
  restoreTooltipIfStillTargeted,
} from "../../../lib/tooltips.js";
import { createUTubSelector, selectUTub } from "../selectors.js";
import { getNumOfUTubs } from "../utils.js";
import { getState, setState } from "../../../store/app-store.js";
import { setCreateUTubEventListeners } from "../create.js";
import {
  applyAlternatingUTubSelectorBackground,
  showUTubSearchBar,
} from "../search.js";

const { mockMetricsClient } = await vi.hoisted(
  async () => await import("../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../lib/metrics-client.js", () => mockMetricsClient());

// Both tooltip helpers this module reaches for are stubbed, so these tests
// assert the delegation (which element each handler acts on) rather than
// Bootstrap's internals. Their own behaviour — the still-targeted guard
// (`:hover` or `:focus-visible`) and the deferral past Bootstrap's fade for
// restoreTooltipIfStillTargeted, the null-instance no-op for hideTooltip — is
// covered in lib/__tests__/tooltips.test.ts.
//
// Deliberately a full stub, not a partial mock. Measured here: a factory that
// pulls the real module in via importOriginal()/importActual() leaves the
// CONSUMING module bound to the actual tooltips module, so the
// restoreTooltipIfStillTargeted override silently stops taking effect (the real
// one then early-returns on its `:hover` guard and the assertions below see
// zero calls). lib/tooltips.js imports the lib/globals.js this file also mocks.
vi.mock("../../../lib/tooltips.js", () => ({
  hideTooltip: vi.fn(),
  restoreTooltipIfStillTargeted: vi.fn(),
}));

// lib/globals.js is replaced wholesale (jQuery + getInputValue + Bootstrap), so
// the Bootstrap stub has to hand back a usable Tooltip instance rather than the
// ambient test-setup mock's null — anything in this module's graph that still
// reaches Bootstrap directly would otherwise silently no-op.
const { globalsMock } = await vi.hoisted(async () => {
  const { mockGlobalsWithTooltipInstance } = await import(
    "../../../__tests__/helpers/mock-globals.js"
  );
  return await mockGlobalsWithTooltipInstance();
});

vi.mock("../../../lib/globals.js", () => globalsMock);

vi.mock("../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));
vi.mock("../selectors.js", () => ({
  createUTubSelector: vi.fn(() =>
    window.jQuery('<div class="UTubSelector" position="2"></div>'),
  ),
  selectUTub: vi.fn(),
}));
vi.mock("../utils.js", () => ({
  getAllAccessibleUTubNames: vi.fn(() => []),
  getNumOfUTubs: vi.fn(() => 1),
  sameNameWarningHideModal: vi.fn(),
  updateUTubDeckCount: vi.fn(),
}));
vi.mock("../search.js", () => ({
  applyAlternatingUTubSelectorBackground: vi.fn(),
  resetUTubSearch: vi.fn(),
  showUTubSearchBar: vi.fn(),
}));
vi.mock("../deck.js", () => ({
  removeCreateUTubEventListeners: vi.fn(),
}));
vi.mock("../../btns-forms.js", () => ({
  highlightInput: vi.fn(),
}));
vi.mock("../../../store/app-store.js", () => ({
  getState: vi.fn(() => ({ utubs: [] })),
  setState: vi.fn(),
}));

const $ = window.jQuery;

const CREATE_UTUB_HTML = `
  <div id="confirmModal"></div>
  <div id="createUTubWrap"></div>
  <div id="UTubDeck">
    <div class="button-container"></div>
  </div>
  <input id="utubNameCreate" value="NewUTub" />
  <input id="utubDescriptionCreate" value="" />
  <div id="utubNameCreate-error"></div>
  <div id="utubDescriptionCreate-error"></div>
  <button id="utubBtnCreate"></button>
  <button id="utubSubmitBtnCreate"></button>
  <button id="utubCancelBtnCreate"></button>
  <div id="listUTubs">
    <div class="UTubSelector" position="3" utubid="7"></div>
  </div>
`;

describe("createUTubSuccess - first-create search-bar guard", () => {
  beforeEach(() => {
    document.body.innerHTML = CREATE_UTUB_HTML;
    vi.clearAllMocks();
    ($.fn as unknown as Record<string, unknown>).modal = function (
      this: JQuery,
    ) {
      return this;
    };
    vi.mocked(is429Handled).mockReturnValue(false);
    vi.mocked(getState).mockReturnValue({
      utubs: [],
    } as unknown as ReturnType<typeof getState>);
  });

  function triggerCreateSubmit(): void {
    const successXhr = createMockXhr({ status: 200 });
    const chainable = createMockJqXHRChainable({
      done: (cb: unknown) => {
        (
          cb as (
            response: unknown,
            textStatus: unknown,
            xhr: JQuery.jqXHR,
          ) => void
        )(
          { utubID: 99, utubName: "NewUTub", utubDescription: null },
          "success",
          successXhr,
        );
      },
    });
    vi.mocked(ajaxCall).mockReturnValue(chainable);

    setCreateUTubEventListeners();
    $("#utubBtnCreate").trigger("click.createUTub");
    $("#utubSubmitBtnCreate").trigger("click.createUTub");
  }

  it("calls showUTubSearchBar exactly once when this is the first UTub (count === 1)", () => {
    vi.mocked(getNumOfUTubs).mockReturnValue(1);

    triggerCreateSubmit();

    expect(vi.mocked(showUTubSearchBar)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(selectUTub)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(createUTubSelector)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(setState)).toHaveBeenCalled();
    expect(
      vi.mocked(applyAlternatingUTubSelectorBackground),
    ).toHaveBeenCalled();
  });

  it("does not call showUTubSearchBar when more than one UTub already exists (count > 1)", () => {
    vi.mocked(getNumOfUTubs).mockReturnValue(3);

    triggerCreateSubmit();

    expect(vi.mocked(showUTubSearchBar)).not.toHaveBeenCalled();
    expect(vi.mocked(selectUTub)).toHaveBeenCalledTimes(1);
  });
});

describe("createUTub form buttons - hover tooltip hide/restore", () => {
  beforeEach(() => {
    document.body.innerHTML = CREATE_UTUB_HTML;
    vi.clearAllMocks();
    ($.fn as unknown as Record<string, unknown>).modal = function (
      this: JQuery,
    ) {
      return this;
    };
    vi.mocked(is429Handled).mockReturnValue(false);
    vi.mocked(getState).mockReturnValue({
      utubs: [],
    } as unknown as ReturnType<typeof getState>);
  });

  function openCreateUTubForm(): void {
    setCreateUTubEventListeners();
    $("#utubBtnCreate").trigger("click.createUTub");
  }

  function mockCreateUTubFailure(responseJSON: Record<string, unknown>): void {
    const failXhr = createMockXhr({ status: 400, responseJSON });
    vi.mocked(ajaxCall).mockReturnValue(
      createMockJqXHRChainable({
        fail: (callback: unknown) =>
          (callback as (xhr: JQuery.jqXHR) => void)(failXhr),
      }),
    );
  }

  it("hides the tooltip when the submit button is clicked", () => {
    vi.mocked(ajaxCall).mockReturnValue(createMockJqXHRChainable());

    openCreateUTubForm();
    $("#utubSubmitBtnCreate").trigger("click.createUTub");

    // Pins the `this` binding — the handler must target its own button.
    expect(vi.mocked(hideTooltip)).toHaveBeenCalledWith(
      document.getElementById("utubSubmitBtnCreate"),
    );
  });

  it("hides the tooltip when the cancel button is clicked", () => {
    openCreateUTubForm();
    $("#utubCancelBtnCreate").trigger("click.createUTub");

    expect(vi.mocked(hideTooltip)).toHaveBeenCalledWith(
      document.getElementById("utubCancelBtnCreate"),
    );
    expect($("#createUTubWrap").hasClass("hidden")).toBe(true);
  });

  it("routes the restore through restoreTooltipIfStillTargeted when a 400 keeps the form open", () => {
    mockCreateUTubFailure({ message: "UTub with that name already exists" });
    openCreateUTubForm();
    const submitBtn = document.getElementById("utubSubmitBtnCreate")!;

    $("#utubSubmitBtnCreate").trigger("click.createUTub");

    expect(vi.mocked(hideTooltip)).toHaveBeenCalled();
    expect(vi.mocked(restoreTooltipIfStillTargeted)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(restoreTooltipIfStillTargeted)).toHaveBeenCalledWith(submitBtn);
  });

  it("does not attempt a restore on a successful submit", () => {
    // Nothing to restore: success closes the form, so the hidden tooltip should
    // stay hidden rather than be re-shown over a button that is going away.
    vi.mocked(ajaxCall).mockReturnValue(createMockJqXHRChainable());
    openCreateUTubForm();

    $("#utubSubmitBtnCreate").trigger("click.createUTub");

    expect(vi.mocked(hideTooltip)).toHaveBeenCalled();
    expect(vi.mocked(restoreTooltipIfStillTargeted)).not.toHaveBeenCalled();
  });
});
