import type {
  TrashList,
  TrashedUrlItem,
  TrashedUtubItem,
} from "../../../types/trash.js";

import { $ } from "../../../lib/globals.js";
import {
  buildTrashUrlRow,
  buildTrashUtubRow,
  formatDaysLeft,
  formatDeletedAgo,
  getTrashListState,
  isUrgent,
  renderTrashList,
  updateEmptyTrashButton,
} from "../render.js";
import { handleTrashTabClick } from "../tabs.js";

const NOW = Date.parse("2026-10-16T12:00:00Z");
const DAY = 86_400_000;
const CURRENT_USER = 5;

function isoFromNow({ days }: { days: number }): string {
  return new Date(NOW + days * DAY).toISOString();
}

function makeUrlItem(overrides: Partial<TrashedUrlItem> = {}): TrashedUrlItem {
  return {
    utubUrlID: 11,
    urlString: "https://example.com/a",
    urlTitle: "Example A",
    utubID: 3,
    utubName: "Reading List",
    originUtubTrashed: false,
    originUtubLocked: false,
    trashedWithUtub: false,
    deletedAt: isoFromNow({ days: -2 }),
    expiresAt: isoFromNow({ days: 20 }),
    deletedByUserID: 9,
    deletedByUsername: "mcarter",
    addedByUserID: 9,
    addedByUsername: "mcarter",
    canRestore: true,
    canDelete: true,
    ...overrides,
  } as TrashedUrlItem;
}

function makeUtubItem(
  overrides: Partial<TrashedUtubItem> = {},
): TrashedUtubItem {
  return {
    utubID: 4,
    utubName: "Work Archive",
    utubDescription: null,
    deletedAt: isoFromNow({ days: -5 }),
    expiresAt: isoFromNow({ days: 25 }),
    deletedByUserID: CURRENT_USER,
    deletedByUsername: "me",
    urlCount: 12,
    memberCount: 3,
    isLocked: false,
    canRestore: true,
    canDelete: true,
    ...overrides,
  };
}

function makeList(overrides: Partial<TrashList> = {}): TrashList {
  return {
    urls: [],
    utubs: [],
    currentUser: CURRENT_USER,
    retentionDays: 30,
    listedAt: new Date(NOW).toISOString(),
    ...overrides,
  } as TrashList;
}

const HTML = `
  <div id="TrashTablist" role="tablist">
    <button id="TrashTabUrls" role="tab" aria-selected="true" tabindex="0"></button>
    <button id="TrashTabUtubs" role="tab" aria-selected="false" tabindex="-1"></button>
  </div>
  <button id="TrashBtnEmpty"></button>
  <p id="TrashRetentionNotice" class="hidden"></p>
  <div id="TrashPanelUrls" role="tabpanel">
    <div id="listTrashURLs"></div>
    <p id="TrashUrlsEmptyState" class="hidden"></p>
  </div>
  <div id="TrashPanelUtubs" role="tabpanel" hidden>
    <div id="listTrashUTubs"></div>
    <p id="TrashUtubsEmptyState" class="hidden"></p>
  </div>
`;

describe("countdown helpers", () => {
  it("formats days left from the server expiresAt", () => {
    expect(
      formatDaysLeft({ expiresAt: isoFromNow({ days: 19 }), now: NOW }),
    ).toBe("19 days left");
    expect(
      formatDaysLeft({ expiresAt: isoFromNow({ days: 2 }), now: NOW }),
    ).toBe("2 days left");
    expect(
      formatDaysLeft({ expiresAt: isoFromNow({ days: 1 }), now: NOW }),
    ).toBe("1 day left");
    expect(
      formatDaysLeft({ expiresAt: isoFromNow({ days: 0.5 }), now: NOW }),
    ).toBe("1 day left");
    expect(
      formatDaysLeft({ expiresAt: isoFromNow({ days: -3 }), now: NOW }),
    ).toBe("Expires today");
    expect(
      formatDaysLeft({ expiresAt: new Date(NOW).toISOString(), now: NOW }),
    ).toBe("Expires today");
  });

  it("is urgent at 3 days or fewer", () => {
    expect(isUrgent({ expiresAt: isoFromNow({ days: 3 }), now: NOW })).toBe(
      true,
    );
    expect(isUrgent({ expiresAt: isoFromNow({ days: 3.2 }), now: NOW })).toBe(
      false,
    );
    expect(isUrgent({ expiresAt: isoFromNow({ days: -1 }), now: NOW })).toBe(
      true,
    );
  });

  it("formats the deleted-ago text", () => {
    expect(
      formatDeletedAgo({ deletedAt: isoFromNow({ days: -0.2 }), now: NOW }),
    ).toBe("today");
    expect(
      formatDeletedAgo({ deletedAt: isoFromNow({ days: -1 }), now: NOW }),
    ).toBe("1 day ago");
    expect(
      formatDeletedAgo({ deletedAt: isoFromNow({ days: -28 }), now: NOW }),
    ).toBe("28 days ago");
  });
});

