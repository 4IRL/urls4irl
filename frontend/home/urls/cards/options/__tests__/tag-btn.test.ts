import { createAddTagBtn } from "../tag-btn.js";
import { showTagCombobox } from "../../../tags/combobox.js";

vi.mock("../../../tags/combobox.js", () => ({
  showTagCombobox: vi.fn(),
}));

vi.mock("../../../../../lib/config.js", () => ({
  APP_CONFIG: {
    strings: { ADD_URL_TAG_TOOLTIP: "Add a tag" },
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

describe("createAddTagBtn — opens the combobox on click", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("calls showTagCombobox once with (urlCard, button) when clicked", () => {
    const urlCard = $('<div class="urlRow"></div>');
    const button = createAddTagBtn(urlCard);

    button.trigger("click");

    expect(showTagCombobox).toHaveBeenCalledTimes(1);
    expect(showTagCombobox).toHaveBeenCalledWith(urlCard, button);
  });
});
