import {
  createMockJqXHRChainable,
  createMockXhr,
} from "../../../__tests__/helpers/mock-jquery.js";
import { ajaxCall, is429Handled } from "../../../lib/ajax.js";
import { createUTubSelector, selectUTub } from "../selectors.js";
import { getNumOfUTubs } from "../utils.js";
import { getState, setState } from "../../../store/app-store.js";
import { setCreateUTubEventListeners } from "../create.js";
import { showUTubSearchBar } from "../search.js";

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
}));
vi.mock("../search.js", () => ({
  resetUTubSearch: vi.fn(),
  showUTubSearchBar: vi.fn(),
}));
vi.mock("../deck.js", () => ({
  removeCreateUTubEventListeners: vi.fn(),
}));
vi.mock("../../btns-forms.js", () => ({ highlightInput: vi.fn() }));
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
  });

  it("does not call showUTubSearchBar when more than one UTub already exists (count > 1)", () => {
    vi.mocked(getNumOfUTubs).mockReturnValue(3);

    triggerCreateSubmit();

    expect(vi.mocked(showUTubSearchBar)).not.toHaveBeenCalled();
    expect(vi.mocked(selectUTub)).toHaveBeenCalledTimes(1);
  });
});
