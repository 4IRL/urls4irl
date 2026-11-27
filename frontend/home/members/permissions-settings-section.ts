import { APP_CONFIG } from "../../lib/config.js";
import { getState } from "../../store/app-store.js";
import { announceSettingsStatus } from "../panel-settings/announce.js";
import { patchUtubSettings } from "../panel-settings/client.js";
import { DEBOUNCE_MS } from "../panel-settings/queue.js";
import { registerSection } from "../panel-settings/registry.js";
import {
  buildRowLabel,
  buildSwitchButton,
} from "../panel-settings/row-controls.js";
import type {
  PanelSection,
  SaveResult,
  SectionContext,
  SectionPatch,
} from "../panel-settings/types.js";

const SECTION_ID = "members-permissions";
const TOUCH_TAP_THRESHOLD_PX = 10;

type PermissionKey =
  | "co_owners_can_remove"
  | "members_can_add"
  | "hide_member_list"
  | "co_owners_can_enable_preview";

type InviteLinkCreators = "owner_and_co_owners" | "owner_only" | "no_one";

const CREATOR_VALUES: readonly InviteLinkCreators[] = [
  "owner_and_co_owners",
  "owner_only",
  "no_one",
];
// Higher rank = fewer people may create links; a rise is a strict tightening.
const CREATOR_RANK: Record<InviteLinkCreators, number> = {
  owner_and_co_owners: 0,
  owner_only: 1,
  no_one: 2,
};

function isInviteLinkCreators(value: unknown): value is InviteLinkCreators {
  return CREATOR_VALUES.some((candidate) => candidate === value);
}

interface PermissionRow {
  key: PermissionKey;
  prefix: string;
  label: () => string;
  desc: () => string;
  onNotice: () => string;
  offNotice: () => string;
}

const ROWS: PermissionRow[] = [
  {
    key: "co_owners_can_remove",
    prefix: "membersPermissionsCoOwnersRemove",
    label: () => APP_CONFIG.strings.MEMBERS_PERMISSIONS_CO_OWNERS_REMOVE_LABEL,
    desc: () => APP_CONFIG.strings.MEMBERS_PERMISSIONS_CO_OWNERS_REMOVE_DESC,
    onNotice: () =>
      APP_CONFIG.strings.MEMBERS_PERMISSIONS_CO_OWNERS_REMOVE_ON_NOTICE,
    offNotice: () =>
      APP_CONFIG.strings.MEMBERS_PERMISSIONS_CO_OWNERS_REMOVE_OFF_NOTICE,
  },
  {
    key: "members_can_add",
    prefix: "membersPermissionsMembersAdd",
    label: () => APP_CONFIG.strings.MEMBERS_PERMISSIONS_MEMBERS_ADD_LABEL,
    desc: () => APP_CONFIG.strings.MEMBERS_PERMISSIONS_MEMBERS_ADD_DESC,
    onNotice: () =>
      APP_CONFIG.strings.MEMBERS_PERMISSIONS_MEMBERS_ADD_ON_NOTICE,
    offNotice: () =>
      APP_CONFIG.strings.MEMBERS_PERMISSIONS_MEMBERS_ADD_OFF_NOTICE,
  },
  {
    key: "hide_member_list",
    prefix: "membersPermissionsHideList",
    label: () => APP_CONFIG.strings.MEMBERS_PERMISSIONS_HIDE_MEMBER_LIST_LABEL,
    desc: () => APP_CONFIG.strings.MEMBERS_PERMISSIONS_HIDE_MEMBER_LIST_DESC,
    onNotice: () =>
      APP_CONFIG.strings.MEMBERS_PERMISSIONS_HIDE_MEMBER_LIST_ON_NOTICE,
    offNotice: () =>
      APP_CONFIG.strings.MEMBERS_PERMISSIONS_HIDE_MEMBER_LIST_OFF_NOTICE,
  },
];

