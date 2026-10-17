import { createMockJqXHRChainable } from "../../../__tests__/helpers/mock-jquery.js";
import { getState, resetStore } from "../../../store/app-store.js";
import {
  loadInitialTrashCount,
  refreshTrashCount,
  renderTrashCount,
} from "../count.js";
import { getAllUTubs } from "../../utubs/utils.js";

vi.mock("../../utubs/utils.js", () => ({
  getAllUTubs: vi.fn(),
}));

type Callback = (arg?: unknown) => void;

const HTML = `
  <div id="TrashSelector"><span id="TrashSelectorCount"></span></div>
  <script id="trash-count-data" type="application/json">6</script>
`;

describe("trash count", () => {
  beforeEach(() => {
    document.body.innerHTML = HTML;
    resetStore();
    vi.mocked(getAllUTubs).mockReset();
  });

  describe("loadInitialTrashCount", () => {
    it("reads #trash-count-data into the store", () => {
      loadInitialTrashCount();
      expect(getState().trashCount).toBe(6);
    });

    it("leaves the count at 0 when the script tag is missing", () => {
      document.getElementById("trash-count-data")?.remove();
      loadInitialTrashCount();
      expect(getState().trashCount).toBe(0);
    });

    it("falls back to 0 when the payload is not a number", () => {
      document.getElementById("trash-count-data")!.textContent = '"abc"';
      loadInitialTrashCount();
      expect(getState().trashCount).toBe(0);
    });
  });

  describe("renderTrashCount", () => {
    it("writes (n) into #TrashSelectorCount", () => {
      loadInitialTrashCount();
      renderTrashCount();
      expect(document.getElementById("TrashSelectorCount")?.textContent).toBe(
        "(6)",
      );
    });
  });

  describe("refreshTrashCount", () => {
    it("fetches GET /utubs and stores + renders the returned trashCount", async () => {
      vi.mocked(getAllUTubs).mockReturnValue(
        createMockJqXHRChainable({
          done: (callback) => (callback as Callback)({ trashCount: 11 }),
          always: (callback) => (callback as Callback)(),
        }) as ReturnType<typeof getAllUTubs>,
      );

      await refreshTrashCount();

      expect(getAllUTubs).toHaveBeenCalledTimes(1);
      expect(getState().trashCount).toBe(11);
      expect(document.getElementById("TrashSelectorCount")?.textContent).toBe(
        "(11)",
      );
    });

    it("drops a superseded response that lands after a newer one", async () => {
      const resolvers: Array<(count: number) => void> = [];
      vi.mocked(getAllUTubs).mockImplementation(() => {
        const chain = {
          done: (callback: Callback) => {
            resolvers.push((count) => callback({ trashCount: count }));
            return chain;
          },
          fail: () => chain,
          always: () => chain,
        };
        return chain as unknown as ReturnType<typeof getAllUTubs>;
      });

      void refreshTrashCount();
      void refreshTrashCount();
      resolvers[1](2);
      resolvers[0](9);

      expect(getState().trashCount).toBe(2);
      expect(document.getElementById("TrashSelectorCount")?.textContent).toBe(
        "(2)",
      );
    });

    it("keeps the old count when the fetch fails", async () => {
      loadInitialTrashCount();
      renderTrashCount();
      vi.mocked(getAllUTubs).mockReturnValue(
        createMockJqXHRChainable({
          fail: (callback) => (callback as Callback)({ status: 500 }),
          always: (callback) => (callback as Callback)(),
        }) as ReturnType<typeof getAllUTubs>,
      );

      await refreshTrashCount();

      expect(getState().trashCount).toBe(6);
      expect(document.getElementById("TrashSelectorCount")?.textContent).toBe(
        "(6)",
      );
    });
  });
});
