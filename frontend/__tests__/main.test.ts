import { getState, setState } from "../store/app-store.js";

vi.mock("../store/app-store.js", () => ({
  getState: vi.fn(() => ({
    preferences: {
      utubSort: "recent_activity",
      memberSort: "name_az",
      showRowCounts: false,
      showListTotals: true,
      tagSort: "most_in_view",
      tagMatchMode: "all",
      tagCountStyle: "in_view_total",
      showTagsOnCollapsed: false,
      collapsedTagsStyle: "one_line",
      tagDropOpensUrl: true,
    },
  })),
  setState: vi.fn(),
}));

describe("loadInitialUtubState", () => {
  afterEach(() => {
    vi.mocked(setState).mockClear();
  });

  it("calls setState with parsed utubs data when #utubs-data is present", async () => {
    const testUtubs = [{ id: 1, name: "Test UTub" }];
    const script = document.createElement("script");
    script.id = "utubs-data";
    script.type = "application/json";
    script.textContent = JSON.stringify(testUtubs);
    document.body.appendChild(script);

    const { loadInitialUtubState } = await import("../lib/initial-state.js");
    loadInitialUtubState();

    expect(vi.mocked(setState)).toHaveBeenCalledWith({ utubs: testUtubs });

    script.remove();
  });

  it("does not call setState when #utubs-data is absent", async () => {
    const { loadInitialUtubState } = await import("../lib/initial-state.js");
    loadInitialUtubState();

    expect(vi.mocked(setState)).not.toHaveBeenCalled();
  });
});

