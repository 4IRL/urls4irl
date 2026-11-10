import { getState, setState } from "../../../store/app-store.js";
import { setRowCountsFromStore } from "../../utubs/row-counts.js";
import { refreshDateAddedBadges } from "../../urls/cards/adder-badge.js";
import {
  cancelCoMemberCandidatesFetch,
  loadCoMemberCandidates,
} from "../co-member-fetch.js";
import { setMemberDeckForUTub } from "../deck.js";
import { applyMemberListVisibility } from "../list-visibility.js";

vi.mock("../../../store/app-store.js", () => ({
  getState: vi.fn(),
  setState: vi.fn(),
}));
vi.mock("../../utubs/row-counts.js", () => ({
  setRowCountsFromStore: vi.fn(),
}));
vi.mock("../../urls/cards/adder-badge.js", () => ({
  refreshDateAddedBadges: vi.fn(),
}));
vi.mock("../co-member-fetch.js", () => ({
  cancelCoMemberCandidatesFetch: vi.fn(),
  loadCoMemberCandidates: vi.fn(),
}));
vi.mock("../deck.js", () => ({
  setMemberDeckForUTub: vi.fn(),
}));
vi.mock("../member-combobox.js", () => ({
  RENDER_KEY: "memberComboboxRender",
}));

const $ = window.jQuery;
const UTUB_ID = 7;

function attachCombobox({ render }: { render: () => void }) {
  document.body.innerHTML = `
    <div id="createMemberWrap"><div class="memberAddComboboxWrap"></div></div>
  `;
  $("#createMemberWrap .memberAddComboboxWrap").data(
    "memberComboboxRender",
    render,
  );
}

function setActiveUTub({ id }: { id: number | null }) {
  vi.mocked(getState).mockReturnValue({ activeUTubID: id } as ReturnType<
    typeof getState
  >);
}

describe("applyMemberListVisibility", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    document.body.innerHTML = "";
    setActiveUTub({ id: UTUB_ID });
  });

  it("reconciles the deck, row counts and adder badges even when nothing flipped", () => {
    applyMemberListVisibility({ wasHidden: false, isHidden: false });

    expect(setMemberDeckForUTub).toHaveBeenCalledTimes(1);
    expect(setRowCountsFromStore).toHaveBeenCalledWith({ utubID: UTUB_ID });
    expect(refreshDateAddedBadges).toHaveBeenCalledTimes(1);
    expect(cancelCoMemberCandidatesFetch).not.toHaveBeenCalled();
    expect(loadCoMemberCandidates).not.toHaveBeenCalled();
    expect(setState).not.toHaveBeenCalled();
  });

  it("skips the row counts when no UTub is active", () => {
    setActiveUTub({ id: null });

    applyMemberListVisibility({ wasHidden: false, isHidden: false });

    expect(setMemberDeckForUTub).toHaveBeenCalledTimes(1);
    expect(setRowCountsFromStore).not.toHaveBeenCalled();
    expect(refreshDateAddedBadges).toHaveBeenCalledTimes(1);
  });

  it("clears the suggestions, marks them loaded and re-renders when the list becomes hidden", () => {
    const render = vi.fn();
    attachCombobox({ render });

    applyMemberListVisibility({ wasHidden: false, isHidden: true });

    expect(cancelCoMemberCandidatesFetch).toHaveBeenCalledTimes(1);
    expect(setState).toHaveBeenCalledWith({
      coMemberCandidates: [],
      coMemberCandidatesLoaded: true,
    });
    expect(render).toHaveBeenCalledTimes(1);
    expect(loadCoMemberCandidates).not.toHaveBeenCalled();
  });

  it("clears the suggestions without a render when hidden and no combobox is open", () => {
    applyMemberListVisibility({ wasHidden: false, isHidden: true });

    expect(cancelCoMemberCandidatesFetch).toHaveBeenCalledTimes(1);
    expect(setState).toHaveBeenCalledWith({
      coMemberCandidates: [],
      coMemberCandidatesLoaded: true,
    });
  });

  it("does nothing more when the list becomes visible and no combobox is open", () => {
    applyMemberListVisibility({ wasHidden: true, isHidden: false });

    expect(setState).not.toHaveBeenCalled();
    expect(loadCoMemberCandidates).not.toHaveBeenCalled();
  });

  it("does not refetch when the list becomes visible with no active UTub", () => {
    setActiveUTub({ id: null });
    attachCombobox({ render: vi.fn() });

    applyMemberListVisibility({ wasHidden: true, isHidden: false });

    expect(setState).not.toHaveBeenCalled();
    expect(loadCoMemberCandidates).not.toHaveBeenCalled();
  });

  it("refetches and renders on settle when the list becomes visible and the combobox is still attached", () => {
    const render = vi.fn();
    attachCombobox({ render });

    applyMemberListVisibility({ wasHidden: true, isHidden: false });

    expect(setState).toHaveBeenCalledWith({ coMemberCandidatesLoaded: false });
    expect(render).toHaveBeenCalledTimes(1);
    expect(loadCoMemberCandidates).toHaveBeenCalledWith(
      UTUB_ID,
      expect.any(Function),
    );

    const onSettle = vi.mocked(loadCoMemberCandidates).mock.calls[0][1];
    onSettle?.();

    expect(render).toHaveBeenCalledTimes(2);
  });

  it("does not render on settle once the combobox has been detached", () => {
    const render = vi.fn();
    attachCombobox({ render });

    applyMemberListVisibility({ wasHidden: true, isHidden: false });
    const wrap = $("#createMemberWrap .memberAddComboboxWrap");
    wrap.detach();
    render.mockClear();

    const onSettle = vi.mocked(loadCoMemberCandidates).mock.calls[0][1];
    onSettle?.();

    expect(render).not.toHaveBeenCalled();
  });
});