const PREVIEW_ROW: PermissionRow = {
  key: "co_owners_can_enable_preview",
  prefix: "membersPermissionsCoOwnersPreview",
  label: () => APP_CONFIG.strings.MEMBERS_PERMISSIONS_CO_OWNERS_PREVIEW_LABEL,
  desc: () => APP_CONFIG.strings.MEMBERS_PERMISSIONS_CO_OWNERS_PREVIEW_DESC,
  onNotice: () =>
    APP_CONFIG.strings.MEMBERS_PERMISSIONS_CO_OWNERS_PREVIEW_ON_NOTICE,
  offNotice: () =>
    APP_CONFIG.strings.MEMBERS_PERMISSIONS_CO_OWNERS_PREVIEW_OFF_NOTICE,
};

const CREATORS_PREFIX = "membersPermissionsInviteCreators";
const CREATORS_LABEL_ID = `${CREATORS_PREFIX}Label`;
const CREATORS_DESC_ID = `${CREATORS_PREFIX}Desc`;
const CREATORS_SELECT_ID = `${CREATORS_PREFIX}Select`;
const CREATORS_WARNING_ID = `${CREATORS_PREFIX}Warning`;
const CREATORS_NOT_APPLIED_ID = `${CREATORS_PREFIX}NotApplied`;
const CREATORS_APPLY_ID = `${CREATORS_PREFIX}ApplyButton`;

function creatorLabel(value: InviteLinkCreators): string {
  switch (value) {
    case "owner_and_co_owners":
      return APP_CONFIG.strings.MEMBERS_PERMISSIONS_INVITE_CREATORS_OPTION_ALL;
    case "owner_only":
      return APP_CONFIG.strings
        .MEMBERS_PERMISSIONS_INVITE_CREATORS_OPTION_OWNER_ONLY;
    case "no_one":
      return APP_CONFIG.strings
        .MEMBERS_PERMISSIONS_INVITE_CREATORS_OPTION_NO_ONE;
  }
}

function creatorDesc(value: InviteLinkCreators): string {
  switch (value) {
    case "owner_and_co_owners":
      return APP_CONFIG.strings.MEMBERS_PERMISSIONS_INVITE_CREATORS_DESC_ALL;
    case "owner_only":
      return APP_CONFIG.strings
        .MEMBERS_PERMISSIONS_INVITE_CREATORS_DESC_OWNER_ONLY;
    case "no_one":
      return APP_CONFIG.strings.MEMBERS_PERMISSIONS_INVITE_CREATORS_DESC_NO_ONE;
  }
}

function creatorNotice(value: InviteLinkCreators): string {
  switch (value) {
    case "owner_and_co_owners":
      return APP_CONFIG.strings.MEMBERS_PERMISSIONS_INVITE_CREATORS_NOTICE_ALL;
    case "owner_only":
      return APP_CONFIG.strings
        .MEMBERS_PERMISSIONS_INVITE_CREATORS_NOTICE_OWNER_ONLY;
    case "no_one":
      return APP_CONFIG.strings
        .MEMBERS_PERMISSIONS_INVITE_CREATORS_NOTICE_NO_ONE;
  }
}

function creatorRevokedSentence(value: InviteLinkCreators): string | null {
  switch (value) {
    case "owner_only":
      return APP_CONFIG.strings
        .MEMBERS_PERMISSIONS_INVITE_CREATORS_REVOKED_OWNER_ONLY;
    case "no_one":
      return APP_CONFIG.strings
        .MEMBERS_PERMISSIONS_INVITE_CREATORS_REVOKED_NO_ONE;
    default:
      return null;
  }
}

function warningFor(value: InviteLinkCreators): string {
  return value === "owner_only"
    ? APP_CONFIG.strings.MEMBERS_PERMISSIONS_INVITE_CREATORS_WARN_OWNER_ONLY
    : APP_CONFIG.strings.MEMBERS_PERMISSIONS_INVITE_CREATORS_WARN_NO_ONE;
}

function readStoredCreators(
  settings: SectionContext["settings"],
): InviteLinkCreators {
  const stored = settings?.members?.invite_link_creators;
  return isInviteLinkCreators(stored) ? stored : "owner_and_co_owners";
}

function isTightening({
  from,
  to,
}: {
  from: InviteLinkCreators;
  to: InviteLinkCreators;
}): boolean {
  return CREATOR_RANK[to] > CREATOR_RANK[from];
}

