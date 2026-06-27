import {
  createTagComboboxBlock,
  hideAndResetTagCombobox,
  showTagCombobox,
  STAGED_GET_KEY,
} from "../combobox.js";
import { ajaxCall } from "../../../../lib/ajax.js";
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

const URL_CARD_HTML = `
  <div class="urlRow" utuburlid="1" urlSelected="true" data-utub-url-tag-ids="">
    <button class="urlTagBtnCreate fourty-p-width"></button>
    <div class="urlBtnAccess"></div>
    <div class="urlStringBtnUpdate"></div>
    <div class="urlBtnDelete"></div>
    <div class="urlBtnCopy"></div>
    <div class="tagBadge"></div>
    <div class="tagsAndTagCreateWrap"></div>
  </div>
`;

function setTags(
  tags: { id: number; tagString: string; tagApplied: number }[],
): void {
  storeTags.length = 0;
  storeTags.push(...tags);
}

function mountCombobox(): JQuery {
  document.body.innerHTML = URL_CARD_HTML;
  const urlCard = $(".urlRow");
  const block = createTagComboboxBlock({
    mode: "url",
    urlCard,
    utubID: 1,
    utubUrlID: 1,
  });
  urlCard.find(".tagsAndTagCreateWrap").append(block);
  // Reveal so input events behave consistently.
  urlCard.find(".urlTagComboboxWrap").removeClass("hidden");
  return urlCard;
}

function typeInInput(urlCard: JQuery, value: string): void {
  const input = urlCard.find(".urlTagComboboxInput");
  input.val(value).trigger("input");
  vi.runAllTimers();
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers();
  setTags([
    { id: 1, tagString: "python", tagApplied: 5 },
    { id: 2, tagString: "pytest", tagApplied: 4 },
    { id: 3, tagString: "backend", tagApplied: 9 },
  ]);
});

afterEach(() => {
  vi.useRealTimers();
});

describe("combobox — happy path", () => {
  it("filters suggestions and shows a create-new option for a novel query", () => {
    const urlCard = mountCombobox();
    typeInInput(urlCard, "py");

    const options = urlCard.find(".urlTagOption");
    const labels = options
      .map((_, el) => $(el).find(".urlTagOptionLabel").text())
      .get();

    expect(labels.some((label) => label === "python")).toBe(true);
    expect(labels.some((label) => label === "pytest")).toBe(true);
    expect(urlCard.find(".urlTagOptionCreateNew").text()).toContain(
      APP_CONFIG.strings.TAG_CREATE_NEW,
    );
  });

  it("does NOT show create-new when an exact match exists", () => {
    const urlCard = mountCombobox();
    typeInInput(urlCard, "python");

    expect(urlCard.find(".urlTagOptionCreateNew").length).toBe(0);
  });

  it("stages two chips by clicking options", () => {
    const urlCard = mountCombobox();
    typeInInput(urlCard, "py");

    urlCard.find(".urlTagOptionCreateNew").trigger("click");
    typeInInput(urlCard, "back");
    urlCard
      .find(".urlTagOption")
      .filter((_, el) => $(el).find(".urlTagOptionLabel").text() === "backend")
      .trigger("click");

    const chips = urlCard.find(".urlTagStagedChip");
    expect(chips.length).toBe(2);
    expect(chips.eq(0).attr("data-staged-tag-string")).toBe("py");
    expect(chips.eq(1).attr("data-staged-tag-string")).toBe("backend");
  });

  it("removes a staged chip via its remove button", () => {
    const urlCard = mountCombobox();
    typeInInput(urlCard, "py");
    urlCard.find(".urlTagOptionCreateNew").trigger("click");
    expect(urlCard.find(".urlTagStagedChip").length).toBe(1);

    urlCard.find(".urlTagStagedChipRemove").trigger("click");
    expect(urlCard.find(".urlTagStagedChip").length).toBe(0);
  });
});

