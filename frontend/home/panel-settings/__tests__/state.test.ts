import {
  isPanelSettingsBusy,
  isPanelSettingsOpen,
  setPanelSettingsOpen,
  setPanelSettingsPendingSaveCount,
} from "../state.js";

describe("panel settings state", () => {
  beforeEach(() => {
    setPanelSettingsOpen({ open: false });
    setPanelSettingsPendingSaveCount({ count: 0 });
  });

  it("is not busy by default", () => {
    expect(isPanelSettingsOpen()).toBe(false);
    expect(isPanelSettingsBusy()).toBe(false);
  });

  it("is busy when open alone", () => {
    setPanelSettingsOpen({ open: true });
    expect(isPanelSettingsBusy()).toBe(true);
  });

  it("is busy when a positive pending count alone", () => {
    setPanelSettingsPendingSaveCount({ count: 2 });
    expect(isPanelSettingsBusy()).toBe(true);
  });

  it("clamps a negative pending count to 0 and is not busy", () => {
    setPanelSettingsPendingSaveCount({ count: -3 });
    expect(isPanelSettingsBusy()).toBe(false);
  });

  it("isPanelSettingsOpen ignores the pending count", () => {
    setPanelSettingsPendingSaveCount({ count: 5 });
    expect(isPanelSettingsOpen()).toBe(false);
  });
});
