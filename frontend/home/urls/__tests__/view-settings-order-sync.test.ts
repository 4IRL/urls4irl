import { APP_CONFIG } from "../../../lib/config.js";
import { getState, resetStore, setState } from "../../../store/app-store.js";
import { EMPTY_MEMBER_SETTINGS } from "../../../types/settings.js";
import type { UtubUrlItem } from "../../../types/url.js";
import type { RefreshResult } from "../../utubs/selectors.js";
import { fetchUTubForRefresh } from "../../utubs/selectors.js";
import { announceSettingsStatus } from "../../panel-settings/announce.js";
import { applyServerUrlOrder } from "../deck.js";
import { syncDeckOrderToServer } from "../view-settings.js";

vi.mock("../../utubs/selectors.js", () => ({ fetchUTubForRefresh: vi.fn() }));
vi.mock("../../panel-settings/announce.js", () => ({
  announceSettingsStatus: vi.fn(),
}));
vi.mock("../deck.js", () => ({ applyServerUrlOrder: vi.fn() }));

const UTUB_ID = 5;

function url(utubUrlID: number): UtubUrlItem {
  return { utubUrlID } as UtubUrlItem;
}

function ok(ids: number[]): RefreshResult {
  return { kind: "ok", data: { id: UTUB_ID, urls: ids.map(url) } as never };
}

function setSort(sort: "newest" | "oldest" | "title_az" | null): void {
  setState({
    memberSettings: { urls: { ...EMPTY_MEMBER_SETTINGS.urls, sort } },
  });
}

interface Deferred {
  promise: Promise<RefreshResult>;
  resolve: (value: RefreshResult) => void;
}

function deferred(): Deferred {
  let resolve!: (value: RefreshResult) => void;
  const promise = new Promise<RefreshResult>((res) => {
    resolve = res;
  });
  return { promise, resolve };
}

describe("syncDeckOrderToServer", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetStore();
    setState({ activeUTubID: UTUB_ID });
    setSort("oldest");
  });

  afterEach(() => resetStore());

  it("fetches once and applies the server order", async () => {
    vi.mocked(fetchUTubForRefresh).mockResolvedValue(ok([3, 1, 2]));

    await syncDeckOrderToServer();

    expect(fetchUTubForRefresh).toHaveBeenCalledTimes(1);
    expect(fetchUTubForRefresh).toHaveBeenCalledWith({ utubID: UTUB_ID });
    expect(applyServerUrlOrder).toHaveBeenCalledWith([url(3), url(1), url(2)]);
  });

  it("does nothing without an active UTub", async () => {
    setState({ activeUTubID: null });

    await syncDeckOrderToServer();

    expect(fetchUTubForRefresh).not.toHaveBeenCalled();
  });

  it("drops an older response that resolves after a newer request", async () => {
    const older = deferred();
    const newer = deferred();
    vi.mocked(fetchUTubForRefresh)
      .mockReturnValueOnce(older.promise)
      .mockReturnValueOnce(newer.promise);

    const olderSync = syncDeckOrderToServer();
    const newerSync = syncDeckOrderToServer();
    newer.resolve(ok([2, 1]));
    await newerSync;
    older.resolve(ok([1, 2]));
    await olderSync;

    expect(applyServerUrlOrder).toHaveBeenCalledTimes(1);
    expect(applyServerUrlOrder).toHaveBeenCalledWith([url(2), url(1)]);
  });

  it("drops a response that lands after a UTub switch", async () => {
    const pending = deferred();
    vi.mocked(fetchUTubForRefresh).mockReturnValueOnce(pending.promise);

    const sync = syncDeckOrderToServer();
    setState({ activeUTubID: 99 });
    pending.resolve(ok([1, 2]));
    await sync;

    expect(applyServerUrlOrder).not.toHaveBeenCalled();
    expect(announceSettingsStatus).not.toHaveBeenCalled();
  });

  it("drops a response after the effective sort changed", async () => {
    const pending = deferred();
    vi.mocked(fetchUTubForRefresh).mockReturnValueOnce(pending.promise);

    const sync = syncDeckOrderToServer();
    setSort("title_az");
    pending.resolve(ok([1, 2]));
    await sync;

    expect(applyServerUrlOrder).not.toHaveBeenCalled();
  });

  it("still applies a response after an unrelated personal save bumped the version", async () => {
    const pending = deferred();
    vi.mocked(fetchUTubForRefresh).mockReturnValueOnce(pending.promise);

    const sync = syncDeckOrderToServer();
    setState({
      memberSettings: {
        urls: {
          ...EMPTY_MEMBER_SETTINGS.urls,
          sort: "oldest",
          hide_copy_button: true,
        },
      },
      memberSettingsVersion: getState().memberSettingsVersion + 1,
    });
    pending.resolve(ok([2, 1]));
    await sync;

    expect(applyServerUrlOrder).toHaveBeenCalledTimes(1);
  });

  it.each(["error", "gone"] as const)(
    "announces a notice and leaves the sort alone when the refresh is a %s",
    async (kind) => {
      vi.mocked(fetchUTubForRefresh).mockResolvedValue({ kind });

      await syncDeckOrderToServer();

      expect(applyServerUrlOrder).not.toHaveBeenCalled();
      expect(announceSettingsStatus).toHaveBeenCalledWith({
        message:
          APP_CONFIG.strings.URLS_PERSONAL_SETTINGS_SORT_ORDER_PENDING_NOTICE,
      });
      expect(getState().memberSettings?.urls.sort).toBe("oldest");
    },
  );

  it("does not announce a failure for a superseded request", async () => {
    const older = deferred();
    const newer = deferred();
    vi.mocked(fetchUTubForRefresh)
      .mockReturnValueOnce(older.promise)
      .mockReturnValueOnce(newer.promise);

    const olderSync = syncDeckOrderToServer();
    const newerSync = syncDeckOrderToServer();
    older.resolve({ kind: "error" });
    await olderSync;
    newer.resolve(ok([1]));
    await newerSync;

    expect(announceSettingsStatus).not.toHaveBeenCalled();
    expect(applyServerUrlOrder).toHaveBeenCalledTimes(1);
  });
});