describe("combobox — sad path", () => {
  it("does NOT show a create-new option for a whitespace-only query", () => {
    const urlCard = mountCombobox();
    typeInInput(urlCard, "   ");

    expect(urlCard.find(".urlTagOptionCreateNew").length).toBe(0);
  });

  it("keeps the listbox closed with no options for an empty query (filter-only)", () => {
    const urlCard = mountCombobox();
    typeInInput(urlCard, "");

    const listbox = urlCard.find(".urlTagListbox");
    const input = urlCard.find(".urlTagComboboxInput");
    expect(listbox.hasClass("hidden")).toBe(true);
    expect(input.attr("aria-expanded")).toBe("false");
    expect(urlCard.find(".urlTagOption").length).toBe(0);
  });

  it("keeps the listbox closed with no options for a whitespace-only query (filter-only)", () => {
    const urlCard = mountCombobox();
    typeInInput(urlCard, "   ");

    const listbox = urlCard.find(".urlTagListbox");
    const input = urlCard.find(".urlTagComboboxInput");
    expect(listbox.hasClass("hidden")).toBe(true);
    expect(input.attr("aria-expanded")).toBe("false");
    expect(urlCard.find(".urlTagOption").length).toBe(0);
  });

  it("opens the listbox with matching options once a query is typed", () => {
    const urlCard = mountCombobox();

    // Empty first: dropdown closed, no options.
    typeInInput(urlCard, "");
    expect(urlCard.find(".urlTagOption").length).toBe(0);

    // Typing a matching substring surfaces option rows and opens the dropdown.
    typeInInput(urlCard, "py");

    const listbox = urlCard.find(".urlTagListbox");
    const input = urlCard.find(".urlTagComboboxInput");
    expect(listbox.hasClass("hidden")).toBe(false);
    expect(input.attr("aria-expanded")).toBe("true");
    expect(urlCard.find(".urlTagOption").length).toBeGreaterThan(0);
  });

  it("does NOT announce 'no matches' on an empty query (e.g. after staging a chip)", () => {
    const urlCard = mountCombobox();
    typeInInput(urlCard, "py");
    // Staging a chip clears the input and re-renders with an empty query.
    urlCard.find(".urlTagOptionCreateNew").trigger("click");

    expect(urlCard.find(".urlTagComboboxMsg").text()).not.toBe(
      APP_CONFIG.strings.TAGS_NO_MATCHES,
    );
    expect(urlCard.find(".urlTagListbox").hasClass("hidden")).toBe(true);
  });

  it("surfaces no existing-tag option rows when a typed query matches nothing", () => {
    const urlCard = mountCombobox();
    setTags([{ id: 1, tagString: "python", tagApplied: 5 }]);
    typeInInput(urlCard, "zzzqqq");

    // No existing-tag substring matches; only the create-new row may appear.
    expect(
      urlCard.find(".urlTagOption:not(.urlTagOptionCreateNew)").length,
    ).toBe(0);
  });

  it("does NOT create a chip from a whitespace-only query on Enter (no active option)", () => {
    const urlCard = mountCombobox();
    typeInInput(urlCard, "   ");
    const input = urlCard.find(".urlTagComboboxInput");

    // Close the dropdown first so no existing suggestion is active; Enter on a
    // trim-empty query with no active option and no staged chips must do nothing.
    input.trigger($.Event("keydown", { key: "Escape" }));
    input.trigger($.Event("keydown", { key: "Enter" }));

    expect(urlCard.find(".urlTagStagedChip").length).toBe(0);
  });

  it("does NOT stage an empty query on Enter when no option is active", () => {
    const urlCard = mountCombobox();
    typeInInput(urlCard, "");
    const input = urlCard.find(".urlTagComboboxInput");

    input.trigger($.Event("keydown", { key: "Escape" }));
    input.trigger($.Event("keydown", { key: "Enter" }));

    expect(urlCard.find(".urlTagStagedChip").length).toBe(0);
  });
});

