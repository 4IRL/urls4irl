import { resetStore, setState } from "../../../store/app-store.js";
import { resolveUtubSettings } from "../../../types/settings.js";
import { setDisabledReason } from "../../../lib/disabled-reason.js";
import { learnPolicyOff } from "../../utubs/policy.js";
import { isMobile } from "../../mobile.js";
import { isTagSheetOpen } from "../sheet.js";
import {
  dismissAddTagTipIfActive,
  maybeShowNextTip,
} from "../../onboarding/nudges.js";
import {
  applyTagDeckControlReasons,
  initTagDeckPolicyControls,
} from "../policy-controls.js";

vi.mock("../../mobile.js", () => ({
  isMobile: vi.fn(() => false),
  isCoarsePointer: vi.fn(() => false),
}));

vi.mock("../sheet.js", () => ({
  isTagSheetOpen: vi.fn(() => false),
}));

vi.mock("../../onboarding/nudges.js", () => ({
  dismissAddTagTipIfActive: vi.fn(),
  maybeShowNextTip: vi.fn(),
}));

vi.mock("../../urls/deck.js", () => ({
  showURLDeckBannerError: vi.fn(),
}));

const CREATE_REASON =
  "Only the owner and co-owners can create tags in this UTub.";
const DELETE_REASON =
  "Only the owner and co-owners can delete tags in this UTub.";

function settings({ tag, del }: { tag: boolean; del: boolean }) {
  return resolveUtubSettings({
    tags: { members_can_tag: tag, members_can_delete_tags: del },
  } as never);
}

function create(): HTMLElement {
  return document.getElementById("utubTagBtnCreate") as HTMLElement;
}

function pencil(): HTMLElement {
  return document.getElementById("utubTagBtnUpdateAllOpen") as HTMLElement;
}

function openMenu(): void {
  document.getElementById("utubTagStandardBtns")!.classList.add("hidden");
  document.querySelectorAll("#listTags .tagMenuWrap").forEach((wrap) => {
    wrap.classList.remove("hidden");
  });
}

function menuOpen(): boolean {
  return (
    document.querySelectorAll("#listTags .tagMenuWrap:not(.hidden)").length > 0
  );
}

