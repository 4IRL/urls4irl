import { initBulkActions } from "../index.js";
import {
  enterMultiSelectMode,
  exitMultiSelectMode,
  isMultiSelectActive,
} from "../bulk-mode.js";
import {
  isTagSheetOpen,
  openTagSheetFromUserAction,
} from "../../../tags/sheet.js";
import { isMobile } from "../../../mobile.js";
import { AppEvents, emit } from "../../../../lib/event-bus.js";

vi.mock("../bulk-mode.js", () => ({
  enterMultiSelectMode: vi.fn(),
  exitMultiSelectMode: vi.fn(),
  isMultiSelectActive: vi.fn(() => false),
}));

vi.mock("../../../tags/sheet.js", () => ({
  isTagSheetOpen: vi.fn(() => false),
  openTagSheetFromUserAction: vi.fn(),
}));

vi.mock("../../../mobile.js", () => ({
  isMobile: vi.fn(() => true),
}));

const $ = window.jQuery;

const HTML = `
  <button id="urlBtnMultiSelect" aria-pressed="false"></button>
  <button id="bulkTagFilterIcon" aria-expanded="false"></button>
  <input id="textField" type="text" />
`;

function pressEscape(): void {
  $(document).trigger($.Event("keydown", { key: "Escape" }));
}

describe("bulk-actions index — Escape-to-exit", () => {
  beforeEach(() => {
    document.body.innerHTML = HTML;
    vi.mocked(exitMultiSelectMode).mockClear();
    vi.mocked(isMultiSelectActive).mockReturnValue(false);
    vi.mocked(isTagSheetOpen).mockReturnValue(false);
    // Focus outside the text input by default.
    $("#textField")[0].blur();
    initBulkActions();
  });

  it("exits mode on Escape when mode is active and focus is outside a text input", () => {
    vi.mocked(isMultiSelectActive).mockReturnValue(true);

    pressEscape();

    expect(vi.mocked(exitMultiSelectMode)).toHaveBeenCalledTimes(1);
  });

  it("does NOT exit on Escape while a text input has focus", () => {
    vi.mocked(isMultiSelectActive).mockReturnValue(true);
    $("#textField")[0].focus();

    pressEscape();

    expect(vi.mocked(exitMultiSelectMode)).not.toHaveBeenCalled();
  });

  it("does NOT exit on Escape while mode is inactive", () => {
    vi.mocked(isMultiSelectActive).mockReturnValue(false);

    pressEscape();

    expect(vi.mocked(exitMultiSelectMode)).not.toHaveBeenCalled();
  });

  it("does NOT exit on Escape while a Bootstrap modal is open (topmost overlay wins)", () => {
    vi.mocked(isMultiSelectActive).mockReturnValue(true);
    // Shared delete/rename/access-confirm modal open.
    $("body").append('<div class="modal show" id="confirmModal"></div>');

    pressEscape();

    expect(vi.mocked(exitMultiSelectMode)).not.toHaveBeenCalled();
  });

  it("does NOT exit on Escape while the tag sheet is open", () => {
    vi.mocked(isMultiSelectActive).mockReturnValue(true);
    vi.mocked(isTagSheetOpen).mockReturnValue(true);

    pressEscape();

    expect(vi.mocked(exitMultiSelectMode)).not.toHaveBeenCalled();
  });
});

describe("bulk-actions index — toggle button", () => {
  beforeEach(() => {
    document.body.innerHTML = HTML;
    vi.mocked(enterMultiSelectMode).mockClear();
    vi.mocked(exitMultiSelectMode).mockClear();
    vi.mocked(isMultiSelectActive).mockReturnValue(false);
    initBulkActions();
  });

  it("enters mode when clicked while inactive", () => {
    vi.mocked(isMultiSelectActive).mockReturnValue(false);

    $("#urlBtnMultiSelect").trigger("click");

    expect(vi.mocked(enterMultiSelectMode)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(exitMultiSelectMode)).not.toHaveBeenCalled();
  });

  it("exits mode when clicked while active", () => {
    vi.mocked(isMultiSelectActive).mockReturnValue(true);

    $("#urlBtnMultiSelect").trigger("click");

    expect(vi.mocked(exitMultiSelectMode)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(enterMultiSelectMode)).not.toHaveBeenCalled();
  });
});

