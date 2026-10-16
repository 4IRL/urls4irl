/**
 * Renders the Trash list response into the two tab panels.
 *
 * Every user-controlled string (titles, URLs, UTub and user names) is written
 * with `.text()` so markup in a title renders literally.
 */

import type {
  TrashList,
  TrashedUrlItem,
  TrashedUtubItem,
} from "../../types/trash.js";

import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { fillTemplate } from "../../lib/string-template.js";
import { getActiveTrashScope } from "./tabs.js";
import type { TrashScope } from "./tabs.js";

const MS_PER_DAY = 86_400_000;
const URGENT_DAYS = 3;

const SCOPE_IDS: Record<
  TrashScope,
  { list: string; emptyState: string; tab: string }
> = {
  urls: {
    list: "#listTrashURLs",
    emptyState: "#TrashUrlsEmptyState",
    tab: "#TrashTabUrls",
  },
  utubs: {
    list: "#listTrashUTubs",
    emptyState: "#TrashUtubsEmptyState",
    tab: "#TrashTabUtubs",
  },
};

interface TrashListState {
  listedAt: string | null;
  urls: TrashedUrlItem[];
  utubs: TrashedUtubItem[];
  currentUser: number | null;
}

let trashListState: TrashListState = {
  listedAt: null,
  urls: [],
  utubs: [],
  currentUser: null,
};

export function getTrashListState(): TrashListState {
  return trashListState;
}

/** Whole days until the server-computed `expiresAt`, rounded up and floored at 0. */
export function getDaysLeft({
  expiresAt,
  now,
}: {
  expiresAt: string;
  now: number;
}): number {
  return Math.max(0, Math.ceil((Date.parse(expiresAt) - now) / MS_PER_DAY));
}

export function formatDaysLeft({
  expiresAt,
  now,
}: {
  expiresAt: string;
  now: number;
}): string {
  const days = getDaysLeft({ expiresAt, now });
  if (days < 1) return APP_CONFIG.strings.TRASH_EXPIRES_TODAY;
  if (days === 1) return APP_CONFIG.strings.TRASH_DAY_LEFT;
  return fillTemplate({
    template: APP_CONFIG.strings.TRASH_DAYS_LEFT,
    values: { n: String(days) },
  });
}

export function isUrgent({
  expiresAt,
  now,
}: {
  expiresAt: string;
  now: number;
}): boolean {
  return getDaysLeft({ expiresAt, now }) <= URGENT_DAYS;
}

export function formatDeletedAgo({
  deletedAt,
  now,
}: {
  deletedAt: string;
  now: number;
}): string {
  const days = Math.max(
    0,
    Math.floor((now - Date.parse(deletedAt)) / MS_PER_DAY),
  );
  if (days < 1) return APP_CONFIG.strings.TRASH_AGO_TODAY;
  if (days === 1) return APP_CONFIG.strings.TRASH_AGO_ONE_DAY;
  return fillTemplate({
    template: APP_CONFIG.strings.TRASH_AGO_DAYS,
    values: { n: String(days) },
  });
}

export function formatDeletedBy({
  item,
  currentUserID,
  now,
}: {
  item: TrashedUrlItem | TrashedUtubItem;
  currentUserID: number;
  now: number;
}): string {
  const ago = formatDeletedAgo({ deletedAt: item.deletedAt, now });
  if (item.deletedByUserID === currentUserID) {
    return fillTemplate({
      template: APP_CONFIG.strings.TRASH_DELETED_BY_YOU,
      values: { ago },
    });
  }
  return fillTemplate({
    template: APP_CONFIG.strings.TRASH_DELETED_BY,
    values: { user: item.deletedByUsername, ago },
  });
}

function setDisabled({
  button,
  disabled,
}: {
  button: JQuery;
  disabled: boolean;
}): void {
  if (!disabled) return;
  button.addClass("disabled").attr("aria-disabled", "true");
}

