import { announceSettingsStatus } from "../announce.js";

function mountRegion(): HTMLElement {
  document.body.innerHTML = '<div id="PanelSettingsAnnouncement"></div>';
  return document.getElementById("PanelSettingsAnnouncement") as HTMLElement;
}

describe("announceSettingsStatus", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
    document.body.innerHTML = "";
  });

  it("empties the region immediately and sets the message on the next tick", () => {
    const region = mountRegion();
    region.textContent = "old";

    announceSettingsStatus({ message: "Saved" });
    expect(region.textContent).toBe("");

    vi.advanceTimersByTime(0);
    expect(region.textContent).toBe("Saved");
  });

  it("re-sets an identical repeated message after clearing it", () => {
    const region = mountRegion();

    announceSettingsStatus({ message: "Saved" });
    vi.advanceTimersByTime(0);
    expect(region.textContent).toBe("Saved");

    announceSettingsStatus({ message: "Saved" });
    expect(region.textContent).toBe("");
    vi.advanceTimersByTime(0);
    expect(region.textContent).toBe("Saved");
  });

  it("cancels the first pending message when called again before the tick", () => {
    const region = mountRegion();

    announceSettingsStatus({ message: "first" });
    announceSettingsStatus({ message: "second" });
    vi.advanceTimersByTime(0);

    expect(region.textContent).toBe("second");
  });

  it("does not throw when the live region is missing", () => {
    document.body.innerHTML = "";
    expect(() => announceSettingsStatus({ message: "Saved" })).not.toThrow();
  });
});
