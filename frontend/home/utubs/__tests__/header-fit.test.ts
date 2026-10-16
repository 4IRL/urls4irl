import {
  computeFittedFontPx,
  descriptionNeedsFullRow,
  fitUTubHeaderAndSubheader,
  DESCRIPTION_FILLS_ROW_CLASS,
} from "../header-fit.js";

describe("descriptionNeedsFullRow", () => {
  it("is false when the description fits beside the search box", () => {
    expect(
      descriptionNeedsFullRow({
        naturalWidthPx: 400,
        availableBesideSearchPx: 700,
      }),
    ).toBe(false);
  });

  it("is false when the description exactly fills the space beside the search box", () => {
    expect(
      descriptionNeedsFullRow({
        naturalWidthPx: 700,
        availableBesideSearchPx: 700,
      }),
    ).toBe(false);
  });

  it("is true when the description is wider than the space beside the search box", () => {
    expect(
      descriptionNeedsFullRow({
        naturalWidthPx: 701,
        availableBesideSearchPx: 700,
      }),
    ).toBe(true);
  });

  it.each([
    ["zero natural width", 0, 700],
    ["zero available width", 400, 0],
    ["negative available width", 400, -10],
    ["NaN natural width", NaN, 700],
    ["Infinity available width", 400, Infinity],
  ])("is false for degenerate input (%s)", (_label, naturalWidthPx, avail) => {
    expect(
      descriptionNeedsFullRow({
        naturalWidthPx,
        availableBesideSearchPx: avail,
      }),
    ).toBe(false);
  });
});

describe("fitUTubHeaderAndSubheader - description fills-row state class", () => {
  const OUTER_CONTENT_WIDTH_PX = 1000;
  // 30% of the row is reserved for the search box, leaving 700px beside it.
  const WIDTH_BESIDE_SEARCH_PX = 700;

  function defineGeometry({
    element,
    props,
  }: {
    element: HTMLElement;
    props: Record<string, number | HTMLElement | null>;
  }): void {
    for (const [name, value] of Object.entries(props))
      Object.defineProperty(element, name, { value, configurable: true });
  }

  function mountDescription({
    naturalWidthPx,
  }: {
    naturalWidthPx: number;
  }): HTMLElement {
    document.body.innerHTML = `
      <div id="UTubDescriptionSubheaderOuterWrap" style="padding-left: 0px; padding-right: 0px">
        <div id="UTubDescriptionSubheaderWrap">
          <h5 id="URLDeckSubheader">A description</h5>
          <span class="edit-pencil-icon"></span>
        </div>
      </div>`;
    const outer = document.getElementById(
      "UTubDescriptionSubheaderOuterWrap",
    ) as HTMLElement;
    const wrap = document.getElementById(
      "UTubDescriptionSubheaderWrap",
    ) as HTMLElement;
    const subheader = document.getElementById(
      "URLDeckSubheader",
    ) as HTMLElement;
    defineGeometry({
      element: outer,
      props: { clientWidth: OUTER_CONTENT_WIDTH_PX },
    });
    defineGeometry({
      element: wrap,
      props: { offsetParent: document.body, clientWidth: 1000 },
    });
    defineGeometry({
      element: subheader,
      props: { offsetParent: document.body, scrollWidth: naturalWidthPx },
    });
    return wrap;
  }

  it("adds the class when the description does not fit beside the search box", () => {
    const wrap = mountDescription({
      naturalWidthPx: WIDTH_BESIDE_SEARCH_PX + 100,
    });

    fitUTubHeaderAndSubheader();

    expect(wrap.classList.contains(DESCRIPTION_FILLS_ROW_CLASS)).toBe(true);
  });

  it("leaves the class off when the description fits beside the search box", () => {
    const wrap = mountDescription({
      naturalWidthPx: WIDTH_BESIDE_SEARCH_PX - 100,
    });

    fitUTubHeaderAndSubheader();

    expect(wrap.classList.contains(DESCRIPTION_FILLS_ROW_CLASS)).toBe(false);
  });

  it("removes the class on re-fit once the description shrinks to fit", () => {
    const wrap = mountDescription({
      naturalWidthPx: WIDTH_BESIDE_SEARCH_PX + 100,
    });
    fitUTubHeaderAndSubheader();
    expect(wrap.classList.contains(DESCRIPTION_FILLS_ROW_CLASS)).toBe(true);

    defineGeometry({
      element: document.getElementById("URLDeckSubheader") as HTMLElement,
      props: { scrollWidth: WIDTH_BESIDE_SEARCH_PX - 100 },
    });
    fitUTubHeaderAndSubheader();

    expect(wrap.classList.contains(DESCRIPTION_FILLS_ROW_CLASS)).toBe(false);
  });

  it("leaves the class untouched while the description wrap is hidden", () => {
    const wrap = mountDescription({
      naturalWidthPx: WIDTH_BESIDE_SEARCH_PX + 100,
    });
    fitUTubHeaderAndSubheader();
    defineGeometry({ element: wrap, props: { offsetParent: null } });
    defineGeometry({
      element: document.getElementById("URLDeckSubheader") as HTMLElement,
      props: { scrollWidth: 10 },
    });

    fitUTubHeaderAndSubheader();

    expect(wrap.classList.contains(DESCRIPTION_FILLS_ROW_CLASS)).toBe(true);
  });

  it("is a no-op when the subheader markup is absent", () => {
    document.body.innerHTML = "";

    expect(() => fitUTubHeaderAndSubheader()).not.toThrow();
  });
});