/** The current render's hooks into the module-level `save`. */
interface SectionController {
  afterSave({
    patch,
    result,
  }: {
    patch: SectionPatch;
    result: SaveResult;
  }): void;
}

// Assigned at the end of render and nulled by the returned cleanup, so a late
// save never reaches a stale render and only one popover is open at a time.
let activeController: SectionController | null = null;

function buildSwitchRow({
  row,
  ctx,
  readOnly,
}: {
  row: PermissionRow;
  ctx: SectionContext;
  readOnly: boolean;
}): HTMLElement {
  const labelId = `${row.prefix}Label`;
  const descId = `${row.prefix}Desc`;
  const rowElement = document.createElement("div");
  rowElement.className = "panelSettingsRow";
  const control = buildSwitchButton({
    id: `${row.prefix}Switch`,
    labelledBy: labelId,
  });
  const described = [descId];
  if (readOnly && ctx.readOnlyNoteId !== undefined) {
    described.push(ctx.readOnlyNoteId);
  }
  control.setAttribute("aria-describedby", described.join(" "));
  control.setAttribute(
    "aria-checked",
    String(ctx.settings?.members?.[row.key] ?? false),
  );
  if (readOnly) control.setAttribute("aria-disabled", "true");
  control.addEventListener("click", () => {
    if (control.getAttribute("aria-disabled") === "true") return;
    const value = control.getAttribute("aria-checked") !== "true";
    control.setAttribute("aria-checked", String(value));
    ctx.submit({ patch: { [row.key]: value } });
  });
  rowElement.append(
    buildRowLabel({
      titleId: labelId,
      title: row.label(),
      descId,
      desc: row.desc(),
    }),
    control,
  );
  return rowElement;
}

/**
 * The "Who can create invite links" row. A choice that tightens who can create
 * links (and so stops a link) is staged behind an Apply button instead of
 * saved; every other choice autosaves. Returns the row, a cleanup and the
 * controller `save` reports outcomes to.
 */
