import { resetStore, setState } from "../../../store/app-store.js";
import { EMPTY_MEMBER_SETTINGS } from "../../../types/settings.js";
import {
  effectiveDensity,
  effectiveHideDateAdded,
  effectiveRenderedViewMode,
  effectiveSort,
  effectiveViewMode,
} from "../view-settings.js";

function memberUrls(overrides: Partial<typeof EMPTY_MEMBER_SETTINGS.urls>) {
  return { urls: { ...EMPTY_MEMBER_SETTINGS.urls, ...overrides } };
}

describe("view-settings effective helpers", () => {
  beforeEach(() => {
    resetStore();
    setState({
      preferences: {
        theme: "dark",
        defaultView: "cards",
        defaultSort: "newest",
        density: "comfortable",
        dateFormat: "iso",
      },
    });
  });

  afterEach(() => resetStore());

  it("returns the override when one is set", () => {
    setState({
      activeUTubID: 1,
      memberSettings: memberUrls({
        sort: "title_az",
        view_mode: "title_line",
        density: "compact",
        hide_date_added: true,
      }),
    });

    expect(effectiveSort()).toBe("title_az");
    expect(effectiveViewMode()).toBe("title_line");
    expect(effectiveDensity()).toBe("compact");
    expect(effectiveHideDateAdded()).toBe(true);
  });

  it("falls back to the Display preference when the override is null", () => {
    setState({ activeUTubID: 1, memberSettings: memberUrls({}) });

    expect(effectiveSort()).toBe("newest");
    expect(effectiveViewMode()).toBe("cards");
    expect(effectiveDensity()).toBe("comfortable");
    expect(effectiveHideDateAdded()).toBe(false);
  });

  it("falls back to the preference with member settings not yet delivered", () => {
    setState({ activeUTubID: 1, memberSettings: null });

    expect(effectiveSort()).toBe("newest");
    expect(effectiveViewMode()).toBe("cards");
    expect(effectiveDensity()).toBe("comfortable");
  });

  it("falls back to the preference when no UTub is selected", () => {
    setState({
      activeUTubID: null,
      memberSettings: memberUrls({
        sort: "oldest",
        view_mode: "title_line",
        density: "compact",
        hide_date_added: true,
      }),
    });

    expect(effectiveSort()).toBe("newest");
    expect(effectiveViewMode()).toBe("cards");
    expect(effectiveDensity()).toBe("comfortable");
    expect(effectiveHideDateAdded()).toBe(false);
  });

  it("falls back to the account default for an unknown override", () => {
    setState({
      activeUTubID: 1,
      memberSettings: memberUrls({ view_mode: "compact" as never }),
    });

    expect(effectiveViewMode()).toBe("cards");
  });

  it("falls back to list when both override and default are unknown", () => {
    setState({
      activeUTubID: 1,
      memberSettings: memberUrls({ view_mode: "compact" as never }),
      preferences: {
        theme: "dark",
        defaultView: "bogus" as never,
        defaultSort: "newest",
        density: "comfortable",
        dateFormat: "iso",
      },
    });

    expect(effectiveViewMode()).toBe("list");
  });

  describe("effectiveRenderedViewMode", () => {
    const originalMatchMedia = window.matchMedia;

    function mockWide({ wide }: { wide: boolean }): void {
      window.matchMedia = vi.fn((query: string) => ({
        matches: wide && query === "(min-width: 992px)",
      })) as unknown as typeof window.matchMedia;
    }

    afterEach(() => {
      window.matchMedia = originalMatchMedia;
    });

    it("keeps cards on a wide viewport", () => {
      mockWide({ wide: true });
      setState({ activeUTubID: 1, memberSettings: memberUrls({}) });
      expect(effectiveRenderedViewMode()).toBe("cards");
    });

    it("renders cards as list on a narrow viewport", () => {
      mockWide({ wide: false });
      setState({ activeUTubID: 1, memberSettings: memberUrls({}) });
      expect(effectiveRenderedViewMode()).toBe("list");
    });

    it("renders cards as list when matchMedia is missing", () => {
      (window as { matchMedia?: unknown }).matchMedia = undefined;
      setState({ activeUTubID: 1, memberSettings: memberUrls({}) });
      expect(effectiveRenderedViewMode()).toBe("list");
    });

    it("never changes a line mode", () => {
      mockWide({ wide: false });
      setState({
        activeUTubID: 1,
        memberSettings: memberUrls({ view_mode: "url_line" }),
      });
      expect(effectiveRenderedViewMode()).toBe("url_line");
    });
  });
});
