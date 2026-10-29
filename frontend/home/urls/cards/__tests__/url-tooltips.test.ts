import { getState, resetStore, setState } from "../../../../store/app-store.js";
import type { ViewModeValue } from "../../../../types/preferences.js";
import { syncAllUrlTooltips, syncUrlTooltips } from "../url-tooltips.js";

const TITLE_TEXT = "A fairly long url title";
const URL_TEXT = "https://example.com/a/very/long/path";

function setView(viewMode: ViewModeValue): void {
  setState({
    activeUTubID: null,
    preferences: { ...getState().preferences, defaultView: viewMode },
  });
}

function mockWide(matches: boolean): void {
  window.matchMedia = vi.fn(() => ({
    matches,
    addEventListener: vi.fn(),
  })) as unknown as typeof window.matchMedia;
}

function card(): JQuery {
  return $("#row");
}

describe("url-tooltips", () => {
  const originalMatchMedia = window.matchMedia;

  beforeEach(() => {
    document.body.innerHTML = `
      <div class="urlRow" id="row" urlSelected="false">
        <h5 class="urlTitle">${TITLE_TEXT}</h5>
        <a class="urlString" href="${URL_TEXT}">example.com/a/very/long/path</a>
      </div>`;
    mockWide(true);
  });

  afterEach(() => {
    window.matchMedia = originalMatchMedia;
    resetStore();
    document.body.innerHTML = "";
  });

  it.each(["title_line", "url_line", "cards"] as const)(
    "sets the full text on an unselected %s row",
    (viewMode) => {
      setView(viewMode);
      syncUrlTooltips(card());
      expect(card().find(".urlTitle").attr("title")).toBe(TITLE_TEXT);
      expect(card().find(".urlString").attr("title")).toBe(URL_TEXT);
    },
  );

  it("sets nothing in List", () => {
    setView("list");
    syncUrlTooltips(card());
    expect(card().find(".urlTitle").attr("title")).toBeUndefined();
    expect(card().find(".urlString").attr("title")).toBeUndefined();
  });

  it("sets nothing for cards at a narrow viewport (renders as List)", () => {
    mockWide(false);
    setView("cards");
    syncUrlTooltips(card());
    expect(card().find(".urlTitle").attr("title")).toBeUndefined();
    expect(card().find(".urlString").attr("title")).toBeUndefined();
  });

  it("removes the attribute on select and restores it on deselect", () => {
    setView("title_line");
    syncUrlTooltips(card());
    card().attr("urlSelected", "true");
    syncUrlTooltips(card());
    expect(card().find(".urlTitle").attr("title")).toBeUndefined();
    expect(card().find(".urlString").attr("title")).toBeUndefined();
    card().attr("urlSelected", "false");
    syncUrlTooltips(card());
    expect(card().find(".urlTitle").attr("title")).toBe(TITLE_TEXT);
  });

  it("follows an edited text, and never sets it on a selected row", () => {
    setView("url_line");
    syncUrlTooltips(card());
    card().find(".urlTitle").text("Edited");
    syncUrlTooltips(card());
    expect(card().find(".urlTitle").attr("title")).toBe("Edited");

    card().attr("urlSelected", "true");
    card().find(".urlTitle").text("Edited again");
    syncUrlTooltips(card());
    expect(card().find(".urlTitle").attr("title")).toBeUndefined();
  });

  it("syncAllUrlTooltips re-syncs every row after a view change", () => {
    document.body.insertAdjacentHTML(
      "beforeend",
      `<div class="urlRow" urlSelected="false"><h5 class="urlTitle">Other</h5></div>`,
    );
    setView("title_line");
    syncAllUrlTooltips();
    expect($(".urlRow .urlTitle").first().attr("title")).toBe(TITLE_TEXT);
    expect($(".urlRow .urlTitle").last().attr("title")).toBe("Other");

    setView("list");
    syncAllUrlTooltips();
    expect($(".urlRow .urlTitle[title]")).toHaveLength(0);
  });
});

describe("bindWideViewportTooltipSync", () => {
  const originalMatchMedia = window.matchMedia;

  afterEach(() => {
    window.matchMedia = originalMatchMedia;
    vi.resetModules();
    document.body.innerHTML = "";
  });

  it("binds once and re-syncs every row when the breakpoint changes", async () => {
    vi.resetModules();
    const listeners: Array<() => void> = [];
    const addEventListener = vi.fn((_type: string, listener: () => void) => {
      listeners.push(listener);
    });
    let wideMatches = false;
    window.matchMedia = vi.fn(() => ({
      get matches() {
        return wideMatches;
      },
      addEventListener,
    })) as unknown as typeof window.matchMedia;
    document.body.innerHTML = `<div class="urlRow" urlSelected="false"><h5 class="urlTitle">T</h5></div>`;

    // Same fresh module graph (after resetModules) for the store and the helper.
    const store = await vi.importActual<
      typeof import("../../../../store/app-store.js")
    >("../../../../store/app-store.js");
    const actual =
      await vi.importActual<typeof import("../url-tooltips.js")>(
        "../url-tooltips.js",
      );
    store.setState({
      preferences: { ...store.getState().preferences, defaultView: "cards" },
    });
    actual.bindWideViewportTooltipSync();
    actual.bindWideViewportTooltipSync();
    expect(addEventListener).toHaveBeenCalledTimes(1);

    // Narrow: cards renders as List, so no tooltip.
    listeners[0]();
    expect($(".urlTitle").attr("title")).toBeUndefined();

    // Crossing into wide: cards truncates, so the tooltip is set.
    wideMatches = true;
    listeners[0]();
    expect($(".urlTitle").attr("title")).toBe("T");

    // And back to narrow: the tooltip is removed.
    wideMatches = false;
    listeners[0]();
    expect($(".urlTitle").attr("title")).toBeUndefined();
  });

  it("does nothing without matchMedia", async () => {
    vi.resetModules();
    (window as { matchMedia?: unknown }).matchMedia = undefined;
    const actual =
      await vi.importActual<typeof import("../url-tooltips.js")>(
        "../url-tooltips.js",
      );
    expect(() => actual.bindWideViewportTooltipSync()).not.toThrow();
  });
});
