import { ajaxCall } from "../../../lib/ajax.js";
import { APP_CONFIG } from "../../../lib/config.js";
import {
  getState,
  resetStore,
  setState,
  subscribe,
} from "../../../store/app-store.js";
import type { PanelId, ResolvedUtubSettings } from "../../../types/settings.js";
import {
  createMockJqXHR,
  createMockXhr,
} from "../../../__tests__/helpers/mock-jquery.js";
import { removeUTubLocally } from "../../utubs/remove-local.js";
import { fetchUTubForRefresh } from "../../utubs/selectors.js";
import type { RefreshResult } from "../../utubs/selectors.js";
import { showURLDeckBannerError } from "../../urls/deck.js";
import {
  PATCH_TIMEOUT_MS,
  handleActiveUTubGone,
  mapXhrToSaveOutcome,
  patchUtubSettings,
  resyncSettings,
} from "../client.js";

vi.mock("../../../lib/ajax.js", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/ajax.js")>(
    "../../../lib/ajax.js",
  );
  return { ...actual, ajaxCall: vi.fn() };
});
vi.mock("../../utubs/remove-local.js", () => ({ removeUTubLocally: vi.fn() }));
vi.mock("../../utubs/selectors.js", () => ({ fetchUTubForRefresh: vi.fn() }));
vi.mock("../../urls/deck.js", () => ({ showURLDeckBannerError: vi.fn() }));

const UTUB_ID = 7;
const LOCKED = APP_CONFIG.strings.UTUB_IS_LOCKED;
const NOT_AUTHORIZED = APP_CONFIG.strings.NOT_AUTHORIZED;

// The resolver fills the urls section's defaults into every payload.
const URLS_DEFAULTS = {
  default_url_scheme: "https",
  hide_scheme_selector: false,
} as const;

function settingsWith(
  overrides: Partial<ResolvedUtubSettings> = {},
): ResolvedUtubSettings {
  return {
    utubs: {},
    members: {},
    tags: {},
    ...overrides,
    urls: { ...URLS_DEFAULTS, ...overrides.urls },
  };
}

function failXhr({
  status,
  message,
  html = false,
  handled429 = false,
}: {
  status: number;
  message?: string;
  html?: boolean;
  handled429?: boolean;
}): JQuery.jqXHR {
  return createMockXhr({
    status,
    responseJSON: html || message === undefined ? undefined : { message },
    getResponseHeader: () =>
      html ? "text/html; charset=utf-8" : "application/json",
    _429Handled: handled429,
  });
}

function startPatch({ panel = "urls" }: { panel?: PanelId } = {}): {
  request: ReturnType<typeof createMockJqXHR>;
  result: ReturnType<typeof patchUtubSettings>;
} {
  const request = createMockJqXHR();
  vi.mocked(ajaxCall).mockReturnValue(request);
  const result = patchUtubSettings({
    utubID: UTUB_ID,
    panel,
    patch: { sort: "added" },
  });
  return { request, result };
}

