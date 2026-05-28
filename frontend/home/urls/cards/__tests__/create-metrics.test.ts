import { createURL, createURLShowInput } from "../create.js";
import { emitValidationError } from "../../../btns-forms.js";
import { isValidURL } from "../../validation.js";
import { ajaxCall } from "../../../../lib/ajax.js";

const { mockMetricsClient } = await vi.hoisted(
  async () =>
    await import("../../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../../lib/metrics-client.js", () => mockMetricsClient());

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

vi.mock("../../../btns-forms.js", () => ({
  emitFormSubmit: vi.fn(),
  emitFormCancel: vi.fn(),
  emitValidationError: vi.fn(),
}));

vi.mock("../../validation.js", () => ({
  isValidURL: vi.fn(() => true),
}));

vi.mock("../../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));

vi.mock("../../../../lib/config.js", () => ({
  APP_CONFIG: {
    routes: {
      createURL: vi.fn(() => "/api/utubs/1/urls"),
    },
    constants: {},
    strings: {
      INVALID_URL: "Invalid URL",
    },
  },
}));

const $ = window.jQuery;

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

describe("create metrics — UI_VALIDATION_ERROR (url_create sad path)", () => {
  const INVALID_URL_STRING = "not-a-url";
  const URL_TITLE_INPUT_VALUE = "Some Title";
  const UTUB_ID = 1;

  const INVALID_URL_FORM_HTML = `
    <div id="createURLWrap"></div>
    <input id="urlStringCreate" value="${INVALID_URL_STRING}" />
    <input id="urlTitleCreate" value="${URL_TITLE_INPUT_VALUE}" />
    <span id="urlStringCreate-error"></span>
    <span id="urlTitleCreate-error"></span>
    <button id="urlBtnCreate"></button>
  `;

  beforeEach(() => {
    document.body.innerHTML = INVALID_URL_FORM_HTML;
    vi.clearAllMocks();
    vi.mocked(isValidURL).mockReturnValue(false);
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("emits ui_validation_error('url_create') when createURL is called with an invalid URL", () => {
    expect(vi.mocked(emitValidationError)).not.toHaveBeenCalled();
    expect(vi.mocked(ajaxCall)).not.toHaveBeenCalled();

    createURL($("#urlTitleCreate"), $("#urlStringCreate"), UTUB_ID);

    expect(vi.mocked(emitValidationError)).toHaveBeenCalledWith("url_create");
    expect(vi.mocked(emitValidationError)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(ajaxCall)).not.toHaveBeenCalled();
  });
});