describe("bulk-actions index — aria-pressed follows mode-changed events", () => {
  beforeEach(() => {
    document.body.innerHTML = HTML;
    initBulkActions();
  });

  it("sets aria-pressed true/false from URL_MULTISELECT_MODE_CHANGED regardless of the exit path", () => {
    emit(AppEvents.URL_MULTISELECT_MODE_CHANGED, { active: true });
    expect($("#urlBtnMultiSelect").attr("aria-pressed")).toBe("true");

    emit(AppEvents.URL_MULTISELECT_MODE_CHANGED, { active: false });
    expect($("#urlBtnMultiSelect").attr("aria-pressed")).toBe("false");
  });
});

describe("bulk-actions index — header tag-filter icon", () => {
  beforeEach(() => {
    document.body.innerHTML = HTML;
    vi.mocked(openTagSheetFromUserAction).mockClear();
    vi.mocked(isTagSheetOpen).mockReturnValue(false);
    vi.mocked(isMobile).mockReturnValue(true);
    initBulkActions();
  });

  it("opens the tag sheet on click while mobile", () => {
    $("#bulkTagFilterIcon").trigger("click");

    expect(vi.mocked(openTagSheetFromUserAction)).toHaveBeenCalledTimes(1);
  });

  it("does NOT open the tag sheet on click on desktop (no-op)", () => {
    vi.mocked(isMobile).mockReturnValue(false);

    $("#bulkTagFilterIcon").trigger("click");

    expect(vi.mocked(openTagSheetFromUserAction)).not.toHaveBeenCalled();
  });

  it("reflects the sheet's open state in aria-expanded after a click opens it", () => {
    // The click opens the sheet; the icon reads back isTagSheetOpen() to sync
    // aria-expanded (the sheet exposes no open/close AppEvent).
    vi.mocked(isTagSheetOpen).mockReturnValue(true);

    $("#bulkTagFilterIcon").trigger("click");

    expect($("#bulkTagFilterIcon").attr("aria-expanded")).toBe("true");
  });

  it("resets aria-expanded to false when focus returns to the icon on sheet close", () => {
    vi.mocked(isTagSheetOpen).mockReturnValue(true);
    $("#bulkTagFilterIcon").trigger("click");
    expect($("#bulkTagFilterIcon").attr("aria-expanded")).toBe("true");

    // Sheet closed → focus returns to the icon (its _opener); the focus handler
    // re-reads isTagSheetOpen() (now false).
    vi.mocked(isTagSheetOpen).mockReturnValue(false);
    $("#bulkTagFilterIcon").trigger("focus");

    expect($("#bulkTagFilterIcon").attr("aria-expanded")).toBe("false");
  });
});

describe("bulk-actions index — mobile deck switch exits mode conditionally", () => {
  // The UTUB_SELECTED / UTUB_DELETED subscriptions call the same trivial
  // () => exitMultiSelectMode() pass-through exercised here; they are not
  // emit-tested because a real UTUB_SELECTED on the shared bus also drives the
  // app's real URL-deck subscriber (a full deck rebuild needing DOM this unit
  // fixture omits). MOBILE_DECK_SWITCHED carries the only branching logic.
  beforeEach(() => {
    document.body.innerHTML = HTML;
    vi.mocked(exitMultiSelectMode).mockClear();
    initBulkActions();
  });

  it("exits mode when switching away from the url-deck panel", () => {
    emit(AppEvents.MOBILE_DECK_SWITCHED, { target: "member-deck" });
    expect(vi.mocked(exitMultiSelectMode)).toHaveBeenCalledTimes(1);
  });

  it("does NOT exit mode when (re-)entering the url-deck panel", () => {
    emit(AppEvents.MOBILE_DECK_SWITCHED, { target: "url-deck" });
    expect(vi.mocked(exitMultiSelectMode)).not.toHaveBeenCalled();
  });
});
