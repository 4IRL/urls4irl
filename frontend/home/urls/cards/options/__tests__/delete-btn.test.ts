import { createDeleteURLBtn } from "../delete-btn.js";
import { deleteURL } from "../../delete.js";
import type { UtubUrlItem } from "../../../../../types/url.js";

vi.mock("../../delete.js", () => ({
  deleteURL: vi.fn(),
}));

vi.mock("../../../../../lib/config.js", () => ({
  APP_CONFIG: {
    strings: { DELETE_URL_TOOLTIP: "Delete URL" },
  },
}));

vi.mock("../../../../../lib/globals.js", async () => {
  const actual = await vi.importActual<
    typeof import("../../../../../lib/globals.js")
  >("../../../../../lib/globals.js");
  return {
    ...actual,
    bootstrap: {
      Tooltip: { getOrCreateInstance: vi.fn() },
    } as unknown as typeof window.bootstrap,
  };
});

const $ = window.jQuery;

describe("createDeleteURLBtn — focus return after delete", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  function clickDelete(): (target: JQuery) => void {
    const urlCard = $('<div class="urlRow"></div>');
    const button = createDeleteURLBtn(
      { utubUrlID: 7 } as UtubUrlItem,
      urlCard,
      1,
    );
    button.trigger("click");
    const { beforeFocus } = vi.mocked(deleteURL).mock.calls[0][0];
    expect(beforeFocus).toBeDefined();
    return beforeFocus as (target: JQuery) => void;
  }

  it("arms swipe-focus-return on the neighbour row so programmatic focus never reads as selected, and the blur clears it", () => {
    const beforeFocus = clickDelete();
    const neighbour = $(
      '<div class="urlRow"><a class="goToUrlIcon"></a></div>',
    );
    neighbour.find(".goToUrlIcon").addClass("visible-on-focus");

    beforeFocus(neighbour);
    expect(neighbour.hasClass("swipe-focus-return")).toBe(true);

    neighbour.trigger("blur");
    expect(neighbour.hasClass("swipe-focus-return")).toBe(false);
    expect(neighbour.find(".goToUrlIcon").hasClass("visible-on-focus")).toBe(
      false,
    );
  });

  it("does not arm the suppression on a non-row focus target", () => {
    const beforeFocus = clickDelete();
    const emptyState = $('<div id="noURLsEmptyState"></div>');

    beforeFocus(emptyState);
    expect(emptyState.hasClass("swipe-focus-return")).toBe(false);
  });
});
