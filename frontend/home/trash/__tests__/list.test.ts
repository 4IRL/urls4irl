import { createMockJqXHRChainable } from "../../../__tests__/helpers/mock-jquery.js";
import { ajaxCall } from "../../../lib/ajax.js";
import { invalidateTrashListRequests, loadTrashList } from "../list.js";
import { renderTrashList } from "../render.js";

vi.mock("../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));

vi.mock("../render.js", () => ({
  renderTrashList: vi.fn(),
}));

const LIST = { urls: [], utubs: [], currentUser: 1, retentionDays: 30 };

function mockXhr(): JQuery.jqXHR {
  return createMockJqXHRChainable({
    done: (callback) => (callback as (response: unknown) => void)(LIST),
    always: (callback) => (callback as () => void)(),
  });
}

describe("loadTrashList", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the response", async () => {
    vi.mocked(ajaxCall).mockReturnValue(mockXhr() as never);
    await loadTrashList();
    expect(renderTrashList).toHaveBeenCalledWith({ list: LIST });
  });

  it("drops a response that arrives after Trash closed", async () => {
    vi.mocked(ajaxCall).mockImplementation(() => {
      invalidateTrashListRequests();
      return mockXhr() as never;
    });
    await loadTrashList();
    expect(renderTrashList).not.toHaveBeenCalled();
  });
});
