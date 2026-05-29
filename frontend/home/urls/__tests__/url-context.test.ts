import { isURLSearchActive, getActiveTagCount } from "../url-context.js";
import { getState } from "../../../store/app-store.js";

vi.mock("../../../store/app-store.js", () => ({
  getState: vi.fn(() => ({ selectedTagIDs: [] })),
  setState: vi.fn(),
}));

describe("isURLSearchActive", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
  });

  it("returns true when #SearchURLWrap has visible-flex class", () => {
    document.body.innerHTML = `<div id="SearchURLWrap" class="visible-flex"></div>`;
    expect(isURLSearchActive()).toBe(true);
  });

  it("returns false when #SearchURLWrap is missing the visible-flex class", () => {
    document.body.innerHTML = `<div id="SearchURLWrap"></div>`;
    expect(isURLSearchActive()).toBe(false);
  });

  it("returns false when #SearchURLWrap is absent from the DOM", () => {
    document.body.innerHTML = `<div></div>`;
    expect(isURLSearchActive()).toBe(false);
  });
});

describe("getActiveTagCount", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns 0 when no tag filters are selected", () => {
    vi.mocked(getState).mockReturnValue({
      selectedTagIDs: [],
    } as unknown as ReturnType<typeof getState>);
    expect(getActiveTagCount()).toBe(0);
  });

  it("returns the length of selectedTagIDs from the store", () => {
    vi.mocked(getState).mockReturnValue({
      selectedTagIDs: [1, 2, 3],
    } as unknown as ReturnType<typeof getState>);
    expect(getActiveTagCount()).toBe(3);
  });
});