function buildActionButton({
  className,
  label,
  ariaLabel,
  disabled,
}: {
  className: string;
  label: string;
  ariaLabel: string;
  disabled: boolean;
}): JQuery {
  const button = $('<button type="button" class="btn"></button>')
    .addClass(className)
    .text(label)
    .attr("aria-label", ariaLabel);
  setDisabled({ button, disabled });
  return button;
}

function buildExpiryChip({
  expiresAt,
  now,
}: {
  expiresAt: string;
  now: number;
}): JQuery {
  const chip = $('<span class="chip chip-expiry"></span>').text(
    formatDaysLeft({ expiresAt, now }),
  );
  if (isUrgent({ expiresAt, now })) chip.addClass("urgent");
  return chip;
}

function buildRowShell({
  title,
  subtitle,
  expiresAt,
  now,
}: {
  title: string;
  subtitle: string;
  expiresAt: string;
  now: number;
}): { row: JQuery; actions: JQuery } {
  const row = $('<div class="trashRow" tabindex="-1"></div>');
  const heading = $("<div></div>")
    .append($('<div class="t-title"></div>').text(title))
    .append($('<div class="t-url"></div>').text(subtitle));
  const rowLine = $('<div class="rowline"></div>')
    .append(heading)
    .append(
      $('<div class="right"></div>').append(
        buildExpiryChip({ expiresAt, now }),
      ),
    );
  const actions = $('<div class="actions"></div>');
  row.append(rowLine).append(actions);
  return { row, actions };
}

function buildOriginChip({ item }: { item: TrashedUrlItem }): JQuery {
  const chip = $('<span class="chip chip-origin"></span>');
  if (item.originUtubTrashed) {
    return chip
      .addClass("dashed")
      .text(APP_CONFIG.strings.TRASH_ORIGIN_DELETED);
  }
  if (item.originUtubLocked) {
    return chip.addClass("dashed").text(APP_CONFIG.strings.TRASH_ORIGIN_LOCKED);
  }
  return chip.text(
    fillTemplate({
      template: APP_CONFIG.strings.TRASH_FROM_UTUB,
      values: { utub: item.utubName },
    }),
  );
}

export function buildTrashUrlRow({
  item,
  currentUserID,
  now,
}: {
  item: TrashedUrlItem;
  currentUserID: number;
  now: number;
}): JQuery {
  const { row, actions } = buildRowShell({
    title: item.urlTitle,
    subtitle: item.urlString,
    expiresAt: item.expiresAt,
    now,
  });
  row
    .attr("data-utub-id", String(item.utubID))
    .attr("data-utub-url-id", String(item.utubUrlID));

  const restore = buildActionButton({
    className: "trashBtnRestore btn-restore",
    label: item.originUtubTrashed
      ? APP_CONFIG.strings.TRASH_RESTORE_TO
      : APP_CONFIG.strings.TRASH_RESTORE,
    ariaLabel: `${
      item.originUtubTrashed
        ? APP_CONFIG.strings.TRASH_RESTORE_TO
        : APP_CONFIG.strings.TRASH_RESTORE
    } ${item.urlTitle}`,
    disabled: !item.canRestore,
  });
  if (item.originUtubTrashed) restore.attr("aria-haspopup", "listbox");

  const purge = buildActionButton({
    className: "trashBtnPurge btn-forever",
    label: APP_CONFIG.strings.TRASH_DELETE_FOREVER,
    ariaLabel: `${APP_CONFIG.strings.TRASH_DELETE_FOREVER} ${item.urlTitle}`,
    disabled: !item.canDelete,
  });

  actions
    .append(restore)
    .append(purge)
    .append($('<span class="grow"></span>'))
    .append(buildOriginChip({ item }))
    .append(
      $('<span class="t-meta"></span>').text(
        formatDeletedBy({ item, currentUserID, now }),
      ),
    );
  return row;
}