describe("loadInitialPreferencesState", () => {
  afterEach(() => {
    vi.mocked(setState).mockClear();
    vi.mocked(getState).mockClear();
    document.getElementById("user-preferences-data")?.remove();
  });

  it("calls setState with the mapped preferences shape when #user-preferences-data holds valid JSON", async () => {
    const context = {
      display_theme: "dark",
      display_default_view: "cards",
      display_default_sort: "oldest",
      display_density: "compact",
      display_date_format: "us",
      display_utub_sort: "name_az",
      display_member_sort: "recently_joined",
      display_show_row_counts: true,
      display_show_list_totals: false,
      display_tag_sort: "name_az",
      display_tag_match_mode: "any",
      display_tag_count_style: "hidden",
      display_show_tags_on_collapsed: true,
      display_collapsed_tags_style: "all",
      display_tag_drop_opens_url: false,
    };
    const script = document.createElement("script");
    script.id = "user-preferences-data";
    script.type = "application/json";
    script.textContent = JSON.stringify(context);
    document.body.appendChild(script);

    const { loadInitialPreferencesState } =
      await import("../lib/initial-state.js");
    loadInitialPreferencesState();

    expect(vi.mocked(setState)).toHaveBeenCalledWith({
      preferences: {
        theme: "dark",
        defaultView: "cards",
        defaultSort: "oldest",
        density: "compact",
        dateFormat: "us",
        utubSort: "name_az",
        memberSort: "recently_joined",
        showRowCounts: true,
        showListTotals: false,
        tagSort: "name_az",
        tagMatchMode: "any",
        tagCountStyle: "hidden",
        showTagsOnCollapsed: true,
        collapsedTagsStyle: "all",
        tagDropOpensUrl: false,
      },
    });
  });

  it("falls back to each tag default for bogus or missing tag values", async () => {
    const script = document.createElement("script");
    script.id = "user-preferences-data";
    script.type = "application/json";
    script.textContent = JSON.stringify({
      display_theme: "dark",
      display_tag_sort: "bogus",
      display_tag_match_mode: "some",
      display_tag_count_style: 3,
      display_show_tags_on_collapsed: "yes",
      display_collapsed_tags_style: null,
      display_tag_drop_opens_url: 0,
    });
    document.body.appendChild(script);

    const { loadInitialPreferencesState } =
      await import("../lib/initial-state.js");
    loadInitialPreferencesState();

    expect(vi.mocked(setState)).toHaveBeenCalledWith({
      preferences: expect.objectContaining({
        tagSort: "most_in_view",
        tagMatchMode: "all",
        tagCountStyle: "in_view_total",
        showTagsOnCollapsed: false,
        collapsedTagsStyle: "one_line",
        tagDropOpensUrl: true,
      }),
    });
  });

  it("keeps the tag defaults when the tag keys are absent", async () => {
    const script = document.createElement("script");
    script.id = "user-preferences-data";
    script.type = "application/json";
    script.textContent = JSON.stringify({ display_theme: "dark" });
    document.body.appendChild(script);

    const { loadInitialPreferencesState } =
      await import("../lib/initial-state.js");
    loadInitialPreferencesState();

    expect(vi.mocked(setState)).toHaveBeenCalledWith({
      preferences: expect.objectContaining({
        tagSort: "most_in_view",
        tagDropOpensUrl: true,
      }),
    });
  });

  it("falls back to name_az for an unknown stored member sort", async () => {
    const script = document.createElement("script");
    script.id = "user-preferences-data";
    script.type = "application/json";
    script.textContent = JSON.stringify({
      display_theme: "dark",
      display_member_sort: "bogus",
    });
    document.body.appendChild(script);

    const { loadInitialPreferencesState } =
      await import("../lib/initial-state.js");
    loadInitialPreferencesState();

    expect(vi.mocked(setState)).toHaveBeenCalledWith({
      preferences: expect.objectContaining({ memberSort: "name_az" }),
    });
  });

  it("falls back to today's look for an unknown sort and non-boolean toggles", async () => {
    const script = document.createElement("script");
    script.id = "user-preferences-data";
    script.type = "application/json";
    script.textContent = JSON.stringify({
      display_theme: "dark",
      display_utub_sort: "bogus",
      display_show_row_counts: "yes",
      display_show_list_totals: 0,
    });
    document.body.appendChild(script);

    const { loadInitialPreferencesState } =
      await import("../lib/initial-state.js");
    loadInitialPreferencesState();

    expect(vi.mocked(setState)).toHaveBeenCalledWith({
      preferences: expect.objectContaining({
        utubSort: "recent_activity",
        showRowCounts: false,
        showListTotals: true,
      }),
    });
  });

  it("falls back to today's look when the new keys are missing", async () => {
    const script = document.createElement("script");
    script.id = "user-preferences-data";
    script.type = "application/json";
    script.textContent = JSON.stringify({ display_theme: "dark" });
    document.body.appendChild(script);

    const { loadInitialPreferencesState } =
      await import("../lib/initial-state.js");
    loadInitialPreferencesState();

    expect(vi.mocked(setState)).toHaveBeenCalledWith({
      preferences: expect.objectContaining({
        utubSort: "recent_activity",
        showRowCounts: false,
        showListTotals: true,
      }),
    });
  });

  it("does not call setState when #user-preferences-data is absent", async () => {
    const { loadInitialPreferencesState } =
      await import("../lib/initial-state.js");
    loadInitialPreferencesState();

    expect(vi.mocked(setState)).not.toHaveBeenCalled();
  });

  it("does not call setState when #user-preferences-data content is empty", async () => {
    const script = document.createElement("script");
    script.id = "user-preferences-data";
    script.type = "application/json";
    script.textContent = "";
    document.body.appendChild(script);

    const { loadInitialPreferencesState } =
      await import("../lib/initial-state.js");
    loadInitialPreferencesState();

    expect(vi.mocked(setState)).not.toHaveBeenCalled();
  });

  it('does not call setState when #user-preferences-data content is literal "null"', async () => {
    const script = document.createElement("script");
    script.id = "user-preferences-data";
    script.type = "application/json";
    script.textContent = "null";
    document.body.appendChild(script);

    const { loadInitialPreferencesState } =
      await import("../lib/initial-state.js");
    loadInitialPreferencesState();

    expect(vi.mocked(setState)).not.toHaveBeenCalled();
  });
});
