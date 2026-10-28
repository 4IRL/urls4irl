import { scrollSelectedCardIntoView } from "../scroll-selected.js";

const $ = window.jQuery;

function setMedia({
  wide,
  reduceMotion,
}: {
  wide: boolean;
  reduceMotion: boolean;
}): void {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches:
      query === "(min-width: 992px)"
        ? wide
        : query === "(prefers-reduced-motion: reduce)"
          ? reduceMotion
          : false,
    media: query,
  })) as unknown as typeof window.matchMedia;
}

describe("scrollSelectedCardIntoView", () => {
  const scrollIntoView = vi.fn();
  let urlCard: JQuery;
  const originalMatchMedia = window.matchMedia;
  const originalScrollIntoView = window.HTMLElement.prototype.scrollIntoView;

  beforeEach(() => {
    scrollIntoView.mockClear();
    window.HTMLElement.prototype.scrollIntoView = scrollIntoView;
    document.body.innerHTML = '<div class="urlRow"></div>';
    document.body.dataset.view = "cards";
    urlCard = $(".urlRow");
  });

  afterEach(() => {
    delete document.body.dataset.view;
    window.matchMedia = originalMatchMedia;
    window.HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
  });

  it("scrolls smoothly to the nearest edge in Cards at >= 992px", () => {
    setMedia({ wide: true, reduceMotion: false });

    scrollSelectedCardIntoView(urlCard);

    expect(scrollIntoView).toHaveBeenCalledWith({
      block: "nearest",
      behavior: "smooth",
    });
  });

  it("jumps instead of animating under reduced motion", () => {
    setMedia({ wide: true, reduceMotion: true });

    scrollSelectedCardIntoView(urlCard);

    expect(scrollIntoView).toHaveBeenCalledWith({
      block: "nearest",
      behavior: "auto",
    });
  });

  it("does nothing below the wide breakpoint, where Cards renders as List", () => {
    setMedia({ wide: false, reduceMotion: false });

    scrollSelectedCardIntoView(urlCard);

    expect(scrollIntoView).not.toHaveBeenCalled();
  });

  it("does nothing in List", () => {
    document.body.dataset.view = "list";
    setMedia({ wide: true, reduceMotion: false });

    scrollSelectedCardIntoView(urlCard);

    expect(scrollIntoView).not.toHaveBeenCalled();
  });

  it("does nothing when matchMedia is unavailable (fails closed)", () => {
    window.matchMedia = undefined as unknown as typeof window.matchMedia;

    scrollSelectedCardIntoView(urlCard);

    expect(scrollIntoView).not.toHaveBeenCalled();
  });
});