export function buildTrashUtubRow({
  item,
  currentUserID,
  now,
}: {
  item: TrashedUtubItem;
  currentUserID: number;
  now: number;
}): JQuery {
  const { row, actions } = buildRowShell({
    title: item.utubName,
    subtitle: fillTemplate({
      template: APP_CONFIG.strings.TRASH_UTUB_SUMMARY,
      values: {
        urls: String(item.urlCount),
        members: String(item.memberCount),
      },
    }),
    expiresAt: item.expiresAt,
    now,
  });
  row.attr("data-utub-id", String(item.utubID));

  actions
    .append(
      buildActionButton({
        className: "trashBtnRestore btn-restore",
        label: APP_CONFIG.strings.TRASH_RESTORE,
        ariaLabel: `${APP_CONFIG.strings.TRASH_RESTORE} ${item.utubName}`,
        disabled: !item.canRestore,
      }),
    )
    .append(
      buildActionButton({
        className: "trashBtnPurge btn-forever",
        label: APP_CONFIG.strings.TRASH_DELETE_FOREVER,
        ariaLabel: `${APP_CONFIG.strings.TRASH_DELETE_FOREVER} ${item.utubName}`,
        disabled: !item.canDelete,
      }),
    )
    .append($('<span class="grow"></span>'));
  if (item.isLocked) {
    actions.append(
      $('<span class="chip chip-origin dashed"></span>').text(
        APP_CONFIG.strings.TRASH_UTUB_LOCKED,
      ),
    );
  }
  actions.append(
    $('<span class="t-meta"></span>').text(
      formatDeletedBy({ item, currentUserID, now }),
    ),
  );
  return row;
}

export function showTrashEmptyState({ scope }: { scope: TrashScope }): void {
  $(SCOPE_IDS[scope].emptyState).removeClass("hidden");
  $(SCOPE_IDS[scope].list).addClass("hidden");
}

export function hideTrashEmptyState({ scope }: { scope: TrashScope }): void {
  $(SCOPE_IDS[scope].emptyState).addClass("hidden");
  $(SCOPE_IDS[scope].list).removeClass("hidden");
}

/**
 * `#TrashBtnEmpty` is inert when the active tab has nothing, or nothing the
 * user may delete. Uses `disabled` + `aria-disabled` like the mock's disabled state.
 */
export function updateEmptyTrashButton(): void {
  const scope = getActiveTrashScope();
  const rows: Array<{ canDelete: boolean }> =
    scope === "urls" ? trashListState.urls : trashListState.utubs;
  const disabled = rows.length === 0 || rows.every((row) => !row.canDelete);
  const button = $("#TrashBtnEmpty");
  button.prop("disabled", disabled);
  if (disabled) {
    button.attr("aria-disabled", "true");
  } else {
    button.removeAttr("aria-disabled");
  }
}

function renderScope<Item>({
  scope,
  items,
  buildRow,
}: {
  scope: TrashScope;
  items: Item[];
  buildRow: (item: Item) => JQuery;
}): void {
  const ids = SCOPE_IDS[scope];
  const tabTemplate =
    scope === "urls"
      ? APP_CONFIG.strings.TRASH_TAB_URLS
      : APP_CONFIG.strings.TRASH_TAB_UTUBS;
  $(ids.tab).text(
    fillTemplate({
      template: tabTemplate,
      values: { n: String(items.length) },
    }),
  );
  $(ids.list).empty().append(items.map(buildRow));
  if (items.length === 0) {
    showTrashEmptyState({ scope });
  } else {
    hideTrashEmptyState({ scope });
  }
}

export function renderTrashList({ list }: { list: TrashList }): void {
  trashListState = {
    listedAt: list.listedAt,
    urls: list.urls,
    utubs: list.utubs,
    currentUser: list.currentUser,
  };
  const now = Date.parse(list.listedAt);

  renderScope({
    scope: "urls",
    items: list.urls,
    buildRow: (item) =>
      buildTrashUrlRow({ item, currentUserID: list.currentUser, now }),
  });
  renderScope({
    scope: "utubs",
    items: list.utubs,
    buildRow: (item) =>
      buildTrashUtubRow({ item, currentUserID: list.currentUser, now }),
  });

  $("#TrashRetentionNotice")
    .text(
      fillTemplate({
        template: APP_CONFIG.strings.TRASH_RETENTION_NOTICE,
        values: { n: String(list.retentionDays) },
      }),
    )
    .removeClass("hidden");
  updateEmptyTrashButton();
}
