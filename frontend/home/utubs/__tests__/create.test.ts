import {
  createMockJqXHRChainable,
  createMockXhr,
} from "../../../__tests__/helpers/mock-jquery.js";
import { ajaxCall, is429Handled } from "../../../lib/ajax.js";
import { bootstrap } from "../../../lib/globals.js";
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

// The ambient test-setup Bootstrap mock returns null from getInstance(), which
// would make the tooltip-hide/show guards silent no-ops. Override lib/globals.js
// with a shared tooltip instance so those guards can be asserted on.
const { tooltipInstance } = vi.hoisted(() => ({
  tooltipInstance: {
    setContent: vi.fn(),
    show: vi.fn(),
    hide: vi.fn(),
  },
}));

vi.mock("../../../lib/globals.js", async () => {
  const jquery = (await import("jquery")).default;
  return {
    $: jquery,
    jQuery: jquery,
    getInputValue: (input: string | JQuery) =>
      (typeof input === "string" ? jquery(input) : input).val() as string,
    bootstrap: {
      Tooltip: {
        getInstance: vi.fn(() => tooltipInstance),
        getOrCreateInstance: vi.fn(() => tooltipInstance),
      },
    },
  };
});

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

    expect(tooltipInstance.hide).toHaveBeenCalled();
    // Pins the `this` binding — the handler must target its own button.
    expect(vi.mocked(bootstrap.Tooltip.getInstance)).toHaveBeenCalledWith(
      document.getElementById("utubSubmitBtnCreate"),
    );
  });

  it("hides the tooltip when the cancel button is clicked", () => {
    openCreateUTubForm();
    $("#utubCancelBtnCreate").trigger("click.createUTub");

    expect(tooltipInstance.hide).toHaveBeenCalled();
    expect(vi.mocked(bootstrap.Tooltip.getInstance)).toHaveBeenCalledWith(
      document.getElementById("utubCancelBtnCreate"),
    );
    expect($("#createUTubWrap").hasClass("hidden")).toBe(true);
  });

  it("does not throw on submit or cancel when no tooltip instance exists", () => {
    // Touch devices never construct a Tooltip, so getInstance() returns null and
    // the `?.` guard must no-op without breaking the create flow.
    vi.mocked(bootstrap.Tooltip.getInstance)
      .mockReturnValueOnce(null)
      .mockReturnValueOnce(null);
    vi.mocked(ajaxCall).mockReturnValue(createMockJqXHRChainable());

    openCreateUTubForm();

    expect(() =>
      $("#utubSubmitBtnCreate").trigger("click.createUTub"),
    ).not.toThrow();
    expect(() =>
      $("#utubCancelBtnCreate").trigger("click.createUTub"),
    ).not.toThrow();
    expect(tooltipInstance.hide).not.toHaveBeenCalled();
  });

  it("restores the submit button tooltip when a 400 keeps the form open and the cursor is still on the button", () => {
    mockCreateUTubFailure({ message: "UTub with that name already exists" });
    openCreateUTubForm();
    const submitBtn = document.getElementById("utubSubmitBtnCreate")!;
    // jsdom has no pointer, so `:hover` never matches on its own.
    vi.spyOn(submitBtn, "matches").mockReturnValue(true);

    $("#utubSubmitBtnCreate").trigger("click.createUTub");

    expect(tooltipInstance.hide).toHaveBeenCalled();
    expect(tooltipInstance.show).toHaveBeenCalled();
    expect(vi.mocked(bootstrap.Tooltip.getInstance)).toHaveBeenCalledWith(
      submitBtn,
    );
  });

  it("does not restore the submit button tooltip when the cursor has left the button", () => {
    // The same 400 is reachable from the Enter-key and same-name-modal submit
    // paths, where re-showing would strand a bubble with no mouseleave to come.
    mockCreateUTubFailure({ message: "UTub with that name already exists" });
    openCreateUTubForm();

    $("#utubSubmitBtnCreate").trigger("click.createUTub");

    expect(tooltipInstance.hide).toHaveBeenCalled();
    expect(tooltipInstance.show).not.toHaveBeenCalled();
  });
});
