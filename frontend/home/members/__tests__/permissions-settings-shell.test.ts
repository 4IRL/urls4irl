// The Members permissions section running inside the real panel settings shell
// (popover, queue, announce): the discard, announce and focus paths that only
// exist because the shell re-renders, closes or force-closes the section.
import { resetStore, setState } from "../../../store/app-store.js";
import { EMPTY_UTUB_SETTINGS } from "../../../types/settings.js";
import { patchUtubSettings } from "../../panel-settings/client.js";
import {
  closePanelSettings,
  initPopover,
  resetPopover,
} from "../../panel-settings/popover.js";
import { DEBOUNCE_MS } from "../../panel-settings/queue.js";
import {
  _resetRegistryForTests,
  registerSection,
} from "../../panel-settings/registry.js";
import type {
  PanelSection,
  SaveResult,
  SectionContext,
} from "../../panel-settings/types.js";
import {
  FIXTURE,
  OTHER_UTUB_ID,
  el,
  mockBreakpoint,
  openGear,
  pressKey,
  selectUTub,
} from "../../panel-settings/__tests__/helpers.js";
import { registerMembersPermissionsSettingsSection } from "../permissions-settings-section.js";

vi.mock("../../panel-settings/client.js", () => ({
  patchUtubSettings: vi.fn(),
  handleActiveUTubGone: vi.fn(),
  resyncSettings: vi.fn(async () => true),
}));
vi.mock("../../utubs/stale-data.js", () => ({
  updateUTubOnFindingStaleData: vi.fn(async () => {}),
}));
vi.mock("../../onboarding/nudges.js", () => ({
  dismissActiveTip: vi.fn(),
  maybeShowNextTip: vi.fn(),
}));
vi.mock("../row-menu.js", () => ({ closeAllMemberRowMenus: vi.fn() }));
vi.mock("../../utubs/header-fit.js", () => ({
  fitUTubHeaderAndSubheader: vi.fn(),
}));
vi.mock("../../../lib/tooltips.js", () => ({ hideTooltip: vi.fn() }));
vi.mock("../../tags/sheet.js", () => ({
  isTagSheetOpen: () => false,
  isTagSheetSelfBackPending: () => false,
}));

const SELECT = "membersPermissionsInviteCreatorsSelect";
const APPLY = "membersPermissionsInviteCreatorsApplyButton";
const PREVIEW = "membersPermissionsCoOwnersPreviewSwitch";

interface Pending {
  patch: Record<string, unknown>;
  resolve: (result: SaveResult) => void;
}

