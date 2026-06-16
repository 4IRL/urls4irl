import { initScrollReveal } from "../scroll-reveal.js";

describe("splash/scroll-reveal", () => {
  let observeMock: ReturnType<typeof vi.fn>;
  let unobserveMock: ReturnType<typeof vi.fn>;
  let intersectionCallback: IntersectionObserverCallback | null;

  function setReducedMotion(reduce: boolean): void {
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: reduce,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })) as unknown as typeof window.matchMedia;
  }

  function installIntersectionObserver(): void {
    observeMock = vi.fn();
    unobserveMock = vi.fn();
    intersectionCallback = null;
    class MockIntersectionObserver {
      constructor(callback: IntersectionObserverCallback) {
        intersectionCallback = callback;
      }
      observe = observeMock;
      unobserve = unobserveMock;
      disconnect = vi.fn();
    }
    window.IntersectionObserver =
      MockIntersectionObserver as unknown as typeof IntersectionObserver;
  }

  function emitIntersection(target: Element, isIntersecting: boolean): void {
    intersectionCallback!(
      [{ target, isIntersecting } as IntersectionObserverEntry],
      { unobserve: unobserveMock } as unknown as IntersectionObserver,
    );
  }

  beforeEach(() => {
    document.body.innerHTML = `
      <div class="reveal-on-scroll" id="tileA"></div>
      <div class="reveal-on-scroll" id="tileB"></div>
    `;
    installIntersectionObserver();
    setReducedMotion(false);
  });

  afterEach(() => {
    document.body.innerHTML = "";
    vi.restoreAllMocks();
  });

  it("observes every reveal target and reveals one when it intersects", () => {
    initScrollReveal();
    expect(observeMock).toHaveBeenCalledTimes(2);

    const tileA = document.getElementById("tileA")!;
    emitIntersection(tileA, true);

    expect(tileA.classList.contains("is-revealed")).toBe(true);
    expect(unobserveMock).toHaveBeenCalledWith(tileA);
    expect(
      document.getElementById("tileB")!.classList.contains("is-revealed"),
    ).toBe(false);
  });

  it("does not reveal a target that has not yet intersected", () => {
    initScrollReveal();

    const tileA = document.getElementById("tileA")!;
    emitIntersection(tileA, false);

    expect(tileA.classList.contains("is-revealed")).toBe(false);
    expect(unobserveMock).not.toHaveBeenCalled();
  });

  it("reveals all targets immediately and skips the observer under reduced motion", () => {
    setReducedMotion(true);

    initScrollReveal();

    expect(observeMock).not.toHaveBeenCalled();
    expect(
      document.getElementById("tileA")!.classList.contains("is-revealed"),
    ).toBe(true);
    expect(
      document.getElementById("tileB")!.classList.contains("is-revealed"),
    ).toBe(true);
  });

  it("reveals all targets immediately when IntersectionObserver is unavailable", () => {
    window.IntersectionObserver =
      undefined as unknown as typeof IntersectionObserver;

    initScrollReveal();

    expect(observeMock).not.toHaveBeenCalled();
    expect(
      document.getElementById("tileA")!.classList.contains("is-revealed"),
    ).toBe(true);
    expect(
      document.getElementById("tileB")!.classList.contains("is-revealed"),
    ).toBe(true);
  });

  it("no-ops when there are no reveal targets", () => {
    document.body.innerHTML = "";

    expect(() => initScrollReveal()).not.toThrow();
    expect(observeMock).not.toHaveBeenCalled();
  });
});