describe("combobox — at-cap", () => {
  it("blocks staging and shows the limit message when at the cap", () => {
    document.body.innerHTML = URL_CARD_HTML;
    const urlCard = $(".urlRow");
    const appliedIds = Array.from(
      { length: APP_CONFIG.constants.TAGS_MAX_ON_URLS },
      (_, i) => i + 1,
    ).join(",");
    urlCard.attr("data-utub-url-tag-ids", appliedIds);
    const block = createTagComboboxBlock({
      mode: "url",
      urlCard,
      utubID: 1,
      utubUrlID: 1,
    });
    urlCard.find(".tagsAndTagCreateWrap").append(block);
    urlCard.find(".urlTagComboboxWrap").removeClass("hidden");

    typeInInput(urlCard, "newtag");

    expect(urlCard.find(".urlTagComboboxInput").prop("disabled")).toBe(true);
    expect(urlCard.find(".urlTagStagedChip").length).toBe(0);
    const expectedMsg = APP_CONFIG.strings.TAGS_LIMIT_REACHED.replace(
      "{max}",
      String(APP_CONFIG.constants.TAGS_MAX_ON_URLS),
    );
    expect(urlCard.find(".urlTagComboboxMsg").text()).toBe(expectedMsg);
  });

  it("disables the input and shows the limit message immediately on open", () => {
    document.body.innerHTML = URL_CARD_HTML;
    const urlCard = $(".urlRow");
    const appliedIds = Array.from(
      { length: APP_CONFIG.constants.TAGS_MAX_ON_URLS },
      (_, index) => index + 1,
    ).join(",");
    urlCard.attr("data-utub-url-tag-ids", appliedIds);
    const block = createTagComboboxBlock({
      mode: "url",
      urlCard,
      utubID: 1,
      utubUrlID: 1,
    });
    urlCard.find(".tagsAndTagCreateWrap").append(block);

    // Open the combobox without typing a single character.
    showTagCombobox({
      urlCard,
      urlTagBtnCreate: urlCard.find(".urlTagBtnCreate"),
    });

    expect(urlCard.find(".urlTagComboboxInput").prop("disabled")).toBe(true);
    const expectedMsg = APP_CONFIG.strings.TAGS_LIMIT_REACHED.replace(
      "{max}",
      String(APP_CONFIG.constants.TAGS_MAX_ON_URLS),
    );
    expect(urlCard.find(".urlTagComboboxMsg").text()).toBe(expectedMsg);
  });
});

describe("combobox — keyboard", () => {
  it("ArrowDown then Enter stages the active option", () => {
    const urlCard = mountCombobox();
    typeInInput(urlCard, "py");
    const input = urlCard.find(".urlTagComboboxInput");

    input.trigger($.Event("keydown", { key: "ArrowDown" }));
    input.trigger($.Event("keydown", { key: "Enter" }));

    expect(urlCard.find(".urlTagStagedChip").length).toBe(1);
  });

  it("Tab with an active option stages it", () => {
    const urlCard = mountCombobox();
    typeInInput(urlCard, "py");
    const input = urlCard.find(".urlTagComboboxInput");

    // A non-empty query auto-activates the first option.
    input.trigger($.Event("keydown", { key: "Tab" }));

    expect(urlCard.find(".urlTagStagedChip").length).toBe(1);
  });

  it("Backspace on empty input removes the last chip", () => {
    const urlCard = mountCombobox();
    typeInInput(urlCard, "py");
    urlCard.find(".urlTagOptionCreateNew").trigger("click");
    expect(urlCard.find(".urlTagStagedChip").length).toBe(1);

    const input = urlCard.find(".urlTagComboboxInput");
    input.val("");
    input.trigger($.Event("keydown", { key: "Backspace" }));

    expect(urlCard.find(".urlTagStagedChip").length).toBe(0);
  });

  it("first Escape closes only the dropdown", () => {
    const urlCard = mountCombobox();
    typeInInput(urlCard, "py");
    expect(urlCard.find(".urlTagListbox").hasClass("hidden")).toBe(false);

    const input = urlCard.find(".urlTagComboboxInput");
    const escapeEvent = $.Event("keydown", { key: "Escape" });
    input.trigger(escapeEvent);

    expect(urlCard.find(".urlTagListbox").hasClass("hidden")).toBe(true);
    expect(escapeEvent.isPropagationStopped()).toBe(true);
    expect(urlCard.find(".urlTagComboboxWrap").hasClass("hidden")).toBe(false);
  });

  it("second Escape cancels and hides the whole combobox", () => {
    const urlCard = mountCombobox();
    typeInInput(urlCard, "py");

    const input = urlCard.find(".urlTagComboboxInput");
    // First Escape closes only the dropdown; the wrap stays visible.
    input.trigger($.Event("keydown", { key: "Escape" }));
    expect(urlCard.find(".urlTagComboboxWrap").hasClass("hidden")).toBe(false);

    // Second Escape runs hideAndResetTagCombobox, hiding the whole wrap.
    input.trigger($.Event("keydown", { key: "Escape" }));

    expect(urlCard.find(".urlTagComboboxWrap").hasClass("hidden")).toBe(true);
  });
});