describe("initTagDeckPolicyControls", () => {
  let unsubscribe: () => void;

  beforeEach(() => {
    document.body.innerHTML = `
      <div id="URLDeckErrorIndicator"></div>
      <div id="TagDeck">
        <div id="utubTagStandardBtns">
          <button id="utubTagBtnCreate">+</button>
          <button id="utubTagBtnUpdateAllOpen">edit</button>
        </div>
        <div id="utubTagCloseUpdateTagBtnContainer" class="hidden"></div>
        <div id="listTags">
          <div class="tagFilter" data-utub-tag-id="7"><div class="tagMenuWrap hidden"></div></div>
        </div>
      </div>
      <div id="tagSheetBody"></div>`;
    window.matchMedia = vi.fn(() => ({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })) as unknown as typeof window.matchMedia;
    vi.mocked(isMobile).mockReturnValue(false);
    vi.mocked(isTagSheetOpen).mockReturnValue(false);
    vi.mocked(dismissAddTagTipIfActive).mockClear();
    vi.mocked(maybeShowNextTip).mockClear();
    resetStore();
    setState({
      activeUTubID: 1,
      isCurrentUserOwner: false,
      isCoCreator: false,
      settings: settings({ tag: true, del: true }),
    });
    unsubscribe = initTagDeckPolicyControls();
  });

  afterEach(() => {
    unsubscribe();
    setDisabledReason({ element: create(), reason: null });
    setDisabledReason({ element: pencil(), reason: null });
  });

  it("leaves both controls enabled for a permitted plain member", () => {
    expect(create().hasAttribute("aria-disabled")).toBe(false);
    expect(pencil().hasAttribute("aria-disabled")).toBe(false);
  });

  it("blocks create and the pencil with their reasons when Tagging is off", () => {
    setState({ settings: settings({ tag: false, del: true }) });
    expect(create().getAttribute("aria-disabled")).toBe("true");
    expect(pencil().getAttribute("aria-disabled")).toBe("true");
    expect(
      document.querySelector(`#utubTagBtnCreate ~ [role="tooltip"]`)
        ?.textContent,
    ).toBe(CREATE_REASON);
    expect(
      document.querySelector(`#utubTagBtnUpdateAllOpen ~ [role="tooltip"]`)
        ?.textContent,
    ).toBe(DELETE_REASON);
    expect(dismissAddTagTipIfActive).toHaveBeenCalled();
  });

  it("a blocked pencil opens no menu on click or Enter", () => {
    const opened = vi.fn();
    pencil().addEventListener("click", opened);
    setState({ settings: settings({ tag: true, del: false }) });
    pencil().click();
    pencil().dispatchEvent(
      new KeyboardEvent("keydown", { key: "Enter", cancelable: true }),
    );
    expect(opened).not.toHaveBeenCalled();
    expect(menuOpen()).toBe(false);
  });

  it("blocks only the pencil when only Delete is off", () => {
    setState({ settings: settings({ tag: true, del: false }) });
    expect(create().hasAttribute("aria-disabled")).toBe(false);
    expect(pencil().getAttribute("aria-disabled")).toBe("true");
  });

  it("never blocks a manager", () => {
    setState({
      isCurrentUserOwner: true,
      settings: settings({ tag: false, del: false }),
    });
    expect(create().hasAttribute("aria-disabled")).toBe(false);
    expect(pencil().hasAttribute("aria-disabled")).toBe(false);
  });

  it("restores the controls and re-shows the tip when the policy re-enables", () => {
    setState({ settings: settings({ tag: false, del: false }) });
    setState({ settings: settings({ tag: true, del: true }) });
    expect(create().hasAttribute("aria-disabled")).toBe(false);
    expect(pencil().hasAttribute("aria-disabled")).toBe(false);
    expect(document.querySelector(".disabledReasonNote")).toBeNull();
    expect(maybeShowNextTip).toHaveBeenCalledTimes(1);
  });

  it("after a delete refusal is learned, the pencil is blocked, the menu closes and create stays enabled", () => {
    openMenu();
    learnPolicyOff({ utubID: 1, key: "tags.members_can_delete_tags" });
    expect(pencil().getAttribute("aria-disabled")).toBe("true");
    expect(create().hasAttribute("aria-disabled")).toBe(false);
    expect(menuOpen()).toBe(false);
  });

  it("after a create refusal is learned, create and the pencil are both blocked", () => {
    learnPolicyOff({ utubID: 1, key: "tags.members_can_tag" });
    expect(create().getAttribute("aria-disabled")).toBe("true");
    expect(pencil().getAttribute("aria-disabled")).toBe("true");
  });

  it("blocks nothing while no UTub is active", () => {
    setState({
      activeUTubID: null,
      settings: settings({ tag: false, del: false }),
    });
    expect(create().hasAttribute("aria-disabled")).toBe(false);
  });

  it("a delete flip with the menu open closes it and focuses the pencil", () => {
    openMenu();
    pencil().blur();
    setState({ settings: settings({ tag: true, del: false }) });
    expect(menuOpen()).toBe(false);
    expect(document.activeElement).toBe(pencil());
    expect(
      document
        .getElementById("utubTagStandardBtns")!
        .classList.contains("hidden"),
    ).toBe(false);
  });

  it("a Tagging flip with the menu open also closes it and focuses the pencil", () => {
    openMenu();
    setState({ settings: settings({ tag: false, del: true }) });
    expect(menuOpen()).toBe(false);
    expect(document.activeElement).toBe(pencil());
  });

  it("on mobile with the sheet closed it closes the menu without focusing the pencil", () => {
    vi.mocked(isMobile).mockReturnValue(true);
    vi.mocked(isTagSheetOpen).mockReturnValue(false);
    const focus = vi.spyOn(pencil(), "focus");
    openMenu();
    setState({ settings: settings({ tag: true, del: false }) });
    expect(menuOpen()).toBe(false);
    expect(focus).not.toHaveBeenCalled();
  });

  it("on mobile with the sheet open it focuses the pencil", () => {
    vi.mocked(isMobile).mockReturnValue(true);
    vi.mocked(isTagSheetOpen).mockReturnValue(true);
    openMenu();
    setState({ settings: settings({ tag: true, del: false }) });
    expect(document.activeElement).toBe(pencil());
  });

  it("a flip with the menu closed does not move focus", () => {
    const focus = vi.spyOn(pencil(), "focus");
    setState({ settings: settings({ tag: true, del: false }) });
    expect(focus).not.toHaveBeenCalled();
  });

  it("keeps the same blocked state on controls relocated into the sheet and back", () => {
    setState({ settings: settings({ tag: false, del: false }) });
    // The whole #TagDeck moves (sheet.ts relocateTagDeckForViewport).
    const sheetBody = document.getElementById("tagSheetBody") as HTMLElement;
    const deck = document.getElementById("TagDeck") as HTMLElement;
    const home = deck.parentElement as HTMLElement;
    sheetBody.appendChild(deck);
    applyTagDeckControlReasons();
    expect(create().getAttribute("aria-disabled")).toBe("true");
    expect(pencil().getAttribute("aria-disabled")).toBe("true");
    expect(sheetBody.querySelectorAll(".disabledReasonNote")).toHaveLength(2);
    expect(sheetBody.querySelectorAll('[role="tooltip"]')).toHaveLength(2);
    home.appendChild(deck);
    expect(create().getAttribute("aria-disabled")).toBe("true");
    expect(document.querySelectorAll(".disabledReasonNote")).toHaveLength(2);
  });
});
