import type { Mock } from "vitest";

import { resetDeviceTypeCache } from "../../__tests__/helpers/device-type-test-utils.js";
import { TABLET_WIDTH } from "../constants.js";
import { getDeviceType, initDeviceTypeListener } from "../device-type.js";

const MOBILE_MEDIA_QUERY = "(max-width: " + (TABLET_WIDTH - 1) + "px)";

type MediaQueryListener = (event: MediaQueryListEvent) => void;

interface MockMediaQueryList {
  matches: boolean;
  media: string;
  addEventListener: Mock;
  removeEventListener: Mock;
}

function makeMockMediaQueryList(matches: boolean): MockMediaQueryList {
  return {
    matches,
    media: MOBILE_MEDIA_QUERY,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  };
}

describe("device-type", () => {
  beforeEach(() => {
    resetDeviceTypeCache();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    resetDeviceTypeCache();
  });

  describe("getDeviceType()", () => {
    it("returns 'mobile' when matchMedia matches", () => {
      const mockMediaQueryList = makeMockMediaQueryList(true);
      const matchMediaMock = vi.fn().mockReturnValue(mockMediaQueryList);
      vi.stubGlobal("matchMedia", matchMediaMock);

      expect(getDeviceType()).toBe("mobile");
      expect(matchMediaMock).toHaveBeenCalledWith(MOBILE_MEDIA_QUERY);
    });

    it("returns 'desktop' when matchMedia does not match", () => {
      const mockMediaQueryList = makeMockMediaQueryList(false);
      const matchMediaMock = vi.fn().mockReturnValue(mockMediaQueryList);
      vi.stubGlobal("matchMedia", matchMediaMock);

      expect(getDeviceType()).toBe("desktop");
      expect(matchMediaMock).toHaveBeenCalledWith(MOBILE_MEDIA_QUERY);
    });

    it("caches the result across repeated calls (matchMedia invoked once)", () => {
      const mockMediaQueryList = makeMockMediaQueryList(true);
      const matchMediaMock = vi.fn().mockReturnValue(mockMediaQueryList);
      vi.stubGlobal("matchMedia", matchMediaMock);

      expect(getDeviceType()).toBe("mobile");
      expect(getDeviceType()).toBe("mobile");
      expect(getDeviceType()).toBe("mobile");
      expect(matchMediaMock).toHaveBeenCalledTimes(1);
    });
  });

  describe("initDeviceTypeListener()", () => {
    it("registers a 'change' listener via addEventListener (not the deprecated addListener)", () => {
      const mockMediaQueryList = makeMockMediaQueryList(false);
      const matchMediaMock = vi.fn().mockReturnValue(mockMediaQueryList);
      vi.stubGlobal("matchMedia", matchMediaMock);

      initDeviceTypeListener();

      expect(matchMediaMock).toHaveBeenCalledWith(MOBILE_MEDIA_QUERY);
      expect(mockMediaQueryList.addEventListener).toHaveBeenCalledTimes(1);
      expect(mockMediaQueryList.addEventListener).toHaveBeenCalledWith(
        "change",
        expect.any(Function),
      );
    });

    it("updates the cached value when the listener fires with matches=true", () => {
      const mockMediaQueryList = makeMockMediaQueryList(false);
      const matchMediaMock = vi.fn().mockReturnValue(mockMediaQueryList);
      vi.stubGlobal("matchMedia", matchMediaMock);

      expect(getDeviceType()).toBe("desktop");
      initDeviceTypeListener();

      const [, registeredListener] =
        mockMediaQueryList.addEventListener.mock.calls[0];
      const fireListener = registeredListener as MediaQueryListener;
      fireListener({ matches: true } as MediaQueryListEvent);

      expect(getDeviceType()).toBe("mobile");
    });

    it("updates the cached value when the listener fires with matches=false", () => {
      const mockMediaQueryList = makeMockMediaQueryList(true);
      const matchMediaMock = vi.fn().mockReturnValue(mockMediaQueryList);
      vi.stubGlobal("matchMedia", matchMediaMock);

      expect(getDeviceType()).toBe("mobile");
      initDeviceTypeListener();

      const [, registeredListener] =
        mockMediaQueryList.addEventListener.mock.calls[0];
      const fireListener = registeredListener as MediaQueryListener;
      fireListener({ matches: false } as MediaQueryListEvent);

      expect(getDeviceType()).toBe("desktop");
    });

    it("uses event.matches from the MediaQueryListEvent, not a re-query of matchMedia", () => {
      // Initial state: matchMedia returns matches=false (desktop).
      // After init, we mutate the mock to return matches=true (mobile).
      // The listener must still classify based on the event payload, NOT
      // a fresh matchMedia call — that would be a race-prone re-query.
      const mockMediaQueryList = makeMockMediaQueryList(false);
      const matchMediaMock = vi.fn().mockReturnValue(mockMediaQueryList);
      vi.stubGlobal("matchMedia", matchMediaMock);

      expect(getDeviceType()).toBe("desktop");
      initDeviceTypeListener();

      // Mutate the underlying list: a re-query would now report mobile.
      mockMediaQueryList.matches = true;

      const [, registeredListener] =
        mockMediaQueryList.addEventListener.mock.calls[0];
      const fireListener = registeredListener as MediaQueryListener;
      // Fire event with matches=false: cache must reflect the event,
      // not the (now mutated) MediaQueryList.matches getter.
      fireListener({ matches: false } as MediaQueryListEvent);

      expect(getDeviceType()).toBe("desktop");
    });
  });
});
