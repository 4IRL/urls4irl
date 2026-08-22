import {
  initBulkCopy,
  isBulkCopyPickerOpen,
  setBulkCopyPickerOpen,
} from "../bulk-copy.js";
import { getAvailableBulkActions } from "../bulk-action-registry.js";
import type { BulkAction, BulkActionContext } from "../bulk-action-registry.js";
import { setPickerOpen } from "../picker-guard.js";
import { APP_CONFIG } from "../../../../lib/config.js";
import { ajaxCall, is429Handled } from "../../../../lib/ajax.js";
import { AppEvents, emit } from "../../../../lib/event-bus.js";
import { createMockJqXHR } from "../../../../__tests__/helpers/mock-jquery.js";

vi.mock("../../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));

vi.mock("../../../../lib/modal-tracking.js", () => ({
  setOpenForm: vi.fn(),
  clearOpenForm: vi.fn(),
}));

interface Utub {
  id: number;
  name: string;
  memberRole: string;
  isLocked: boolean;
}
const storeState: { activeUTubID: number | null; utubs: Utub[] } = {
  activeUTubID: 1,
  utubs: [],
};
vi.mock("../../../../store/app-store.js", () => ({
  getState: vi.fn(() => storeState),
  setState: vi.fn((partial: Partial<typeof storeState>) => {
    Object.assign(storeState, partial);
  }),
}));

const $ = window.jQuery;

interface CopiedEntry {
  sourceUtubUrlID: number;
  utubUrlID: number;
  urlString: string;
  urlTitle: string;
}
interface SkippedEntry {
  utubUrlID: number;
  reason: string;
}
type DestStatus = "ok" | "locked";
interface DestResult {
  destUtubID: number;
  status: DestStatus;
  copied: CopiedEntry[];
  skipped: SkippedEntry[];
}
interface MultiCopyResponse {
  results: DestResult[];
  totalCopied: number;
  totalSkipped: number;
}

const BASE_HTML = `
  <div id="URLDeck">
    <div id="listURLs"></div>
    <div id="bulkActionBar">
      <button id="bulkSelectExit" type="button">Exit</button>
      <div id="bulkActionButtons"></div>
      <div id="bulkTagPickerMount" class="hidden"></div>
      <div id="bulkTagResultBanner" class="hidden" role="status"></div>
      <div id="bulkCopyPickerMount" class="bulkCopyPickerMount hidden"></div>
      <div id="bulkCopyResultBanner" class="bulkTagBanner hidden" role="status"></div>
    </div>
  </div>
`;

const DEFAULT_UTUBS: Utub[] = [
  { id: 1, name: "Source UTub", memberRole: "creator", isLocked: false },
  { id: 2, name: "Recipes to try", memberRole: "member", isLocked: false },
  { id: 3, name: "Reading list", memberRole: "member", isLocked: false },
  { id: 4, name: "Locked one", memberRole: "member", isLocked: true },
];

function seedUrlRows(ids: number[]): void {
  const listURLs = $("#listURLs");
  ids.forEach((id) => {
    listURLs.append(`<div class="urlRow" utuburlid="${id}"></div>`);
  });
}

function getCopyAction(): BulkAction {
  const context: BulkActionContext = { selectedURLCardIDs: [1], urls: [] };
  const action = getAvailableBulkActions(context).find(
    (candidate) => candidate.id === "bulk-copy",
  );
  if (!action) throw new Error("bulk-copy action not registered");
  return action;
}

function mount(): JQuery {
  return $("#bulkCopyPickerMount");
}

/** Open the picker for a selection (uses the current storeState.utubs). */
function openPickerFor(selectedURLCardIDs: number[]): void {
  getCopyAction().onActivate({
    selectedURLCardIDs,
    urls: [] as unknown as BulkActionContext["urls"],
  });
}

/** Build a single per-destination result. */
function destResult(
  destUtubID: number,
  {
    status = "ok",
    copied = [],
    skipped = [],
  }: { status?: DestStatus; copied?: CopiedEntry[]; skipped?: SkippedEntry[] },
): DestResult {
  return { destUtubID, status, copied, skipped };
}

/** Build the aggregated multi-destination response envelope from per-dest results. */
function multiResponse(results: DestResult[]): MultiCopyResponse {
  const totalCopied = results.reduce(
    (sum, result) => sum + result.copied.length,
    0,
  );
  const totalSkipped = results.reduce(
    (sum, result) => sum + result.skipped.length,
    0,
  );
  return { results, totalCopied, totalSkipped };
}

const COPIED_10: CopiedEntry = {
  sourceUtubUrlID: 10,
  utubUrlID: 100,
  urlString: "a",
  urlTitle: "A",
};
const COPIED_20: CopiedEntry = {
  sourceUtubUrlID: 20,
  utubUrlID: 200,
  urlString: "b",
  urlTitle: "B",
};

beforeAll(() => {
  document.body.innerHTML = BASE_HTML;
  initBulkCopy();
});

beforeEach(() => {
  document.body.innerHTML = BASE_HTML;
  storeState.activeUTubID = 1;
  storeState.utubs = DEFAULT_UTUBS.map((utub) => ({ ...utub }));
  vi.clearAllMocks();
  vi.mocked(is429Handled).mockReturnValue(false);
});

afterEach(() => {
  if (isBulkCopyPickerOpen()) {
    emit(AppEvents.URL_MULTISELECT_MODE_CHANGED, { active: false });
  }
  setBulkCopyPickerOpen(false);
  setPickerOpen("bulk-tag", false);
  document.body.innerHTML = "";
});

describe("bulk-copy action registration + availability", () => {
  it("registers the bulk-copy action with the Copy-to-UTub label", () => {
    expect(getCopyAction().label).toBe(APP_CONFIG.strings.URL_BULK_COPY_LABEL);
  });

  it("isAvailable is false with no selection", () => {
    expect(
      getCopyAction().isAvailable({ selectedURLCardIDs: [], urls: [] }),
    ).toBe(false);
  });

  it("isAvailable is false when the user is in only one UTub", () => {
    // Resolve the action reference while it is still available (default utubs),
    // then collapse the store to a single UTub before asserting isAvailable —
    // getCopyAction() itself filters on isAvailable, so it must run first.
    const action = getCopyAction();
    storeState.utubs = [DEFAULT_UTUBS[0]];
    expect(action.isAvailable({ selectedURLCardIDs: [10], urls: [] })).toBe(
      false,
    );
  });

  it("isAvailable is true with a selection and at least one other UTub", () => {
    expect(
      getCopyAction().isAvailable({ selectedURLCardIDs: [10], urls: [] }),
    ).toBe(true);
  });
});

describe("openBulkCopyPicker (onActivate)", () => {
  it("lists the OTHER UTubs as options excluding the active/source UTub, locking locked rows", () => {
    openPickerFor([10, 20, 30]);

    const options = mount().find('.UTubSelector[role="option"]');
    // 3 destinations (ids 2,3,4) — the source UTub (id 1) is excluded.
    expect(options.length).toBe(3);
    expect(mount().find("#bulkCopyOption-1").length).toBe(0);
    // The locked UTub (id 4) is disabled.
    const locked = mount().find("#bulkCopyOption-4");
    expect(locked.hasClass("disabled")).toBe(true);
    expect(locked.attr("aria-disabled")).toBe("true");
    expect(isBulkCopyPickerOpen()).toBe(true);
    expect($("#URLDeck").hasClass("bulkCopyPickerOpen")).toBe(true);
  });

  it("renders role=listbox on the INNER listbox (not the mount) and role=option/stable-id/aria-selected=false on each row", () => {
    openPickerFor([10]);

    // The role=listbox moved to an inner element so the filter input + footer
    // are not invalid children of a listbox.
    expect(mount().attr("role")).toBeUndefined();
    expect(mount().find(".bulkCopyListbox").attr("role")).toBe("listbox");
    const firstRow = mount().find("#bulkCopyOption-2");
    expect(firstRow.attr("role")).toBe("option");
    expect(firstRow.attr("aria-selected")).toBe("false");
    expect(firstRow.attr("id")).toBe("bulkCopyOption-2");
  });

  it("focuses the FILTER INPUT on open, keeps the first enabled row as the roving entry (tabindex 0), all others -1, and the listbox aria-label carries the count (DD-10/DD-24)", () => {
    openPickerFor([10, 20, 30]);

    const firstEnabled = mount().find("#bulkCopyOption-2");
    const secondEnabled = mount().find("#bulkCopyOption-3");
    const locked = mount().find("#bulkCopyOption-4");
    expect(firstEnabled.attr("tabindex")).toBe("0");
    expect(secondEnabled.attr("tabindex")).toBe("-1");
    expect(locked.attr("tabindex")).toBe("-1");
    // Real DOM focus lands on the filter input so the user can immediately type
    // to narrow; the first enabled row holds tabindex 0 as the roving entry.
    expect(document.activeElement).toBe(
      mount().find(".bulkCopyFilterInput")[0],
    );
    const listbox = mount().find(".bulkCopyListbox");
    // No aria-activedescendant anywhere — DD-7 dropped it entirely.
    expect(listbox.attr("aria-activedescendant")).toBeUndefined();
    expect(listbox.attr("aria-label")).toContain(
      APP_CONFIG.strings.URL_BULK_COPY_ARIA.replace("{n}", "3"),
    );
  });

  it("renders the all-locked message and keeps Copy disabled when every other UTub is locked (DD-18)", () => {
    storeState.utubs = [
      { id: 1, name: "Source", memberRole: "creator", isLocked: false },
      { id: 2, name: "Locked A", memberRole: "member", isLocked: true },
      { id: 3, name: "Locked B", memberRole: "member", isLocked: true },
    ];
    openPickerFor([10]);

    const allLocked = mount().find(".bulkCopyAllLocked");
    expect(allLocked.length).toBe(1);
    expect(allLocked.text()).toBe(APP_CONFIG.strings.URL_BULK_COPY_ALL_LOCKED);
    expect(allLocked.attr("role")).toBe("status");
    expect(allLocked.attr("aria-live")).toBe("polite");
    // No focusable destination rows; Copy is disabled.
    expect(mount().find('.UTubSelector[role="option"]').length).toBe(0);
    expect(mount().find(".bulkCopyConfirmBtn").prop("disabled")).toBe(true);
  });

  it("renders a per-row role badge on enabled rows and a locked label on locked rows, mutually exclusively (DD-4/DD-12)", () => {
    openPickerFor([10]);

    // Enabled row (id 2, memberRole "member"): role badge present with the
    // interpolated aria-label + raw role text; no locked label.
    const enabled = mount().find("#bulkCopyOption-2");
    const badge = enabled.find(".bulkCopyRoleBadge");
    expect(badge.length).toBe(1);
    expect(badge.text()).toBe("member");
    expect(badge.attr("aria-label")).toBe(
      APP_CONFIG.strings.URL_BULK_COPY_ROLE_ARIA.replace("{role}", "member"),
    );
    expect(enabled.find(".bulkCopyLockedLabel").length).toBe(0);
    // Decorative aria-hidden check affordance is present.
    const check = enabled.find(".bulkCopyOptionCheck");
    expect(check.length).toBe(1);
    expect(check.attr("aria-hidden")).toBe("true");

    // Locked row (id 4): locked label with "🔒 locked"; no role badge.
    const locked = mount().find("#bulkCopyOption-4");
    const lockedLabel = locked.find(".bulkCopyLockedLabel");
    expect(lockedLabel.length).toBe(1);
    expect(lockedLabel.text()).toBe(
      APP_CONFIG.strings.URL_BULK_COPY_LOCKED_LABEL,
    );
    expect(locked.find(".bulkCopyRoleBadge").length).toBe(0);
  });

  it("marks the inner listbox aria-multiselectable=true (DD-7)", () => {
    openPickerFor([10]);
    expect(mount().find(".bulkCopyListbox").attr("aria-multiselectable")).toBe(
      "true",
    );
  });

  it("is a no-op re-entrant activation (never double-mounts) — DD-15", () => {
    openPickerFor([10]);
    openPickerFor([10]);
    expect(mount().find('.UTubSelector[role="option"]').length).toBe(3);
  });

  it("no-ops when the tag picker is already open — DD-15", () => {
    setPickerOpen("bulk-tag", true);
    openPickerFor([10]);
    expect(isBulkCopyPickerOpen()).toBe(false);
    expect(mount().find('.UTubSelector[role="option"]').length).toBe(0);
  });

  it("does not open when there is no active UTub", () => {
    storeState.activeUTubID = null;
    openPickerFor([10]);
    expect(isBulkCopyPickerOpen()).toBe(false);
  });
});

describe("destination filter box", () => {
  const filterInput = (): JQuery => mount().find(".bulkCopyFilterInput");
  const optionRows = (): JQuery => mount().find('.UTubSelector[role="option"]');
  const visibleRows = (): JQuery =>
    optionRows().filter((_, el) => !$(el).hasClass("hidden"));

  it("renders a filter input (with the bridged placeholder) above the listbox", () => {
    openPickerFor([10]);
    expect(filterInput().length).toBe(1);
    expect(filterInput().attr("type")).toBe("search");
    expect(filterInput().attr("placeholder")).toBe(
      APP_CONFIG.strings.URL_BULK_COPY_FILTER_PLACEHOLDER,
    );
    expect(filterInput().attr("aria-label")).toBe(
      APP_CONFIG.strings.URL_BULK_COPY_FILTER_PLACEHOLDER,
    );
  });

  it("typing narrows the option rows by UTub name (case-insensitive), hiding non-matches", () => {
    openPickerFor([10]);
    // DEFAULT_UTUBS destinations: id2 "Recipes to try", id3 "Reading list",
    // id4 "Locked one". "read" matches only "Reading list" (id3).
    filterInput().val("read").trigger("input");
    expect(mount().find("#bulkCopyOption-3").hasClass("hidden")).toBe(false);
    expect(mount().find("#bulkCopyOption-2").hasClass("hidden")).toBe(true);
    expect(mount().find("#bulkCopyOption-4").hasClass("hidden")).toBe(true);
    expect(visibleRows().length).toBe(1);
  });

  it("shows the no-matches message when nothing matches, and clears it when the filter matches again", () => {
    openPickerFor([10]);
    const noMatches = mount().find(".bulkCopyNoMatches");

    filterInput().val("zzzz").trigger("input");
    expect(noMatches.hasClass("hidden")).toBe(false);
    expect(visibleRows().length).toBe(0);

    // Clearing the filter restores every row and hides the message.
    filterInput().val("").trigger("input");
    expect(noMatches.hasClass("hidden")).toBe(true);
    expect(visibleRows().length).toBe(3);
  });

  it("moves the roving entry (tabindex 0) onto the first STILL-VISIBLE enabled row after filtering", () => {
    openPickerFor([10]);
    // Match only id3 → the previously-first enabled row (id2) is filtered out.
    filterInput().val("reading").trigger("input");
    expect(mount().find("#bulkCopyOption-2").hasClass("hidden")).toBe(true);
    expect(mount().find("#bulkCopyOption-3").attr("tabindex")).toBe("0");
    expect(mount().find("#bulkCopyOption-2").attr("tabindex")).toBe("-1");
  });

  it("keeps a staged destination staged + Copy enabled even when the filter hides its row", () => {
    openPickerFor([10]);
    // Stage id3 (Reading list).
    mount().find("#bulkCopyOption-3").trigger("click");
    expect(mount().find("#bulkCopyOption-3").attr("aria-selected")).toBe(
      "true",
    );
    expect(mount().find(".bulkCopyConfirmBtn").prop("disabled")).toBe(false);

    // Filter to "recipes" → hides the staged id3 but keeps it staged.
    filterInput().val("recipes").trigger("input");
    expect(mount().find("#bulkCopyOption-3").hasClass("hidden")).toBe(true);
    expect(mount().find("#bulkCopyOption-3").attr("aria-selected")).toBe(
      "true",
    );
    expect(mount().find("#bulkCopyOption-3").hasClass("active")).toBe(true);
    expect(mount().find(".bulkCopyConfirmBtn").prop("disabled")).toBe(false);
  });

  it("ArrowDown from the filter input moves real focus to the first VISIBLE row after filtering", () => {
    openPickerFor([10]);
    // Filter so only id3 remains, then ArrowDown from the (focused) input.
    filterInput().val("reading").trigger("input");
    mount()[0]!.dispatchEvent(
      new KeyboardEvent("keydown", {
        key: "ArrowDown",
        bubbles: true,
        cancelable: true,
      }),
    );
    expect(document.activeElement).toBe(mount().find("#bulkCopyOption-3")[0]);
  });
});

describe("staging (DD-8/DD-9/DD-20)", () => {
  it("clicking a row stages it (aria-selected + active + Copy enabled) without firing AJAX", () => {
    openPickerFor([10]);
    const row = mount().find("#bulkCopyOption-3");
    row.trigger("click");

    expect(row.attr("aria-selected")).toBe("true");
    expect(row.hasClass("active")).toBe(true);
    expect(mount().find(".bulkCopyConfirmBtn").prop("disabled")).toBe(false);
    expect(vi.mocked(ajaxCall)).not.toHaveBeenCalled();
    // Staging moved the roving tabindex/focus onto the staged row (DD-20).
    expect(row.attr("tabindex")).toBe("0");
    expect(document.activeElement).toBe(row[0]);
  });

  it("Enter on the focused row stages it on keyup (mirrors .UTubSelector)", () => {
    openPickerFor([10]);
    const rowEl = mount().find("#bulkCopyOption-2")[0]!;
    rowEl.dispatchEvent(
      new KeyboardEvent("keyup", { key: "Enter", bubbles: true }),
    );
    expect(mount().find("#bulkCopyOption-2").attr("aria-selected")).toBe(
      "true",
    );
  });

  it("Space is prevent-defaulted on keydown and stages on the paired keyup (DD-9)", () => {
    openPickerFor([10]);
    const rowEl = mount().find("#bulkCopyOption-2")[0]!;

    const keydown = new KeyboardEvent("keydown", {
      key: " ",
      bubbles: true,
      cancelable: true,
    });
    rowEl.dispatchEvent(keydown);
    expect(keydown.defaultPrevented).toBe(true);
    // keydown alone does not stage.
    expect(mount().find("#bulkCopyOption-2").attr("aria-selected")).toBe(
      "false",
    );

    rowEl.dispatchEvent(
      new KeyboardEvent("keyup", { key: " ", bubbles: true }),
    );
    expect(mount().find("#bulkCopyOption-2").attr("aria-selected")).toBe(
      "true",
    );
  });

  it("ArrowDown/ArrowUp rove real DOM focus + tabindex across enabled rows (skipping disabled), preventing default", () => {
    openPickerFor([10]);
    const first = mount().find("#bulkCopyOption-2");
    const second = mount().find("#bulkCopyOption-3");

    // On open focus is on the filter input, so the FIRST ArrowDown enters the
    // list at the first enabled row.
    const down = new KeyboardEvent("keydown", {
      key: "ArrowDown",
      bubbles: true,
      cancelable: true,
    });
    mount()[0]!.dispatchEvent(down);
    expect(down.defaultPrevented).toBe(true);
    expect(document.activeElement).toBe(first[0]);
    expect(first.attr("tabindex")).toBe("0");

    // ArrowDown again moves to the second enabled row.
    mount()[0]!.dispatchEvent(
      new KeyboardEvent("keydown", {
        key: "ArrowDown",
        bubbles: true,
        cancelable: true,
      }),
    );
    expect(document.activeElement).toBe(second[0]);
    expect(second.attr("tabindex")).toBe("0");
    expect(first.attr("tabindex")).toBe("-1");

    // ArrowDown again wraps past the disabled locked row (id 4) back to the first.
    mount()[0]!.dispatchEvent(
      new KeyboardEvent("keydown", {
        key: "ArrowDown",
        bubbles: true,
        cancelable: true,
      }),
    );
    expect(document.activeElement).toBe(first[0]);
  });

  it("staging 2+ rows leaves BOTH aria-selected=true simultaneously (multi-select)", () => {
    openPickerFor([10]);
    mount().find("#bulkCopyOption-2").trigger("click");
    mount().find("#bulkCopyOption-3").trigger("click");
    expect(mount().find("#bulkCopyOption-2").attr("aria-selected")).toBe(
      "true",
    );
    expect(mount().find("#bulkCopyOption-3").attr("aria-selected")).toBe(
      "true",
    );
    expect(mount().find("#bulkCopyOption-2").hasClass("active")).toBe(true);
    expect(mount().find("#bulkCopyOption-3").hasClass("active")).toBe(true);
    // Footer live-region shows the plural staged count.
    expect(mount().find(".bulkCopyPickerMsg").text()).toBe(
      APP_CONFIG.strings.URL_BULK_COPY_N_SELECTED.replace("{n}", "2"),
    );
  });

  it("toggling a staged row OFF clears its aria-selected; emptying the set disables Copy and shows the select-destination hint", () => {
    openPickerFor([10]);
    const row = mount().find("#bulkCopyOption-2");
    // Stage it.
    row.trigger("click");
    expect(row.attr("aria-selected")).toBe("true");
    expect(mount().find(".bulkCopyConfirmBtn").prop("disabled")).toBe(false);
    expect(mount().find(".bulkCopyPickerMsg").text()).toBe(
      APP_CONFIG.strings.URL_BULK_COPY_ONE_SELECTED,
    );

    // Toggle it back off — set empties.
    row.trigger("click");
    expect(row.attr("aria-selected")).toBe("false");
    expect(row.hasClass("active")).toBe(false);
    expect(mount().find(".bulkCopyConfirmBtn").prop("disabled")).toBe(true);
    expect(mount().find(".bulkCopyPickerMsg").text()).toBe(
      APP_CONFIG.strings.URL_BULK_COPY_SELECT_DESTINATION,
    );
  });

  it("opens already showing the select-destination hint with Copy disabled (nothing staged)", () => {
    openPickerFor([10]);
    expect(mount().find(".bulkCopyConfirmBtn").prop("disabled")).toBe(true);
    expect(mount().find(".bulkCopyPickerMsg").text()).toBe(
      APP_CONFIG.strings.URL_BULK_COPY_SELECT_DESTINATION,
    );
  });
});

describe("confirm (Copy) — resolve flows", () => {
  function stageAndSubmit(
    destOptionIds: string[],
  ): ReturnType<typeof createMockJqXHR> {
    const deferred = createMockJqXHR();
    vi.mocked(ajaxCall).mockReturnValue(deferred);
    destOptionIds.forEach((optionId) =>
      mount().find(optionId).trigger("click"),
    );
    mount().find(".bulkCopyConfirmBtn").trigger("click");
    return deferred;
  }

  it("fires ONE batch request whose body carries destUtubIds (order-preserved) + sourceUtubId + utubUrlIds (DD-2)", () => {
    seedUrlRows([10, 20]);
    openPickerFor([10, 20]);
    stageAndSubmit(["#bulkCopyOption-2", "#bulkCopyOption-3"]);

    expect(vi.mocked(ajaxCall)).toHaveBeenCalledTimes(1);
    const [method, url, body] = vi.mocked(ajaxCall).mock.calls[0];
    expect(method).toBe("post");
    expect(url).toBe(APP_CONFIG.routes.copyURLsToUtubs);
    expect(body).toEqual({
      sourceUtubId: 1,
      destUtubIds: [2, 3],
      utubUrlIds: [10, 20],
    });
  });

  it("all-copied into 2 destinations → URLS_COPIED_MULTI banner, ONE green cue per source card (not two), picker closed, no store patch", () => {
    seedUrlRows([10, 20]);
    openPickerFor([10, 20]);
    const deferred = stageAndSubmit(["#bulkCopyOption-2", "#bulkCopyOption-3"]);

    deferred.resolve(
      multiResponse([
        destResult(2, { copied: [COPIED_10, COPIED_20] }),
        destResult(3, { copied: [COPIED_10, COPIED_20] }),
      ]),
      "success",
      { status: 200 },
    );

    const banner = $("#bulkCopyResultBanner");
    expect(banner.hasClass("success")).toBe(true);
    expect(banner.text()).toContain(
      APP_CONFIG.strings.URLS_COPIED_MULTI.replace("{n}", "2"),
    );
    expect(banner.attr("aria-live")).toBe("polite");
    // ONE green cue per source card, even though it landed in two destinations.
    expect($('.urlRow[utuburlid="10"] .bulkCardResultCue--copied').length).toBe(
      1,
    );
    expect($('.urlRow[utuburlid="20"] .bulkCardResultCue--copied').length).toBe(
      1,
    );
    expect(isBulkCopyPickerOpen()).toBe(false);
  });

  it("single-destination all-copied → singular URLS_COPIED success banner (polite), not URLS_COPIED_MULTI", () => {
    seedUrlRows([10]);
    openPickerFor([10]);
    const deferred = stageAndSubmit(["#bulkCopyOption-2"]);

    deferred.resolve(
      multiResponse([destResult(2, { copied: [COPIED_10] })]),
      "success",
      { status: 200 },
    );

    const banner = $("#bulkCopyResultBanner");
    expect(banner.hasClass("success")).toBe(true);
    expect(banner.attr("aria-live")).toBe("polite");
    expect(banner.text()).toContain(APP_CONFIG.strings.URLS_COPIED);
    expect(banner.text()).not.toContain(
      APP_CONFIG.strings.URLS_COPIED_MULTI.replace("{n}", "1"),
    );
    // ONE green cue on the single source card.
    expect($('.urlRow[utuburlid="10"] .bulkCardResultCue--copied').length).toBe(
      1,
    );
    expect(isBulkCopyPickerOpen()).toBe(false);
  });

  it("partial across destinations (green-if-any) → URLS_COPIED_MULTI_PARTIAL; banner has no URL title", () => {
    seedUrlRows([10, 20]);
    openPickerFor([10, 20]);
    const deferred = stageAndSubmit(["#bulkCopyOption-2", "#bulkCopyOption-3"]);

    // id 10 is new in BOTH dests; id 20 is new in dest 2 but a duplicate in
    // dest 3 → green-if-any means id 20 still shows a green cue.
    deferred.resolve(
      multiResponse([
        destResult(2, {
          copied: [COPIED_10, { ...COPIED_20, urlTitle: "Flexbox cheatsheet" }],
        }),
        destResult(3, {
          copied: [COPIED_10],
          skipped: [{ utubUrlID: 20, reason: "duplicate" }],
        }),
      ]),
      "success",
      { status: 200 },
    );

    const banner = $("#bulkCopyResultBanner");
    expect(banner.hasClass("partial")).toBe(true);
    expect(banner.text()).toContain(
      APP_CONFIG.strings.URLS_COPIED_MULTI_PARTIAL.replace("{n}", "2").replace(
        "{skipped}",
        "1",
      ),
    );
    expect(banner.text()).not.toContain("Flexbox cheatsheet");
    // Both source cards show a GREEN cue (id 20 was new in ≥1 dest).
    expect($('.urlRow[utuburlid="10"] .bulkCardResultCue--copied').length).toBe(
      1,
    );
    expect($('.urlRow[utuburlid="20"] .bulkCardResultCue--copied').length).toBe(
      1,
    );
  });

  it("locked destination + 2 copying → plural URLS_COPIED_MULTI_SOME_LOCKED (assertive)", () => {
    seedUrlRows([10]);
    openPickerFor([10]);
    const deferred = stageAndSubmit(["#bulkCopyOption-2"]);

    deferred.resolve(
      multiResponse([
        destResult(2, { copied: [COPIED_10] }),
        destResult(3, { copied: [COPIED_10] }),
        destResult(4, { status: "locked" }),
      ]),
      "success",
      { status: 200 },
    );

    const banner = $("#bulkCopyResultBanner");
    expect(banner.hasClass("partial")).toBe(true);
    expect(banner.attr("aria-live")).toBe("assertive");
    expect(banner.text()).toContain(
      APP_CONFIG.strings.URLS_COPIED_MULTI_SOME_LOCKED.replace(
        "{n}",
        "2",
      ).replace("{locked}", "1"),
    );
  });

  it("locked destination + exactly ONE copying → singular URLS_COPIED_SOME_LOCKED (assertive, DD-11)", () => {
    seedUrlRows([10]);
    openPickerFor([10]);
    const deferred = stageAndSubmit(["#bulkCopyOption-2"]);

    deferred.resolve(
      multiResponse([
        destResult(2, { copied: [COPIED_10] }),
        destResult(3, { status: "locked" }),
      ]),
      "success",
      { status: 200 },
    );

    const banner = $("#bulkCopyResultBanner");
    expect(banner.hasClass("partial")).toBe(true);
    expect(banner.attr("aria-live")).toBe("assertive");
    expect(banner.text()).toContain(
      APP_CONFIG.strings.URLS_COPIED_SOME_LOCKED.replace("{locked}", "1"),
    );
  });

  it("every targeted destination locked (nothing copied) → UNABLE_TO_COPY_URLS fail banner AND no per-card cue (DD-13)", () => {
    seedUrlRows([10]);
    openPickerFor([10]);
    const deferred = stageAndSubmit(["#bulkCopyOption-2"]);

    deferred.resolve(
      multiResponse([destResult(2, { status: "locked" })]),
      "success",
      { status: 200 },
    );

    const banner = $("#bulkCopyResultBanner");
    expect(banner.hasClass("fail")).toBe(true);
    expect(banner.attr("aria-live")).toBe("assertive");
    expect(banner.text()).toContain(APP_CONFIG.strings.UNABLE_TO_COPY_URLS);
    // Cues suppressed — a lock-block must not paint a misleading amber cue.
    expect($('.urlRow[utuburlid="10"] .bulkCardResultCue').length).toBe(0);
  });

  it("all-duplicate, no locks, 2+ destinations → URLS_COPY_MULTI_NONE_NEW AND amber cues DO fire (DD-13)", () => {
    seedUrlRows([10]);
    openPickerFor([10]);
    const deferred = stageAndSubmit(["#bulkCopyOption-2", "#bulkCopyOption-3"]);

    deferred.resolve(
      multiResponse([
        destResult(2, { skipped: [{ utubUrlID: 10, reason: "duplicate" }] }),
        destResult(3, { skipped: [{ utubUrlID: 10, reason: "duplicate" }] }),
      ]),
      "success",
      { status: 200 },
    );

    const banner = $("#bulkCopyResultBanner");
    expect(banner.hasClass("partial")).toBe(true);
    expect(banner.text()).toContain(
      APP_CONFIG.strings.URLS_COPY_MULTI_NONE_NEW,
    );
    // Unlike the all-locked case, amber "Already there" cues DO fire.
    expect(
      $('.urlRow[utuburlid="10"] .bulkCardResultCue--skipped').length,
    ).toBe(1);
  });

  it("single-destination all-duplicate → singular URLS_COPY_NONE_NEW (DD-14) + amber cue fires", () => {
    seedUrlRows([10]);
    openPickerFor([10]);
    const deferred = stageAndSubmit(["#bulkCopyOption-2"]);

    deferred.resolve(
      multiResponse([
        destResult(2, { skipped: [{ utubUrlID: 10, reason: "duplicate" }] }),
      ]),
      "success",
      { status: 200 },
    );

    const banner = $("#bulkCopyResultBanner");
    expect(banner.hasClass("partial")).toBe(true);
    expect(banner.text()).toContain(APP_CONFIG.strings.URLS_COPY_NONE_NEW);
    expect(banner.text()).not.toContain(
      APP_CONFIG.strings.URLS_COPY_MULTI_NONE_NEW,
    );
    expect(
      $('.urlRow[utuburlid="10"] .bulkCardResultCue--skipped').length,
    ).toBe(1);
  });

  it("stale-UTub race: nothing rendered when activeUTubID changes mid-flight", () => {
    seedUrlRows([10]);
    openPickerFor([10]);
    const deferred = stageAndSubmit(["#bulkCopyOption-2"]);

    storeState.activeUTubID = 999;
    deferred.resolve(
      multiResponse([destResult(2, { copied: [COPIED_10] })]),
      "success",
      { status: 200 },
    );

    expect($("#bulkCopyResultBanner").hasClass("hidden")).toBe(true);
    expect($('.urlRow[utuburlid="10"] .bulkCardResultCue').length).toBe(0);
  });

  it("is429Handled short-circuits the failure path", () => {
    seedUrlRows([10]);
    openPickerFor([10]);
    vi.mocked(is429Handled).mockReturnValueOnce(true);
    const deferred = stageAndSubmit(["#bulkCopyOption-2"]);
    deferred.reject({ status: 429 });

    // No fail banner rendered.
    expect($("#bulkCopyResultBanner").hasClass("fail")).toBe(false);
  });

  it("a message-level 400 renders the fail banner and closes the picker", () => {
    seedUrlRows([10]);
    openPickerFor([10]);
    const deferred = stageAndSubmit(["#bulkCopyOption-2"]);
    deferred.reject({
      status: 400,
      responseJSON: { message: "URL not found in the source UTub." },
    });

    const banner = $("#bulkCopyResultBanner");
    expect(banner.hasClass("fail")).toBe(true);
    expect(banner.attr("aria-live")).toBe("assertive");
    expect(banner.text()).toContain(APP_CONFIG.strings.UNABLE_TO_COPY_URLS);
    expect(isBulkCopyPickerOpen()).toBe(false);
  });

  it("redirects to the error page on a JSON 403 (auth/lock lost mid-flight)", () => {
    const locationAssignSpy = vi
      .spyOn(window.location, "assign")
      .mockImplementation(() => {});
    try {
      seedUrlRows([10]);
      openPickerFor([10]);
      const deferred = stageAndSubmit(["#bulkCopyOption-2"]);
      deferred.reject({ status: 403, responseJSON: { message: "Forbidden" } });

      expect(locationAssignSpy).toHaveBeenCalledWith(
        APP_CONFIG.routes.errorPage,
      );
    } finally {
      locationAssignSpy.mockRestore();
    }
  });

  it("redirects to the error page on a JSON 404 (stale source UTub/URL)", () => {
    const locationAssignSpy = vi
      .spyOn(window.location, "assign")
      .mockImplementation(() => {});
    try {
      seedUrlRows([10]);
      openPickerFor([10]);
      const deferred = stageAndSubmit(["#bulkCopyOption-2"]);
      deferred.reject({ status: 404, responseJSON: { message: "Not found" } });

      expect(locationAssignSpy).toHaveBeenCalledWith(
        APP_CONFIG.routes.errorPage,
      );
    } finally {
      locationAssignSpy.mockRestore();
    }
  });

  it("replaces the body with the server HTML on a non-JSON 403 (CSRF expired)", () => {
    seedUrlRows([10]);
    openPickerFor([10]);
    const deferred = stageAndSubmit(["#bulkCopyOption-2"]);

    const forbiddenHtml = '<div id="forbiddenPage">Forbidden</div>';
    // No `responseJSON` key → the non-JSON branch; a 403 with an HTML content
    // type swaps the server body in place (login/forbidden page) rather than
    // redirecting to the error page.
    deferred.reject({
      status: 403,
      responseText: forbiddenHtml,
      getResponseHeader: (name: string) =>
        name === "Content-Type" ? "text/html; charset=utf-8" : null,
    });

    expect($("#forbiddenPage").length).toBe(1);
  });
});

describe("Escape + Cancel (DD-17)", () => {
  it("Escape (capture-phase, single-stage) closes the picker without exiting mode", () => {
    openPickerFor([10]);
    const docSpy = vi.fn();
    document.addEventListener("keydown", docSpy);
    try {
      mount()[0]!.dispatchEvent(
        new KeyboardEvent("keydown", {
          key: "Escape",
          bubbles: true,
          cancelable: true,
        }),
      );
      expect(isBulkCopyPickerOpen()).toBe(false);
      // stopPropagation kept it from the document-level exit handler.
      expect(docSpy).not.toHaveBeenCalled();
    } finally {
      document.removeEventListener("keydown", docSpy);
    }
  });

  it("Cancel closes the picker", () => {
    openPickerFor([10]);
    mount().find(".bulkCopyCancelBtn").trigger("click");
    expect(isBulkCopyPickerOpen()).toBe(false);
  });

  it("does NOT preventDefault Space when a footer button is focused (native activation preserved)", () => {
    openPickerFor([10]);
    const cancelBtn = mount().find(".bulkCopyCancelBtn")[0]!;
    const spaceOnButton = new KeyboardEvent("keydown", {
      key: " ",
      bubbles: true,
      cancelable: true,
    });
    cancelBtn.dispatchEvent(spaceOnButton);
    // Space on the button keeps native behaviour — not prevented.
    expect(spaceOnButton.defaultPrevented).toBe(false);
  });
});

describe("in-flight guards", () => {
  it("no-ops Cancel, Escape, and re-submit while a copy is in flight", () => {
    openPickerFor([10]);
    const deferred = createMockJqXHR();
    vi.mocked(ajaxCall).mockReturnValue(deferred);
    mount().find("#bulkCopyOption-2").trigger("click");
    mount().find(".bulkCopyConfirmBtn").trigger("click");
    expect(vi.mocked(ajaxCall)).toHaveBeenCalledTimes(1);

    // Cancel is a no-op while in flight (picker stays open).
    mount().find(".bulkCopyCancelBtn").trigger("click");
    expect(isBulkCopyPickerOpen()).toBe(true);

    // Escape is a no-op while in flight (still swallowed).
    mount()[0]!.dispatchEvent(
      new KeyboardEvent("keydown", {
        key: "Escape",
        bubbles: true,
        cancelable: true,
      }),
    );
    expect(isBulkCopyPickerOpen()).toBe(true);

    // A second Copy click never fires a second request.
    mount().find(".bulkCopyConfirmBtn").trigger("click");
    expect(vi.mocked(ajaxCall)).toHaveBeenCalledTimes(1);

    // Settle so the module's in-flight state resets for the next test.
    deferred.resolve(multiResponse([]), "success", { status: 200 });
  });
});
