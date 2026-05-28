import { createURLShowInput } from "../create.js";

vi.mock("../../../../lib/metrics-client.js", () => ({
  emit: vi.fn(),
  flush: vi.fn().mockResolvedValue(undefined),
  initMetricsClient: vi.fn(),
  resetMetricsClient: vi.fn(),
}));

vi.mock("../cards.js", () => ({
  newURLInputAddEventListeners: vi.fn(),
  newURLInputRemoveEventListeners: vi.fn(),
  createURLBlock: vi.fn(),
}));

vi.mock("../../utils.js", () => ({
  getNumOfURLs: vi.fn(() => 0),
  getNumOfVisibleURLs: vi.fn(() => 0),
}));

vi.mock("../../search.js", () => ({
  closeURLSearchAndEraseInput: vi.fn(),
  temporarilyHideSearchForEdit: vi.fn(),
  showURLSearchIcon: vi.fn(),
}));

vi.mock("../../empty-state.js", () => ({
  showURLsEmptyState: vi.fn(),
  hideURLsEmptyState: vi.fn(),
}));

vi.mock("../selection.js", () => ({
  selectURLCard: vi.fn(),
}));

vi.mock("../../../tags/utils.js", () => ({
  isATagSelected: vi.fn(() => false),
}));

vi.mock("../utils.js", () => ({
  isEmptyString: vi.fn((val: string) => val.trim() === ""),
  updateColorOfFollowingURLCardsAfterURLCreated: vi.fn(),
}));

vi.mock("../conflict-handler.js", () => ({
  checkForStaleDataOn409: vi.fn(),
}));

vi.mock("../../../../store/app-store.js", () => ({
  getState: vi.fn(() => ({ urls: [] })),
  setState: vi.fn(),
}));

const CREATE_URL_FORM_HTML = `
  <div id="createURLWrap"></div>
  <input id="urlStringCreate" />
  <input id="urlTitleCreate" />
  <button id="urlBtnCreate"></button>
`;

describe("create metrics — UI_URL_CREATE_OPEN", () => {
  beforeEach(() => {
    document.body.innerHTML = CREATE_URL_FORM_HTML;
    vi.clearAllMocks();
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("emits ui_url_create_open at the top of createURLShowInput", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");

    createURLShowInput(1);

    expect(emit).toHaveBeenCalledWith("ui_url_create_open");
  });

  it("emits once per call", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");

    createURLShowInput(1);

    expect(emit).toHaveBeenCalledTimes(1);
  });
});
