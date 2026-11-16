import { resetStore, setState } from "../../../store/app-store.js";
import { EMPTY_UTUB_SETTINGS } from "../../../types/settings.js";
import { patchUtubSettings } from "../../panel-settings/client.js";
import {
  closePanelSettings,
  initPopover,
  resetPopover,
} from "../../panel-settings/popover.js";
import { _resetRegistryForTests } from "../../panel-settings/registry.js";
import type { SaveResult } from "../../panel-settings/types.js";
import {
  FIXTURE,
  OTHER_UTUB_ID,
  el,
  mockBreakpoint,
  openGear,
  selectUTub,
} from "../../panel-settings/__tests__/helpers.js";
import { registerTagsPermissionsSettingsSection } from "../permissions-settings-section.js";

// The real section inside the real shell: the inherited phase 1/2 invariants.
vi.mock("../../panel-settings/client.js", () => ({
  handleActiveUTubGone: vi.fn(),
  resyncSettings: vi.fn(async () => true),
  patchUtubSettings: vi.fn(),
}));
vi.mock("../../utubs/stale-data.js", () => ({
  updateUTubOnFindingStaleData: vi.fn(async () => {}),
}));
vi.mock("../../onboarding/nudges.js", () => ({
  dismissActiveTip: vi.fn(),
  maybeShowNextTip: vi.fn(),
}));
vi.mock("../../members/row-menu.js", () => ({
  closeAllMemberRowMenus: vi.fn(),
}));
vi.mock("../../utubs/header-fit.js", () => ({
  fitUTubHeaderAndSubheader: vi.fn(),
}));
vi.mock("../../../lib/tooltips.js", () => ({ hideTooltip: vi.fn() }));
vi.mock("../sheet.js", () => ({
  isTagSheetOpen: () => false,
  isTagSheetSelfBackPending: () => false,
}));

const TAG = "tagsPermissionsMembersCanTagSwitch";
const DELETE = "tagsPermissionsMembersCanDeleteSwitch";

function announced(): string {
  vi.advanceTimersByTime(0);
  return el("PanelSettingsAnnouncement").textContent ?? "";
}

async function settle(): Promise<void> {
  await vi.advanceTimersByTimeAsync(0);
}

describe("Tag permissions section inside the panel settings shell", () => {
  const originalMatchMedia = window.matchMedia;

  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    document.body.innerHTML = FIXTURE;
    resetStore();
    mockBreakpoint({ matches: false });
    initPopover();
    registerTagsPermissionsSettingsSection();
    selectUTub({
      settings: {
        ...EMPTY_UTUB_SETTINGS,
        tags: { members_can_tag: true, members_can_delete_tags: true },
      },
    });
    openGear("tags");
  });

  afterEach(() => {
    resetPopover();
    _resetRegistryForTests();
    window.matchMedia = originalMatchMedia;
    vi.useRealTimers();
  });

  it("renders for the owner, enabled", () => {
    expect(el(TAG).getAttribute("aria-checked")).toBe("true");
    expect(el(TAG).hasAttribute("aria-disabled")).toBe(false);
  });

  it("renders read-only for a plain member", () => {
    closePanelSettings();
    selectUTub({ owner: false });
    setState({ isCoCreator: false });
    openGear("tags");
    expect(el(TAG).getAttribute("aria-disabled")).toBe("true");
    expect(el(DELETE).getAttribute("aria-disabled")).toBe("true");
  });

  it("renders read-only in a locked UTub", () => {
    closePanelSettings();
    selectUTub({ locked: true });
    openGear("tags");
    expect(el(TAG).getAttribute("aria-disabled")).toBe("true");
  });

  it("sends two quick toggles in order, each with only its own key", async () => {
    const pending: { resolve: (result: SaveResult) => void }[] = [];
    vi.mocked(patchUtubSettings).mockImplementation(
      () =>
        new Promise<SaveResult>((resolve) => {
          pending.push({ resolve });
        }),
    );
    el(TAG).click();
    el(DELETE).click(); // disabled by the Tagging toggle: not sent
    el(TAG).click();
    await settle();
    expect(patchUtubSettings).toHaveBeenCalledTimes(1);
    expect(vi.mocked(patchUtubSettings).mock.calls[0][0].patch).toEqual({
      members_can_tag: false,
    });
    pending[0].resolve({ outcome: "ok" });
    await settle();
    expect(patchUtubSettings).toHaveBeenCalledTimes(2);
    expect(vi.mocked(patchUtubSettings).mock.calls[1][0].patch).toEqual({
      members_can_tag: true,
    });
  });

  it("announces the combined notice when Tagging is turned off", async () => {
    vi.mocked(patchUtubSettings).mockResolvedValue({ outcome: "ok" });
    el(TAG).click();
    await settle();
    expect(announced()).toContain(
      "Members can no longer tag. Deleting tags is unavailable too.",
    );
  });

  it("announces the plain on notice when Tagging is turned back on", async () => {
    vi.mocked(patchUtubSettings).mockResolvedValue({ outcome: "ok" });
    el(TAG).click();
    await settle();
    el(TAG).click();
    await settle();
    expect(announced()).toContain("Members can now tag.");
  });

  it("flips to read-only on a 403 and refuses further edits", async () => {
    vi.mocked(patchUtubSettings).mockResolvedValue({ outcome: "forbidden" });
    el(TAG).click();
    await settle();
    expect(el(TAG).getAttribute("aria-disabled")).toBe("true");
    expect(el(DELETE).getAttribute("aria-disabled")).toBe("true");
    el(TAG).click();
    await settle();
    expect(patchUtubSettings).toHaveBeenCalledTimes(1);
  });

  it("re-renders read-only when the UTub locks", () => {
    setState({ isCurrentUTubLocked: true });
    expect(el(TAG).getAttribute("aria-disabled")).toBe("true");
    expect(el(DELETE).getAttribute("aria-disabled")).toBe("true");
    expect(el(DELETE).getAttribute("aria-describedby")).toContain(
      "panelSettingsNote-tags-permissions",
    );
  });

  it("is writable for a co-owner", async () => {
    closePanelSettings();
    selectUTub({ owner: false });
    setState({ isCoCreator: true });
    openGear("tags");
    expect(el(TAG).hasAttribute("aria-disabled")).toBe(false);
    vi.mocked(patchUtubSettings).mockResolvedValue({ outcome: "ok" });
    el(TAG).click();
    await settle();
    expect(patchUtubSettings).toHaveBeenCalledTimes(1);
  });

  it("coalesces Delete then Tagging toggles and announces only the combined notice", async () => {
    const pending: { resolve: (result: SaveResult) => void }[] = [];
    vi.mocked(patchUtubSettings).mockImplementation(
      () =>
        new Promise<SaveResult>((resolve) => {
          pending.push({ resolve });
        }),
    );
    el(DELETE).click();
    await settle();
    el(DELETE).click();
    el(TAG).click();
    await settle();
    pending[0].resolve({ outcome: "ok" });
    await settle();
    expect(patchUtubSettings).toHaveBeenCalledTimes(2);
    expect(vi.mocked(patchUtubSettings).mock.calls[1][0].patch).toEqual({
      members_can_delete_tags: true,
      members_can_tag: false,
    });
    pending[1].resolve({ outcome: "ok" });
    await settle();
    expect(announced()).toContain(
      "Members can no longer tag. Deleting tags is unavailable too.",
    );
  });

  it("closes when the active UTub changes", () => {
    selectUTub({ utubID: OTHER_UTUB_ID });
    expect(el("panelSettingsPopover").classList.contains("hidden")).toBe(true);
  });
});