describe("trash rows", () => {
  it("builds a URL row with title, url, chips and enabled actions", () => {
    const row = buildTrashUrlRow({
      item: makeUrlItem({ expiresAt: isoFromNow({ days: 2 }) }),
      currentUserID: CURRENT_USER,
      now: NOW,
    });

    expect(row.hasClass("trashRow")).toBe(true);
    expect(row.attr("tabindex")).toBe("-1");
    expect(row.attr("data-utub-id")).toBe("3");
    expect(row.attr("data-utub-url-id")).toBe("11");
    expect(row.find(".t-title").text()).toBe("Example A");
    expect(row.find(".t-url").text()).toBe("https://example.com/a");
    expect(row.find(".chip-expiry").text()).toBe("2 days left");
    expect(row.find(".chip-expiry").hasClass("urgent")).toBe(true);
    expect(row.find(".chip-origin").text()).toBe("from Reading List");
    expect(row.find(".chip-origin").hasClass("dashed")).toBe(false);
    expect(row.find(".t-meta").text()).toBe("Deleted by mcarter · 2 days ago");

    const restore = row.find(".trashBtnRestore");
    expect(restore.hasClass("btn-restore")).toBe(true);
    expect(restore.text()).toBe("Restore");
    expect(restore.attr("aria-label")).toContain("Example A");
    expect(restore.attr("aria-haspopup")).toBeUndefined();
    expect(restore.hasClass("disabled")).toBe(false);
    const purge = row.find(".trashBtnPurge");
    expect(purge.hasClass("btn-forever")).toBe(true);
    expect(purge.attr("aria-label")).toContain("Example A");
  });

  it("renders 'you' when the current user deleted the row", () => {
    const row = buildTrashUrlRow({
      item: makeUrlItem({ deletedByUserID: CURRENT_USER }),
      currentUserID: CURRENT_USER,
      now: NOW,
    });
    expect(row.find(".t-meta").text()).toBe("Deleted by you · 2 days ago");
  });

  it("marks a trashed-origin row with the dashed chip and a listbox Restore to…", () => {
    const row = buildTrashUrlRow({
      item: makeUrlItem({ originUtubTrashed: true }),
      currentUserID: CURRENT_USER,
      now: NOW,
    });
    const chip = row.find(".chip-origin");
    expect(chip.hasClass("dashed")).toBe(true);
    expect(chip.text()).toBe("Origin UTub deleted · choose a UTub on restore");
    const restore = row.find(".trashBtnRestore");
    expect(restore.text()).toBe("Restore to…");
    expect(restore.attr("aria-haspopup")).toBe("listbox");
  });

  it("marks a locked-origin row dashed and disables both actions without the native attribute", () => {
    const row = buildTrashUrlRow({
      item: makeUrlItem({
        originUtubLocked: true,
        canRestore: false,
        canDelete: false,
      }),
      currentUserID: CURRENT_USER,
      now: NOW,
    });
    const chip = row.find(".chip-origin");
    expect(chip.hasClass("dashed")).toBe(true);
    expect(chip.text()).toBe("Origin UTub locked");

    for (const selector of [".trashBtnRestore", ".trashBtnPurge"]) {
      const button = row.find(selector);
      expect(button.hasClass("disabled")).toBe(true);
      expect(button.attr("aria-disabled")).toBe("true");
      expect(button.attr("disabled")).toBeUndefined();
    }
  });

  it("disables only the action the row cannot perform", () => {
    const row = buildTrashUrlRow({
      item: makeUrlItem({ canRestore: true, canDelete: false }),
      currentUserID: CURRENT_USER,
      now: NOW,
    });
    expect(row.find(".trashBtnRestore").hasClass("disabled")).toBe(false);
    expect(row.find(".trashBtnPurge").hasClass("disabled")).toBe(true);
  });

  it("builds a UTub row with the summary line and a locked chip", () => {
    const row = buildTrashUtubRow({
      item: makeUtubItem({
        isLocked: true,
        canRestore: false,
        canDelete: false,
      }),
      currentUserID: CURRENT_USER,
      now: NOW,
    });
    expect(row.attr("data-utub-id")).toBe("4");
    expect(row.attr("data-utub-url-id")).toBeUndefined();
    expect(row.find(".t-title").text()).toBe("Work Archive");
    expect(row.find(".t-url").text()).toBe("URLs: 12 · Members: 3");
    expect(row.find(".chip-origin").text()).toBe("UTub locked");
    expect(row.find(".t-meta").text()).toBe("Deleted by you · 5 days ago");
    expect(row.find(".trashBtnRestore").attr("aria-disabled")).toBe("true");
    expect(row.find(".trashBtnPurge").attr("aria-disabled")).toBe("true");
  });

  it("omits the locked chip for an unlocked UTub", () => {
    const row = buildTrashUtubRow({
      item: makeUtubItem(),
      currentUserID: CURRENT_USER,
      now: NOW,
    });
    expect(row.find(".chip-origin").length).toBe(0);
  });

  it("renders user text literally, never as markup", () => {
    const row = buildTrashUrlRow({
      item: makeUrlItem({
        urlTitle: "<b>bold</b>",
        utubName: "<i>x</i>",
        deletedByUsername: "<u>y</u>",
      }),
      currentUserID: CURRENT_USER,
      now: NOW,
    });
    expect(row.find(".t-title").text()).toBe("<b>bold</b>");
    expect(row.find("b, i, u").length).toBe(0);

    const utubRow = buildTrashUtubRow({
      item: makeUtubItem({ utubName: "<b>boom</b>" }),
      currentUserID: CURRENT_USER,
      now: NOW,
    });
    expect(utubRow.find(".t-title").text()).toBe("<b>boom</b>");
    expect(utubRow.find("b").length).toBe(0);
  });
});

