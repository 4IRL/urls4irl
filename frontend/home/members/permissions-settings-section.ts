import { APP_CONFIG } from "../../lib/config.js";
import { patchUtubSettings } from "../panel-settings/client.js";
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

type PermissionKey = "co_owners_can_remove" | "members_can_add";

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
];

function render({
  container,
  ctx,
}: {
  container: HTMLElement;
  ctx: SectionContext;
}): void {
  // Fail closed: anything but an explicit write grant is read-only.
  const readOnly = ctx.canWrite !== true;
  for (const row of ROWS) {
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
    container.append(rowElement);
  }
}

async function save({
  utubID,
  patch,
}: {
  utubID: number | null;
  patch: SectionPatch;
}): Promise<SaveResult> {
  if (utubID === null) return { outcome: "error" };
  const result = await patchUtubSettings({ utubID, panel: "members", patch });
  if (result.outcome !== "ok") return result;

  // A coalesced patch can carry both keys; announce each change.
  const notices: string[] = [];
  for (const row of ROWS) {
    const value = patch[row.key];
    if (typeof value === "boolean") {
      notices.push(value ? row.onNotice() : row.offNotice());
    }
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
