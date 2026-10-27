import { resetStore, setState } from "../../../store/app-store.js";
import { EMPTY_MEMBER_SETTINGS } from "../../../types/settings.js";
import {
  effectiveDensity,
  effectiveHideDateAdded,
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
        view_mode: "compact",
        density: "compact",
        hide_date_added: true,
      }),
    });

    expect(effectiveSort()).toBe("title_az");
    expect(effectiveViewMode()).toBe("compact");
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
        view_mode: "compact",
        density: "compact",
        hide_date_added: true,
      }),
    });

    expect(effectiveSort()).toBe("newest");
    expect(effectiveViewMode()).toBe("cards");
    expect(effectiveDensity()).toBe("comfortable");
    expect(effectiveHideDateAdded()).toBe(false);
  });
});