describe("renderTrashList", () => {
  beforeEach(() => {
    document.body.innerHTML = HTML;
    renderTrashList({ list: makeList() });
  });

  it("shows both empty states and disables Empty trash for an empty response", () => {
    expect($("#TrashTabUrls").text()).toBe("URLs (0)");
    expect($("#TrashTabUtubs").text()).toBe("UTubs (0)");
    expect($("#TrashUrlsEmptyState").hasClass("hidden")).toBe(false);
    expect($("#listTrashURLs").hasClass("hidden")).toBe(true);
    expect($("#TrashUtubsEmptyState").hasClass("hidden")).toBe(false);
    expect($("#TrashBtnEmpty").prop("disabled")).toBe(true);
    expect($("#TrashBtnEmpty").attr("aria-disabled")).toBe("true");
  });

  it("renders rows, counts and hides the empty state", () => {
    renderTrashList({
      list: makeList({
        urls: [makeUrlItem(), makeUrlItem({ utubUrlID: 12 })],
        utubs: [makeUtubItem()],
      }),
    });

    expect($("#TrashTabUrls").text()).toBe("URLs (2)");
    expect($("#TrashTabUtubs").text()).toBe("UTubs (1)");
    expect($("#listTrashURLs .trashRow").length).toBe(2);
    expect($("#listTrashUTubs .trashRow").length).toBe(1);
    expect($("#TrashUrlsEmptyState").hasClass("hidden")).toBe(true);
    expect($("#listTrashURLs").hasClass("hidden")).toBe(false);
    expect($("#TrashBtnEmpty").prop("disabled")).toBe(false);
    expect($("#TrashBtnEmpty").attr("aria-disabled")).toBeUndefined();
  });

  it("rebuilds rather than appends on a second render", () => {
    const list = makeList({ urls: [makeUrlItem()] });
    renderTrashList({ list });
    renderTrashList({ list });
    expect($("#listTrashURLs .trashRow").length).toBe(1);
  });

  it("stores the list state", () => {
    const list = makeList({ urls: [makeUrlItem()], utubs: [makeUtubItem()] });
    renderTrashList({ list });
    const state = getTrashListState();
    expect(state.listedAt).toBe(list.listedAt);
    expect(state.urls.length).toBe(1);
    expect(state.utubs.length).toBe(1);
  });

  it("fills and shows the retention notice", () => {
    renderTrashList({ list: makeList({ retentionDays: 14 }) });
    expect($("#TrashRetentionNotice").text()).toBe(
      "Items here are permanently deleted 14 days after they were removed.",
    );
    expect($("#TrashRetentionNotice").hasClass("hidden")).toBe(false);
  });

  it("disables Empty trash when no row in the active tab can be deleted", () => {
    renderTrashList({
      list: makeList({ urls: [makeUrlItem({ canDelete: false })] }),
    });
    expect($("#TrashBtnEmpty").prop("disabled")).toBe(true);
    expect($("#TrashBtnEmpty").attr("aria-disabled")).toBe("true");
  });

  it("re-evaluates Empty trash for the newly active tab", () => {
    renderTrashList({
      list: makeList({
        urls: [makeUrlItem()],
        utubs: [makeUtubItem({ canDelete: false })],
      }),
    });
    expect($("#TrashBtnEmpty").prop("disabled")).toBe(false);

    handleTrashTabClick({ tabId: "TrashTabUtubs" });
    updateEmptyTrashButton();
    expect($("#TrashBtnEmpty").prop("disabled")).toBe(true);

    handleTrashTabClick({ tabId: "TrashTabUrls" });
    updateEmptyTrashButton();
    expect($("#TrashBtnEmpty").prop("disabled")).toBe(false);
  });
});
