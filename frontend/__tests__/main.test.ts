import { setState } from "../store/app-store.js";

vi.mock("../store/app-store.js", () => ({
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
