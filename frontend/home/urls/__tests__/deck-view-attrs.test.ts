import { getState, resetStore, setState } from "../../../store/app-store.js";
import {
  EMPTY_MEMBER_SETTINGS,
  EMPTY_UTUB_SETTINGS,
  type ResolvedMemberSettings,
  type ResolvedUtubSettings,
} from "../../../types/settings.js";
import { armFocusReturnSuppression } from "../cards/focus-return.js";
import { refreshDateAddedBadges } from "../cards/adder-badge.js";
import {
  applyUrlDeckPolicyAttrs,
  applyUrlDeckViewSettings,
  initUrlDeckPolicyAttrs,
  shortLinkFocusTarget,
} from "../deck-view-attrs.js";

vi.mock("../cards/focus-return.js", () => ({
  armFocusReturnSuppression: vi.fn(),
}));
vi.mock("../cards/adder-badge.js", () => ({
  refreshDateAddedBadges: vi.fn(),
}));

const POLICY_RULE =
  '#URLDeck[data-allow-short-links="false"] .urlBtnShortLink { display: none !important; }';

function settings({
  allowShortLinks,
}: {
  allowShortLinks: boolean;
}): ResolvedUtubSettings {
  return {
    ...EMPTY_UTUB_SETTINGS,
    urls: { ...EMPTY_UTUB_SETTINGS.urls, allow_short_links: allowShortLinks },
  } as ResolvedUtubSettings;
}

function deck(): HTMLElement {
  return document.getElementById("URLDeck")!;
}

describe("deck-view-attrs", () => {
  let dispose: (() => void) | undefined;

  beforeEach(() => {
    document.head.innerHTML = `<style>${POLICY_RULE}</style>`;
    document.body.innerHTML = `
      <div id="URLDeck">
        <div class="urlRow" tabindex="0" id="rowA">
          <button class="urlBtnCopy" id="copyA"></button>
          <button class="urlBtnShortLink" id="shortA"></button>
        </div>
      </div>`;
    vi.mocked(armFocusReturnSuppression).mockReset();
    setState({ settings: null, activeUTubID: null });
    dispose = undefined;
  });

  afterEach(() => {
    dispose?.();
    setState({ settings: null, activeUTubID: null });
    document.head.innerHTML = "";
    document.body.innerHTML = "";
  });

  it("defaults the attribute to true without settings", () => {
    applyUrlDeckPolicyAttrs();
    expect(deck().getAttribute("data-allow-short-links")).toBe("true");
  });

  it("does not throw when #URLDeck is missing", () => {
    document.body.innerHTML = "";
    expect(() => applyUrlDeckPolicyAttrs()).not.toThrow();
  });

  it("sets and clears the attribute on settings change and UTub switch", () => {
    dispose = initUrlDeckPolicyAttrs();

    setState({
      activeUTubID: 1,
      settings: settings({ allowShortLinks: false }),
    });
    expect(deck().getAttribute("data-allow-short-links")).toBe("false");

    setState({ settings: settings({ allowShortLinks: true }) });
    expect(deck().getAttribute("data-allow-short-links")).toBe("true");

    setState({ settings: settings({ allowShortLinks: false }) });
    setState({ activeUTubID: 2, settings: null });
    expect(deck().getAttribute("data-allow-short-links")).toBe("true");
  });

  it("stops updating after dispose", () => {
    dispose = initUrlDeckPolicyAttrs();
    dispose();
    dispose = undefined;
    setState({ settings: settings({ allowShortLinks: false }) });
    expect(deck().getAttribute("data-allow-short-links")).toBe("true");
  });

  it("returns focus from a hidden Copy short link to its card row", () => {
    dispose = initUrlDeckPolicyAttrs();
    const short = document.getElementById("shortA")!;
    short.focus();
    expect(document.activeElement).toBe(short);

    setState({
      activeUTubID: 1,
      settings: settings({ allowShortLinks: false }),
    });

    expect(
      short.matches(
        '#URLDeck[data-allow-short-links="false"] .urlBtnShortLink',
      ),
    ).toBe(true);
    expect(armFocusReturnSuppression).toHaveBeenCalledTimes(1);
    expect(document.activeElement).toBe(document.getElementById("rowA"));
  });

  it("arms the suppression before moving focus", () => {
    dispose = initUrlDeckPolicyAttrs();
    const row = document.getElementById("rowA")!;
    vi.mocked(armFocusReturnSuppression).mockImplementation(() => {
      expect(document.activeElement).not.toBe(row);
    });
    document.getElementById("shortA")!.focus();

    setState({ settings: settings({ allowShortLinks: false }) });

    expect(armFocusReturnSuppression).toHaveBeenCalled();
    expect(document.activeElement).toBe(row);
  });

  it("keeps focus on an unrelated element", () => {
    dispose = initUrlDeckPolicyAttrs();
    const copy = document.getElementById("copyA")!;
    copy.focus();

    setState({ settings: settings({ allowShortLinks: false }) });

    expect(armFocusReturnSuppression).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(copy);
  });

  it("keeps a button re-shown by showClassFlex hidden while the attribute is false", () => {
    dispose = initUrlDeckPolicyAttrs();
    const short = document.getElementById("shortA")!;
    // What the update-string / tag-edit close paths do.
    short.style.display = "flex";
    expect(getComputedStyle(short).display).toBe("flex");

    setState({ settings: settings({ allowShortLinks: false }) });
    short.style.display = "flex";

    expect(getComputedStyle(short).display).toBe("none");
  });
});