function buildCreatorsRow({
  container,
  ctx,
  readOnly,
}: {
  container: HTMLElement;
  ctx: SectionContext;
  readOnly: boolean;
}): { row: HTMLElement; controller: SectionController; cleanup: () => void } {
  let stored = readStoredCreators(ctx.settings);
  let lastSubmitted: InviteLinkCreators | null = null;
  let staged: InviteLinkCreators | null = null;
  let applyInFlight = false;
  let applyValue: InviteLinkCreators | null = null;
  let applyPressed = false;
  let touchStart: { x: number; y: number } | null = null;
  let stageTimer: ReturnType<typeof setTimeout> | null = null;
  const settleTimers = new Set<ReturnType<typeof setTimeout>>();
  let pressTimer: ReturnType<typeof setTimeout> | null = null;
  let disposed = false;

  const row = document.createElement("div");
  row.className = "panelSettingsRow";
  const label = buildRowLabel({
    titleId: CREATORS_LABEL_ID,
    title: APP_CONFIG.strings.MEMBERS_PERMISSIONS_INVITE_CREATORS_LABEL,
    descId: CREATORS_DESC_ID,
    desc: creatorDesc(stored),
  });
  const descElement = label.querySelector(`#${CREATORS_DESC_ID}`);
  row.append(label);

  const wrap = document.createElement("div");
  wrap.className = "panelSettingsSelectWrap";
  const select = document.createElement("select");
  select.className = "panelSettingsSelect";
  select.id = CREATORS_SELECT_ID;
  select.setAttribute("aria-labelledby", CREATORS_LABEL_ID);
  for (const value of CREATOR_VALUES) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = creatorLabel(value);
    select.append(option);
  }
  select.value = stored;
  const baseDescribed = [CREATORS_DESC_ID];
  if (readOnly) {
    select.setAttribute("aria-disabled", "true");
    if (ctx.readOnlyNoteId !== undefined)
      baseDescribed.push(ctx.readOnlyNoteId);
  }
  const setDescribed = (ids: string[]): void =>
    select.setAttribute("aria-describedby", ids.join(" "));
  setDescribed(baseDescribed);
  wrap.append(select);
  row.append(wrap);

  let stagedBlock: HTMLElement | null = null;
  let warningElement: HTMLElement | null = null;
  let notAppliedElement: HTMLElement | null = null;
  let applyButton: HTMLButtonElement | null = null;

  const baseline = (): InviteLinkCreators => lastSubmitted ?? stored;

  const clearStageTimer = (): void => {
    if (stageTimer !== null) clearTimeout(stageTimer);
    stageTimer = null;
  };

  const removeStagedDom = (): void => {
    stagedBlock?.remove();
    stagedBlock = null;
    warningElement = null;
    notAppliedElement = null;
    applyButton = null;
    setDescribed(baseDescribed);
  };

  const later = (callback: () => void): void => {
    // A render torn down by the shell removes the focused select, whose focusout
    // schedules a settle check here after cleanup already ran: never let that
    // dead render discard or announce over the cleanup's message.
    if (disposed) return;
    const timer = setTimeout(() => {
      settleTimers.delete(timer);
      if (disposed) return;
      callback();
    }, 0);
    settleTimers.add(timer);
  };

  /** Drops a staged value (never saved). No-op while Apply is in flight. */
  const discard = ({
    announce,
    focusSelect,
  }: {
    announce: boolean;
    focusSelect: boolean;
  }): void => {
    if (staged === null || applyInFlight) return;
    staged = null;
    applyPressed = false;
    clearStageTimer();
    removeStagedDom();
    select.value = baseline();
    if (announce) {
      announceSettingsStatus({
        message: APP_CONFIG.strings.MEMBERS_PERMISSIONS_CHANGE_NOT_APPLIED,
      });
    }
    if (focusSelect) select.focus();
  };

  const sendApply = (): void => {
    if (staged === null || applyInFlight || applyButton === null) return;
    const value = staged;
    applyPressed = false;
    clearStageTimer();
    applyInFlight = true;
    applyValue = value;
    lastSubmitted = value;
    select.focus();
    applyButton.disabled = true;
    applyButton.setAttribute("aria-busy", "true");
    select.setAttribute("aria-disabled", "true");
    notAppliedElement?.remove();
    notAppliedElement = null;
    setDescribed([CREATORS_DESC_ID, CREATORS_WARNING_ID]);
    ctx.submit({
      patch: { invite_link_creators: value },
      debounce: false,
    });
  };

  const onEscape = (event: KeyboardEvent): void => {
    if (event.key !== "Escape" || staged === null || applyInFlight) return;
    event.preventDefault();
    event.stopPropagation();
    discard({ announce: true, focusSelect: true });
  };

  const onPairFocusOut = (): void => {
    later(() => {
      if (staged === null || applyInFlight) return;
      if (applyPressed) {
        applyPressed = false;
        return;
      }
      const active = document.activeElement;
      if (active === select || active === applyButton) return;
      if (active === null || active === document.body) return;
      discard({ announce: true, focusSelect: false });
    });
  };

  const stage = (value: InviteLinkCreators): void => {
    staged = value;
    if (stagedBlock === null) {
      stagedBlock = document.createElement("div");
      stagedBlock.className = "panelSettingsStaged";
      warningElement = document.createElement("div");
      warningElement.id = CREATORS_WARNING_ID;
      warningElement.className = "panelSettingsStagedWarning";
      notAppliedElement = document.createElement("div");
      notAppliedElement.id = CREATORS_NOT_APPLIED_ID;
      notAppliedElement.className = "panelSettingsStagedNote";
      notAppliedElement.textContent =
        APP_CONFIG.strings.MEMBERS_PERMISSIONS_NOT_APPLIED_YET;
      applyButton = document.createElement("button");
      applyButton.type = "button";
      applyButton.id = CREATORS_APPLY_ID;
      applyButton.className = "panelSettingsActionBtn panelSettingsApply";
      applyButton.textContent =
        APP_CONFIG.strings.MEMBERS_PERMISSIONS_APPLY_LABEL;
      applyButton.setAttribute("aria-describedby", CREATORS_WARNING_ID);
      const pressed = (): void => {
        applyPressed = true;
      };
      applyButton.addEventListener("pointerdown", pressed);
      applyButton.addEventListener("mousedown", pressed);
      applyButton.addEventListener("pointercancel", () => {
        applyPressed = false;
      });
      applyButton.addEventListener("click", sendApply);
      applyButton.addEventListener("focusout", onPairFocusOut);
      applyButton.addEventListener("keydown", onEscape);
      stagedBlock.append(warningElement, notAppliedElement, applyButton);
      row.append(stagedBlock);
    }
    const text = warningFor(value);
    if (warningElement !== null) warningElement.textContent = text;
    setDescribed([
      CREATORS_DESC_ID,
      CREATORS_WARNING_ID,
      CREATORS_NOT_APPLIED_ID,
    ]);
    if (typeof row.scrollIntoView === "function") {
      row.scrollIntoView({ block: "nearest" });
    }
    clearStageTimer();
    stageTimer = setTimeout(() => {
      stageTimer = null;
      announceSettingsStatus({
        message: `${text} ${APP_CONFIG.strings.MEMBERS_PERMISSIONS_NOT_APPLIED_YET}`,
      });
    }, DEBOUNCE_MS);
  };

  select.addEventListener("change", () => {
    const picked = select.value;
    if (readOnly) {
      select.value = stored;
      return;
    }
    if (applyInFlight) {
      select.value = staged ?? stored;
      return;
    }
    if (!isInviteLinkCreators(picked)) return;
    const current = baseline();
    if (
      picked === stored &&
      lastSubmitted !== null &&
      lastSubmitted !== stored
    ) {
      // An autosave to another value is pending or in flight: undo it.
      discard({ announce: true, focusSelect: false });
      select.value = picked;
      lastSubmitted = stored;
      ctx.submit({ patch: { invite_link_creators: stored }, debounce: true });
      return;
    }
    if (picked === current) {
      // Back to the baseline: silent clear.
      if (staged !== null) {
        staged = null;
        applyPressed = false;
        clearStageTimer();
        removeStagedDom();
      }
      return;
    }
    if (isTightening({ from: current, to: picked })) {
      stage(picked);
      return;
    }
    discard({ announce: true, focusSelect: true });
    select.value = picked;
    lastSubmitted = picked;
    ctx.submit({ patch: { invite_link_creators: picked }, debounce: true });
  });
  select.addEventListener("focusout", onPairFocusOut);
  select.addEventListener("keydown", onEscape);

  const onDocumentPointerDown = (event: PointerEvent): void => {
    const target = event.target;
    const outside = !(target instanceof Node) || !container.contains(target);
    if (!outside) return;
    if (event.pointerType === "touch") {
      touchStart = { x: event.clientX, y: event.clientY };
      return;
    }
    discard({ announce: true, focusSelect: false });
  };
  const onDocumentPointerUp = (event: PointerEvent): void => {
    // Deferred so a queued focusout settle check has already read the flag.
    if (pressTimer !== null) clearTimeout(pressTimer);
    pressTimer = setTimeout(() => {
      pressTimer = null;
      applyPressed = false;
    }, 0);
    const start = touchStart;
    touchStart = null;
    if (start === null || event.pointerType !== "touch") return;
    const target = event.target;
    if (target instanceof Node && container.contains(target)) return;
    const moved = Math.hypot(event.clientX - start.x, event.clientY - start.y);
    if (moved < TOUCH_TAP_THRESHOLD_PX) {
      discard({ announce: true, focusSelect: false });
    }
  };
  const onDocumentPointerCancel = (): void => {
    touchStart = null;
  };
  document.addEventListener("pointerdown", onDocumentPointerDown);
  document.addEventListener("pointerup", onDocumentPointerUp);
  document.addEventListener("pointercancel", onDocumentPointerCancel);

  const onSettled = (): void => {
    stored = readStoredCreators(getState().settings);
    if (descElement !== null) descElement.textContent = creatorDesc(stored);
    if (staged === null) select.value = baseline();
  };

  const controller: SectionController = {
    afterSave({ patch, result }) {
      const saved = patch.invite_link_creators;
      if (saved !== undefined) {
        if (lastSubmitted === saved) lastSubmitted = null;
        // Only the saved value Apply sent tears the staging down: an earlier
        // autosave of another value resolving first must not.
        if (applyInFlight && saved === applyValue) {
          applyInFlight = false;
          applyValue = null;
          staged = null;
          applyPressed = false;
          removeStagedDom();
          if (!readOnly) select.removeAttribute("aria-disabled");
          if (result.outcome !== "ok") select.value = baseline();
        }
      }
      if (result.outcome === "ok") onSettled();
    },
  };

  const cleanup = (): void => {
    disposed = true;
    document.removeEventListener("pointerdown", onDocumentPointerDown);
    document.removeEventListener("pointerup", onDocumentPointerUp);
    document.removeEventListener("pointercancel", onDocumentPointerCancel);
    if (pressTimer !== null) clearTimeout(pressTimer);
    for (const timer of settleTimers) clearTimeout(timer);
    settleTimers.clear();
    clearStageTimer();
    if (staged !== null && !applyInFlight && select.isConnected) {
      announceSettingsStatus({
        message: APP_CONFIG.strings.MEMBERS_PERMISSIONS_CHANGE_NOT_APPLIED,
        append: true,
      });
    }
  };

  return { row, controller, cleanup };
}

