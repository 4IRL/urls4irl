import { updateUTubOnFindingStaleData } from "../stale-data.js";
import { getUTubInfo } from "../selectors.js";
import { setState } from "../../../store/app-store.js";
import { emit, AppEvents } from "../../../lib/event-bus.js";
import type { UtubDetail } from "../../../types/utub.js";

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

  describe("when getUTubInfo resolves with a full UTub", () => {
    const mockUtubID = 1;
    const mockUrls = [
      {
        utubUrlID: 10,
        urlString: "https://example.com",
        utubUrlTagIDs: [100],
        urlTitle: "Example",
        canDelete: true,
      },
    ];
    const mockTags = [{ id: 100, tagString: "tag-a", tagApplied: 1 }];
    const mockMembers = [{ id: 1000, username: "alice" }];
    const mockUtubDetail: UtubDetail = {
      status: "Success",
      id: mockUtubID,
      name: "My UTub",
      createdByUserID: 1000,
      createdAt: "2026-01-01T00:00:00Z",
      description: "Sample description",
      members: mockMembers,
      urls: mockUrls,
      tags: mockTags,
      isCreator: true,
      currentUser: 1000,
    };

    beforeEach(() => {
      document.body.innerHTML = `
        <div id="URLDeckHeader"></div>
        <div id="URLDeckSubheader"></div>
        <utubselector utubid="1"><span class="UTubName"></span></utubselector>
      `;
      vi.mocked(getUTubInfo).mockReturnValue(
        $.Deferred<UtubDetail>()
          .resolve(mockUtubDetail)
          .promise() as unknown as ReturnType<typeof getUTubInfo>,
      );
    });

    it("emits STALE_DATA_DETECTED with urls, tags, members from response", async () => {
      await updateUTubOnFindingStaleData(mockUtubID);

      expect(emit).toHaveBeenCalledWith(AppEvents.STALE_DATA_DETECTED, {
        utubID: mockUtubID,
        urls: mockUrls,
        tags: mockTags,
        members: mockMembers,
      });
    });

    it("calls setState with urls, tags, members from response", async () => {
      await updateUTubOnFindingStaleData(mockUtubID);

      expect(setState).toHaveBeenCalledWith({
        urls: mockUrls,
        tags: mockTags,
        members: mockMembers,
      });
    });

    it("emits event BEFORE calling setState", async () => {
      await updateUTubOnFindingStaleData(mockUtubID);

      const emitOrder = vi.mocked(emit).mock.invocationCallOrder[0];
      const setStateOrder = vi.mocked(setState).mock.invocationCallOrder[0];
      expect(emitOrder).toBeLessThan(setStateOrder);
    });
  });
});