describe("patchUtubSettings", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetStore();
    setState({ activeUTubID: UTUB_ID, settings: settingsWith() });
    document.body.innerHTML =
      '<div id="MobilePanelAnnouncement"></div><div id="confirmModal"></div>';
  });

  it("sends { [panel]: patch } with the explicit write timeout", async () => {
    const { request, result } = startPatch({ panel: "tags" });
    request.resolve({ utubID: UTUB_ID, settings: settingsWith() });
    await result;

    expect(ajaxCall).toHaveBeenCalledWith(
      "patch",
      APP_CONFIG.routes.updateUTubSettings(UTUB_ID),
      { tags: { sort: "added" } },
      PATCH_TIMEOUT_MS,
    );
    expect(PATCH_TIMEOUT_MS).toBe(10000);
  });

  describe("200", () => {
    it("merges only the PATCHed panel key and bumps the version in one setState", async () => {
      setState({
        settings: settingsWith({ tags: { keep: 1 } as never }),
        settingsVersion: 4,
      });
      const listener = vi.fn();
      const unsubscribe = subscribe(listener);

      const { request, result } = startPatch({ panel: "urls" });
      request.resolve({
        utubID: UTUB_ID,
        settings: settingsWith({
          urls: { sort: "added" } as never,
          tags: { other: 2 } as never,
        }),
      });
      const outcome = await result;
      unsubscribe();

      expect(getState().settings).toEqual(
        settingsWith({
          urls: { sort: "added" } as never,
          tags: { keep: 1 } as never,
        }),
      );
      expect(getState().settingsVersion).toBe(5);
      expect(outcome).toEqual({
        outcome: "ok",
        settings: getState().settings,
      });
      const settingsNotifications = listener.mock.calls.filter(([keys]) =>
        keys.includes("settings"),
      );
      expect(settingsNotifications).toHaveLength(1);
      expect(settingsNotifications[0][0]).toContain("settingsVersion");
    });

    it("an out-of-order 200 for panel A does not revert panel B", async () => {
      const first = startPatch({ panel: "urls" });
      const second = startPatch({ panel: "tags" });

      second.request.resolve({
        utubID: UTUB_ID,
        settings: settingsWith({
          tags: { t: 1 } as never,
          urls: {} as never,
        }),
      });
      await second.result;
      first.request.resolve({
        utubID: UTUB_ID,
        settings: settingsWith({
          urls: { u: 1 } as never,
          tags: {} as never,
        }),
      });
      await first.result;

      expect(getState().settings?.tags).toEqual({ t: 1 });
      expect(getState().settings?.urls).toEqual({ ...URLS_DEFAULTS, u: 1 });
      expect(getState().settingsVersion).toBe(2);
    });

    it.each([
      ["a non-JSON body", "<html>login</html>"],
      ["a missing settings field", { utubID: UTUB_ID }],
      ["a missing panel key", { utubID: UTUB_ID, settings: { tags: {} } }],
    ])(
      "%s resolves error and does not write the store",
      async (_label, body) => {
        setState({ settings: settingsWith({ urls: { keep: 1 } as never }) });
        const before = getState().settings;
        const { request, result } = startPatch({ panel: "urls" });
        request.resolve(body);

        expect(await result).toEqual({ outcome: "error" });
        expect(getState().settings).toBe(before);
        expect(getState().settingsVersion).toBe(0);
      },
    );

    it("uses the resolved response when the slice is null", async () => {
      setState({ settings: null });
      const { request, result } = startPatch();
      request.resolve({
        utubID: UTUB_ID,
        settings: { urls: { sort: "added" } },
      });
      await result;

      expect(getState().settings).toEqual(
        settingsWith({ urls: { sort: "added" } as never }),
      );
    });
  });

  describe("failures", () => {
    const table: Array<[string, Parameters<typeof failXhr>[0], object]> = [
      ["400", { status: 400, message: "bad" }, { outcome: "invalid" }],
      ["403 locked", { status: 403, message: LOCKED }, { outcome: "locked" }],
      [
        "403 not authorized",
        { status: 403, message: NOT_AUTHORIZED },
        { outcome: "forbidden" },
      ],
      ["403 HTML (CSRF)", { status: 403, html: true }, { outcome: "error" }],
      [
        "403 other JSON",
        { status: 403, message: "nope" },
        { outcome: "error" },
      ],
      ["404", { status: 404, message: "gone" }, { outcome: "gone" }],
      ["404 HTML", { status: 404, html: true }, { outcome: "error" }],
      ["400 HTML", { status: 400, html: true }, { outcome: "invalid" }],
      [
        "429 handled",
        { status: 429, handled429: true },
        { outcome: "error", resync: false },
      ],
      ["500", { status: 500, message: "boom" }, { outcome: "error" }],
      ["timeout (status 0)", { status: 0 }, { outcome: "error" }],
    ];

    it.each(table)("%s", async (_label, xhrProps, expected) => {
      const { request, result } = startPatch();
      request.reject(failXhr(xhrProps));
      const outcome = await result;

      expect(outcome).toEqual(expected);
      expect(getState().settingsVersion).toBe(0);
      expect(showURLDeckBannerError).not.toHaveBeenCalledWith(LOCKED);
    });

    it("omits resync on every error except the handled 429", async () => {
      const { request, result } = startPatch();
      request.reject(failXhr({ status: 500, message: "boom" }));
      expect(await result).not.toHaveProperty("resync");
    });

    it("does not touch the confirm modal or banner for either 403 JSON case", async () => {
      // The bootstrap plugin is not loaded under test: install a stand-in.
      const hide = vi.fn();
      const jQueryFn = window.jQuery.fn as unknown as Record<string, unknown>;
      jQueryFn.modal = hide;
      try {
        for (const message of [LOCKED, NOT_AUTHORIZED]) {
          const { request, result } = startPatch();
          request.reject(failXhr({ status: 403, message }));
          await result;
        }
        expect(hide).not.toHaveBeenCalled();
        expect(showURLDeckBannerError).not.toHaveBeenCalled();
      } finally {
        delete jQueryFn.modal;
      }
    });

    it("an active-UTub 404 removes the UTub once and shows the banner", async () => {
      const { request, result } = startPatch();
      request.reject(failXhr({ status: 404, message: "gone" }));
      await result;

      expect(removeUTubLocally).toHaveBeenCalledTimes(1);
      expect(removeUTubLocally).toHaveBeenCalledWith({ utubID: UTUB_ID });
      expect(showURLDeckBannerError).toHaveBeenCalledWith(
        APP_CONFIG.strings.UTUB_NO_LONGER_AVAILABLE,
      );
    });
  });

  describe("stale results (active UTub changed)", () => {
    it("a late 200 resolves stale/failed:false with no store effect", async () => {
      const { request, result } = startPatch();
      setState({ activeUTubID: 99, settings: settingsWith() });
      const before = getState().settings;
      request.resolve({
        utubID: UTUB_ID,
        settings: settingsWith({ urls: { x: 1 } as never }),
      });

      expect(await result).toEqual({ outcome: "stale", failed: false });
      expect(getState().settings).toBe(before);
      expect(getState().settingsVersion).toBe(0);
    });

    it.each([404, 500])(
      "a late %i resolves stale/failed:true with no removal",
      async (status) => {
        const { request, result } = startPatch();
        setState({ activeUTubID: 99 });
        request.reject(failXhr({ status, message: "x" }));

        expect(await result).toEqual({ outcome: "stale", failed: true });
        expect(removeUTubLocally).not.toHaveBeenCalled();
        expect(showURLDeckBannerError).not.toHaveBeenCalled();
        expect(getState().settingsVersion).toBe(0);
      },
    );
  });
});