function render({
  container,
  ctx,
}: {
  container: HTMLElement;
  ctx: SectionContext;
}): () => void {
  // Fail closed: anything but an explicit write grant is read-only.
  const readOnly = ctx.canWrite !== true;
  for (const row of ROWS) {
    container.append(buildSwitchRow({ row, ctx, readOnly }));
  }
  const creators = buildCreatorsRow({ container, ctx, readOnly });
  container.append(creators.row);
  container.append(buildSwitchRow({ row: PREVIEW_ROW, ctx, readOnly }));
  activeController = creators.controller;
  return () => {
    if (activeController === creators.controller) activeController = null;
    creators.cleanup();
  };
}

async function save({
  utubID,
  patch,
}: {
  utubID: number | null;
  patch: SectionPatch;
}): Promise<SaveResult> {
  if (utubID === null) return { outcome: "error" };
  // The controller registered now is the one to tell: a re-render during the
  // request must not redirect the outcome to a different render.
  const controller = activeController;
  let result: SaveResult = { outcome: "error" };
  try {
    result = await patchUtubSettings({ utubID, panel: "members", patch });
  } finally {
    // Runs on every outcome (also a rejected request) before returning to the shell.
    if (activeController === controller) {
      controller?.afterSave({ patch, result });
    }
  }
  if (result.outcome !== "ok") return result;

  // A coalesced patch can carry several keys; announce each change.
  const notices: string[] = [];
  for (const row of ROWS) {
    const value = patch[row.key];
    if (typeof value === "boolean") {
      notices.push(value ? row.onNotice() : row.offNotice());
    }
  }
  const creators = patch.invite_link_creators;
  if (isInviteLinkCreators(creators)) {
    notices.push(creatorNotice(creators));
    const revoked = creatorRevokedSentence(creators);
    if (result.inviteLinkRevoked === true && revoked !== null) {
      notices.push(revoked);
    }
  }
  const preview = patch[PREVIEW_ROW.key];
  if (typeof preview === "boolean") {
    notices.push(preview ? PREVIEW_ROW.onNotice() : PREVIEW_ROW.offNotice());
  }
  if (result.invitePreviewEnded === true) {
    notices.push(APP_CONFIG.strings.MEMBERS_PERMISSIONS_INVITE_PREVIEW_ENDED);
  }
  if (notices.length === 0) return result;
  return { ...result, notice: notices.join(". ") };
}

/**
 * Registers the owner's "Member permissions" section on the Members gear.
 * Returns the unregister function.
 */
export function registerMembersPermissionsSettingsSection(): () => void {
  const section: PanelSection = {
    id: SECTION_ID,
    panel: "members",
    scope: "utub",
    writeAccess: "owner",
    visibleTo: "managers",
    title: APP_CONFIG.strings.MEMBERS_PERMISSIONS_SECTION_TITLE,
    render,
    save,
  };
  return registerSection(section);
}
