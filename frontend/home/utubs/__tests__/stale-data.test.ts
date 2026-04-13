import { updateUTubOnFindingStaleData } from "../stale-data.js";
import { getUTubInfo } from "../selectors.js";
import { setState } from "../../../store/app-store.js";
import { emit } from "../../../lib/event-bus.js";

vi.mock("../selectors.js", () => ({
  getUTubInfo: vi.fn(),
}));

vi.mock("../../../store/app-store.js", () => ({
  setState: vi.fn(),
}));

vi.mock("../../../lib/event-bus.js", async () => {
  const actual = await vi.importActual<
    typeof import("../../../lib/event-bus.js")
  >("../../../lib/event-bus.js");
  return {
    ...actual,
    emit: vi.fn(),
  };
});

describe("updateUTubOnFindingStaleData", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("when getUTubInfo resolves null", () => {
    it("returns early without calling setState or emit", async () => {
      vi.mocked(getUTubInfo).mockReturnValue(
        $.Deferred<null>().resolve(null).promise() as unknown as ReturnType<
          typeof getUTubInfo
        >,
      );

      await updateUTubOnFindingStaleData(42);

      expect(setState).not.toHaveBeenCalled();
      expect(emit).not.toHaveBeenCalled();
    });
  });
});