describe("mapXhrToSaveOutcome", () => {
  beforeEach(() => vi.clearAllMocks());

  it("maps the failure table without any removal or banner side effects", () => {
    expect(mapXhrToSaveOutcome(failXhr({ status: 404, message: "x" }))).toEqual(
      { outcome: "gone" },
    );
    expect(mapXhrToSaveOutcome(failXhr({ status: 400, message: "x" }))).toEqual(
      { outcome: "invalid" },
    );
    expect(
      mapXhrToSaveOutcome(failXhr({ status: 429, handled429: true })),
    ).toEqual({ outcome: "error", resync: false });
    expect(mapXhrToSaveOutcome(failXhr({ status: 403, html: true }))).toEqual({
      outcome: "error",
    });
    expect(mapXhrToSaveOutcome(failXhr({ status: 404, html: true }))).toEqual({
      outcome: "error",
    });
    expect(mapXhrToSaveOutcome(failXhr({ status: 502 }))).toEqual({
      outcome: "error",
    });
    expect(removeUTubLocally).not.toHaveBeenCalled();
    expect(showURLDeckBannerError).not.toHaveBeenCalled();
  });

  it("treats a 403 with no JSON body as error", () => {
    expect(mapXhrToSaveOutcome(failXhr({ status: 403 }))).toEqual({
      outcome: "error",
    });
  });
});

