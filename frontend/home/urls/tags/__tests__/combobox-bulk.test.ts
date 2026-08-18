import {
  BULK_RESET_KEY,
  ComboboxMode,
  createTagComboboxBlock,
} from "../combobox.js";
import { APP_CONFIG } from "../../../../lib/config.js";

vi.mock("../../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));

const { mockMetricsClient } = await vi.hoisted(
  async () =>
    await import("../../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../../cards/selection.js", () => ({
  disableClickOnSelectedURLCardToHide: vi.fn(),
  enableClickOnSelectedURLCardToHide: vi.fn(),
}));

vi.mock("../../cards/utils.js", () => ({
  disableEditingURLString: vi.fn(),
  disableEditingURLTitle: vi.fn(),
  enableEditingURLString: vi.fn(),
  enableEditingURLTitle: vi.fn(),
}));

vi.mock("../../cards/options/tag-btn.js", () => ({
  createAddTagIcon: vi.fn(() => window.jQuery("<i></i>")),
}));

vi.mock("../../mobile.js", () => ({
  isMobile: vi.fn(() => false),
}));

vi.mock("../../../../lib/modal-tracking.js", () => ({
  setOpenForm: vi.fn(),
  clearOpenForm: vi.fn(),
}));

vi.mock("../../../../lib/globals.js", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("../../../../lib/globals.js")>();
  return {
    ...actual,
    bootstrap: {
      Tooltip: { getInstance: vi.fn(() => null) },
    } as unknown as typeof window.bootstrap,
  };
});

vi.mock("../tags.js", () => ({
  createTagDeleteIcon: vi.fn(() => window.jQuery("<svg></svg>")),
  disableTagRemovalInURLCard: vi.fn(),
  enableTagRemovalInURLCard: vi.fn(),
}));

const storeTags: { id: number; tagString: string; tagApplied: number }[] = [];

vi.mock("../../../../store/app-store.js", () => ({
  getState: vi.fn(() => ({ urls: [], tags: storeTags })),
  setState: vi.fn(),
}));

const $ = window.jQuery;

const BULK_MOUNT_HTML = `<div id="bulkTagPickerMount"></div>`;

function setTags(
  tags: { id: number; tagString: string; tagApplied: number }[],
): void {
  storeTags.length = 0;
  storeTags.push(...tags);
}

function mountBulkModeCombobox(
  onSubmit: (stagedStrings: string[]) => void = vi.fn(),
  selectedCount = 3,
): JQuery {
  document.body.innerHTML = BULK_MOUNT_HTML;
  const block = createTagComboboxBlock({
    mode: ComboboxMode.BULK,
    urlCard: null,
    utubID: 1,
    selectedCount,
    onSubmit,
  });
  block.removeClass("hidden");
  $("#bulkTagPickerMount").append(block);
  return $("#bulkTagPickerMount").find(".urlTagComboboxWrap");
}

function typeInInput({ wrap, value }: { wrap: JQuery; value: string }): void {
  const input = wrap.find(".urlTagComboboxInput");
  input.val(value).trigger("input");
  vi.runAllTimers();
}

function stageOneChip({ wrap, query }: { wrap: JQuery; query: string }): void {
  typeInInput({ wrap, value: query });
  wrap.find(".urlTagOptionCreateNew").trigger("click");
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers();
  setTags([
    { id: 1, tagString: "python", tagApplied: 5 },
    { id: 2, tagString: "backend", tagApplied: 9 },
  ]);
});

afterEach(() => {
  vi.useRealTimers();
  document.body.innerHTML = "";
});

describe("combobox — bulk mode", () => {
  it("builds with a count-aware bulk aria-label and keeps the submit button", () => {
    const wrap = mountBulkModeCombobox(vi.fn(), 3);

    const input = wrap.find(".urlTagComboboxInput");
    expect(input.attr("aria-label")).toBe(
      APP_CONFIG.strings.URL_BULK_ADD_TAGS_ARIA.replace("{n}", "3"),
    );
    // Bulk mode keeps the internal submit button (unlike create mode) and has no
    // visible <label>.
    expect(wrap.find(".urlTagComboboxSubmitBtn").length).toBe(1);
    expect(wrap.find("label.urlTagComboboxLabel").length).toBe(0);
  });

  it("disables submit until at least one chip is staged", () => {
    const wrap = mountBulkModeCombobox();
    const submitBtn = wrap.find(".urlTagComboboxSubmitBtn");

    // A render with no staged chips gates the submit button disabled
    // (updateSubmitState runs on every listbox render).
    typeInInput({ wrap, value: "py" });
    expect(submitBtn.prop("disabled")).toBe(true);

    // Staging the first chip re-renders and enables submit.
    wrap.find(".urlTagOptionCreateNew").trigger("click");
    expect(wrap.find(".urlTagStagedChip").length).toBe(1);
    expect(submitBtn.prop("disabled")).toBe(false);
  });

  it("invokes the provided onSubmit with the staged strings on submit-button click", () => {
    const onSubmit = vi.fn();
    const wrap = mountBulkModeCombobox(onSubmit);

    stageOneChip({ wrap, query: "py" });
    wrap.find(".urlTagComboboxSubmitBtn").trigger("click");

    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit).toHaveBeenCalledWith(["py"]);
  });

  it("invokes onSubmit via Enter when only staged chips remain (empty input)", () => {
    const onSubmit = vi.fn();
    const wrap = mountBulkModeCombobox(onSubmit);
    stageOneChip({ wrap, query: "py" });

    const input = wrap.find(".urlTagComboboxInput");
    // Close the dropdown so Enter lands on the submit path (no active option).
    input.trigger($.Event("keydown", { key: "Escape" }));
    input.trigger($.Event("keydown", { key: "Enter" }));

    expect(onSubmit).toHaveBeenCalledWith(["py"]);
  });

  it("neutralizes the per-URL capacity gate (no card, staging is never blocked)", () => {
    const wrap = mountBulkModeCombobox();

    // With no owning card, applied-count is always 0, so staging multiple chips
    // stays under the staged-only cap and the input is never disabled.
    stageOneChip({ wrap, query: "py" });
    stageOneChip({ wrap, query: "back" });

    expect(wrap.find(".urlTagStagedChip").length).toBe(2);
    expect(wrap.find(".urlTagComboboxInput").prop("disabled")).toBe(false);
  });

  it("clears staged/input/message state via the card-independent BULK_RESET_KEY closure", () => {
    const wrap = mountBulkModeCombobox();
    stageOneChip({ wrap, query: "py" });
    typeInInput({ wrap, value: "back" });
    expect(wrap.find(".urlTagStagedChip").length).toBe(1);
    expect(wrap.find(".urlTagListbox").hasClass("hidden")).toBe(false);

    const resetBulk = wrap.data(BULK_RESET_KEY) as () => void;
    resetBulk();

    expect(wrap.find(".urlTagStagedChip").length).toBe(0);
    expect(wrap.find(".urlTagComboboxInput").val()).toBe("");
    expect(wrap.find(".urlTagListbox").hasClass("hidden")).toBe(true);
    expect(wrap.find(".urlTagComboboxMsg").text()).toBe("");
  });
});
