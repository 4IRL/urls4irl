import { getState, setState } from "../store/app-store.js";

vi.mock("../store/app-store.js", () => ({
  getState: vi.fn(() => ({ preferences: {} })),
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
    };
    const script = document.createElement("script");
    script.id = "user-preferences-data";
    script.type = "application/json";
    script.textContent = JSON.stringify(context);
    document.body.appendChild(script);

    const { loadInitialPreferencesState } = await import(
      "../lib/initial-state.js"
    );
    loadInitialPreferencesState();

    expect(vi.mocked(setState)).toHaveBeenCalledWith({
      preferences: {
        theme: "dark",
        defaultView: "cards",
        defaultSort: "oldest",
        density: "compact",
        dateFormat: "us",
      },
    });
  });

  it("does not call setState when #user-preferences-data is absent", async () => {
    const { loadInitialPreferencesState } = await import(
      "../lib/initial-state.js"
    );
    loadInitialPreferencesState();

    expect(vi.mocked(setState)).not.toHaveBeenCalled();
  });

  it("does not call setState when #user-preferences-data content is empty", async () => {
    const script = document.createElement("script");
    script.id = "user-preferences-data";
    script.type = "application/json";
    script.textContent = "";
    document.body.appendChild(script);

    const { loadInitialPreferencesState } = await import(
      "../lib/initial-state.js"
    );
    loadInitialPreferencesState();

    expect(vi.mocked(setState)).not.toHaveBeenCalled();
  });

  it('does not call setState when #user-preferences-data content is literal "null"', async () => {
    const script = document.createElement("script");
    script.id = "user-preferences-data";
    script.type = "application/json";
    script.textContent = "null";
    document.body.appendChild(script);

    const { loadInitialPreferencesState } = await import(
      "../lib/initial-state.js"
    );
    loadInitialPreferencesState();

    expect(vi.mocked(setState)).not.toHaveBeenCalled();
  });
});
