import {
  clearFieldSavedTick,
  showFieldSavedTick,
} from "../field-saved-tick.js";

vi.mock("../../../lib/globals.js", () => ({
  $: window.jQuery,
  jQuery: window.jQuery,
}));

vi.mock("../../../lib/config.js", () => {
  const configScript = document.getElementById("app-config");
  const config = JSON.parse(configScript?.textContent ?? "{}");
  return { APP_CONFIG: config };
});

const $ = window.jQuery;

const TICK_ID = "utubNameSavedTick";
const ANNOUNCE_ID = "fieldSavedAnnouncement";
const DWELL_MS = 1500;

const MARKUP = `
  <div class="field-saved-tick-slot">
    <span class="field-saved-tick opa-0" id="${TICK_ID}" aria-hidden="true">Saved <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-check" viewBox="0 0 16 16" aria-hidden="true"><path d="M10.97 4.97a.75.75 0 0 1 1.07 1.05l-3.99 4.99a.75.75 0 0 1-1.08.02L4.324 8.384a.75.75 0 1 1 1.06-1.06l2.094 2.093 3.473-4.425a.267.267 0 0 1 .02-.022z"/></svg></span>
  </div>
  <span id="${ANNOUNCE_ID}" aria-live="polite" class="visually-hidden"></span>
`;

describe("field-saved-tick", () => {
  beforeEach(() => {
    document.body.innerHTML = MARKUP;
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows the tick and sets the announcer text immediately", () => {
    const tick = $(`#${TICK_ID}`);
    const announce = $(`#${ANNOUNCE_ID}`);

    showFieldSavedTick({ tick, announce, label: "UTub name" });

    expect(tick.hasClass("opa-1")).toBe(true);
    expect(tick.hasClass("opa-0")).toBe(false);
    expect(announce.text()).toBe("UTub name Saved");
  });

  it("renders the checkmark as an inline bi-check SVG (no icon font shipped)", () => {
    // This project ships no bootstrap-icons font, so the tick must use an
    // inline SVG rather than a font-based `<i class="bi bi-check">` (which would
    // render as empty space). Guard the rendered markup against regressing.
    const tick = $(`#${TICK_ID}`);

    expect(tick.find("svg.bi-check").length).toBe(1);
    expect(tick.find("i.bi-check").length).toBe(0);
  });

  it("fades the tick and clears the announcer after ~1.5s", () => {
    const tick = $(`#${TICK_ID}`);
    const announce = $(`#${ANNOUNCE_ID}`);

    showFieldSavedTick({ tick, announce, label: "UTub name" });
    vi.advanceTimersByTime(DWELL_MS);

    expect(tick.hasClass("opa-0")).toBe(true);
    expect(tick.hasClass("opa-1")).toBe(false);
    expect(announce.text()).toBe("");
  });

  it("does not fade before the dwell elapses", () => {
    const tick = $(`#${TICK_ID}`);
    const announce = $(`#${ANNOUNCE_ID}`);

    showFieldSavedTick({ tick, announce, label: "UTub name" });
    vi.advanceTimersByTime(DWELL_MS - 1);

    expect(tick.hasClass("opa-1")).toBe(true);
  });

  it("cancels and restarts the timer when called again before it fires", () => {
    const tick = $(`#${TICK_ID}`);
    const announce = $(`#${ANNOUNCE_ID}`);

    showFieldSavedTick({ tick, announce, label: "UTub name" });
    // Advance most of the way, then re-show — the fade should NOT fire yet.
    vi.advanceTimersByTime(DWELL_MS - 100);
    showFieldSavedTick({ tick, announce, label: "UTub name" });

    // The original timer would have fired here; the restart prevents it.
    vi.advanceTimersByTime(100);
    expect(tick.hasClass("opa-1")).toBe(true);
    expect(announce.text()).toBe("UTub name Saved");

    // The restarted timer fades on schedule.
    vi.advanceTimersByTime(DWELL_MS - 100);
    expect(tick.hasClass("opa-0")).toBe(true);
    expect(announce.text()).toBe("");
  });

  it("clearFieldSavedTick cancels the pending timer and forces opa-0", () => {
    const tick = $(`#${TICK_ID}`);
    const announce = $(`#${ANNOUNCE_ID}`);

    showFieldSavedTick({ tick, announce, label: "UTub name" });
    expect(tick.hasClass("opa-1")).toBe(true);

    clearFieldSavedTick(tick);
    expect(tick.hasClass("opa-0")).toBe(true);
    expect(tick.hasClass("opa-1")).toBe(false);

    // The previously-pending fade timer is a no-op now (no error, stays opa-0).
    vi.advanceTimersByTime(DWELL_MS);
    expect(tick.hasClass("opa-0")).toBe(true);
  });

  it("works without an announcer element", () => {
    const tick = $(`#${TICK_ID}`);

    expect(() =>
      showFieldSavedTick({ tick, label: "UTub name" }),
    ).not.toThrow();
    expect(tick.hasClass("opa-1")).toBe(true);

    vi.advanceTimersByTime(DWELL_MS);
    expect(tick.hasClass("opa-0")).toBe(true);
  });
});
