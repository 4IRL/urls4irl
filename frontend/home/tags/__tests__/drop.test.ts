// Marks this file as a module so its top-level names do not collide with the
// sibling drag-drop.test.ts (which has no imports).
export {};

const submitStagedTagsMock = vi.hoisted(() => vi.fn());
const selectURLCardMock = vi.hoisted(() => vi.fn());
const showURLOutcomeBannerMock = vi.hoisted(() => vi.fn());

vi.mock("../../mobile.js", () => ({ isMobile: vi.fn(() => false) }));
vi.mock("../../urls/tags/combobox.js", () => ({
  submitStagedTags: submitStagedTagsMock,
}));
vi.mock("../../urls/cards/selection.js", () => ({
  selectURLCard: selectURLCardMock,
}));
vi.mock("../../urls/outcome-banner.js", () => ({
  showURLOutcomeBanner: showURLOutcomeBannerMock,
}));

const MIME = "application/x-u4i-tag-id";
const ADD_HINT_ALPHA = 'Add "alpha" to this URL';
const HAS_HINT_ALPHA = 'Already has "alpha"';
const LIMIT_HINT = "Maximum 20 tags reached — remove a tag to add more";

const PAGE_HTML = `
  <div id="TagDeck">
    <div id="listTags">
      <div class="tagFilter" data-utub-tag-id="7"><span>alpha</span><div class="tagMenuWrap hidden"></div></div>
      <div class="tagFilter" data-utub-tag-id="9"><span>beta</span><div class="tagMenuWrap hidden"></div></div>
    </div>
  </div>
  <div id="listURLs">
    <div class="urlRow" id="cardA" utuburlid="1" filterable="true" data-utub-url-tag-ids="">
      <div class="urlTagsContainer"></div>
      <span class="urlTitle">Title A</span>
      <span class="cardChild">child</span>
      <div class="urlTagComboboxWrap hidden"></div>
    </div>
    <div class="urlRow" id="cardB" utuburlid="2" filterable="true" data-utub-url-tag-ids="7">
      <div class="urlTagsContainer"><span class="tagBadge" data-utub-tag-id="7">alpha</span></div>
      <div class="urlTagComboboxWrap hidden"></div>
    </div>
    <div class="urlRow" id="cardC" utuburlid="3" filterable="true" data-utub-url-tag-ids="">
      <div class="urlTagsContainer"></div>
      <div class="urlTagComboboxWrap hidden"></div>
    </div>
  </div>
`;

type DragModule = typeof import("../drag-drop.js");
type StoreModule = typeof import("../../../store/app-store.js");
type TrackingModule = typeof import("../../../lib/modal-tracking.js");

let drag: DragModule;
let store: StoreModule;
let tracking: TrackingModule;

function el(id: string): HTMLElement {
  return document.getElementById(id) as HTMLElement;
}

function chip(tagID: number): HTMLElement {
  return document.querySelector(
    `#listTags .tagFilter[data-utub-tag-id="${tagID}"]`,
  ) as HTMLElement;
}

function startDrag(tagID: number): void {
  const dataTransfer = {
    setData: vi.fn(),
    setDragImage: vi.fn(),
    effectAllowed: "uninitialized",
  };
  const event = new Event("dragstart", { bubbles: true, cancelable: true });
  Object.defineProperty(event, "dataTransfer", { value: dataTransfer });
  chip(tagID).dispatchEvent(event);
}

interface FiredDrag {
  event: Event;
  dataTransfer: { types: string[]; dropEffect: string; getData: () => string };
}

function fire({
  type,
  target,
  types = [MIME],
  payload = "7",
  relatedTarget = null,
}: {
  type: string;
  target: Element;
  types?: string[];
  payload?: string;
  relatedTarget?: Element | null;
}): FiredDrag {
  const dataTransfer = {
    types,
    dropEffect: "move",
    getData: vi.fn(() => payload),
  };
  const event = new Event(type, { bubbles: true, cancelable: true });
  Object.defineProperty(event, "dataTransfer", { value: dataTransfer });
  Object.defineProperty(event, "relatedTarget", { value: relatedTarget });
  target.dispatchEvent(event);
  return { event, dataTransfer };
}

