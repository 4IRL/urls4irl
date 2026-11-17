import { bootstrap } from "../../../../lib/globals.js";
import { resetStore, setState } from "../../../../store/app-store.js";
import { resolveUtubSettings } from "../../../../types/settings.js";
import { isCoarsePointer } from "../../../mobile.js";
import {
  applyURLTagControlReasons,
  initURLTagPolicyControls,
} from "../policy-controls.js";
import {
  disableTagRemovalInURLCard,
  enableTagRemovalInURLCard,
} from "../tags.js";

vi.mock("../../../mobile.js", () => ({
  isMobile: vi.fn(() => false),
  isCoarsePointer: vi.fn(() => false),
}));

const ADD_REASON = "Only the owner and co-owners can tag URLs in this UTub.";
const REMOVE_REASON =
  "Only the owner and co-owners can remove tags in this UTub.";

function settings(canTag: boolean) {
  return resolveUtubSettings({
    tags: { members_can_tag: canTag, members_can_delete_tags: true },
  } as never);
}

function addBtn(): HTMLElement {
  return document.querySelector(".urlTagBtnCreate") as HTMLElement;
}

function removeBtn(): HTMLElement {
  return document.querySelector(".urlTagBtnDelete") as HTMLElement;
}

function tooltipFor(element: HTMLElement): string | undefined {
  return document.getElementById(
    element.getAttribute("aria-describedby") ?? "none",
  )?.textContent as string | undefined;
}

describe("URL card tag controls policy", () => {
  let unsubscribe: () => void;
  const tooltipInstance = { hide: vi.fn(), disable: vi.fn(), enable: vi.fn() };

  beforeEach(() => {
    document.body.innerHTML = `
      <div id="URLDeck"><div id="listURLs">
        <div class="urlRow">
          <div class="urlOptions"><button class="urlTagBtnCreate" type="button">+</button></div>
          <div class="urlTagsContainer"><span class="tagBadge"><button class="urlTagBtnDelete" type="button">x</button></span></div>
        </div>
      </div></div>`;
    window.matchMedia = vi.fn(() => ({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })) as unknown as typeof window.matchMedia;
    vi.mocked(isCoarsePointer).mockReturnValue(false);
    vi.spyOn(bootstrap.Tooltip, "getInstance").mockReturnValue(
      tooltipInstance as never,
    );
    Object.values(tooltipInstance).forEach((spy) => spy.mockClear());
    resetStore();
    setState({
      activeUTubID: 1,
      isCurrentUserOwner: false,
      isCoCreator: false,
      settings: settings(true),
    });
    unsubscribe = initURLTagPolicyControls();
  });

  afterEach(() => {
    unsubscribe();
    vi.restoreAllMocks();
  });

  it("leaves both controls untouched for a permitted plain member", () => {
    expect(addBtn().hasAttribute("aria-disabled")).toBe(false);
    expect(removeBtn().hasAttribute("aria-disabled")).toBe(false);
  });

  it("blocks Add tag and the badge remove with their reasons while Tagging is off", () => {
    setState({ settings: settings(false) });
    expect(addBtn().getAttribute("aria-disabled")).toBe("true");
    expect(removeBtn().getAttribute("aria-disabled")).toBe("true");
    expect(tooltipFor(addBtn())).toBe(ADD_REASON);
    expect(tooltipFor(removeBtn())).toBe(REMOVE_REASON);
  });

  it("never blocks a manager", () => {
    setState({ settings: settings(false), isCoCreator: true });
    expect(addBtn().hasAttribute("aria-disabled")).toBe(false);
  });

  it("shows only the reason tooltip: the Bootstrap tooltip is disabled while blocked and works again once unblocked", () => {
    setState({ settings: settings(false) });
    expect(tooltipInstance.hide).toHaveBeenCalled();
    expect(tooltipInstance.disable).toHaveBeenCalled();
    expect(tooltipInstance.enable).not.toHaveBeenCalled();

    setState({ settings: settings(true) });
    expect(tooltipInstance.enable).toHaveBeenCalledTimes(2);
    expect(addBtn().hasAttribute("aria-disabled")).toBe(false);
    expect(document.querySelector('[role="tooltip"]')).toBeNull();
  });

  it("does not re-enable a Bootstrap tooltip it never disabled", () => {
    setState({ settings: settings(false) });
    setState({ settings: settings(true) });
    tooltipInstance.enable.mockClear();
    applyURLTagControlReasons();
    expect(tooltipInstance.enable).not.toHaveBeenCalled();
  });

  it("a blocked Add tag button runs no click handler", () => {
    const opened = vi.fn();
    addBtn().addEventListener("click", opened);
    setState({ settings: settings(false) });
    addBtn().click();
    expect(opened).not.toHaveBeenCalled();
  });

  it("skips the Cancel-mode button of an open picker", () => {
    addBtn().classList.add("cancel");
    setState({ settings: settings(false) });
    expect(addBtn().hasAttribute("aria-disabled")).toBe(false);
  });

  it("blocks a card or badge added while Tagging is off", async () => {
    setState({ settings: settings(false) });
    const row = document.createElement("div");
    row.innerHTML = `<span class="tagBadge"><button class="urlTagBtnDelete" type="button">x</button></span>`;
    document.getElementById("listURLs")!.append(row);
    const added = row.querySelector(".urlTagBtnDelete") as HTMLElement;
    await vi.waitFor(() =>
      expect(added.getAttribute("aria-disabled")).toBe("true"),
    );
  });

  it("releases document listeners of a blocked control whose card is removed", async () => {
    setState({ settings: settings(false) });
    const removeSpy = vi.spyOn(document, "removeEventListener");
    document.querySelector(".urlRow")!.remove();
    await vi.waitFor(() =>
      expect(removeSpy.mock.calls.some(([type]) => type === "keydown")).toBe(
        true,
      ),
    );
  });

  it("edit-mode hiding still wins over a blocked remove button and leaving edit mode restores the block", () => {
    setState({ settings: settings(false) });
    const urlCard = window.jQuery(".urlRow");
    disableTagRemovalInURLCard(urlCard);
    expect(removeBtn().classList.contains("hidden")).toBe(true);
    enableTagRemovalInURLCard(urlCard);
    expect(removeBtn().classList.contains("hidden")).toBe(false);
    expect(removeBtn().getAttribute("aria-disabled")).toBe("true");
  });

  it("shows a lock on touch and a tap writes the reason note", () => {
    vi.mocked(isCoarsePointer).mockReturnValue(true);
    setState({ settings: settings(false) });
    expect(removeBtn().querySelector(".disabledReasonLock")).not.toBeNull();
    removeBtn().click();
    expect(
      removeBtn().parentElement?.querySelector(".disabledReasonNote")
        ?.textContent,
    ).toBe(REMOVE_REASON);
  });
});
