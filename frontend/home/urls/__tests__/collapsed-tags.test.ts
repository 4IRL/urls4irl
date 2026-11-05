import { getState, resetStore, setState } from "../../../store/app-store.js";
import {
  EMPTY_MEMBER_SETTINGS,
  type ResolvedMemberSettings,
} from "../../../types/settings.js";
import {
  applyCollapsedTagsAttr,
  initCollapsedTagOverflow,
  refreshCollapsedTagOverflow,
} from "../collapsed-tags.js";

type BadgeSpec = { top: number; cls?: string };

function badgeHtml({
  spec,
  index,
}: {
  spec: BadgeSpec;
  index: number;
}): string {
  return `<span class="tagBadge ${spec.cls ?? ""}" data-utub-tag-id="${index + 1}" data-top="${spec.top}"><button class="urlTagBtnDelete tabbable"></button></span>`;
}

function rowHtml({
  id,
  badges,
  selected = false,
}: {
  id: number;
  badges: BadgeSpec[];
  selected?: boolean;
}): string {
  const html = badges.map((spec, index) => badgeHtml({ spec, index })).join("");
  return `<div class="urlRow" id="row${id}" filterable="true" searchable="true" urlSelected="${selected}"><div class="urlTags"><div class="urlTagsContainer">${html}</div></div></div>`;
}

// jsdom has no layout: offsetTop comes from each element's data-top, and the
// "+N" badge sits on the first line unless a test says otherwise.
function mockLayout({ moreTop = 0 }: { moreTop?: number } = {}): void {
  Object.defineProperty(HTMLElement.prototype, "offsetTop", {
    configurable: true,
    get(this: HTMLElement) {
      if (this.classList.contains("tagBadgeMore")) return moreTop;
      return Number(this.dataset.top ?? 0);
    },
  });
}

function mount(rows: string): void {
  document.body.innerHTML = `<div id="URLDeck">${rows}</div>`;
}

function setCollapsedSettings({
  show,
  style,
}: {
  show: boolean;
  style: "one_line" | "all";
}): void {
  setState({
    activeUTubID: 1,
    preferences: {
      ...getState().preferences,
      showTagsOnCollapsed: show,
      collapsedTagsStyle: style,
    },
  });
}

function overflowCount(rowId: number): number {
  return document.querySelectorAll(`#row${rowId} .tagBadgeOverflow`).length;
}

function moreBadge(rowId: number): HTMLElement | null {
  return document.querySelector<HTMLElement>(`#row${rowId} .tagBadgeMore`);
}