describe("Members permissions section inside the shell", () => {
  const originalMatchMedia = window.matchMedia;
  let pending: Pending[];
  let managerCtx: SectionContext[];

  function select(): HTMLSelectElement {
    return el(SELECT) as HTMLSelectElement;
  }

  function pick(value: string): void {
    select().value = value;
    select().dispatchEvent(new Event("change", { bubbles: true }));
  }

  function region(): string {
    vi.advanceTimersByTime(0);
    return el("PanelSettingsAnnouncement").textContent ?? "";
  }

  function stage(): void {
    pick("owner_only");
    vi.advanceTimersByTime(DEBOUNCE_MS + 10);
  }

  async function settle(): Promise<void> {
    await vi.advanceTimersByTimeAsync(0);
  }

  function resolveLast(result: SaveResult): Promise<void> {
    pending[pending.length - 1].resolve(result);
    return settle();
  }

  function open({ owner = true }: { owner?: boolean } = {}): void {
    selectUTub({ owner, settings: EMPTY_UTUB_SETTINGS });
    openGear("members");
  }

  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    document.body.innerHTML = FIXTURE;
    Element.prototype.scrollIntoView = vi.fn();
    resetStore();
    mockBreakpoint({ matches: false });
    pending = [];
    managerCtx = [];
    vi.mocked(patchUtubSettings).mockImplementation(
      ({ patch }: { patch: Record<string, unknown> }) =>
        new Promise<SaveResult>((resolve) => {
          pending.push({ patch, resolve });
        }),
    );
    initPopover();
    registerMembersPermissionsSettingsSection();
    // A separately registered manager-access section on the same gear.
    const manager: PanelSection = {
      id: "members-manager-probe",
      panel: "members",
      scope: "utub",
      title: "Probe",
      render: ({ ctx }) => {
        managerCtx.push(ctx);
      },
      save: async () => ({ outcome: "ok" }),
    };
    registerSection(manager);
  });

  afterEach(() => {
    resetPopover();
    _resetRegistryForTests();
    window.matchMedia = originalMatchMedia;
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
  });

  it("renders both rows in the open gear", () => {
    open();
    expect(select().value).toBe("owner_and_co_owners");
    expect(el(PREVIEW)).not.toBeNull();
  });

  it("an error on the switch row while staged announces the shell failure joined with Change not applied.", async () => {
    open();
    stage();
    el(APPLY).focus();
    el(PREVIEW).click();
    await vi.advanceTimersByTimeAsync(DEBOUNCE_MS + 10);
    await resolveLast({ outcome: "error" });
    expect(region()).toBe(
      "Member permissions: Couldn't save. Change not applied.",
    );
    expect(document.getElementById(APPLY)).toBeNull();
    expect(select().value).toBe("owner_and_co_owners");
  });

  it("with focus on the removed Apply the shell's fallback focuses the first control", async () => {
    open();
    stage();
    el(APPLY).focus();
    el(PREVIEW).click();
    await vi.advanceTimersByTimeAsync(DEBOUNCE_MS + 10);
    await resolveLast({ outcome: "error" });
    expect(document.getElementById(APPLY)).toBeNull();
    const popover = el("panelSettingsPopover");
    expect(popover.contains(document.activeElement)).toBe(true);
    expect(document.activeElement).not.toBe(document.body);
  });

  it("a user close with a staged value is announced as Change not applied", () => {
    open();
    stage();
    closePanelSettings();
    expect(region()).toContain("Change not applied.");
  });

  it("a second Escape closes after the first discards only", () => {
    open();
    stage();
    select().focus();
    pressKey({ key: "Escape", target: select() });
    expect(document.getElementById(APPLY)).toBeNull();
    expect(el("panelSettingsPopover").classList.contains("hidden")).toBe(false);
    pressKey({ key: "Escape", target: select() });
    expect(el("panelSettingsPopover").classList.contains("hidden")).toBe(true);
  });

  it("a UTub change force-closes and discards the staged value", () => {
    open();
    stage();
    selectUTub({ utubID: OTHER_UTUB_ID, settings: EMPTY_UTUB_SETTINGS });
    expect(el("panelSettingsPopover").classList.contains("hidden")).toBe(true);
    expect(patchUtubSettings).not.toHaveBeenCalled();
  });

  it("a lock flip discards the staged value and leaves the shell's message last", () => {
    open();
    stage();
    setState({ isCurrentUTubLocked: true });
    vi.advanceTimersByTime(10);
    expect(document.getElementById(APPLY)).toBeNull();
    expect(patchUtubSettings).not.toHaveBeenCalled();
    expect(region()).not.toBe("Change not applied.");
    expect(region()).not.toBe("");
  });

  it("a role change (owner to co-owner) discards the staged value without saving", () => {
    open();
    stage();
    setState({ isCurrentUserOwner: false, isCoCreator: true });
    vi.advanceTimersByTime(10);
    expect(patchUtubSettings).not.toHaveBeenCalled();
    expect(document.getElementById(APPLY)).toBeNull();
  });

  it("Apply sends once, and a forbidden outcome leaves the manager section writable", async () => {
    open();
    stage();
    el(APPLY).focus();
    el(APPLY).click();
    await vi.advanceTimersByTimeAsync(10);
    expect(pending).toHaveLength(1);
    expect(pending[0].patch).toEqual({ invite_link_creators: "owner_only" });
    await resolveLast({ outcome: "forbidden" });
    expect(document.getElementById(APPLY)).toBeNull();
    expect(select().getAttribute("aria-disabled")).toBe("true");
    expect(select().value).toBe("owner_and_co_owners");
    expect(el(PREVIEW).getAttribute("aria-disabled")).toBe("true");
    expect(managerCtx[managerCtx.length - 1].canWrite).toBe(true);
  });

  it.each([
    ["ok", { outcome: "ok" }],
    ["error", { outcome: "error" }],
    ["forbidden", { outcome: "forbidden" }],
    ["locked", { outcome: "locked" }],
  ] as Array<[string, SaveResult]>)(
    "focus is on the select after an Apply %s outcome",
    async (_name, result) => {
      open();
      stage();
      el(APPLY).focus();
      el(APPLY).click();
      await vi.advanceTimersByTimeAsync(10);
      await resolveLast(result);
      expect(document.activeElement).toBe(select());
    },
  );

  it("a 403 on Apply keeps no Apply and no warning, with no stray announcement", async () => {
    open();
    stage();
    el(APPLY).click();
    await vi.advanceTimersByTimeAsync(10);
    await resolveLast({ outcome: "forbidden" });
    expect(
      document.getElementById("membersPermissionsInviteCreatorsWarning"),
    ).toBeNull();
    expect(region()).not.toContain("Change not applied.");
  });

  it("an owner-only switch click saves through the queue", async () => {
    open();
    el(PREVIEW).click();
    await vi.advanceTimersByTimeAsync(DEBOUNCE_MS + 10);
    expect(pending[0].patch).toEqual({ co_owners_can_enable_preview: true });
  });
});
