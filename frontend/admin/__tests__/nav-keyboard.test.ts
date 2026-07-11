/**
 * Roving-tabindex keyboard navigation for the admin portal section nav
 * (#AdminNav). Mirrors the metrics dashboard tablist interaction model:
 *   - the active link starts as the sole tab stop (tabindex="0")
 *   - Left/Right cycle with wrap-around, Home/End jump to first/last
 *   - focus and the roving tabindex move together; links stay real <a href>
 *     so Enter/click navigate natively (not exercised here — jsdom no-ops nav)
 */

import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { $ } from "../../lib/globals.js";
import { initAdminNavKeyboard } from "../nav-keyboard.js";

const NAV_HTML = `
  <nav id="AdminNav" aria-label="Admin sections">
    <ul class="admin-nav-list">
      <li><a id="AdminNavDashboard" class="admin-nav-link" href="/admin">Dashboard</a></li>
      <li><a id="AdminNavHealth" class="admin-nav-link active" href="/admin/health">Health</a></li>
      <li><a id="AdminNavSystemOps" class="admin-nav-link" href="/admin/system-operations">System Operations</a></li>
      <li><a id="AdminNavUsers" class="admin-nav-link" href="/admin/users">User Actions</a></li>
      <li><a id="AdminNavUtubActions" class="admin-nav-link" href="/admin/utubs">UTub Actions</a></li>
      <li><a id="AdminNavDbBrowser" class="admin-nav-link" href="/admin/db">DB</a></li>
      <li><a id="AdminNavAuditLog" class="admin-nav-link" href="/admin/audit-log">Audit</a></li>
      <li><a id="AdminNavMetrics" class="admin-nav-link" href="/admin/metrics">Metrics</a></li>
    </ul>
  </nav>
`;

function link(id: string): HTMLAnchorElement {
  return document.getElementById(id) as HTMLAnchorElement;
}

function press({ id, key }: { id: string; key: string }): void {
  $(`#${id}`).trigger($.Event("keydown", { key }));
}

describe("admin nav keyboard", () => {
  let dispose: () => void;

  beforeEach(() => {
    document.body.innerHTML = NAV_HTML;
    dispose = initAdminNavKeyboard();
  });

  afterEach(() => {
    dispose();
    document.body.innerHTML = "";
  });

  it("seeds the active link as the sole tab stop", () => {
    expect(link("AdminNavHealth").getAttribute("tabindex")).toBe("0");
    expect(link("AdminNavDashboard").getAttribute("tabindex")).toBe("-1");
    expect(link("AdminNavMetrics").getAttribute("tabindex")).toBe("-1");
  });

  it("ArrowRight moves focus and the tab stop to the next link", () => {
    link("AdminNavHealth").focus();
    press({ id: "AdminNavHealth", key: "ArrowRight" });

    expect(document.activeElement).toBe(link("AdminNavSystemOps"));
    expect(link("AdminNavSystemOps").getAttribute("tabindex")).toBe("0");
    expect(link("AdminNavHealth").getAttribute("tabindex")).toBe("-1");
  });

  it("ArrowLeft moves focus to the previous link", () => {
    link("AdminNavHealth").focus();
    press({ id: "AdminNavHealth", key: "ArrowLeft" });

    expect(document.activeElement).toBe(link("AdminNavDashboard"));
    expect(link("AdminNavDashboard").getAttribute("tabindex")).toBe("0");
  });

  it("ArrowLeft on the first link wraps to the last", () => {
    link("AdminNavDashboard").focus();
    press({ id: "AdminNavDashboard", key: "ArrowLeft" });

    expect(document.activeElement).toBe(link("AdminNavMetrics"));
  });

  it("ArrowRight on the last link wraps to the first", () => {
    link("AdminNavMetrics").focus();
    press({ id: "AdminNavMetrics", key: "ArrowRight" });

    expect(document.activeElement).toBe(link("AdminNavDashboard"));
  });

  it("Home and End jump to the first and last links", () => {
    link("AdminNavUsers").focus();
    press({ id: "AdminNavUsers", key: "End" });
    expect(document.activeElement).toBe(link("AdminNavMetrics"));

    press({ id: "AdminNavMetrics", key: "Home" });
    expect(document.activeElement).toBe(link("AdminNavDashboard"));
  });

  it("ignores non-navigation keys", () => {
    link("AdminNavHealth").focus();
    press({ id: "AdminNavHealth", key: "a" });

    expect(document.activeElement).toBe(link("AdminNavHealth"));
    expect(link("AdminNavHealth").getAttribute("tabindex")).toBe("0");
  });

  it("falls back to the first link when none is active", () => {
    dispose();
    link("AdminNavHealth").classList.remove("active");
    dispose = initAdminNavKeyboard();

    expect(link("AdminNavDashboard").getAttribute("tabindex")).toBe("0");
    expect(link("AdminNavHealth").getAttribute("tabindex")).toBe("-1");
  });

  it("no-ops without throwing when the nav is absent", () => {
    document.body.innerHTML = "";
    const noopDispose = initAdminNavKeyboard();
    expect(() => noopDispose()).not.toThrow();
  });
});