async function flush(): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, 0));
}

function expectNoMarks(): void {
  expect(document.querySelector(".tagDropTarget")).toBeNull();
  expect(document.querySelector(".tagDropInvalid")).toBeNull();
  expect(document.querySelector("[data-drop-hint]")).toBeNull();
}

describe("tag drag-and-drop drop target", () => {
  beforeEach(async () => {
    vi.resetModules();
    submitStagedTagsMock.mockReset();
    submitStagedTagsMock.mockResolvedValue("applied");
    selectURLCardMock.mockReset();
    showURLOutcomeBannerMock.mockReset();
    document.body.innerHTML = PAGE_HTML;

    window.matchMedia = vi.fn(() => ({
      matches: true,
      addEventListener: vi.fn(),
    })) as unknown as typeof window.matchMedia;

    store = await import("../../../store/app-store.js");
    tracking = await import("../../../lib/modal-tracking.js");
    store.setState({
      activeUTubID: 1,
      isCurrentUTubLocked: false,
      multiSelectMode: false,
      tags: [
        { id: 7, tagString: "alpha", tagApplied: 1 },
        { id: 9, tagString: "beta", tagApplied: 0 },
      ],
    });
    tracking.clearOpenForm();

    drag = await import("../drag-drop.js");
    drag.initTagDragDrop();
  });

  afterEach(() => {
    document.body.innerHTML = "";
    vi.restoreAllMocks();
  });

  describe("dragenter / dragover", () => {
    it.each(["dragenter", "dragover"])(
      "%s on a valid card accepts the drag, rings it and sets the add hint",
      (type) => {
        startDrag(7);
        const { event, dataTransfer } = fire({ type, target: el("cardA") });

        expect(event.defaultPrevented).toBe(true);
        expect(dataTransfer.dropEffect).toBe("copy");
        expect(el("cardA").classList.contains("tagDropTarget")).toBe(true);
        expect(el("cardA").getAttribute("data-drop-hint")).toBe(ADD_HINT_ALPHA);
      },
    );

    it("rings the closest card when the event comes from a child element", () => {
      startDrag(7);
      fire({
        type: "dragover",
        target: el("cardA").querySelector(".cardChild")!,
      });
      expect(el("cardA").classList.contains("tagDropTarget")).toBe(true);
    });

    it("dims an already-tagged card with the has-tag hint and refuses the drop", () => {
      startDrag(7);
      const { event, dataTransfer } = fire({
        type: "dragover",
        target: el("cardB"),
      });

      expect(event.defaultPrevented).toBe(false);
      expect(dataTransfer.dropEffect).toBe("none");
      expect(el("cardB").classList.contains("tagDropInvalid")).toBe(true);
      expect(el("cardB").classList.contains("tagDropTarget")).toBe(false);
      expect(el("cardB").getAttribute("data-drop-hint")).toBe(HAS_HINT_ALPHA);
    });

    it("dims an at-limit card with the tag-limit hint and refuses the drop", () => {
      const ids = Array.from({ length: 20 }, (_, index) => index + 100);
      el("cardC").setAttribute("data-utub-url-tag-ids", ids.join(","));
      startDrag(7);
      const { event, dataTransfer } = fire({
        type: "dragover",
        target: el("cardC"),
      });

      expect(event.defaultPrevented).toBe(false);
      expect(dataTransfer.dropEffect).toBe("none");
      expect(el("cardC").classList.contains("tagDropInvalid")).toBe(true);
      expect(el("cardC").getAttribute("data-drop-hint")).toBe(LIMIT_HINT);
    });

    it("moves the highlight and hint between cards without leaving residue", () => {
      startDrag(7);
      fire({ type: "dragover", target: el("cardA") });
      fire({ type: "dragover", target: el("cardB") });

      expect(el("cardA").classList.contains("tagDropTarget")).toBe(false);
      expect(el("cardA").hasAttribute("data-drop-hint")).toBe(false);
      expect(el("cardB").classList.contains("tagDropInvalid")).toBe(true);
      expect(el("cardB").getAttribute("data-drop-hint")).toBe(HAS_HINT_ALPHA);
    });

    it("clears the hint and ring when leaving the card, but not when crossing its children", () => {
      startDrag(7);
      fire({ type: "dragover", target: el("cardA") });

      fire({
        type: "dragleave",
        target: el("cardA"),
        relatedTarget: el("cardA").querySelector(".cardChild"),
      });
      expect(el("cardA").classList.contains("tagDropTarget")).toBe(true);

      fire({ type: "dragleave", target: el("cardA"), relatedTarget: null });
      expectNoMarks();
    });

    it("keeps the entered card's marks when dragenter on it precedes dragleave on the old card", () => {
      startDrag(7);
      fire({ type: "dragenter", target: el("cardA") });
      fire({ type: "dragenter", target: el("cardC") });
      fire({
        type: "dragleave",
        target: el("cardA"),
        relatedTarget: el("cardC").querySelector(".urlTagsContainer"),
      });

      expect(el("cardC").classList.contains("tagDropTarget")).toBe(true);
      expect(el("cardC").getAttribute("data-drop-hint")).toBe(ADD_HINT_ALPHA);
      expect(el("cardA").classList.contains("tagDropTarget")).toBe(false);
      expect(el("cardA").hasAttribute("data-drop-hint")).toBe(false);
    });

    it("strips only the old card, including its ghost, when leaving into another card", () => {
      el("cardA").setAttribute("urlSelected", "true");
      el("cardC").setAttribute("urlSelected", "true");
      startDrag(7);
      fire({ type: "dragenter", target: el("cardA") });
      fire({ type: "dragenter", target: el("cardC") });
      fire({
        type: "dragleave",
        target: el("cardA"),
        relatedTarget: el("cardC"),
      });

      expect(el("cardA").querySelector(".tagDropGhost")).toBeNull();
      expect(el("cardC").querySelectorAll(".tagDropGhost")).toHaveLength(1);
      expect(el("cardC").classList.contains("tagDropTarget")).toBe(true);
    });

    it("clears every mark when leaving to outside any card", () => {
      startDrag(7);
      fire({ type: "dragover", target: el("cardA") });
      fire({
        type: "dragleave",
        target: el("cardA"),
        relatedTarget: el("listURLs"),
      });
      expectNoMarks();
    });

    it("clears the ring and hint when the drag ends", () => {
      startDrag(7);
      fire({ type: "dragover", target: el("cardA") });
      document.dispatchEvent(new Event("dragend", { bubbles: true }));

      expectNoMarks();
      expect(drag.getDraggedTagID()).toBeNull();
    });

    it("gives no ring or hint over a non-card area", () => {
      startDrag(7);
      const { event, dataTransfer } = fire({
        type: "dragover",
        target: el("listURLs"),
      });
      expect(event.defaultPrevented).toBe(false);
      expect(dataTransfer.dropEffect).toBe("none");
      expectNoMarks();
    });

    it("ignores a foreign drag without the tag MIME type", () => {
      startDrag(7);
      const { event } = fire({
        type: "dragover",
        target: el("cardA"),
        types: ["text/plain", "Files"],
      });
      expect(event.defaultPrevented).toBe(false);
      expectNoMarks();
    });

    it("clears stale drag state on a MIME-less dragenter", () => {
      startDrag(7);
      fire({ type: "dragover", target: el("cardA") });
      fire({
        type: "dragenter",
        target: el("cardA"),
        types: ["text/uri-list"],
      });

      expectNoMarks();
      expect(drag.getDraggedTagID()).toBeNull();
    });

    it("ignores a tag-MIME drag when draggedTagID is null (foreign tab)", () => {
      const { event } = fire({ type: "dragover", target: el("cardA") });
      expect(event.defaultPrevented).toBe(false);
      expectNoMarks();
    });
  });

  describe("ghost pill on a selected card", () => {
    const ghosts = () => document.querySelectorAll(".tagDropGhost");

    beforeEach(() => {
      el("cardA").setAttribute("urlSelected", "true");
      el("cardB").setAttribute("urlSelected", "true");
    });

    it("adds exactly one aria-hidden ghost labelled with the tag, kept across repeated dragover", () => {
      startDrag(7);
      for (let index = 0; index < 3; index++) {
        fire({ type: "dragover", target: el("cardA") });
      }

      expect(ghosts()).toHaveLength(1);
      const ghost = ghosts()[0] as HTMLElement;
      expect(ghost.parentElement?.classList.contains("urlTagsContainer")).toBe(
        true,
      );
      expect(ghost.textContent).toBe("alpha");
      expect(ghost.getAttribute("aria-hidden")).toBe("true");
      expect(ghost.classList.contains("tagBadge")).toBe(false);
      expect(ghost.hasAttribute("data-utub-tag-id")).toBe(false);
      expect(el("cardA").getAttribute("data-utub-url-tag-ids")).toBe("");
      expect(el("cardA").getAttribute("data-drop-hint")).toBe(ADD_HINT_ALPHA);
    });

    it("appends the ghost after existing pills", () => {
      el("cardC").setAttribute("urlSelected", "true");
      el("cardC")
        .querySelector(".urlTagsContainer")!
        .insertAdjacentHTML(
          "beforeend",
          '<span class="tagBadge" data-utub-tag-id="9">beta</span>',
        );
      startDrag(7);
      fire({ type: "dragover", target: el("cardC") });

      const container = el("cardC").querySelector(".urlTagsContainer")!;
      expect(
        container.lastElementChild?.classList.contains("tagDropGhost"),
      ).toBe(true);
      expect(container.querySelectorAll(".tagBadge")).toHaveLength(1);
    });

    it("removes the ghost on dragleave, dragend and drop, and moves it between cards", () => {
      startDrag(7);
      fire({ type: "dragover", target: el("cardA") });
      fire({ type: "dragleave", target: el("cardA"), relatedTarget: null });
      expect(ghosts()).toHaveLength(0);

      fire({ type: "dragover", target: el("cardA") });
      el("cardC").setAttribute("urlSelected", "true");
      fire({ type: "dragover", target: el("cardC") });
      expect(ghosts()).toHaveLength(1);
      expect(el("cardA").querySelector(".tagDropGhost")).toBeNull();

      document.dispatchEvent(new Event("dragend", { bubbles: true }));
      expect(ghosts()).toHaveLength(0);

      startDrag(7);
      fire({ type: "dragover", target: el("cardA") });
      fire({ type: "drop", target: el("cardA") });
      expect(ghosts()).toHaveLength(0);
    });

    it("emphasizes the existing pill for HAS_TAG and clears it afterwards", () => {
      startDrag(7);
      fire({ type: "dragover", target: el("cardB") });
      fire({ type: "dragover", target: el("cardB") });

      expect(ghosts()).toHaveLength(0);
      const pill = el("cardB").querySelector(".tagBadge")!;
      expect(pill.classList.contains("tagDropExisting")).toBe(true);
      expect(document.querySelectorAll(".tagDropExisting")).toHaveLength(1);
      expect(el("cardB").getAttribute("data-drop-hint")).toBe(HAS_HINT_ALPHA);

      document.dispatchEvent(new Event("dragend", { bubbles: true }));
      expect(document.querySelector(".tagDropExisting")).toBeNull();
    });

    it("adds no ghost on an at-limit selected card but keeps the hint attribute", () => {
      const ids = Array.from({ length: 20 }, (_, index) => index + 100);
      el("cardC").setAttribute("urlSelected", "true");
      el("cardC").setAttribute("data-utub-url-tag-ids", ids.join(","));
      startDrag(7);
      fire({ type: "dragover", target: el("cardC") });

      expect(ghosts()).toHaveLength(0);
      expect(el("cardC").getAttribute("data-drop-hint")).toBe(LIMIT_HINT);
    });

    it("keeps the hint and adds no ghost or emphasis on a collapsed card", () => {
      el("cardA").setAttribute("urlSelected", "false");
      el("cardB").setAttribute("urlSelected", "false");
      startDrag(7);
      fire({ type: "dragover", target: el("cardA") });
      expect(el("cardA").getAttribute("data-drop-hint")).toBe(ADD_HINT_ALPHA);
      expect(ghosts()).toHaveLength(0);

      fire({ type: "dragover", target: el("cardB") });
      expect(document.querySelector(".tagDropExisting")).toBeNull();
    });
  });

  describe("card validity", () => {
    const urlCard = () => window.jQuery("#cardA");

    it("returns valid, has-tag and at-limit for the affirmative cases", () => {
      expect(drag.getCardDropReason({ urlCard: urlCard(), tagID: 7 })).toBe(
        "valid",
      );
      expect(
        drag.getCardDropReason({ urlCard: window.jQuery("#cardB"), tagID: 7 }),
      ).toBe("has-tag");
      el("cardC").setAttribute(
        "data-utub-url-tag-ids",
        Array.from({ length: 20 }, (_, index) => index + 100).join(","),
      );
      expect(
        drag.getCardDropReason({ urlCard: window.jQuery("#cardC"), tagID: 7 }),
      ).toBe("at-limit");
    });

    const blockers: Array<[string, () => void]> = [
      ["locked UTub", () => store.setState({ isCurrentUTubLocked: true })],
      ["no active UTub", () => store.setState({ activeUTubID: null })],
      ["multi-select mode", () => store.setState({ multiSelectMode: true })],
      ["an open form elsewhere", () => tracking.setOpenForm("tag_create")],
      [
        "a visible combobox on another card with no open-form token",
        () =>
          el("cardC")
            .querySelector(".urlTagComboboxWrap")!
            .classList.remove("hidden"),
      ],
      [
        "a visible combobox on the target card",
        () =>
          el("cardA")
            .querySelector(".urlTagComboboxWrap")!
            .classList.remove("hidden"),
      ],
      [
        "an open title edit on the card",
        () => {
          const wrap = document.createElement("div");
          wrap.className = "updateUrlTitleWrap";
          el("cardA").appendChild(wrap);
        },
      ],
      [
        "a hidden (unfilterable) card",
        () => el("cardA").setAttribute("filterable", "false"),
      ],
      [
        "a non-searchable card",
        () => el("cardA").setAttribute("searchable", "false"),
      ],
    ];

    it.each(blockers)("is blocked with %s", (_label, arrange) => {
      arrange();
      expect(drag.getCardDropReason({ urlCard: urlCard(), tagID: 7 })).toBe(
        "blocked",
      );
    });

    it("is blocked on every card, with no ring, when any form is open", () => {
      tracking.setOpenForm("tag_create");
      startDrag(7);
      const { event, dataTransfer } = fire({
        type: "dragover",
        target: el("cardC"),
      });
      expect(event.defaultPrevented).toBe(false);
      expect(dataTransfer.dropEffect).toBe("none");
      expectNoMarks();
    });

    it("blocks a card that matches no single element", () => {
      expect(
        drag.getCardDropReason({ urlCard: window.jQuery("#nope"), tagID: 7 }),
      ).toBe("blocked");
    });
  });

  describe("drop", () => {
    it("sends the dragged tag once, with the captured utubID, even though draggedTagID is null afterwards", () => {
      startDrag(7);
      const { event } = fire({ type: "drop", target: el("cardA") });

      expect(event.defaultPrevented).toBe(true);
      expect(submitStagedTagsMock).toHaveBeenCalledTimes(1);
      const args = submitStagedTagsMock.mock.calls[0][0];
      expect(args.utubID).toBe(1);
      expect(args.utubUrlID).toBe(1);
      expect(args.stagedStrings).toEqual(["alpha"]);
      expect(args.applySource).toBe("drag");
      expect(args.urlCard.is(el("cardA"))).toBe(true);
      expect(drag.getDraggedTagID()).toBeNull();
      expectNoMarks();
    });

    it("aborts without a request when getData differs from draggedTagID", () => {
      startDrag(7);
      fire({ type: "drop", target: el("cardA"), payload: "9" });
      expect(submitStagedTagsMock).not.toHaveBeenCalled();
    });

    it("aborts without a request when the payload is not a number", () => {
      startDrag(7);
      fire({ type: "drop", target: el("cardA"), payload: "abc" });
      expect(submitStagedTagsMock).not.toHaveBeenCalled();
    });

    it("ignores a drop without the tag MIME type", () => {
      startDrag(7);
      const { event } = fire({
        type: "drop",
        target: el("cardA"),
        types: ["text/plain"],
      });
      expect(event.defaultPrevented).toBe(false);
      expect(submitStagedTagsMock).not.toHaveBeenCalled();
    });

    it("aborts without a request when draggedTagID is null", () => {
      fire({ type: "drop", target: el("cardA") });
      expect(submitStagedTagsMock).not.toHaveBeenCalled();
    });

    it("aborts without a request for an unknown tag ID (stale store)", () => {
      startDrag(7);
      store.setState({ tags: [] });
      fire({ type: "drop", target: el("cardA") });
      expect(submitStagedTagsMock).not.toHaveBeenCalled();
    });

    it("sends nothing for a drop outside any card and leaves no stale state", () => {
      startDrag(7);
      fire({ type: "dragover", target: el("cardA") });
      fire({ type: "drop", target: el("listURLs") });
      expect(submitStagedTagsMock).not.toHaveBeenCalled();
      expectNoMarks();
      expect(drag.getDraggedTagID()).toBeNull();
    });

    it("clears the drag state for a drop that lands outside #listURLs", () => {
      startDrag(7);
      fire({ type: "dragover", target: el("cardA") });
      fire({ type: "drop", target: document.body });
      expect(submitStagedTagsMock).not.toHaveBeenCalled();
      expectNoMarks();
      expect(drag.getDraggedTagID()).toBeNull();
    });

    it("clears the ring and state after a refused (already-tagged) drop", () => {
      startDrag(7);
      fire({ type: "dragover", target: el("cardB") });
      fire({ type: "drop", target: el("cardB") });
      expectNoMarks();
      expect(drag.getDraggedTagID()).toBeNull();
    });

    it("re-validates at drop time: an already-tagged card sends nothing", () => {
      startDrag(7);
      fire({ type: "drop", target: el("cardB") });
      expect(submitStagedTagsMock).not.toHaveBeenCalled();
    });

    it("re-validates at drop time: a form opened after the last dragover sends nothing", () => {
      startDrag(7);
      fire({ type: "dragover", target: el("cardA") });
      tracking.setOpenForm("tag_create");
      fire({ type: "drop", target: el("cardA") });
      expect(submitStagedTagsMock).not.toHaveBeenCalled();
    });

    it("sends nothing when another card shows a leftover combobox (open-form token already cleared)", () => {
      el("cardC")
        .querySelector(".urlTagComboboxWrap")!
        .classList.remove("hidden");
      startDrag(7);
      fire({ type: "drop", target: el("cardA") });
      expect(submitStagedTagsMock).not.toHaveBeenCalled();
    });

    it("sends nothing in a locked UTub or multi-select mode", () => {
      startDrag(7);
      store.setState({ isCurrentUTubLocked: true });
      fire({ type: "drop", target: el("cardA") });
      store.setState({ isCurrentUTubLocked: false, multiSelectMode: true });
      fire({ type: "drop", target: el("cardA") });
      expect(submitStagedTagsMock).not.toHaveBeenCalled();
    });
  });

  describe("one drop at a time", () => {
    it("blocks every card and ignores a second drop on any card while one is pending", async () => {
      let resolveFirst: (outcome: string) => void = () => {};
      submitStagedTagsMock.mockReturnValueOnce(
        new Promise((resolve) => {
          resolveFirst = resolve;
        }),
      );

      startDrag(7);
      fire({ type: "drop", target: el("cardA") });
      expect(drag.isDropInFlight()).toBe(true);

      startDrag(7);
      const { event, dataTransfer } = fire({
        type: "dragover",
        target: el("cardC"),
      });
      expect(event.defaultPrevented).toBe(false);
      expect(dataTransfer.dropEffect).toBe("none");
      expectNoMarks();

      fire({ type: "drop", target: el("cardC") });
      fire({ type: "drop", target: el("cardA") });
      expect(submitStagedTagsMock).toHaveBeenCalledTimes(1);

      resolveFirst("applied");
      await flush();
      expect(drag.isDropInFlight()).toBe(false);
    });

    it.each(["applied", "noop", "failed", "aborted"])(
      "releases the flag after the %s outcome so the next drop is accepted",
      async (outcome) => {
        submitStagedTagsMock.mockResolvedValueOnce(outcome);
        startDrag(7);
        fire({ type: "drop", target: el("cardA") });
        expect(drag.isDropInFlight()).toBe(true);
        await flush();
        expect(drag.isDropInFlight()).toBe(false);

        startDrag(7);
        fire({ type: "drop", target: el("cardC") });
        expect(submitStagedTagsMock).toHaveBeenCalledTimes(2);
      },
    );

    it("releases the flag when the request throws", async () => {
      submitStagedTagsMock.mockRejectedValueOnce(new Error("renderer threw"));

      startDrag(7);
      fire({ type: "drop", target: el("cardA") });
      await flush();

      expect(drag.isDropInFlight()).toBe(false);
    });

    it("does not clear the in-flight flag on dragend", () => {
      submitStagedTagsMock.mockReturnValueOnce(new Promise(() => {}));
      startDrag(7);
      fire({ type: "drop", target: el("cardA") });
      document.dispatchEvent(new Event("dragend", { bubbles: true }));
      expect(drag.isDropInFlight()).toBe(true);
    });
  });

  describe("tag strings with replacement-pattern or HTML characters", () => {
    const SPECIAL_TAG = "a$&b<i>";

    beforeEach(() => {
      const specialChip = document.createElement("div");
      specialChip.className = "tagFilter";
      specialChip.setAttribute("data-utub-tag-id", "11");
      const label = document.createElement("span");
      label.textContent = SPECIAL_TAG;
      specialChip.appendChild(label);
      document.getElementById("listTags")!.appendChild(specialChip);
      store.setState({
        tags: [
          { id: 7, tagString: "alpha", tagApplied: 1 },
          { id: 11, tagString: SPECIAL_TAG, tagApplied: 0 },
        ],
      });
    });

    it("keeps the hint and the ghost text verbatim", () => {
      el("cardA").setAttribute("urlSelected", "true");
      startDrag(11);
      fire({ type: "dragover", target: el("cardA"), payload: "11" });

      expect(el("cardA").getAttribute("data-drop-hint")).toBe(
        `Add "${SPECIAL_TAG}" to this URL`,
      );
      const ghost = el("cardA").querySelector(".tagDropGhost") as HTMLElement;
      expect(ghost.textContent).toBe(SPECIAL_TAG);
      expect(ghost.querySelector("i")).toBeNull();
    });

    it("keeps the success banner message verbatim", async () => {
      startDrag(11);
      fire({ type: "drop", target: el("cardA"), payload: "11" });
      await flush();

      expect(submitStagedTagsMock.mock.calls[0][0].stagedStrings).toEqual([
        SPECIAL_TAG,
      ]);
      expect(showURLOutcomeBannerMock.mock.calls[0][0].message).toBe(
        `Added tag "${SPECIAL_TAG}" to Title A.`,
      );
    });
  });

  describe("outcome step", () => {
    // Drops tag 7 on cardA; `whilePending` runs after the drop and before the
    // request settles, to change the world the way a slow request would.
    async function dropAndSettle({
      outcome,
      whilePending,
    }: {
      outcome: string;
      whilePending?: () => void;
    }): Promise<void> {
      let settle: (value: string) => void = () => {};
      submitStagedTagsMock.mockReturnValueOnce(
        new Promise((resolve) => {
          settle = resolve;
        }),
      );
      startDrag(7);
      fire({ type: "drop", target: el("cardA") });
      whilePending?.();
      settle(outcome);
      await flush();
    }

    it("selects an unselected card, then shows the success banner", async () => {
      await dropAndSettle({ outcome: "applied" });

      expect(selectURLCardMock).toHaveBeenCalledTimes(1);
      expect(selectURLCardMock.mock.calls[0][0].is(el("cardA"))).toBe(true);
      expect(showURLOutcomeBannerMock).toHaveBeenCalledTimes(1);
      const banner = showURLOutcomeBannerMock.mock.calls[0][0];
      expect(banner.variant).toBe("success");
      expect(banner.message).toBe('Added tag "alpha" to Title A.');
      expect(banner.returnFocusTo.is(el("cardA"))).toBe(true);
      expect(selectURLCardMock.mock.invocationCallOrder[0]).toBeLessThan(
        showURLOutcomeBannerMock.mock.invocationCallOrder[0],
      );
    });

    it("shows only the banner on an already selected card", async () => {
      el("cardA").setAttribute("urlSelected", "true");
      await dropAndSettle({ outcome: "applied" });

      expect(selectURLCardMock).not.toHaveBeenCalled();
      expect(showURLOutcomeBannerMock).toHaveBeenCalledTimes(1);
    });

    it("expands the card and shows the polite no-op banner naming tag and title", async () => {
      await dropAndSettle({ outcome: "noop" });

      expect(selectURLCardMock).toHaveBeenCalledTimes(1);
      const banner = showURLOutcomeBannerMock.mock.calls[0][0];
      expect(banner.variant).toBe("partial");
      expect(banner.message).toBe('"alpha" is already on Title A.');
      expect(banner.message).toContain("alpha");
      expect(banner.message).toContain("Title A");
      expect(banner.message).not.toBe(HAS_HINT_ALPHA);
    });

    it.each(["failed", "aborted"])(
      "selects nothing and shows no success banner for %s",
      async (outcome) => {
        await dropAndSettle({ outcome });

        expect(selectURLCardMock).not.toHaveBeenCalled();
        expect(showURLOutcomeBannerMock).not.toHaveBeenCalled();
      },
    );

    const worldChanges: Array<[string, () => void]> = [
      ["a form opened", () => tracking.setOpenForm("tag_create")],
      [
        "a combobox is visible on another card",
        () =>
          el("cardC")
            .querySelector(".urlTagComboboxWrap")!
            .classList.remove("hidden"),
      ],
      [
        "multi-select was entered",
        () => store.setState({ multiSelectMode: true }),
      ],
      [
        "the card was hidden by a filter",
        () => el("cardA").setAttribute("filterable", "false"),
      ],
      [
        "the card was hidden by search",
        () => el("cardA").setAttribute("searchable", "false"),
      ],
    ];

    it.each(worldChanges)(
      "skips selectURLCard but still shows the banner when %s during the request",
      async (_label, change) => {
        await dropAndSettle({ outcome: "applied", whilePending: change });

        expect(selectURLCardMock).not.toHaveBeenCalled();
        expect(showURLOutcomeBannerMock).toHaveBeenCalledTimes(1);
      },
    );

    it.each(["applied", "noop"])(
      "shows nothing for %s when the active UTub changed while pending",
      async (outcome) => {
        await dropAndSettle({
          outcome,
          whilePending: () => store.setState({ activeUTubID: 2 }),
        });

        expect(selectURLCardMock).not.toHaveBeenCalled();
        expect(showURLOutcomeBannerMock).not.toHaveBeenCalled();
      },
    );

    it.each(["applied", "noop"])(
      "shows nothing for %s when the card was removed while pending",
      async (outcome) => {
        await dropAndSettle({
          outcome,
          whilePending: () => el("cardA").remove(),
        });

        expect(selectURLCardMock).not.toHaveBeenCalled();
        expect(showURLOutcomeBannerMock).not.toHaveBeenCalled();
      },
    );

    it("finds a card the pre-flight rebuilt by utuburlid", async () => {
      await dropAndSettle({
        outcome: "applied",
        whilePending: () => {
          const rebuilt = el("cardA").cloneNode(true) as HTMLElement;
          rebuilt.id = "cardA2";
          el("cardA").replaceWith(rebuilt);
        },
      });

      expect(selectURLCardMock.mock.calls[0][0].is(el("cardA2"))).toBe(true);
      expect(showURLOutcomeBannerMock).toHaveBeenCalledTimes(1);
    });
  });
});