const PERSONAL_RULES = `
  #URLDeck[data-hide-copy="true"] .urlBtnCopy { display: none !important; }
  #URLDeck[data-hide-short-link="true"] .urlBtnShortLink { display: none !important; }
  #URLDeck[data-hide-date="true"] .urlDateAddedBadgeInline { display: none !important; }
  #URLDeck[data-swipe-delete="off"] .urlRowSwipeReveal { display: none !important; }`;

function member(
  overrides: Partial<ResolvedMemberSettings["urls"]>,
): ResolvedMemberSettings {
  return { urls: { ...EMPTY_MEMBER_SETTINGS.urls, ...overrides } };
}

describe("deck-view-attrs personal view settings", () => {
  let dispose: (() => void) | undefined;

  beforeEach(() => {
    resetStore();
    document.head.innerHTML = `<style>${PERSONAL_RULES}</style>`;
    document.body.innerHTML = `
      <div id="URLDeck">
        <div class="urlRow" tabindex="0" id="rowA">
          <button class="urlBtnCopy" id="copyA"></button>
          <button class="urlBtnShortLink" id="shortA"></button>
          <time class="urlDateAddedBadgeInline" id="dateA"></time>
          <div class="urlRowSwipeReveal" id="revealA"></div>
        </div>
      </div>`;
    vi.mocked(armFocusReturnSuppression).mockReset();
    vi.mocked(refreshDateAddedBadges).mockReset();
    dispose = undefined;
  });

  it("mirrors disable_swipe_delete onto data-swipe-delete and hides only the reveal panel", () => {
    dispose = initUrlDeckPolicyAttrs();

    setState({
      activeUTubID: 1,
      memberSettings: member({ disable_swipe_delete: true }),
    });
    expect(deck().getAttribute("data-swipe-delete")).toBe("off");
    expect(getComputedStyle(document.getElementById("revealA")!).display).toBe(
      "none",
    );

    setState({
      memberSettings: member({ disable_swipe_delete: false }),
    });
    expect(deck().getAttribute("data-swipe-delete")).toBe("on");

    setState({ activeUTubID: null });
    expect(deck().hasAttribute("data-swipe-delete")).toBe(false);
  });

  it("keeps the reveal panel shown for a member who has not disabled swipe", () => {
    dispose = initUrlDeckPolicyAttrs();

    setState({ activeUTubID: 1, memberSettings: member({}) });

    expect(deck().getAttribute("data-swipe-delete")).toBe("on");
    expect(
      getComputedStyle(document.getElementById("revealA")!).display,
    ).not.toBe("none");
  });

  afterEach(() => {
    dispose?.();
    resetStore();
    document.head.innerHTML = "";
    document.body.innerHTML = "";
    delete document.body.dataset.view;
    delete document.body.dataset.density;
  });

  it("sets the hide attributes and hides only the matching controls", () => {
    dispose = initUrlDeckPolicyAttrs();

    setState({
      activeUTubID: 1,
      memberSettings: member({
        hide_copy_button: true,
        hide_short_link_button: true,
        hide_date_added: true,
      }),
    });

    expect(deck().getAttribute("data-hide-copy")).toBe("true");
    expect(deck().getAttribute("data-hide-short-link")).toBe("true");
    expect(deck().getAttribute("data-hide-date")).toBe("true");
    for (const id of ["copyA", "shortA", "dateA"]) {
      expect(getComputedStyle(document.getElementById(id)!).display).toBe(
        "none",
      );
    }
    expect(document.getElementById("rowA")).not.toBeNull();
  });

  it("writes false attributes for a member with no overrides", () => {
    dispose = initUrlDeckPolicyAttrs();

    setState({ activeUTubID: 1, memberSettings: member({}) });

    expect(deck().getAttribute("data-hide-copy")).toBe("false");
    expect(deck().getAttribute("data-hide-short-link")).toBe("false");
    expect(deck().getAttribute("data-hide-date")).toBe("false");
    expect(
      getComputedStyle(document.getElementById("copyA")!).display,
    ).not.toBe("none");
  });

  it("a showClassFlex-style re-show cannot bring a hidden Copy button back", () => {
    dispose = initUrlDeckPolicyAttrs();
    setState({
      activeUTubID: 1,
      memberSettings: member({ hide_copy_button: true }),
    });

    document.getElementById("copyA")!.style.display = "flex";

    expect(getComputedStyle(document.getElementById("copyA")!).display).toBe(
      "none",
    );
  });

  it("applies the view and density overrides and restores the preferences on switch and deselect", () => {
    const { defaultView, density } = getState().preferences;
    dispose = initUrlDeckPolicyAttrs();
    expect(document.body.dataset.view).toBe(defaultView);
    expect(document.body.dataset.density).toBe(density);

    setState({
      activeUTubID: 1,
      memberSettings: member({ view_mode: "title_line", density: "compact" }),
    });
    expect(document.body.dataset.view).toBe("title_line");
    expect(document.body.dataset.density).toBe("compact");

    // Switching to a UTub without overrides.
    setState({ activeUTubID: 2, memberSettings: member({}) });
    expect(document.body.dataset.view).toBe(defaultView);
    expect(document.body.dataset.density).toBe(density);

    // Deselect clears the deck attributes and keeps the preference values.
    setState({
      activeUTubID: 3,
      memberSettings: member({
        view_mode: "title_line",
        hide_copy_button: true,
      }),
    });
    setState({ activeUTubID: null });
    expect(deck().hasAttribute("data-hide-copy")).toBe(false);
    expect(deck().hasAttribute("data-hide-short-link")).toBe(false);
    expect(deck().hasAttribute("data-hide-date")).toBe(false);
    expect(document.body.dataset.view).toBe(defaultView);
    expect(document.body.dataset.density).toBe(density);
  });

  it("re-applies when the Display preferences change", () => {
    dispose = initUrlDeckPolicyAttrs();
    setState({ activeUTubID: 1, memberSettings: member({}) });

    setState({
      preferences: { ...getState().preferences, defaultView: "list" },
    });

    expect(document.body.dataset.view).toBe("list");
  });

  it("does not throw when #URLDeck is missing", () => {
    document.body.innerHTML = "";
    expect(() => applyUrlDeckViewSettings()).not.toThrow();
  });

  it("rebuilds the date badges only when the effective hide-date value changes", () => {
    dispose = initUrlDeckPolicyAttrs();

    setState({
      activeUTubID: 1,
      memberSettings: member({ hide_date_added: true }),
    });
    expect(refreshDateAddedBadges).toHaveBeenCalledTimes(1);

    setState({
      memberSettings: member({ hide_date_added: true, sort: "oldest" }),
    });
    expect(refreshDateAddedBadges).toHaveBeenCalledTimes(1);

    setState({ activeUTubID: 2, memberSettings: member({}) });
    expect(refreshDateAddedBadges).toHaveBeenCalledTimes(2);
  });

  it.each([["Copy short link", "shortA", { hide_short_link_button: true }]])(
    "returns focus from a hidden %s to its card row",
    (_label, buttonId, overrides) => {
      dispose = initUrlDeckPolicyAttrs();
      setState({ activeUTubID: 1, memberSettings: member({}) });
      const button = document.getElementById(buttonId)!;
      button.focus();

      setState({ memberSettings: member(overrides) });

      expect(armFocusReturnSuppression).toHaveBeenCalledTimes(1);
      expect(document.activeElement).toBe(document.getElementById("rowA"));
    },
  );

  it("returns focus from a hidden Copy button to its card row", () => {
    dispose = initUrlDeckPolicyAttrs();
    setState({ activeUTubID: 1, memberSettings: member({}) });
    document.getElementById("copyA")!.focus();

    setState({ memberSettings: member({ hide_copy_button: true }) });

    expect(document.activeElement).toBe(document.getElementById("rowA"));
  });

  describe("shortLinkFocusTarget", () => {
    function row(): JQuery {
      return window.jQuery("#rowA");
    }

    it("returns the button when it is not hidden by an attribute", () => {
      expect(shortLinkFocusTarget(row())[0]).toBe(
        document.getElementById("shortA"),
      );
    });

    it.each([
      ["data-hide-short-link", "true"],
      ["data-allow-short-links", "false"],
    ])("returns the card row when %s=%s hides the button", (attr, value) => {
      deck().setAttribute(attr, value);

      expect(shortLinkFocusTarget(row())[0]).toBe(
        document.getElementById("rowA"),
      );
    });

    it("returns the card row when the card has no short-link button", () => {
      document.getElementById("shortA")!.remove();

      expect(shortLinkFocusTarget(row())[0]).toBe(
        document.getElementById("rowA"),
      );
    });
  });
});
