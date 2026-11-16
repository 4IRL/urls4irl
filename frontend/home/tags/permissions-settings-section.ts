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

const SECTION_ID = "tags-permissions";

const TAG_PREFIX = "tagsPermissionsMembersCanTag";
const DELETE_PREFIX = "tagsPermissionsMembersCanDelete";
const DELETE_HINT_ID = `${DELETE_PREFIX}Hint`;

function render({
  container,
  ctx,
}: {
  container: HTMLElement;
  ctx: SectionContext;
}): void {
  // Fail closed: anything but an explicit write grant is read-only.
  const readOnly = ctx.canWrite !== true;
  const strings = APP_CONFIG.strings;
  const tagsSlice = ctx.settings?.tags;
  // The stored values; missing settings resolve to the defaults (allowed).
  let tagIntent = tagsSlice?.members_can_tag !== false;
  let deleteIntent = tagsSlice?.members_can_delete_tags !== false;

  function buildRow({
    prefix,
    label,
    desc,
    nested,
  }: {
    prefix: string;
    label: string;
    desc: string;
    nested: boolean;
  }): { row: HTMLElement; control: HTMLElement; labelColumn: HTMLElement } {
    const row = document.createElement("div");
    row.className = nested
      ? "panelSettingsRow tagsSettingsRow tagsSettingsRow--nested"
      : "panelSettingsRow tagsSettingsRow";
    const control = buildSwitchButton({
      id: `${prefix}Switch`,
      labelledBy: `${prefix}Label`,
    });
    const labelColumn = buildRowLabel({
      titleId: `${prefix}Label`,
      title: label,
      descId: `${prefix}Desc`,
      desc,
    });
    row.append(labelColumn, control);
    return { row, control, labelColumn };
  }

  const tagRow = buildRow({
    prefix: TAG_PREFIX,
    label: strings.TAGS_SETTINGS_MEMBERS_CAN_TAG_LABEL,
    desc: strings.TAGS_SETTINGS_MEMBERS_CAN_TAG_DESC,
    nested: false,
  });
  const deleteRow = buildRow({
    prefix: DELETE_PREFIX,
    label: strings.TAGS_SETTINGS_MEMBERS_CAN_DELETE_LABEL,
    desc: strings.TAGS_SETTINGS_MEMBERS_CAN_DELETE_DESC,
    nested: true,
  });
  const hint = document.createElement("div");
  hint.className = "urlsSettingsHint";
  hint.id = DELETE_HINT_ID;
  hint.textContent = strings.TAGS_SETTINGS_DELETE_REQUIRES_TAG;
  hint.hidden = true;
  deleteRow.labelColumn.append(hint);

  const tagSwitch = tagRow.control;
  const deleteSwitch = deleteRow.control;

  function describedBy({
    prefix,
    extra,
  }: {
    prefix: string;
    extra: string | null;
  }): string {
    const ids = [`${prefix}Desc`];
    if (extra !== null) ids.push(extra);
    if (readOnly && ctx.readOnlyNoteId !== undefined) {
      ids.push(ctx.readOnlyNoteId);
    }
    return ids.join(" ");
  }

  /** The Delete switch shows off, disabled, with the hint, while Tagging is off. */
  function syncDelete(): void {
    const forcedOff = !tagIntent;
    deleteSwitch.setAttribute(
      "aria-checked",
      String(!forcedOff && deleteIntent),
    );
    if (forcedOff || readOnly) {
      deleteSwitch.setAttribute("aria-disabled", "true");
    } else {
      deleteSwitch.removeAttribute("aria-disabled");
    }
    // The hint explains a manager's disabled switch; read-only has its own note.
    const showHint = forcedOff && !readOnly;
    hint.hidden = !showHint;
    deleteSwitch.setAttribute(
      "aria-describedby",
      describedBy({
        prefix: DELETE_PREFIX,
        extra: showHint ? DELETE_HINT_ID : null,
      }),
    );
  }

  tagSwitch.setAttribute("aria-checked", String(tagIntent));
  tagSwitch.setAttribute(
    "aria-describedby",
    describedBy({ prefix: TAG_PREFIX, extra: null }),
  );
  if (readOnly) tagSwitch.setAttribute("aria-disabled", "true");
  tagSwitch.addEventListener("click", () => {
    if (tagSwitch.getAttribute("aria-disabled") === "true") return;
    tagIntent = tagSwitch.getAttribute("aria-checked") !== "true";
    tagSwitch.setAttribute("aria-checked", String(tagIntent));
    syncDelete();
    ctx.submit({ patch: { members_can_tag: tagIntent } });
  });

  deleteSwitch.addEventListener("click", () => {
    if (deleteSwitch.getAttribute("aria-disabled") === "true") return;
    deleteIntent = deleteSwitch.getAttribute("aria-checked") !== "true";
    syncDelete();
    ctx.submit({ patch: { members_can_delete_tags: deleteIntent } });
  });

  syncDelete();
  container.append(tagRow.row, deleteRow.row);
}

async function save({
  utubID,
  patch,
}: {
  utubID: number | null;
  patch: SectionPatch;
}): Promise<SaveResult> {
  if (utubID === null) return { outcome: "error" };
  const result = await patchUtubSettings({ utubID, panel: "tags", patch });
  if (result.outcome !== "ok") return result;

  // A coalesced patch can carry both keys; announce each change that happened.
  const strings = APP_CONFIG.strings;
  const notices: string[] = [];
  const tagValue = patch.members_can_tag;
  const deleteValue = patch.members_can_delete_tags;
  if (typeof tagValue === "boolean") {
    notices.push(
      tagValue
        ? strings.TAGS_SETTINGS_MEMBERS_CAN_TAG_ON
        : strings.TAGS_SETTINGS_TAG_OFF_DELETE_FORCED,
    );
  }
  // With Tagging going off, Delete is forced off, so its own notice would mislead.
  if (typeof deleteValue === "boolean" && tagValue !== false) {
    notices.push(
      deleteValue
        ? strings.TAGS_SETTINGS_MEMBERS_CAN_DELETE_ON
        : strings.TAGS_SETTINGS_MEMBERS_CAN_DELETE_OFF,
    );
  }
  if (notices.length === 0) return result;
  return { ...result, notice: notices.join(" ") };
}

/**
 * Registers the shared "Tag permissions" section on the Tags gear: who may tag
 * and who may delete tags in this UTub. Returns the unregister function.
 */
export function registerTagsPermissionsSettingsSection(): () => void {
  const section: PanelSection = {
    id: SECTION_ID,
    panel: "tags",
    scope: "utub",
    title: APP_CONFIG.strings.TAGS_SETTINGS_SECTION_TITLE,
    render,
    save,
  };
  return registerSection(section);
}