describe("computeFittedFontPx", () => {
  const baseFontPx = 32;
  const minFontPx = 16;

  describe("content already fits at base font", () => {
    it("returns baseFontPx when content is narrower than the container", () => {
      expect(
        computeFittedFontPx({
          contentWidthPx: 100,
          containerWidthPx: 200,
          baseFontPx,
          minFontPx,
        }),
      ).toBe(baseFontPx);
    });

    it("returns baseFontPx when content exactly equals the container (no upscaling above base)", () => {
      expect(
        computeFittedFontPx({
          contentWidthPx: 200,
          containerWidthPx: 200,
          baseFontPx,
          minFontPx,
        }),
      ).toBe(baseFontPx);
    });
  });

  describe("content overflows the container", () => {
    it("scales font proportionally (content 2x container -> half base, still above min)", () => {
      expect(
        computeFittedFontPx({
          contentWidthPx: 400,
          containerWidthPx: 200,
          baseFontPx,
          minFontPx,
        }),
      ).toBe(16);
    });

    it("rounds the scaled font to the nearest integer pixel", () => {
      // 32 * 200 / 300 = 21.333... -> rounds to 21
      expect(
        computeFittedFontPx({
          contentWidthPx: 300,
          containerWidthPx: 200,
          baseFontPx,
          minFontPx,
        }),
      ).toBe(21);
    });

    it("never returns below minFontPx when the proportional value would dip under it", () => {
      // 32 * 200 / 500 = 12.8 -> would round to 13, clamped up to min 16
      expect(
        computeFittedFontPx({
          contentWidthPx: 500,
          containerWidthPx: 200,
          baseFontPx,
          minFontPx,
        }),
      ).toBe(minFontPx);
    });
  });

  describe("content hugely overflows (wrap-at-min case)", () => {
    it("clamps exactly to minFontPx when content is 10x the container", () => {
      expect(
        computeFittedFontPx({
          contentWidthPx: 2000,
          containerWidthPx: 200,
          baseFontPx,
          minFontPx,
        }),
      ).toBe(minFontPx);
    });
  });

  describe("degenerate inputs are no-ops returning baseFontPx", () => {
    it("returns baseFontPx when containerWidthPx is 0", () => {
      expect(
        computeFittedFontPx({
          contentWidthPx: 400,
          containerWidthPx: 0,
          baseFontPx,
          minFontPx,
        }),
      ).toBe(baseFontPx);
    });

    it("returns baseFontPx when contentWidthPx is 0", () => {
      expect(
        computeFittedFontPx({
          contentWidthPx: 0,
          containerWidthPx: 200,
          baseFontPx,
          minFontPx,
        }),
      ).toBe(baseFontPx);
    });

    it("returns baseFontPx when contentWidthPx is non-finite (NaN)", () => {
      expect(
        computeFittedFontPx({
          contentWidthPx: NaN,
          containerWidthPx: 200,
          baseFontPx,
          minFontPx,
        }),
      ).toBe(baseFontPx);
    });

    it("returns baseFontPx when containerWidthPx is non-finite (Infinity)", () => {
      expect(
        computeFittedFontPx({
          contentWidthPx: 400,
          containerWidthPx: Infinity,
          baseFontPx,
          minFontPx,
        }),
      ).toBe(baseFontPx);
    });

    it("returns baseFontPx when a width is negative", () => {
      expect(
        computeFittedFontPx({
          contentWidthPx: 400,
          containerWidthPx: -200,
          baseFontPx,
          minFontPx,
        }),
      ).toBe(baseFontPx);
    });
  });
});
