import { resetStore, setState } from "../../../store/app-store.js";
import { resolveUtubSettings } from "../../../types/settings.js";
import { isMobile } from "../../mobile.js";
import { showPolicyBanner } from "../policy-banner.js";
import {
  DropReason,
  getCardDropReason,
  getDraggedTagID,
  initTagDragDrop,
  syncTagDragState,
} from "../drag-drop.js";

vi.mock("../../mobile.js", () => ({ isMobile: vi.fn(() => false) }));
vi.mock("../policy-banner.js", () => ({ showPolicyBanner: vi.fn() }));
vi.mock("../../urls/tags/combobox.js", () => ({
  submitStagedTags: vi.fn(),
}));

const $ = window.jQuery;
const MIME = "application/x-u4i-tag-id";

function settings({ tag }: { tag: boolean }) {
  return resolveUtubSettings({
    tags: { members_can_tag: tag, members_can_delete_tags: true },
  } as never);
}

function chip(): HTMLElement {
  return document.querySelector("#listTags .tagFilter") as HTMLElement;
}

function pointer({
  type,
  x,
  y,
  pointerType = "mouse",
}: {
  type: string;
  x: number;
  y: number;
  pointerType?: string;
}): void {
  const event = new MouseEvent(type, {
    bubbles: true,
    clientX: x,
    clientY: y,
    buttons: type === "pointerup" ? 0 : 1,
  });
  Object.defineProperty(event, "pointerType", { value: pointerType });
  chip().dispatchEvent(event);
}

function startDrag(): void {
  const event = new Event("dragstart", { bubbles: true, cancelable: true });
  Object.defineProperty(event, "dataTransfer", {
    value: { setData: vi.fn(), setDragImage: vi.fn(), effectAllowed: "" },
  });
  chip().dispatchEvent(event);
}

function setWide(matches: boolean): void {
  window.matchMedia = vi.fn(() => ({
    matches,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  })) as unknown as typeof window.matchMedia;
}