describe("collapsed-tags", () => {
  let dispose: (() => void) | undefined;

  beforeEach(() => {
    resetStore();
    mockLayout();
    dispose = undefined;
  });

  afterEach(() => {
    dispose?.();
    delete (HTMLElement.prototype as { offsetTop?: number }).offsetTop;
    document.body.innerHTML = "";
    delete document.body.dataset.view;
  });

  describe("data-collapsed-tags attribute", () => {
    it("is off by default", () => {
      mount("");
      setState({ activeUTubID: 1 });
      applyCollapsedTagsAttr();
      expect(
        document.getElementById("URLDeck")!.getAttribute("data-collapsed-tags"),
      ).toBe("off");
    });

    it.each(["one_line", "all"] as const)("writes %s when shown", (style) => {
      mount("");
      setCollapsedSettings({ show: true, style });
      applyCollapsedTagsAttr();
      expect(
        document.getElementById("URLDeck")!.getAttribute("data-collapsed-tags"),
      ).toBe(style);
    });

    it("keeps the chosen style but writes off when the switch is off", () => {
      mount("");
      setCollapsedSettings({ show: false, style: "all" });
      applyCollapsedTagsAttr();
      expect(
        document.getElementById("URLDeck")!.getAttribute("data-collapsed-tags"),
      ).toBe("off");
      expect(getState().preferences.collapsedTagsStyle).toBe("all");
    });

    it("lets a per-UTub override win", () => {
      mount("");
      setCollapsedSettings({ show: false, style: "one_line" });
      setState({
        memberSettings: {
          ...EMPTY_MEMBER_SETTINGS,
          tags: {
            ...EMPTY_MEMBER_SETTINGS.tags,
            show_tags_on_collapsed: true,
            collapsed_tags_style: "all",
          },
        } as ResolvedMemberSettings,
      });
      applyCollapsedTagsAttr();
      expect(
        document.getElementById("URLDeck")!.getAttribute("data-collapsed-tags"),
      ).toBe("all");
    });

    it("fails closed to off for an unknown style", () => {
      mount("");
      setState({ activeUTubID: 1 });
      setCollapsedSettings({
        show: true,
        style: "bogus" as unknown as "all",
      });
      applyCollapsedTagsAttr();
      expect(
        document.getElementById("URLDeck")!.getAttribute("data-collapsed-tags"),
      ).toBe("off");
    });

    it("is off with no active UTub", () => {
      mount("");
      setCollapsedSettings({ show: true, style: "one_line" });
      setState({ activeUTubID: null });
      applyCollapsedTagsAttr();
      expect(
        document.getElementById("URLDeck")!.getAttribute("data-collapsed-tags"),
      ).toBe("off");
    });
  });

  describe("one_line overflow", () => {
    beforeEach(() => setCollapsedSettings({ show: true, style: "one_line" }));

    it("adds nothing when every badge fits", () => {
      mount(rowHtml({ id: 1, badges: [{ top: 0 }, { top: 0 }, { top: 0 }] }));
      refreshCollapsedTagOverflow();
      expect(overflowCount(1)).toBe(0);
      expect(moreBadge(1)).toBeNull();
    });

    it("hides the wrapped badges and shows +N equal to the hidden count", () => {
      mount(
        rowHtml({
          id: 1,
          badges: [{ top: 0 }, { top: 0 }, { top: 24 }, { top: 24 }],
        }),
      );
      refreshCollapsedTagOverflow();
      expect(overflowCount(1)).toBe(2);
      const more = moreBadge(1)!;
      expect(more.querySelector('[aria-hidden="true"]')!.textContent).toBe(
        "+2",
      );
      expect(more.querySelector(".visually-hidden")!.textContent).toBe(
        "2 more tags",
      );
      expect(more.getAttribute("tabindex")).toBeNull();
    });

    it("uses the singular spoken text for one hidden tag", () => {
      mount(rowHtml({ id: 1, badges: [{ top: 0 }, { top: 24 }] }));
      refreshCollapsedTagOverflow();
      expect(moreBadge(1)!.querySelector(".visually-hidden")!.textContent).toBe(
        "1 more tag",
      );
    });

    it("hides every badge after the first when all but one overflow", () => {
      mount(rowHtml({ id: 1, badges: [{ top: 0 }, { top: 24 }, { top: 24 }] }));
      refreshCollapsedTagOverflow();
      expect(overflowCount(1)).toBe(2);
      expect(moreBadge(1)!.textContent).toContain("+2");
    });

    it("hides one more badge when +N would wrap onto a second line", () => {
      mockLayout({ moreTop: 24 });
      mount(rowHtml({ id: 1, badges: [{ top: 0 }, { top: 0 }, { top: 24 }] }));
      refreshCollapsedTagOverflow();
      expect(overflowCount(1)).toBe(2);
      expect(
        moreBadge(1)!.querySelector('[aria-hidden="true"]')!.textContent,
      ).toBe("+2");
    });

    it("measures before hiding so the hidden set is a suffix", () => {
      // Hiding badge 3 would let the shorter badge 4 reflow to line 1 if the
      // measurement were interleaved with the hiding.
      let hiddenSoFar = 0;
      Object.defineProperty(HTMLElement.prototype, "offsetTop", {
        configurable: true,
        get(this: HTMLElement) {
          if (this.classList.contains("tagBadgeMore")) return 0;
          hiddenSoFar = document.querySelectorAll(".tagBadgeOverflow").length;
          const top = Number(this.dataset.top ?? 0);
          return hiddenSoFar > 0 && this.dataset.top === "24" ? 0 : top;
        },
      });
      mount(
        rowHtml({
          id: 1,
          badges: [{ top: 0 }, { top: 24 }, { top: 24 }, { top: 24 }],
        }),
      );
      refreshCollapsedTagOverflow();
      expect(overflowCount(1)).toBe(3);
      expect(moreBadge(1)!.textContent).toContain("+3");
    });

    it("stops hiding at one visible badge when +N still wraps", () => {
      mockLayout({ moreTop: 24 });
      mount(rowHtml({ id: 1, badges: [{ top: 0 }, { top: 24 }, { top: 24 }] }));
      refreshCollapsedTagOverflow();
      expect(overflowCount(1)).toBe(2);
      expect(moreBadge(1)).not.toBeNull();
    });

    it("does not count or hide drop ghosts", () => {
      mount(
        rowHtml({
          id: 1,
          badges: [
            { top: 0 },
            { top: 0 },
            { top: 24, cls: "tagDropGhost" },
            { top: 24, cls: "tagDropExisting" },
          ],
        }),
      );
      refreshCollapsedTagOverflow();
      expect(overflowCount(1)).toBe(0);
      expect(moreBadge(1)).toBeNull();
    });

    it("is idempotent across repeated refreshes", () => {
      mount(rowHtml({ id: 1, badges: [{ top: 0 }, { top: 24 }, { top: 24 }] }));
      refreshCollapsedTagOverflow();
      refreshCollapsedTagOverflow();
      expect(document.querySelectorAll(".tagBadgeMore")).toHaveLength(1);
      expect(overflowCount(1)).toBe(2);
    });

    it("recomputes the count after a badge is removed", () => {
      mount(rowHtml({ id: 1, badges: [{ top: 0 }, { top: 24 }, { top: 24 }] }));
      refreshCollapsedTagOverflow();
      document.querySelector('#row1 .tagBadge[data-utub-tag-id="3"]')!.remove();
      refreshCollapsedTagOverflow();
      expect(moreBadge(1)!.textContent).toContain("+1");
    });

    it("removes +N and shows every badge when the card is expanded", () => {
      mount(rowHtml({ id: 1, badges: [{ top: 0 }, { top: 24 }, { top: 24 }] }));
      refreshCollapsedTagOverflow();
      document.getElementById("row1")!.setAttribute("urlSelected", "true");
      refreshCollapsedTagOverflow();
      expect(moreBadge(1)).toBeNull();
      expect(overflowCount(1)).toBe(0);
    });

    it("skips rows hidden by a filter or search", () => {
      mount(rowHtml({ id: 1, badges: [{ top: 0 }, { top: 24 }] }));
      document.getElementById("row1")!.setAttribute("filterable", "false");
      refreshCollapsedTagOverflow();
      expect(moreBadge(1)).toBeNull();
    });

    it("never shows collapsed tags in the line view modes", () => {
      mount(rowHtml({ id: 1, badges: [{ top: 0 }, { top: 24 }] }));
      document.body.dataset.view = "title_line";
      refreshCollapsedTagOverflow();
      expect(moreBadge(1)).toBeNull();
      expect(overflowCount(1)).toBe(0);
    });

    it("adds nothing in all mode or when off", () => {
      mount(rowHtml({ id: 1, badges: [{ top: 0 }, { top: 24 }] }));
      setCollapsedSettings({ show: true, style: "all" });
      refreshCollapsedTagOverflow();
      expect(moreBadge(1)).toBeNull();
      setCollapsedSettings({ show: false, style: "one_line" });
      refreshCollapsedTagOverflow();
      expect(moreBadge(1)).toBeNull();
    });
  });

  describe("recompute triggers", () => {
    beforeEach(() => {
      vi.useFakeTimers();
      setCollapsedSettings({ show: true, style: "one_line" });
    });

    afterEach(() => vi.useRealTimers());

    async function settleObserver(): Promise<void> {
      await Promise.resolve();
      await Promise.resolve();
    }

    it("recomputes on a debounced resize", () => {
      mount(rowHtml({ id: 1, badges: [{ top: 0 }, { top: 0 }] }));
      dispose = initCollapsedTagOverflow();
      expect(moreBadge(1)).toBeNull();
      document
        .querySelector<HTMLElement>('#row1 [data-utub-tag-id="2"]')!
        .setAttribute("data-top", "24");
      window.dispatchEvent(new Event("resize"));
      window.dispatchEvent(new Event("resize"));
      vi.advanceTimersByTime(149);
      expect(moreBadge(1)).toBeNull();
      vi.advanceTimersByTime(1);
      expect(moreBadge(1)).not.toBeNull();
    });

    it("stops recomputing after dispose", () => {
      mount(rowHtml({ id: 1, badges: [{ top: 0 }, { top: 0 }] }));
      dispose = initCollapsedTagOverflow();
      dispose();
      dispose = undefined;
      document
        .querySelector<HTMLElement>('#row1 [data-utub-tag-id="2"]')!
        .setAttribute("data-top", "24");
      window.dispatchEvent(new Event("resize"));
      vi.advanceTimersByTime(200);
      expect(moreBadge(1)).toBeNull();
    });

    it("adds no +N on resize in all mode", () => {
      setCollapsedSettings({ show: true, style: "all" });
      mount(rowHtml({ id: 1, badges: [{ top: 0 }, { top: 24 }] }));
      dispose = initCollapsedTagOverflow();
      window.dispatchEvent(new Event("resize"));
      vi.advanceTimersByTime(200);
      expect(moreBadge(1)).toBeNull();
    });

    it("recomputes when a badge is added", async () => {
      mount(rowHtml({ id: 1, badges: [{ top: 0 }] }));
      dispose = initCollapsedTagOverflow();
      document
        .querySelector("#row1 .urlTagsContainer")!
        .insertAdjacentHTML(
          "beforeend",
          badgeHtml({ spec: { top: 24 }, index: 1 }),
        );
      await settleObserver();
      expect(moreBadge(1)!.textContent).toContain("+1");
    });

    it("recomputes when a badge is renamed", async () => {
      mount(rowHtml({ id: 1, badges: [{ top: 0 }, { top: 0 }] }));
      dispose = initCollapsedTagOverflow();
      const badge = document.querySelector<HTMLElement>(
        '#row1 [data-utub-tag-id="2"]',
      )!;
      badge.setAttribute("data-top", "24");
      badge.insertBefore(document.createTextNode("renamed"), badge.firstChild);
      await settleObserver();
      expect(moreBadge(1)).not.toBeNull();
    });

    it("recomputes when a card is deselected or revealed by a filter", async () => {
      mount(
        rowHtml({
          id: 1,
          badges: [{ top: 0 }, { top: 24 }],
          selected: true,
        }),
      );
      dispose = initCollapsedTagOverflow();
      expect(moreBadge(1)).toBeNull();
      document.getElementById("row1")!.setAttribute("urlSelected", "false");
      await settleObserver();
      expect(moreBadge(1)).not.toBeNull();

      document.getElementById("row1")!.setAttribute("filterable", "false");
      await settleObserver();
      expect(moreBadge(1)).toBeNull();
      document.getElementById("row1")!.setAttribute("filterable", "true");
      await settleObserver();
      expect(moreBadge(1)).not.toBeNull();
    });

    it("recomputes on a view change", async () => {
      mount(rowHtml({ id: 1, badges: [{ top: 0 }, { top: 24 }] }));
      document.body.dataset.view = "title_line";
      dispose = initCollapsedTagOverflow();
      expect(moreBadge(1)).toBeNull();
      document.body.dataset.view = "list";
      await settleObserver();
      expect(moreBadge(1)).not.toBeNull();
    });

    it("does not loop on its own writes", async () => {
      mount(rowHtml({ id: 1, badges: [{ top: 0 }, { top: 24 }] }));
      dispose = initCollapsedTagOverflow();
      await settleObserver();
      await settleObserver();
      expect(document.querySelectorAll(".tagBadgeMore")).toHaveLength(1);
    });
  });

  describe("badge delete buttons tab order", () => {
    it("takes them out of the tab order on collapsed rows", () => {
      mount(rowHtml({ id: 1, badges: [{ top: 0 }, { top: 0 }] }));
      refreshCollapsedTagOverflow();
      document
        .querySelectorAll("#row1 .urlTagBtnDelete")
        .forEach((button) =>
          expect(button.getAttribute("tabindex")).toBe("-1"),
        );
    });

    it("leaves expanded rows to the selection code", () => {
      mount(rowHtml({ id: 1, badges: [{ top: 0 }], selected: true }));
      document
        .querySelector("#row1 .urlTagBtnDelete")!
        .setAttribute("tabindex", "0");
      refreshCollapsedTagOverflow();
      expect(
        document
          .querySelector("#row1 .urlTagBtnDelete")!
          .getAttribute("tabindex"),
      ).toBe("0");
    });
  });
});
