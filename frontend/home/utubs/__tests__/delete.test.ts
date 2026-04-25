import {
  createMockJqXHRChainable,
  createMockXhr,
} from "../../../__tests__/helpers/mock-jquery.js";
import { ajaxCall, is429Handled } from "../../../lib/ajax.js";
import {
  hideInputsAndUpdateUTubDeck,
  resetUTubDeckIfNoUTubs,
} from "../deck.js";
import { getNumOfUTubs } from "../utils.js";
import { getState, setState } from "../../../store/app-store.js";
import { setDeleteEventListeners } from "../delete.js";

vi.mock("../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));
vi.mock("../deck.js", () => ({
  resetUTubDeckIfNoUTubs: vi.fn(),
  hideInputsAndUpdateUTubDeck: vi.fn(),
}));
vi.mock("../utils.js", () => ({ getNumOfUTubs: vi.fn(() => 0) }));
vi.mock("../search.js", () => ({ resetUTubSearch: vi.fn() }));
vi.mock("../../btns-forms.js", () => ({ hideInputs: vi.fn() }));
vi.mock("../../init.js", () => ({ setUIWhenNoUTubSelected: vi.fn() }));
vi.mock("../../mobile.js", () => ({
  isMobile: vi.fn(() => false),
  setMobileUIWhenUTubNotSelectedOrUTubDeleted: vi.fn(),
}));
vi.mock("../../../lib/event-bus.js", async () => {
  const actual = await vi.importActual<
    typeof import("../../../lib/event-bus.js")
  >("../../../lib/event-bus.js");
  return {
    ...actual,
    emit: vi.fn(),
  };
});
vi.mock("../../../store/app-store.js", () => ({
  getState: vi.fn(() => ({ utubs: [] })),
  setState: vi.fn(),
}));

const $ = window.jQuery;

const DELETE_UTUB_HTML = `
  <div id="confirmModal">
    <div id="confirmModalTitle"></div>
    <div id="confirmModalBody"></div>
    <button id="modalDismiss"></button>
    <button id="modalSubmit"></button>
    <div id="modalRedirect"></div>
  </div>
  <button id="utubBtnDelete"></button>
  <button id="utubTagBtnCreate"></button>
  <div id="listUTubs">
    <div class="UTubSelector" utubid="42"></div>
  </div>
`;

describe("deleteUTubSuccess - last-delete UTub deck dispatch", () => {
  beforeEach(() => {
    document.body.innerHTML = DELETE_UTUB_HTML;
    vi.clearAllMocks();
    ($.fn as unknown as Record<string, unknown>).modal = function (
      this: JQuery,
    ) {
      return this;
    };
    // Override fadeOut so the post-fade callback fires synchronously
    ($.fn as unknown as Record<string, unknown>).fadeOut = function (
      this: JQuery,
      _duration: unknown,
      callback?: () => void,
    ) {
      if (typeof callback === "function") callback();
      return this;
    };
    vi.mocked(is429Handled).mockReturnValue(false);
    vi.mocked(getState).mockReturnValue({
      utubs: [{ id: 42 }],
    } as unknown as ReturnType<typeof getState>);
  });

  function triggerDeleteSubmit(utubID: number): void {
    const successXhr = createMockXhr({ status: 200 });
    const chainable = createMockJqXHRChainable({
      done: (cb: unknown) => {
        (
          cb as (
            _response: unknown,
            _textStatus: unknown,
            xhr: JQuery.jqXHR,
          ) => void
        )({}, "success", successXhr);
      },
    });
    vi.mocked(ajaxCall).mockReturnValue(chainable);

    setDeleteEventListeners(utubID);
    $("#utubBtnDelete").trigger("click.deleteUTub");
    $("#modalSubmit").trigger("click");
  }

  it("calls resetUTubDeckIfNoUTubs and skips hideInputsAndUpdateUTubDeck when no UTubs remain", () => {
    vi.mocked(getNumOfUTubs).mockReturnValue(0);

    triggerDeleteSubmit(42);

    expect(vi.mocked(resetUTubDeckIfNoUTubs)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(hideInputsAndUpdateUTubDeck)).not.toHaveBeenCalled();
    expect(setState).toHaveBeenCalled();
  });

  it("calls hideInputsAndUpdateUTubDeck and skips resetUTubDeckIfNoUTubs when UTubs remain", () => {
    vi.mocked(getNumOfUTubs).mockReturnValue(2);

    triggerDeleteSubmit(42);

    expect(vi.mocked(hideInputsAndUpdateUTubDeck)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(resetUTubDeckIfNoUTubs)).not.toHaveBeenCalled();
  });
});