describe("handleActiveUTubGone", () => {
  it("removes the UTub, shows the banner and announces on the next tick", () => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    document.body.innerHTML = '<div id="MobilePanelAnnouncement"></div>';

    handleActiveUTubGone({ utubID: UTUB_ID });
    vi.runAllTimers();

    expect(removeUTubLocally).toHaveBeenCalledWith({ utubID: UTUB_ID });
    expect(showURLDeckBannerError).toHaveBeenCalledWith(
      APP_CONFIG.strings.UTUB_NO_LONGER_AVAILABLE,
    );
    expect(
      document.getElementById("MobilePanelAnnouncement")?.textContent,
    ).toBe(APP_CONFIG.strings.UTUB_NO_LONGER_AVAILABLE);
    vi.useRealTimers();
  });
});

describe("resyncSettings", () => {
  function ok({ urls }: { urls: object }): RefreshResult {
    return {
      kind: "ok",
      data: { id: UTUB_ID, settings: { urls } } as never,
    };
  }

  beforeEach(() => {
    vi.clearAllMocks();
    resetStore();
    setState({
      activeUTubID: UTUB_ID,
      settings: settingsWith({ tags: { keep: 1 } as never }),
      settingsVersion: 3,
      urls: [],
    });
  });

  it("writes only settings, without bumping the version", async () => {
    vi.mocked(fetchUTubForRefresh).mockResolvedValue(ok({ urls: { a: 1 } }));
    const urlsBefore = getState().urls;

    expect(await resyncSettings({ utubID: UTUB_ID })).toBe(true);

    expect(getState().settings).toEqual(
      settingsWith({ urls: { a: 1 } as never }),
    );
    expect(getState().urls).toBe(urlsBefore);
    expect(getState().settingsVersion).toBe(3);
  });

  it("is skipped when the active UTub differs", async () => {
    expect(await resyncSettings({ utubID: 99 })).toBe(false);
    expect(fetchUTubForRefresh).not.toHaveBeenCalled();
  });

  it("does not write when the UTub changed mid-flight", async () => {
    vi.mocked(fetchUTubForRefresh).mockImplementation(async () => {
      setState({ activeUTubID: 99 });
      return ok({ urls: { a: 1 } });
    });

    expect(await resyncSettings({ utubID: UTUB_ID })).toBe(false);
    // Switching UTub cleared the slice; the stale payload was not written.
    expect(getState().settings).toBeNull();
  });

  it("retries once with a fresh capture when a 200 lands mid-flight", async () => {
    let calls = 0;
    vi.mocked(fetchUTubForRefresh).mockImplementation(async () => {
      calls += 1;
      if (calls === 1) {
        setState({ settingsVersion: getState().settingsVersion + 1 });
        return ok({ urls: { stale: 1 } });
      }
      return ok({ urls: { fresh: 1 } });
    });

    expect(await resyncSettings({ utubID: UTUB_ID })).toBe(true);
    expect(calls).toBe(2);
    expect(getState().settings?.urls).toEqual({ ...URLS_DEFAULTS, fresh: 1 });
    expect(getState().settingsVersion).toBe(4);
  });

  it("is a no-op resolving false when the guard trips again", async () => {
    vi.mocked(fetchUTubForRefresh).mockImplementation(async () => {
      setState({ settingsVersion: getState().settingsVersion + 1 });
      return ok({ urls: { a: 1 } });
    });
    const before = getState().settings;

    expect(await resyncSettings({ utubID: UTUB_ID })).toBe(false);
    expect(fetchUTubForRefresh).toHaveBeenCalledTimes(2);
    expect(getState().settings).toBe(before);
  });

  it.each(["error", "gone"] as const)(
    "a %s re-fetch resolves false without a retry",
    async (kind) => {
      vi.mocked(fetchUTubForRefresh).mockResolvedValue({ kind });
      const before = getState().settings;

      expect(await resyncSettings({ utubID: UTUB_ID })).toBe(false);
      expect(fetchUTubForRefresh).toHaveBeenCalledTimes(1);
      expect(getState().settings).toBe(before);
    },
  );
});
