import { $ } from "../../../lib/globals.js";
import { AppEvents, emit, on } from "../../../lib/event-bus.js";
import { getState, resetStore, setState } from "../../../store/app-store.js";
import { setUIWhenNoUTubSelected } from "../../init.js";
import { invalidateTrashListRequests, loadTrashList } from "../list.js";
import { buildSelectedUTub, selectUTub } from "../../utubs/selectors.js";
import {
  closeTrash,
  initTrashPanel,
  isTrashOpen,
  openTrash,
} from "../panel.js";

vi.mock("../list.js", () => ({
  loadTrashList: vi.fn(() => Promise.resolve()),
  invalidateTrashListRequests: vi.fn(),
}));

vi.mock("../../init.js", () => ({
  setUIWhenNoUTubSelected: vi.fn(),
}));

// The real URL deck subscribes to UTUB_SELECTED and rebuilds a full deck, which
// this fixture does not provide.
vi.mock("../../urls/deck.js", () => ({
  showURLDeckBannerError: vi.fn(),
}));

vi.mock("../../utubs/selectors.js", () => ({
  selectUTub: vi.fn(),
  buildSelectedUTub: vi.fn(),
}));

const HTML = `
  <div id="listUTubs">
    <div class="UTubSelector active focus" tabindex="0"></div>
    <div class="UTubSelector" tabindex="0"></div>
  </div>
  <div id="TrashSelectorWrap">
    <div id="TrashSelector" class="TrashSelector" role="button" tabindex="0">
      <span id="TrashSelectorCount"></span>
    </div>
  </div>
  <div id="URLDeck"></div>
  <div id="TrashPanel" class="hidden" tabindex="-1">
    <button id="TrashTabUrls"></button>
    <button id="TrashTabUtubs"></button>
    <button id="TrashBtnEmpty"></button>
    <div id="TrashOutcomeBanner" class="urlOutcomeBanner"><span>msg</span></div>
    <p id="TrashUrlsEmptyState" class="hidden"></p>
    <p id="TrashUtubsEmptyState" class="hidden"></p>
  </div>
`;

describe("trash panel", () => {
  beforeEach(() => {
    document.body.innerHTML = HTML;
    resetStore();
    vi.clearAllMocks();
    initTrashPanel();
    vi.spyOn(window.history, "pushState").mockImplementation(() => undefined);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    $("#TrashSelector").off(".trashPanel");
  });

  it("openTrash hides the URL deck, shows the panel and marks the entry active", () => {
    openTrash({ fromHistory: false });

    expect($("#URLDeck").hasClass("hidden")).toBe(true);
    expect($("#TrashPanel").hasClass("hidden")).toBe(false);
    expect($("#TrashSelector").hasClass("active")).toBe(true);
    expect($("#TrashSelector").attr("aria-current")).toBe("page");
    expect(isTrashOpen()).toBe(true);
  });

  it("removes .active from every .UTubSelector and clears the active UTub from the store", () => {
    setState({ activeUTubID: 7, activeUTubName: "Seven", urls: [] });

    openTrash({ fromHistory: false });

    expect($(".UTubSelector.active").length).toBe(0);
    expect(getState().activeUTubID).toBeNull();
    expect(getState().activeUTubName).toBeNull();
    expect(setUIWhenNoUTubSelected).toHaveBeenCalledTimes(1);
  });

  it("emits TRASH_OPENED", () => {
    const handler = vi.fn();
    const unsubscribe = on(AppEvents.TRASH_OPENED, handler);

    openTrash({ fromHistory: false });

    expect(handler).toHaveBeenCalledTimes(1);
    unsubscribe();
  });

  it("never calls selectUTub / buildSelectedUTub", () => {
    openTrash({ fromHistory: false });

    expect(selectUTub).not.toHaveBeenCalled();
    expect(buildSelectedUTub).not.toHaveBeenCalled();
  });

  it("pushes /home?view=trash unless opened from history", () => {
    openTrash({ fromHistory: false });
    expect(window.history.pushState).toHaveBeenCalledWith(
      { trash: true },
      "",
      "/home?view=trash",
    );

    closeTrash();
    vi.mocked(window.history.pushState).mockClear();
    openTrash({ fromHistory: true });
    expect(window.history.pushState).not.toHaveBeenCalled();
  });

  it("loads the Trash list on open and invalidates in-flight loads on close", () => {
    openTrash({ fromHistory: false });
    expect(loadTrashList).toHaveBeenCalledTimes(1);

    closeTrash();
    expect(invalidateTrashListRequests).toHaveBeenCalledTimes(1);
  });

  it("closeTrash restores the URL deck and clears the Trash banner", () => {
    openTrash({ fromHistory: false });
    closeTrash();

    expect($("#URLDeck").hasClass("hidden")).toBe(false);
    expect($("#TrashPanel").hasClass("hidden")).toBe(true);
    expect($("#TrashSelector").hasClass("active")).toBe(false);
    expect($("#TrashSelector").attr("aria-current")).toBeUndefined();
    expect($("#TrashOutcomeBanner").hasClass("hidden")).toBe(true);
    expect($("#TrashOutcomeBanner").children().length).toBe(0);
  });

  it("a UTUB_SELECTED emit closes an open Trash and restores #URLDeck", () => {
    openTrash({ fromHistory: false });

    emit(AppEvents.UTUB_SELECTED, {
      utubID: 1,
      utubName: "One",
      urls: [],
      tags: [],
      members: [],
      utubOwnerID: 1,
      isCurrentUserOwner: true,
      currentUserID: 1,
    });

    expect(isTrashOpen()).toBe(false);
    expect($("#URLDeck").hasClass("hidden")).toBe(false);
  });

  it("clicking the entry opens Trash; re-selecting while open is a no-op", () => {
    $("#TrashSelector").trigger("click");
    expect(isTrashOpen()).toBe(true);
    expect(window.history.pushState).toHaveBeenCalledTimes(1);

    $("#TrashSelector").trigger("click");
    expect(window.history.pushState).toHaveBeenCalledTimes(1);
  });

  it("Enter and Space open Trash (Space is default-prevented); other keys do not", () => {
    const other = $.Event("keydown", { key: "a" });
    $("#TrashSelector").trigger(other);
    expect(isTrashOpen()).toBe(false);

    const space = $.Event("keydown", { key: " " });
    $("#TrashSelector").trigger(space);
    expect(space.isDefaultPrevented()).toBe(true);
    expect(isTrashOpen()).toBe(true);

    closeTrash();
    $("#TrashSelector").trigger($.Event("keydown", { key: "Enter" }));
    expect(isTrashOpen()).toBe(true);
  });
});