describe("tag drag-drop with tag permissions", () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <div id="URLDeckErrorIndicator"></div>
      <div id="TagDeck"><div id="listTags">
        <div class="tagFilter" data-utub-tag-id="7"><span>alpha</span><div class="tagMenuWrap hidden"></div></div>
      </div></div>
      <div id="listURLs"><div class="urlRow" id="card" utuburlid="3"></div></div>`;
    setWide(true);
    vi.mocked(isMobile).mockReturnValue(false);
    vi.mocked(showPolicyBanner).mockClear();
    resetStore();
    setState({
      activeUTubID: 1,
      isCurrentUserOwner: false,
      isCoCreator: false,
      isCurrentUTubLocked: false,
      multiSelectMode: false,
      settings: settings({ tag: false }),
      tags: [{ id: 7, tagString: "alpha", tagApplied: 0 }],
    });
    initTagDragDrop();
  });

  it("keeps chips non-draggable while !canTag and restores draggable when allowed", () => {
    expect(chip().hasAttribute("draggable")).toBe(false);
    setState({ settings: settings({ tag: true }) });
    expect(chip().getAttribute("draggable")).toBe("true");
    setState({ settings: settings({ tag: false }) });
    expect(chip().hasAttribute("draggable")).toBe(false);
    syncTagDragState();
    expect(chip().hasAttribute("draggable")).toBe(false);
  });

  it("shows the reason once per press after movement past the threshold, no control", () => {
    pointer({ type: "pointerdown", x: 0, y: 0 });
    pointer({ type: "pointermove", x: 2, y: 0 });
    expect(showPolicyBanner).not.toHaveBeenCalled();
    pointer({ type: "pointermove", x: 12, y: 0 });
    pointer({ type: "pointermove", x: 30, y: 0 });
    expect(showPolicyBanner).toHaveBeenCalledTimes(1);
    expect(showPolicyBanner).toHaveBeenCalledWith({
      message: "Only the owner and co-owners can tag URLs in this UTub.",
    });
  });

  it("suppresses a repeat press while the banner is up and shows again once it is gone", () => {
    const banner = document.getElementById(
      "URLDeckErrorIndicator",
    ) as HTMLElement;
    banner.classList.add("URLDeckErrorIndicatorShow");
    pointer({ type: "pointerdown", x: 0, y: 0 });
    pointer({ type: "pointermove", x: 20, y: 0 });
    pointer({ type: "pointerup", x: 20, y: 0 });
    expect(showPolicyBanner).not.toHaveBeenCalled();

    banner.classList.remove("URLDeckErrorIndicatorShow");
    pointer({ type: "pointerdown", x: 0, y: 0 });
    pointer({ type: "pointermove", x: 20, y: 0 });
    expect(showPolicyBanner).toHaveBeenCalledTimes(1);
  });

  it("a press shows once and a new press after pointerup shows again", () => {
    pointer({ type: "pointerdown", x: 0, y: 0 });
    pointer({ type: "pointermove", x: 20, y: 0 });
    pointer({ type: "pointerup", x: 20, y: 0 });
    pointer({ type: "pointerdown", x: 0, y: 0 });
    pointer({ type: "pointermove", x: 20, y: 0 });
    expect(showPolicyBanner).toHaveBeenCalledTimes(2);
  });

  it("a release outside the deck ends the press, so later hovering shows nothing", () => {
    pointer({ type: "pointerdown", x: 0, y: 0 });
    document.body.dispatchEvent(new Event("pointerup", { bubbles: true }));
    pointer({ type: "pointermove", x: 40, y: 0 });
    expect(showPolicyBanner).not.toHaveBeenCalled();

    // Even without a pointerup, a move with no button held ends the press.
    pointer({ type: "pointerdown", x: 0, y: 0 });
    const hover = new MouseEvent("pointermove", {
      bubbles: true,
      clientX: 40,
      buttons: 0,
    });
    Object.defineProperty(hover, "pointerType", { value: "mouse" });
    chip().dispatchEvent(hover);
    expect(showPolicyBanner).not.toHaveBeenCalled();
  });

  it("a plain click shows nothing", () => {
    pointer({ type: "pointerdown", x: 0, y: 0 });
    pointer({ type: "pointerup", x: 0, y: 0 });
    chip().click();
    expect(showPolicyBanner).not.toHaveBeenCalled();
  });

  it("a touch pointer shows nothing", () => {
    pointer({ type: "pointerdown", x: 0, y: 0, pointerType: "touch" });
    pointer({ type: "pointermove", x: 40, y: 0, pointerType: "touch" });
    expect(showPolicyBanner).not.toHaveBeenCalled();
  });

  it("canTag true: the listeners do nothing", () => {
    setState({ settings: settings({ tag: true }) });
    pointer({ type: "pointerdown", x: 0, y: 0 });
    pointer({ type: "pointermove", x: 40, y: 0 });
    expect(showPolicyBanner).not.toHaveBeenCalled();
  });

  it("narrow layout with !canTag shows nothing", () => {
    setWide(false);
    pointer({ type: "pointerdown", x: 0, y: 0 });
    pointer({ type: "pointermove", x: 40, y: 0 });
    expect(showPolicyBanner).not.toHaveBeenCalled();
  });

  it("clears an in-progress drag when canTag flips off and drops nothing", () => {
    setState({ settings: settings({ tag: true }) });
    startDrag();
    expect(getDraggedTagID()).toBe(7);
    document.getElementById("card")!.classList.add("tagDropTarget");
    chip().classList.add("tagDragging");

    setState({ settings: settings({ tag: false }) });

    expect(getDraggedTagID()).toBeNull();
    expect(document.querySelector(".tagDragging")).toBeNull();
    expect(document.querySelector(".tagDropTarget")).toBeNull();
    expect(getCardDropReason({ urlCard: $("#card"), tagID: 7 })).toBe(
      DropReason.BLOCKED,
    );

    const drop = new Event("drop", { bubbles: true, cancelable: true });
    Object.defineProperty(drop, "dataTransfer", {
      value: { types: [MIME], getData: () => "7" },
    });
    document.getElementById("card")!.dispatchEvent(drop);
    return import("../../urls/tags/combobox.js").then(
      ({ submitStagedTags }) => {
        expect(submitStagedTags).not.toHaveBeenCalled();
      },
    );
  });
});
