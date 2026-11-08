import type { UtubDetail } from "../../../types/utub.js";

import {
  captureSettingsVersions,
  resolveIncomingSettings,
  shouldKeepSettings,
} from "../selectors.js";
import { learnPolicyOff } from "../policy.js";
import { resetStore, setState } from "../../../store/app-store.js";
import { resolveUtubSettings } from "../../../types/settings.js";

const { mockMetricsClient } = await vi.hoisted(
  async () => await import("../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../lib/metrics-client.js", () => mockMetricsClient());
vi.mock("../header-fit.js", () => ({ fitUTubHeaderAndSubheader: vi.fn() }));
vi.mock("../deck.js", () => ({
  showUTubLoadingIconAndSetTimeout: vi.fn(() => 0),
  hideUTubLoadingIconAndClearTimeout: vi.fn(),
  setUTubDeckOnUTubSelected: vi.fn(),
}));
vi.mock("../../urls/update-description.js", () => ({
  removeEventListenersForShowCreateUTubDescIfEmptyDesc: vi.fn(),
  showCreateDescriptionButtonAlways: vi.fn(),
}));
vi.mock("../../mobile.js", () => ({
  isMobile: vi.fn(() => false),
  replaceMobilePanelHistoryState: vi.fn(),
}));

const SELECTED = { id: 1 } as UtubDetail;

const ALL_ON = {
  members: { members_can_add: true, co_owners_can_remove: true },
  urls: { allow_short_links: true },
} as UtubDetail["settings"];

describe("resolveIncomingSettings — per-key independence", () => {
  it("forces off only the listed key", () => {
    const resolved = resolveIncomingSettings({
      settings: ALL_ON,
      forceOffKeys: ["members.members_can_add"],
    });

    expect(resolved.members.members_can_add).toBe(false);
    expect(resolved.members.co_owners_can_remove).toBe(true);
    expect(resolved.urls.allow_short_links).toBe(true);
  });

  it.each([
    ["urls.allow_short_links" as const],
    ["members.co_owners_can_remove" as const],
  ])("forcing %s leaves members_can_add untouched", (key) => {
    const resolved = resolveIncomingSettings({
      settings: ALL_ON,
      forceOffKeys: [key],
    });

    expect(resolved.members.members_can_add).toBe(true);
  });

  it("forces nothing when no key is listed", () => {
    const resolved = resolveIncomingSettings({
      settings: ALL_ON,
      forceOffKeys: [],
    });

    expect(resolved.members.members_can_add).toBe(true);
    expect(resolved.members.co_owners_can_remove).toBe(true);
    expect(resolved.urls.allow_short_links).toBe(true);
  });
});

describe("shouldKeepSettings — learned keys vs the captured counter", () => {
  beforeEach(() => {
    resetStore();
    setState({
      activeUTubID: 1,
      settings: resolveUtubSettings(ALL_ON),
    });
  });

  it("lists only the key learned after the capture", () => {
    const captured = captureSettingsVersions();
    learnPolicyOff({ utubID: 1, key: "members.members_can_add" });

    expect(
      shouldKeepSettings({ selectedUTub: SELECTED, captured }).forceOffKeys,
    ).toEqual(["members.members_can_add"]);
  });

  it("lists nothing for a payload captured after the learn (a newer payload re-enables its key)", () => {
    learnPolicyOff({ utubID: 1, key: "members.members_can_add" });
    const captured = captureSettingsVersions();

    expect(
      shouldKeepSettings({ selectedUTub: SELECTED, captured }).forceOffKeys,
    ).toEqual([]);
  });

  it("lists each learned key independently", () => {
    const captured = captureSettingsVersions();
    learnPolicyOff({ utubID: 1, key: "urls.allow_short_links" });
    learnPolicyOff({ utubID: 1, key: "members.co_owners_can_remove" });

    expect(
      shouldKeepSettings({ selectedUTub: SELECTED, captured }).forceOffKeys,
    ).toEqual(["urls.allow_short_links", "members.co_owners_can_remove"]);
  });

  it("lists nothing for a different UTub", () => {
    const captured = captureSettingsVersions();
    learnPolicyOff({ utubID: 1, key: "members.members_can_add" });

    expect(
      shouldKeepSettings({ selectedUTub: { id: 2 } as UtubDetail, captured })
        .forceOffKeys,
    ).toEqual([]);
  });

  it("resets the learned map when the active UTub changes", () => {
    const captured = captureSettingsVersions();
    learnPolicyOff({ utubID: 1, key: "members.members_can_add" });
    setState({ activeUTubID: 2 });
    setState({ activeUTubID: 1 });

    expect(
      shouldKeepSettings({ selectedUTub: SELECTED, captured }).forceOffKeys,
    ).toEqual([]);
  });
});