describe("hideAndResetTagCombobox", () => {
  it("clears staged chips and re-enables card buttons", () => {
    const urlCard = mountCombobox();
    typeInInput(urlCard, "py");
    urlCard.find(".urlTagOptionCreateNew").trigger("click");
    expect(urlCard.find(".urlTagStagedChip").length).toBe(1);

    hideAndResetTagCombobox(urlCard);

    expect(urlCard.find(".urlTagStagedChip").length).toBe(0);
    expect(urlCard.find(".urlTagComboboxWrap").hasClass("hidden")).toBe(true);
  });
});

const CREATE_FORM_HTML = `
  <div id="createURLWrap">
    <div class="text-input-container"></div>
    <div class="flex-row flex-start">
      <button id="urlSubmitBtnCreate" type="button">Add URL</button>
      <button id="urlCancelBtnCreate" type="button">Cancel</button>
    </div>
  </div>
`;

function mountCreateModeCombobox(onSecondEscape?: () => void): JQuery {
  document.body.innerHTML = CREATE_FORM_HTML;
  const block = createTagComboboxBlock({
    mode: "create",
    urlCard: null,
    utubID: 1,
    onSecondEscape,
  });
  block.removeClass("hidden");
  $("#urlSubmitBtnCreate").closest(".flex-row").before(block);
  return $("#createURLWrap").find(".urlTagComboboxWrap");
}

function typeInCreateInput(wrap: JQuery, value: string): void {
  const input = wrap.find(".urlTagComboboxInput");
  input.val(value).trigger("input");
  vi.runAllTimers();
}

describe("combobox — create mode", () => {
  it("mounts inside #createURLWrap with no internal submit button", () => {
    const wrap = mountCreateModeCombobox();

    expect($("#createURLWrap").find(".urlTagComboboxWrap").length).toBe(1);
    expect(wrap.find(".urlTagComboboxSubmitBtn").length).toBe(0);
  });

  it("renders a visible 'Tags (optional)' label tied to the input and no aria-label", () => {
    const wrap = mountCreateModeCombobox();

    const label = wrap.find("label.urlTagComboboxLabel");
    const input = wrap.find(".urlTagComboboxInput");
    expect(label.text()).toBe(APP_CONFIG.strings.TAGS_OPTIONAL_LABEL);
    expect(label.attr("for")).toBe(input.attr("id"));
    expect(input.attr("aria-label")).toBeUndefined();
  });

  it("exposes staged strings via the STAGED_GET_KEY getter", () => {
    const wrap = mountCreateModeCombobox();
    typeInCreateInput(wrap, "py");
    wrap.find(".urlTagOptionCreateNew").trigger("click");

    const getStaged = wrap.data(STAGED_GET_KEY) as () => string[];
    expect(getStaged()).toEqual(["py"]);
  });

  it("does NOT trigger a batch AJAX call when Enter is pressed with staged tags", () => {
    const wrap = mountCreateModeCombobox();
    typeInCreateInput(wrap, "py");
    wrap.find(".urlTagOptionCreateNew").trigger("click");
    expect((wrap.data(STAGED_GET_KEY) as () => string[])()).toEqual(["py"]);

    const input = wrap.find(".urlTagComboboxInput");
    // Close the dropdown so the Enter lands on the (suppressed) batch-submit path.
    input.trigger($.Event("keydown", { key: "Escape" }));
    input.trigger($.Event("keydown", { key: "Enter" }));

    expect(ajaxCall).not.toHaveBeenCalled();
  });

  it("second Escape delegates dismissal to onSecondEscape", () => {
    const onSecondEscape = vi.fn();
    const wrap = mountCreateModeCombobox(onSecondEscape);
    typeInCreateInput(wrap, "py");

    const input = wrap.find(".urlTagComboboxInput");
    // First Escape closes only the dropdown.
    input.trigger($.Event("keydown", { key: "Escape" }));
    expect(onSecondEscape).not.toHaveBeenCalled();

    // Second Escape (dropdown closed) delegates to onSecondEscape.
    input.trigger($.Event("keydown", { key: "Escape" }));
    expect(onSecondEscape).toHaveBeenCalledTimes(1);
  });
});
